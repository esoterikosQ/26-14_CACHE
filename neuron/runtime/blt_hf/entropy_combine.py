"""Native NIKL+FineWeb2 combination producing the same splits as entropy_fineweb.combine_corpora.

The SQLite reference stores every body and runs per-document queries; this path keeps only
fixed-size hashes in memory, hashes shards in parallel, and writes splits through sorted buckets.
"""
import argparse
import ctypes
from contextlib import closing
import gzip
import hashlib
import json
from multiprocessing import get_context
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
import unicodedata

import numpy as np

from . import entropy_corpus, entropy_fineweb
from .entropy_corpus import GROUP_POLICY, MIN_FREE_BYTES, _digest, _write_json
from .entropy_data import MAX_RECORD_BYTES, file_sha256, inspect_dataset
from .entropy_fineweb import (DiskBudget, OFFICIAL_TEST, REPOSITORY, REVISION, SOURCE, _assigned,
                              _read_catalog, _state)

RECORD = 128
QUARANTINE, FALLBACK = 1, 2
SPLITS = ('train', 'validation', 'test')
CHUNK_BYTES = 64 * 1024**2
SOURCE_PATH = Path(__file__).with_name('native') / 'combine.cpp'
_LIBRARY = None


def render_unicode_tables():
    whitespace = [code for code in range(0x110000) if chr(code).isspace()]
    unsafe = set(range(0x1161, 0x1176)) | set(range(0x11A8, 0x11C3))
    for code in range(0x110000):
        if 0xD800 <= code <= 0xDFFF:
            continue
        char = chr(code)
        if unicodedata.combining(char) or unicodedata.normalize('NFC', char) != char:
            unsafe.add(code)
        decomposition = unicodedata.decomposition(char)
        if decomposition and not decomposition.startswith('<'):
            parts = [int(part, 16) for part in decomposition.split()]
            if len(parts) == 2 and unicodedata.normalize('NFC', chr(parts[0]) + chr(parts[1])) == char:
                unsafe.add(parts[1])
    ranges = []
    for code in sorted(unsafe):
        if ranges and ranges[-1][1] + 1 == code:
            ranges[-1][1] = code
        else:
            ranges.append([code, code])
    lines = [f'static const char UNICODE_VERSION[] = "{unicodedata.unidata_version}";',
             'static const uint32_t WHITESPACE[] = {' + ', '.join(map(str, whitespace)) + '};',
             'static const uint32_t UNSAFE[][2] = {']
    lines += [f'    {{{low}, {high}}},' for low, high in ranges]
    lines.append('};')
    return '\n'.join(lines) + '\n'


def build_native(directory):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'unicode_tables.inc').write_text(render_unicode_tables())
    compiler = os.environ.get('CXX', 'c++')
    library = directory / 'combine.so'
    subprocess.run([compiler, '-std=c++11', '-O3', '-shared', '-fPIC', '-I', str(directory), str(SOURCE_PATH),
                    '-o', str(library)], check=True)
    version = subprocess.run([compiler, '--version'], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    return library, {'compiler': version, 'source_sha256': file_sha256(SOURCE_PATH),
                     'unicode_tables_sha256': file_sha256(directory / 'unicode_tables.inc'),
                     'library_sha256': file_sha256(library), 'unicode_version': unicodedata.unidata_version}


def load_native(path):
    global _LIBRARY
    if _LIBRARY is not None and _LIBRARY[0] == str(path):
        return _LIBRARY[1]
    library = ctypes.CDLL(str(path))
    u64, pointer, text = ctypes.c_uint64, ctypes.c_void_p, ctypes.c_char_p
    out = ctypes.POINTER(ctypes.c_uint64)
    library.bltc_unicode_version.restype = text
    library.bltc_hash_text.argtypes = [text, u64, pointer, pointer, ctypes.POINTER(ctypes.c_int)]
    library.bltc_roundtrip.argtypes = [text, u64, pointer, u64, out, pointer, u64]
    library.bltc_scan.argtypes = [text, u64, ctypes.c_int, text, u64, pointer, u64, out, out, pointer, u64]
    library.bltc_group.argtypes = [pointer, u64, pointer, pointer, pointer, u64, u64, pointer, pointer, pointer, u64,
                                   text, u64, ctypes.c_double, ctypes.c_double, pointer, pointer, pointer, pointer, u64]
    library.bltc_bucket_open.argtypes = [text]
    library.bltc_bucket_open.restype = pointer
    library.bltc_bucket_close.argtypes = [pointer]
    library.bltc_bucket_write.argtypes = [pointer, text, u64, ctypes.c_int, pointer, pointer, u64, out, out, pointer, u64]
    library.bltc_merge.argtypes = [text, text, text, text, ctypes.POINTER(ctypes.c_void_p), pointer, u64]
    library.bltc_free.argtypes = [pointer]
    if library.bltc_unicode_version().decode() != unicodedata.unidata_version:
        raise ValueError('Native Unicode tables differ from this Python')
    _LIBRARY = (str(path), library)
    return library


def _address(array):
    return array.ctypes.data if array is not None and array.size else None


def _check(status, error):
    if status:
        raise ValueError(error.value.decode('utf-8', 'replace'))


def _normalized_digest(text):
    normalized = ' '.join(unicodedata.normalize('NFC', text).split())
    return bytes.fromhex(_digest(normalized)) if normalized else None


def _stream_lines(path, handle_chunk):
    """Feeds gzip or plain JSONL to handle_chunk(data, final) -> consumed bytes, keeping unconsumed tails."""
    opener = gzip.open if path.suffix == '.gz' else open
    pending = b''
    with opener(path, 'rb') as stream:
        while True:
            block = stream.read(CHUNK_BYTES)
            data = pending + block if pending else block
            final = not block
            consumed = handle_chunk(data, final)
            pending = data[consumed:]
            if final:
                if pending:
                    raise ValueError('Unconsumed JSONL tail')
                return


def scan_shard(task):
    library_path, path, sha256, documents, utf8_bytes, records_path, quarantine_path, relative = task
    library = load_native(library_path)
    path = Path(path)
    if file_sha256(path) != sha256:
        raise ValueError('FineWeb JSONL hash/path changed')
    batches, state = [], {'position': 0, 'quarantined': 0, 'quarantined_bytes': 0}
    error = ctypes.create_string_buffer(512)
    source = SOURCE.encode('utf-8')
    with quarantine_path.open('x', encoding='utf-8') as ledger:
        def handle(data, final):
            capacity = data.count(b'\n') + 1
            records = np.zeros((capacity, RECORD), np.uint8)
            count, consumed = ctypes.c_uint64(), ctypes.c_uint64()
            _check(library.bltc_scan(data, len(data), int(final), source, len(source), _address(records), capacity,
                                     ctypes.byref(count), ctypes.byref(consumed), error, len(error)), error)
            records = records[:count.value]
            for index in np.flatnonzero(records[:, 116]):
                record = records[index]
                offset = int(record[104:112].view(np.uint64)[0])
                length = int(record[112:116].view(np.uint32)[0])
                row = json.loads(data[offset:offset + length].decode('utf-8'))
                if record[116] == FALLBACK:
                    digest = _normalized_digest(row['text'])
                    record[116] = QUARANTINE if digest is None else 0
                    if digest is not None:
                        record[64:96] = np.frombuffer(digest, np.uint8)
                if record[116] == QUARANTINE:
                    ledger.write(json.dumps({
                        'source': row['source'], 'document_id': row['id'], 'text': row['text'],
                        'exact_sha': _digest(row['text']), 'file_path': relative,
                        'position': state['position'] + int(index), 'parts': 1,
                        'empty_form_parts': int(row['text'] == ''), 'reason': 'no_non_whitespace_text'},
                        ensure_ascii=False) + '\n')
                    state['quarantined'] += 1
                    state['quarantined_bytes'] += len(row['text'].encode('utf-8'))
            records[:, 104:116] = 0
            batches.append(records)
            state['position'] += len(records)
            return consumed.value
        _stream_lines(path, handle)
    records = np.concatenate(batches) if batches else np.zeros((0, RECORD), np.uint8)
    total = int(records[:, 96:104].copy().view(np.uint64).sum())
    if len(records) != documents or total != utf8_bytes:
        raise ValueError('FineWeb shard document/byte totals changed')
    np.save(records_path, records)
    return len(records), total, state['quarantined'], state['quarantined_bytes']


def write_buckets(task):
    library_path, path, splits_path, records_path, prefix = task
    library = load_native(library_path)
    splits = np.load(splits_path)
    exact = np.ascontiguousarray(np.load(records_path, mmap_mode='r')[:, :32]) if records_path else None
    handle = library.bltc_bucket_open(str(prefix).encode())
    if not handle:
        raise OSError(f'Cannot open buckets {prefix}')
    error = ctypes.create_string_buffer(512)
    state = {'line': 0}
    try:
        def handle_chunk(data, final):
            done, consumed = ctypes.c_uint64(), ctypes.c_uint64()
            start = state['line']
            _check(library.bltc_bucket_write(
                handle, data, len(data), int(final), _address(splits[start:]),
                _address(exact[start:]) if exact is not None else None, len(splits) - start,
                ctypes.byref(done), ctypes.byref(consumed), error, len(error)), error)
            state['line'] += done.value
            return consumed.value
        _stream_lines(Path(path), handle_chunk)
    finally:
        if library.bltc_bucket_close(handle):
            raise OSError(f'Bucket close failed: {prefix}')
    if state['line'] != len(splits):
        raise ValueError('Line count changed between passes')
    return int((splits != 255).sum())


def _validated_inputs(nikl_audit, nikl_manifest, fineweb_report):
    base = json.loads(nikl_manifest.read_text())
    audit = json.loads((nikl_audit / 'audit.json').read_text())
    downloaded = json.loads(fineweb_report.read_text())
    catalog = _read_catalog(fineweb_report.parent / 'catalog.json')
    database = nikl_audit / 'index.sqlite'
    if (audit.get('status') != 'complete' or audit.get('group_policy') != GROUP_POLICY or
            base.get('group_policy') != GROUP_POLICY or
            audit['code_sha256'] != file_sha256(Path(entropy_corpus.__file__)) or
            base['source_audit_sha256'] != file_sha256(nikl_audit / 'audit.json') or
            base['audit_index_sha256'] != audit['index_sha256'] or
            file_sha256(database) != audit['index_sha256']):
        raise ValueError('Completed immutable NIKL audit/manifest required')
    if (downloaded.get('status') != 'complete' or downloaded.get('revision') != REVISION or
            downloaded.get('repository') != REPOSITORY or downloaded.get('configuration') != 'kor_Hang' or
            downloaded.get('reserved_official_test') != [OFFICIAL_TEST] or
            downloaded['identity']['catalog_sha256'] != file_sha256(fineweb_report.parent / 'catalog.json') or
            downloaded['identity']['code_sha256'] != file_sha256(Path(entropy_fineweb.__file__)) or
            [item['source'] for item in downloaded['shards']] != catalog['train_shards']):
        raise ValueError('Completed full pinned FineWeb download required')
    inspect_dataset(nikl_manifest)
    return base, audit, downloaded, database


def _nikl_expected(nikl_manifest, base, audit):
    specs = {**base['splits'], 'test': base['held_out_test']}
    expected, paths = {}, {}
    for split, spec in specs.items():
        path = (nikl_manifest.parent / spec['path']).resolve()
        if not path.is_relative_to(nikl_manifest.parent) or path.is_symlink() or file_sha256(path) != spec['sha256']:
            raise ValueError('NIKL split hash/path changed')
        paths[split] = path
        for row in entropy_fineweb._json_rows(path):
            digest = _digest(row['text'])
            if digest in expected:
                raise ValueError('NIKL duplicate across frozen splits')
            expected[digest] = (split, row['source'], row['id'])
    if len(expected) != audit['unique_exact_documents']:
        raise ValueError('NIKL split coverage differs from audit')
    return expected, paths


def _nikl_graph(database, expected, policy):
    roles, exact, groups, group_index = bytearray(), bytearray(), [], {}
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        for count, (number, digest, group) in enumerate(
                connection.execute('SELECT number, exact_sha, group_id FROM records ORDER BY number')):
            if number != count:
                raise ValueError('NIKL record numbering changed')
            role = expected[digest][0]
            if role != _assigned(group, policy):
                raise ValueError('NIKL frozen assignment differs from its policy')
            index = group_index.setdefault(group, len(group_index))
            roles.append(SPLITS.index(role))
            exact += bytes.fromhex(digest)
            groups.append(index)
        for source, identity, digest in connection.execute('''SELECT source, document_id, exact_sha FROM records
                WHERE number IN (SELECT MIN(number) FROM records GROUP BY exact_sha)'''):
            if expected[digest][1:] != (source, identity):
                raise ValueError('NIKL representative identity changed')
        kinds, tokens, owners = bytearray(), bytearray(), []
        for kind, token, owner in connection.execute('SELECT kind, token, owner FROM links'):
            kinds.append({'id': 0, 'normalized': 1}[kind])
            tokens += bytes.fromhex(token)
            owners.append(owner)
    return (np.frombuffer(bytes(exact), np.uint8), np.frombuffer(bytes(roles), np.uint8), np.asarray(groups, np.int64),
            len(group_index), np.frombuffer(bytes(kinds), np.uint8), np.frombuffer(bytes(tokens), np.uint8),
            np.asarray(owners, np.int64))


def combine_native(nikl_audit, nikl_manifest, fineweb_report, output, max_output_bytes, workers,
                   min_free_bytes=MIN_FREE_BYTES):
    if type(workers) is not int or workers < 1:
        raise ValueError('Positive worker count required')
    nikl_audit, nikl_manifest, fineweb_report, output = (
        Path(path).resolve() for path in (nikl_audit, nikl_manifest, fineweb_report, output))
    for protected in (nikl_audit, nikl_manifest.parent, fineweb_report.parent):
        if output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError('Combined output must be separate from all source directories')
    started = time.time()
    base, audit, downloaded, database = _validated_inputs(nikl_audit, nikl_manifest, fineweb_report)
    expected, nikl_paths = _nikl_expected(nikl_manifest, base, audit)
    output.mkdir(parents=True, exist_ok=False)
    work = output / 'work'
    (work / 'buckets').mkdir(parents=True)
    budget = DiskBudget([fineweb_report.parent, output], max_output_bytes, min_free_bytes)
    nikl_bytes = sum(path.stat().st_size for path in nikl_paths.values())
    input_documents = sum(shard['documents'] for shard in downloaded['shards'])
    input_bytes = sum(shard['utf8_bytes'] for shard in downloaded['shards'])
    budget.check(2 * (input_bytes + nikl_bytes) + RECORD * input_documents)
    progress = {'status': 'running', 'stage': 'build', 'implementation': 'native_v1', 'started_unix': started,
                'nikl_manifest_sha256': file_sha256(nikl_manifest), 'fineweb_report_sha256': file_sha256(fineweb_report)}
    _state(output / 'progress.json', progress)
    library_path, build = build_native(output / 'native')
    library = load_native(library_path)

    def stage(name, **details):
        progress.update(stage=name, elapsed_seconds=time.time() - started, **details)
        _state(output / 'progress.json', progress)
        print(json.dumps({'stage': name, 'elapsed_seconds': round(time.time() - started, 1), **details}), flush=True)

    shards = downloaded['shards']
    tasks = []
    for number, shard in enumerate(shards):
        path = (fineweb_report.parent / shard['path']).resolve()
        if not path.is_relative_to(fineweb_report.parent) or path.is_symlink():
            raise ValueError('FineWeb JSONL hash/path changed')
        tasks.append((str(library_path), str(path), shard['sha256'], shard['documents'], shard['utf8_bytes'],
                      work / f'records-{number:03d}.npy', work / f'quarantine-{number:03d}.jsonl', 'fineweb2/' + path.name))
    stage('scan', shards=len(tasks), workers=workers)
    context = get_context('fork')
    with context.Pool(workers) as pool:
        scanned = []
        for result in pool.imap(scan_shard, tasks):
            scanned.append(result)
            budget.check()
            stage('scan', shards_done=len(scanned), fineweb_documents=sum(item[0] for item in scanned))
    fineweb_count = sum(item[0] for item in scanned)
    fineweb_bytes = sum(item[1] for item in scanned)
    empty_count = sum(item[2] for item in scanned)
    empty_bytes = sum(item[3] for item in scanned)
    with (output / 'quarantine.jsonl').open('xb') as ledger:
        for task in tasks:
            with task[6].open('rb') as part:
                shutil.copyfileobj(part, ledger)
            task[6].unlink()

    stage('group', fineweb_documents=fineweb_count)
    records = np.empty((fineweb_count, RECORD), np.uint8)
    offset = 0
    for task in tasks:
        part = np.load(task[5], mmap_mode='r')
        records[offset:offset + len(part)] = part
        offset += len(part)
    nikl_exact, nikl_role, nikl_group, nikl_groups, kinds, tokens, owners = _nikl_graph(
        database, expected, base['split_policy'])
    policy = base['split_policy']
    fineweb_split = np.empty(fineweb_count, np.uint8)
    nikl_split = np.empty(len(nikl_role), np.uint8)
    stats = np.zeros(5, np.uint64)
    seed = f'{policy["seed"]}:'.encode('utf-8')
    error = ctypes.create_string_buffer(512)
    _check(library.bltc_group(
        _address(records), fineweb_count, _address(nikl_exact), _address(nikl_role), _address(nikl_group), len(nikl_role),
        nikl_groups, _address(kinds), _address(tokens), _address(owners), len(kinds), seed, len(seed),
        float(policy['validation_percent']), float(policy['test_percent']), _address(fineweb_split),
        _address(nikl_split), _address(stats), error, len(error)), error)
    if not np.array_equal(nikl_split, nikl_role):
        raise ValueError('Protected NIKL split moved')
    del records, nikl_exact, nikl_group, kinds, tokens, owners
    offset = 0
    for number, shard in enumerate(shards):
        np.save(work / f'splits-{number:03d}.npy', fineweb_split[offset:offset + shard['documents']])
        offset += shard['documents']
    del fineweb_split

    stage('buckets', groups=[int(value) for value in stats[:3]], unique_documents=int(stats[3]))
    bucket_tasks = [(str(library_path), task[1], work / f'splits-{number:03d}.npy', task[5],
                     work / 'buckets' / f'fineweb-{number:03d}-') for number, task in enumerate(tasks)]
    for split, path in nikl_paths.items():
        with path.open('rb') as handle:
            lines = sum(block.count(b'\n') for block in iter(lambda: handle.read(CHUNK_BYTES), b''))
        splits_path = work / f'nikl-{split}.npy'
        np.save(splits_path, np.full(lines, SPLITS.index(split), np.uint8))
        bucket_tasks.append((str(library_path), str(path), splits_path, None, work / 'buckets' / f'nikl-{split}-'))
    written = 0
    with context.Pool(workers) as pool:
        for count in pool.imap(write_buckets, bucket_tasks):
            written += count
            budget.check()
    if written != int(stats[3]):
        raise ValueError('Bucketed document count differs from grouping')
    for path in work.glob('*.npy'):
        path.unlink()

    stage('merge')
    summaries = {split: {'documents': 0, 'utf8_bytes': 0, 'groups': int(stats[index]), 'sources': {}}
                 for index, split in enumerate(SPLITS)}
    targets = [str(output / f'{split}.jsonl').encode() for split in SPLITS]
    for split in SPLITS:
        (output / f'{split}.jsonl').open('x').close()
    for bucket in range(256):
        paths = sorted((work / 'buckets').glob(f'*-{bucket:03d}.bin'))
        pointer = ctypes.c_void_p()
        _check(library.bltc_merge('\n'.join(map(str, paths)).encode(), *targets, ctypes.byref(pointer),
                                  error, len(error)), error)
        try:
            counts = json.loads(ctypes.string_at(pointer).decode('utf-8'))
        finally:
            library.bltc_free(pointer)
        for split_index, source, documents, utf8_bytes in counts:
            summary = summaries[SPLITS[split_index]]
            summary['documents'] += documents
            summary['utf8_bytes'] += utf8_bytes
            summary['sources'][source] = summary['sources'].get(source, 0) + documents
        for path in paths:
            path.unlink()
        if bucket % 16 == 15:
            budget.check()
            stage('merge', buckets_done=bucket + 1)
    shutil.rmtree(work)
    if any(not summary['documents'] for summary in summaries.values()):
        raise ValueError('Combined split is empty')
    if sum(summary['documents'] for summary in summaries.values()) != int(stats[3]):
        raise ValueError('Merged document count differs from grouping')
    if file_sha256(database) != audit['index_sha256'] or file_sha256(nikl_manifest) != progress['nikl_manifest_sha256']:
        raise ValueError('Protected NIKL inputs changed during preparation')
    if file_sha256(fineweb_report) != progress['fineweb_report_sha256']:
        raise ValueError('FineWeb input report changed during preparation')
    budget.check()
    specs = {split: {'path': f'{split}.jsonl', 'sha256': file_sha256(output / f'{split}.jsonl')} for split in SPLITS}
    policy = {**base['split_policy'], 'assignment': 'Frozen NIKL roles; linked FineWeb inherits; new groups SHA256(seed:min-exact-sha)',
              'cross_role_bridge': 'Fail without reassigning frozen NIKL roles'}
    manifest = {'schema_version': 1, 'group_policy': GROUP_POLICY, 'split_policy': policy,
                'source_nikl_manifest_sha256': progress['nikl_manifest_sha256'],
                'source_fineweb_report_sha256': progress['fineweb_report_sha256'],
                'fineweb_revision': REVISION, 'reserved_official_test': [OFFICIAL_TEST],
                'empty_document_policy': 'quarantine',
                'quarantined_documents': audit['quarantined_documents'] + empty_count,
                'pii_review_approved': False, 'near_duplicate_split_review_approved': False,
                'preprocessing': 'Accepted UTF-8 unchanged; normalization used only for grouping; no prescribed byte mixture',
                'splits': {split: specs[split] for split in ('train', 'validation')}, 'held_out_test': specs['test']}
    _write_json(output / 'manifest.json', manifest)
    inspect_dataset(output / 'manifest.json')
    result = {'schema_version': 1, 'status': 'complete', 'splits': summaries,
              'documents': sum(summary['documents'] for summary in summaries.values()),
              'fineweb_input_documents': fineweb_count, 'fineweb_input_utf8_bytes': fineweb_bytes,
              'quarantined_documents': manifest['quarantined_documents'],
              'quarantined_utf8_bytes': audit['quarantined_utf8_bytes'] + empty_bytes,
              'exact_duplicate_documents': int(stats[4]) - int(stats[3]),
              'nikl_original_roles_preserved': True, 'policy': policy,
              'manifest_sha256': file_sha256(output / 'manifest.json'),
              'quarantine_ledger': 'quarantine.jsonl (FineWeb); NIKL quarantine stays in the audit index',
              'quarantine_ledger_sha256': file_sha256(output / 'quarantine.jsonl'),
              'implementation': {'name': 'native_v1', 'code_sha256': file_sha256(Path(__file__)), 'workers': workers,
                                 **build, 'reference': 'entropy_fineweb.combine_corpora split/manifest semantics'},
              'max_output_bytes': max_output_bytes, 'min_free_bytes': min_free_bytes,
              'elapsed_seconds': time.time() - started,
              'limitations': ['No fuzzy/partial-overlap or PII review', 'Official FineWeb test never downloaded',
                              'Unique data composition is not a training exposure or replay mixture contract']}
    _write_json(output / 'report.json', result)
    _state(output / 'progress.json', {**progress, 'status': 'complete', 'stage': 'finished',
                                      'elapsed_seconds': result['elapsed_seconds']})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nikl-audit', type=Path, required=True)
    parser.add_argument('--nikl-manifest', type=Path, required=True)
    parser.add_argument('--fineweb-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-output-bytes', type=int, required=True)
    parser.add_argument('--min-free-gib', type=int, default=100)
    parser.add_argument('--memory-limit-gib', type=int, default=48)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    import resource
    if args.memory_limit_gib <= 0:
        parser.error('Positive memory limit required')
    resource.setrlimit(resource.RLIMIT_AS, (args.memory_limit_gib * 1024**3,) * 2)
    result = combine_native(args.nikl_audit, args.nikl_manifest, args.fineweb_report, args.output,
                            args.max_output_bytes, args.workers, args.min_free_gib * 1024**3)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
