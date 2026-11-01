"""Pinned FineWeb2 Korean acquisition and opt-in NIKL-preserving preparation."""
import argparse
from contextlib import closing, ExitStack
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import unicodedata
import uuid
from urllib.request import Request, urlopen

from . import entropy_corpus
from .entropy_corpus import GROUP_POLICY, MIN_FREE_BYTES, _digest, _find, _space, _write_json
from .entropy_data import MAX_RECORD_BYTES, file_sha256, inspect_dataset


REPOSITORY = 'HuggingFaceFW/fineweb-2'
REVISION = 'af9c13333eb981300149d5ca60a8e9d659b276b9'
PREFIX = 'data/kor_Hang/train/'
SOURCE = 'FineWeb2:kor_Hang'
OFFICIAL_TEST = 'data/kor_Hang/test/000_00000.parquet'


def catalog_from_tree(entries):
    shards = []
    for entry in entries:
        path = entry.get('path', '')
        if not path.startswith(PREFIX):
            continue
        metadata = entry.get('lfs', {})
        size, digest = entry.get('size'), metadata.get('oid')
        if (entry.get('type') != 'file' or not path.endswith('.parquet') or
                Path(path).parent.as_posix() != PREFIX.rstrip('/') or
                type(size) is not int or size <= 0 or metadata.get('size') != size or
                not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('Pinned regular Parquet path/size/LFS SHA256 required')
        shards.append({'path': path, 'size_bytes': size, 'sha256': digest})
    if len(shards) != 25 or len({item['path'] for item in shards}) != 25:
        raise ValueError('Exactly25 unique Korean train shards required')
    return {'schema_version': 1, 'repository': REPOSITORY, 'revision': REVISION,
            'configuration': 'kor_Hang', 'train_shards': sorted(shards, key=lambda item: item['path']),
            'compressed_bytes': sum(item['size_bytes'] for item in shards),
            'reserved_official_test': [OFFICIAL_TEST], 'selection': 'Entire pinned Korean train',
            'license': 'ODC-By-1.0', 'additional_terms': 'https://commoncrawl.org/terms-of-use',
            'pii_review_approved': False}


def resolve_catalog(output):
    url = f'https://huggingface.co/api/datasets/{REPOSITORY}/tree/{REVISION}/{PREFIX}?recursive=false&expand=false'
    with urlopen(url, timeout=60) as response:
        catalog = catalog_from_tree(json.load(response))
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output, catalog)
    return catalog


class DiskBudget:
    def __init__(self, roots, maximum, minimum=MIN_FREE_BYTES):
        if type(maximum) is not int or maximum <= 0 or type(minimum) is not int or minimum < 0:
            raise ValueError('Explicit positive output budget and nonnegative free reserve required')
        self.roots = [Path(path).resolve() for path in roots]
        self.maximum, self.minimum = maximum, minimum

    def check(self, reserve=0):
        paths = {path for root in self.roots if root.exists() for path in root.rglob('*') if path.is_file()}
        size = sum(path.stat().st_size for path in paths)
        if size + reserve > self.maximum:
            raise ValueError('New artifact disk budget exceeded')
        _space(self.roots[-1], self.minimum, reserve)
        return size


def _read_catalog(path):
    catalog = json.loads(Path(path).read_text(encoding='utf-8'))
    if (catalog.get('repository') != REPOSITORY or catalog.get('revision') != REVISION or
            catalog.get('configuration') != 'kor_Hang' or
            catalog.get('reserved_official_test') != [OFFICIAL_TEST]):
        raise ValueError('Only the pinned Korean train with reserved official test is accepted')
    verified = catalog_from_tree([{'type': 'file', 'path': item['path'], 'size': item['size_bytes'],
                                 'lfs': {'oid': item['sha256'], 'size': item['size_bytes']}}
                                for item in catalog['train_shards']])
    if verified['train_shards'] != catalog['train_shards'] or verified['compressed_bytes'] != catalog['compressed_bytes']:
        raise ValueError('Catalog order or total changed')
    return catalog


def _state(path, payload):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2)
        handle.write('\n')
    temporary.replace(path)


def _download_shard(spec, directory, budget):
    path = spec['path']
    if Path(path).parent.as_posix() != PREFIX.rstrip('/') or not path.endswith('.parquet'):
        raise ValueError('Refusing non-train shard')
    destination = directory / Path(path).name
    partial = destination.with_suffix('.parquet.partial')
    if destination.exists():
        if destination.stat().st_size != spec['size_bytes'] or file_sha256(destination) != spec['sha256']:
            raise ValueError('Existing Parquet does not match pinned SHA/size; preserve it and use a fresh run')
        return destination
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > spec['size_bytes']:
        raise ValueError('Partial download exceeds pinned size')
    digest = hashlib.sha256()
    if partial.exists():
        with partial.open('rb') as handle:
            for block in iter(lambda: handle.read(1024**2), b''):
                digest.update(block)
    budget.check(spec['size_bytes'] - offset)
    if offset < spec['size_bytes']:
        headers = {'Accept-Encoding': 'identity'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        request = Request(f'https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{path}', headers=headers)
        with urlopen(request, timeout=60) as response:
            if offset and (response.status != 206 or response.headers.get('Content-Range') !=
                           f'bytes {offset}-{spec["size_bytes"] - 1}/{spec["size_bytes"]}'):
                raise ValueError('Server did not honor the pinned resume range')
            with partial.open('ab') as handle:
                while True:
                    block = response.read(1024**2)
                    if not block:
                        break
                    if offset + len(block) > spec['size_bytes']:
                        raise ValueError('Download exceeded pinned size')
                    _space(directory, budget.minimum, len(block))
                    handle.write(block)
                    digest.update(block)
                    offset += len(block)
    if offset != spec['size_bytes'] or digest.hexdigest() != spec['sha256']:
        raise ValueError('Incomplete or SHA-mismatched Parquet; partial file preserved')
    partial.rename(destination)
    budget.check()
    return destination


def _parquet_rows(path):
    try:
        import pyarrow.parquet as parquet
    except ImportError as error:
        raise RuntimeError('FineWeb preparation requires pyarrow in the selected Python environment') from error
    reader = parquet.ParquetFile(path)
    if not {'id', 'text'}.issubset(reader.schema_arrow.names):
        raise ValueError('FineWeb Parquet id/text schema changed')
    for batch in reader.iter_batches(batch_size=32, columns=['id', 'text']):
        for row in batch.to_pylist():
            if not isinstance(row['id'], str) or not row['id'] or not isinstance(row['text'], str):
                raise ValueError('FineWeb requires nonempty string ID and string text')
            yield {'id': row['id'], 'source': SOURCE, 'text': row['text']}


def _json_rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rb') as handle:
        while True:
            raw = handle.readline(MAX_RECORD_BYTES + 1)
            if not raw:
                return
            if len(raw) > MAX_RECORD_BYTES:
                raise ValueError('JSONL record exceeds16MiB')
            row = json.loads(raw.decode('utf-8'))
            if (not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key]
                                               for key in ('id', 'source')) or not isinstance(row.get('text'), str)):
                raise ValueError('Invalid id/source/text record')
            yield row


def download_corpus(catalog_path, output, max_output_bytes, min_free_bytes=MIN_FREE_BYTES, resume=False):
    catalog_path, output = Path(catalog_path).resolve(), Path(output).resolve()
    catalog = _read_catalog(catalog_path)
    identity = {'catalog_sha256': file_sha256(catalog_path), 'max_output_bytes': max_output_bytes,
                'min_free_bytes': min_free_bytes, 'code_sha256': file_sha256(Path(__file__))}
    if resume:
        state = json.loads((output / 'progress.json').read_text())
        if state['identity'] != identity:
            raise ValueError('Resume source/code/budget identity changed')
    else:
        output.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(catalog_path, output / 'catalog.json')
        _state(output / 'progress.json', {'identity': identity, 'status': 'running', 'shards': []})
    (output / 'parquet').mkdir(exist_ok=True)
    (output / 'documents').mkdir(exist_ok=True)
    (output / 'shard_reports').mkdir(exist_ok=True)
    budget = DiskBudget([output], max_output_bytes, min_free_bytes)
    budget.check(catalog['compressed_bytes'] - sum(path.stat().st_size for path in (output / 'parquet').glob('*.parquet*')))
    reports = []
    for spec in catalog['train_shards']:
        raw = _download_shard(spec, output / 'parquet', budget)
        stem = Path(spec['path']).stem
        converted = output / 'documents' / (stem + '.jsonl.gz')
        report_path = output / 'shard_reports' / (stem + '.json')
        if report_path.exists():
            report = json.loads(report_path.read_text())
            if report['source'] != spec or file_sha256(converted) != report['sha256']:
                raise ValueError('Completed conversion identity changed')
        else:
            partial = converted.with_suffix('.gz.partial')
            if converted.exists():
                converted.rename(converted.with_name(converted.name + '.unreported-' + uuid.uuid4().hex))
            if partial.exists():
                partial.rename(partial.with_name(partial.name + '.interrupted-' + uuid.uuid4().hex))
            count = total = empty = 0
            with partial.open('xb') as handle, gzip.GzipFile(filename='', mode='wb', fileobj=handle, mtime=0) as compressed:
                for row in _parquet_rows(raw):
                    encoded = (json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8')
                    if len(encoded) > MAX_RECORD_BYTES:
                        raise ValueError('FineWeb document exceeds16MiB; original Parquet preserved')
                    if count % 256 == 0:
                        budget.check(MAX_RECORD_BYTES * 32)
                    compressed.write(encoded)
                    count += 1
                    total += len(row['text'].encode('utf-8'))
                    empty += not bool(row['text'].strip())
            partial.rename(converted)
            report = {'source': spec, 'path': str(converted.relative_to(output)), 'sha256': file_sha256(converted),
                      'documents': count, 'utf8_bytes': total, 'contentless_documents': empty}
            _write_json(report_path, report)
        reports.append(report)
        budget.check()
        _state(output / 'progress.json', {'identity': identity, 'status': 'running', 'shards': reports})
        print(json.dumps({'stage': 'fineweb_download', 'shards': len(reports), 'documents': sum(item['documents'] for item in reports)}), flush=True)
    result = {'schema_version': 1, 'status': 'complete', 'identity': identity, 'repository': REPOSITORY,
              'revision': REVISION, 'configuration': 'kor_Hang', 'reserved_official_test': [OFFICIAL_TEST],
              'shards': reports, 'documents': sum(item['documents'] for item in reports),
              'utf8_bytes': sum(item['utf8_bytes'] for item in reports),
              'preprocessing': 'Original UTF-8 text; no trimming/normalization; empty text retained for quarantine',
              'original_parquet_preserved': True, 'pii_review_approved': False}
    _state(output / 'report.json', result)
    _state(output / 'progress.json', {**result, 'identity': identity})
    return result


def _join_groups(parents, roles, number, owners):
    roots = {_find(parents, value) for value in [number, *owners]}
    anchored = {roles[root] for root in roots if root in roles}
    if len(anchored) > 1:
        raise ValueError('FineWeb document bridges protected NIKL splits; no reassignment allowed')
    root = min(roots)
    for member in roots:
        parents[member] = root
        roles.pop(member, None)
    if anchored:
        roles[root] = anchored.pop()


def _assigned(group, policy):
    score = int(_digest(f'{policy["seed"]}:{group}')[:16], 16) / 2**64 * 100
    return ('test' if score < policy['test_percent'] else 'validation'
            if score < policy['test_percent'] + policy['validation_percent'] else 'train')


def combine_corpora(nikl_audit, nikl_manifest, fineweb_report, output, max_output_bytes,
                    min_free_bytes=MIN_FREE_BYTES):
    nikl_audit, nikl_manifest, fineweb_report, output = (
        Path(path).resolve() for path in (nikl_audit, nikl_manifest, fineweb_report, output))
    for protected in (nikl_audit, nikl_manifest.parent, fineweb_report.parent):
        if output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError('Combined output must be separate from all source directories')
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
            downloaded['identity']['code_sha256'] != file_sha256(Path(__file__)) or
            [item['source'] for item in downloaded['shards']] != catalog['train_shards']):
        raise ValueError('Completed full pinned FineWeb download required')
    inspect_dataset(nikl_manifest)
    specs = {**base['splits'], 'test': base['held_out_test']}
    expected = {}
    for split, spec in specs.items():
        path = (nikl_manifest.parent / spec['path']).resolve()
        if not path.is_relative_to(nikl_manifest.parent) or path.is_symlink() or file_sha256(path) != spec['sha256']:
            raise ValueError('NIKL split hash/path changed')
        for row in _json_rows(path):
            digest = _digest(row['text'])
            if digest in expected:
                raise ValueError('NIKL duplicate across frozen splits')
            expected[digest] = (split, row['source'], row['id'])
    if len(expected) != audit['unique_exact_documents']:
        raise ValueError('NIKL split coverage differs from audit')
    output.mkdir(parents=True, exist_ok=False)
    budget = DiskBudget([fineweb_report.parent, output], max_output_bytes, min_free_bytes)
    budget.check(database.stat().st_size * 2)
    child = output / 'index.sqlite'
    parents, roles, group_roots = [], {}, {}
    progress = {'status': 'running', 'stage': 'merge', 'fineweb_documents': 0,
                'nikl_manifest_sha256': file_sha256(nikl_manifest),
                'fineweb_report_sha256': file_sha256(fineweb_report)}
    _state(output / 'progress.json', progress)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as original, closing(sqlite3.connect(child)) as connection:
        original.backup(connection)
        connection.execute('PRAGMA cache_size=-16384')
        connection.execute('PRAGMA temp_store=FILE')
        for number, exact, group in connection.execute('SELECT number, exact_sha, group_id FROM records ORDER BY number'):
            if number != len(parents):
                raise ValueError('NIKL record numbering changed')
            role = expected[exact][0]
            if role != _assigned(group, base['split_policy']):
                raise ValueError('NIKL frozen assignment differs from its policy')
            root = group_roots.setdefault(group, number)
            parents.append(root)
            if root in roles and roles[root] != role:
                raise ValueError('NIKL group crosses frozen splits')
            roles[root] = role
        for source, identity, exact in connection.execute('''SELECT source, document_id, exact_sha FROM records
                WHERE number IN (SELECT MIN(number) FROM records GROUP BY exact_sha)'''):
            if expected[exact][1:] != (source, identity):
                raise ValueError('NIKL representative identity changed')
        del group_roots
        fineweb_count = fineweb_bytes = empty_count = empty_bytes = 0
        for shard in downloaded['shards']:
            path = (fineweb_report.parent / shard['path']).resolve()
            if not path.is_relative_to(fineweb_report.parent) or path.is_symlink() or file_sha256(path) != shard['sha256']:
                raise ValueError('FineWeb JSONL hash/path changed')
            relative = 'fineweb2/' + path.name
            connection.execute('INSERT INTO files VALUES (?, ?)', (relative, shard['sha256']))
            shard_count = shard_bytes = 0
            for position, row in enumerate(_json_rows(path)):
                if row['source'] != SOURCE:
                    raise ValueError('FineWeb source changed')
                text, identity = row['text'], row['id']
                exact = _digest(text)
                normalized = ' '.join(unicodedata.normalize('NFC', text).split())
                previous = connection.execute('''SELECT exact_sha FROM records WHERE source=? AND document_id=?
                    UNION ALL SELECT exact_sha FROM quarantine WHERE source=? AND document_id=? LIMIT 1''',
                    (SOURCE, identity, SOURCE, identity)).fetchone()
                if previous and previous[0] != exact:
                    raise ValueError('Conflicting FineWeb document identity')
                shard_count += 1
                shard_bytes += len(text.encode('utf-8'))
                if not normalized:
                    connection.execute('INSERT INTO quarantine VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (SOURCE, identity, text, exact, relative, position, 1, int(text == ''), 'no_non_whitespace_text'))
                    empty_count += 1
                    empty_bytes += len(text.encode('utf-8'))
                else:
                    number = len(parents)
                    parents.append(number)
                    owners = []
                    for kind, token in [('id', _digest(identity)), ('normalized', _digest(normalized))]:
                        owner = connection.execute('SELECT owner FROM links WHERE kind=? AND token=?', (kind, token)).fetchone()
                        if owner:
                            owners.append(owner[0])
                        else:
                            connection.execute('INSERT INTO links VALUES (?, ?, ?)', (kind, token, number))
                    _join_groups(parents, roles, number, owners)
                    connection.execute('INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (number, SOURCE, identity, text, exact, '', relative, position))
                if shard_count % 256 == 0:
                    connection.commit()
                    budget.check(MAX_RECORD_BYTES * 32)
                if shard_count % 10000 == 0:
                    _state(output / 'progress.json', {**progress, 'fineweb_documents': fineweb_count + shard_count})
                    print(json.dumps({'stage': 'fineweb_merge', 'documents': fineweb_count + shard_count}), flush=True)
            if shard_count != shard['documents'] or shard_bytes != shard['utf8_bytes']:
                raise ValueError('FineWeb shard document/byte totals changed')
            fineweb_count += shard_count
            fineweb_bytes += shard_bytes
            connection.commit()
            budget.check()
        keys = {}
        for number, exact in connection.execute('SELECT number, exact_sha FROM records'):
            root = _find(parents, number)
            keys[root] = min(keys.get(root, exact), exact)
        connection.executemany('UPDATE records SET group_id=? WHERE number=?',
            ((keys[_find(parents, number)], number) for number in range(len(parents))))
        connection.commit()
        assignments = {key: roles.get(root) or _assigned(key, base['split_policy']) for root, key in keys.items()}
        summaries = {split: {'documents': 0, 'utf8_bytes': 0, 'groups': 0, 'sources': {}}
                     for split in ('train', 'validation', 'test')}
        for role in assignments.values():
            summaries[role]['groups'] += 1
        with ExitStack() as stack:
            handles = {split: stack.enter_context((output / f'{split}.jsonl').open('x', encoding='utf-8')) for split in summaries}
            rows = connection.execute('''SELECT source, document_id, text, group_id FROM records
                WHERE number IN (SELECT MIN(number) FROM records GROUP BY exact_sha) ORDER BY exact_sha''')
            for position, (source, identity, text, group) in enumerate(rows):
                split = assignments[group]
                if _digest(text) in expected and expected[_digest(text)][0] != split:
                    raise ValueError('Protected NIKL split moved')
                encoded = (json.dumps({'id': identity, 'source': source, 'text': text}, ensure_ascii=False) + '\n').encode('utf-8')
                if position % 256 == 0:
                    budget.check(MAX_RECORD_BYTES * 32)
                handles[split].write(encoded.decode('utf-8'))
                summary = summaries[split]
                summary['documents'] += 1
                summary['utf8_bytes'] += len(text.encode('utf-8'))
                summary['sources'][source] = summary['sources'].get(source, 0) + 1
        if any(not summary['documents'] for summary in summaries.values()):
            raise ValueError('Combined split is empty')
    if file_sha256(database) != audit['index_sha256'] or file_sha256(nikl_manifest) != progress['nikl_manifest_sha256']:
        raise ValueError('Protected NIKL inputs changed during preparation')
    if file_sha256(fineweb_report) != progress['fineweb_report_sha256']:
        raise ValueError('FineWeb input report changed during preparation')
    budget.check()
    specs = {split: {'path': f'{split}.jsonl', 'sha256': file_sha256(output / f'{split}.jsonl')} for split in summaries}
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
              'exact_duplicate_documents': len(parents) - sum(summary['documents'] for summary in summaries.values()),
              'nikl_original_roles_preserved': True, 'policy': policy,
              'manifest_sha256': file_sha256(output / 'manifest.json'), 'index_sha256': file_sha256(child),
              'max_output_bytes': max_output_bytes, 'min_free_bytes': min_free_bytes,
              'limitations': ['No fuzzy/partial-overlap or PII review', 'Official FineWeb test never downloaded',
                              'Unique data composition is not a training exposure or replay mixture contract']}
    _write_json(output / 'report.json', result)
    _state(output / 'progress.json', {**progress, 'status': 'complete', 'stage': 'finished'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    catalog_parser = commands.add_parser('catalog')
    catalog_parser.add_argument('--output', type=Path, required=True)
    download_parser = commands.add_parser('download')
    download_parser.add_argument('--catalog', type=Path, required=True)
    download_parser.add_argument('--output', type=Path, required=True)
    download_parser.add_argument('--max-output-bytes', type=int, required=True)
    download_parser.add_argument('--min-free-gib', type=int, default=100)
    download_parser.add_argument('--resume', action='store_true')
    combine_parser = commands.add_parser('combine')
    combine_parser.add_argument('--nikl-audit', type=Path, required=True)
    combine_parser.add_argument('--nikl-manifest', type=Path, required=True)
    combine_parser.add_argument('--fineweb-report', type=Path, required=True)
    combine_parser.add_argument('--output', type=Path, required=True)
    combine_parser.add_argument('--max-output-bytes', type=int, required=True)
    combine_parser.add_argument('--min-free-gib', type=int, default=100)
    for command in (download_parser, combine_parser):
        command.add_argument('--memory-limit-gib', type=int, default=48)
    args = parser.parse_args()
    if args.command != 'catalog':
        import resource
        if args.memory_limit_gib <= 0:
            parser.error('Positive memory limit required')
        resource.setrlimit(resource.RLIMIT_AS, (args.memory_limit_gib * 1024**3,) * 2)
    if args.command == 'catalog':
        result = resolve_catalog(args.output)
    elif args.command == 'download':
        result = download_corpus(args.catalog, args.output, args.max_output_bytes, args.min_free_gib * 1024**3, args.resume)
    else:
        result = combine_corpora(args.nikl_audit, args.nikl_manifest, args.fineweb_report, args.output,
                                 args.max_output_bytes, args.min_free_gib * 1024**3)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()