"""Korean count-patcher data (background, label and evaluation documents) sampled from the CPT splits.

A seeded hash of each source line picks its role, so background and label lines are disjoint. Every source
file is read to its end and checked against the manifest SHA-256; the held-out test is only sampled here.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import time

from .entropy_data import MAX_RECORD_BYTES, file_sha256

LENGTH_FILTER = (256, 65536)
BLOCK = 8 * 1024 * 1024


def line_value(seed, raw):
    """Uniform value in [0, 1) of a source line (without its newline) under the seed."""
    return int.from_bytes(hashlib.sha256(f'count-sample:{seed}:'.encode() + raw).digest()[:8], 'big') / 2 ** 64


class Selection:
    def __init__(self, name, low, high, target, stream):
        self.name, self.low, self.high, self.target, self.stream = name, low, high, target, stream
        self.digest = hashlib.sha256()
        self.documents = self.utf8_bytes = 0
        self.sources = Counter()
        self.text_sha256 = set()

    @property
    def full(self):
        return self.utf8_bytes >= self.target

    def write(self, row, size, keep_hash):
        data = (json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8')
        self.digest.update(data)
        self.stream.write(data)
        self.documents += 1
        self.utf8_bytes += size
        self.sources[row['source']] += 1
        if keep_hash:
            self.text_sha256.add(row['text_sha256'])

    def summary(self):
        return {'documents': self.documents, 'utf8_bytes': self.utf8_bytes, 'file_sha256': self.digest.hexdigest(),
                'sources': dict(sorted(self.sources.items()))}


def scan(path, expected_sha256, split, seed, revision, selections, *, skip=0, exclude=frozenset(),
         keep_hash=(), progress=None, progress_every=1_000_000):
    """Write the first in-range lines of each selection up to its byte target, then hash the rest of the file."""
    digest = hashlib.sha256()
    lines = 0
    with Path(path).open('rb') as handle:
        while not all(selection.full for selection in selections):
            raw = handle.readline(MAX_RECORD_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_RECORD_BYTES:
                raise ValueError(f'Record exceeds 16MiB: {path}:{lines + 1}')
            digest.update(raw)
            lines += 1
            if progress is not None and lines % progress_every == 0:
                progress(split, lines, selections)
            if lines <= skip:
                continue
            value = line_value(seed, raw.rstrip(b'\n'))
            selection = next((item for item in selections if item.low <= value < item.high), None)
            if selection is None or selection.full:
                continue
            record = json.loads(raw)
            if not isinstance(record, dict) or any(not isinstance(record.get(key), str) or not record[key]
                                                   for key in ('id', 'source', 'text')):
                raise ValueError(f'Expected nonempty id/source/text: {path}:{lines}')
            data = record['text'].encode('utf-8')
            if not LENGTH_FILTER[0] <= len(data) <= LENGTH_FILTER[1]:
                continue
            text_sha256 = hashlib.sha256(data).hexdigest()
            if text_sha256 in exclude:
                raise ValueError(f'Text repeats a held-out document: {path}:{lines}')
            row = {'document_id': record['id'], 'source': record['source'], 'text': record['text'],
                   'text_sha256': text_sha256, 'revision': revision, 'source_split': split, 'source_line': lines}
            selection.write(row, len(data), selection.name in keep_hash)
        for block in iter(lambda: handle.read(BLOCK), b''):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise ValueError(f'Source split hash mismatch: {split}')
    for selection in selections:
        if not selection.full:
            raise ValueError(f'{selection.name}: {selection.utf8_bytes} of {selection.target} bytes available')
    return lines


def sample(manifest_path, output, *, seed, background_bytes, train_bytes, validation_bytes, test_bytes,
           validation_skip, background_rate, label_rate, holdout_rate, progress_every=1_000_000):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    if 'held_out_test' not in manifest:
        raise ValueError(f'No held_out_test in {manifest_path}; use the split manifest that lists it')
    specs = {'train': manifest['splits']['train'], 'validation': manifest['splits']['validation'],
             'test': manifest['held_out_test']}
    paths = {split: (manifest_path.parent / spec['path']).resolve() for split, spec in specs.items()}
    if not (0 < label_rate and 0 < background_rate and label_rate + background_rate <= 1 and 0 < holdout_rate <= 1):
        raise ValueError('Rates must be positive and the train ranges must fit in [0, 1)')
    if min(background_bytes, train_bytes, validation_bytes, test_bytes) < 1 or validation_skip < 0:
        raise ValueError('Positive byte targets and a nonnegative validation skip required')
    output = Path(output)
    output.mkdir(exist_ok=False)
    revision = file_sha256(manifest_path)
    started = time.time()

    def progress(split, lines, selections):
        print(json.dumps({'split': split, 'lines': lines, 'elapsed_seconds': round(time.time() - started, 1),
                          **{item.name: item.utf8_bytes for item in selections}}), flush=True)

    report = {
        'schema_version': 1, 'status': 'running', 'run_id': output.name,
        'source_manifest': str(manifest_path), 'source_manifest_sha256': revision,
        'source_files': {split: {'path': str(paths[split]), 'sha256': spec['sha256']} for split, spec in specs.items()},
        'seed': seed, 'utf8_length_filter': list(LENGTH_FILTER),
        'targets': {'background': background_bytes, 'train': train_bytes, 'validation': validation_bytes,
                    'test': test_bytes},
        'selection': {
            'value': 'First 8 bytes of SHA-256("count-sample:<seed>:" + source line without newline) / 2^64',
            'ranges': {'train': [0, label_rate], 'background': [label_rate, label_rate + background_rate],
                       'validation': [0, holdout_rate], 'test': [0, holdout_rate]},
            'roles': 'background and train from the CPT train split; validation from CPT validation after '
                     'skipping its first lines (used by CPT evaluations); test from the held-out test',
            'validation_skip_lines': validation_skip,
            'order': 'Source file order; whole documents until each UTF-8 byte target is reached',
        },
        'script_sha256': file_sha256(Path(__file__)),
        'limitations': ['No near-duplicate check between roles beyond the CPT exact/normalized grouping',
                        'Byte targets overshoot by at most one document'],
    }
    try:
        holdout = set()
        selections = {}
        for split, target, skip in (('validation', validation_bytes, validation_skip), ('test', test_bytes, 0)):
            with (output / f'{split}.jsonl').open('xb') as stream:
                selections[split] = Selection(split, 0.0, holdout_rate, target, stream)
                report['source_files'][split]['lines'] = scan(
                    paths[split], specs[split]['sha256'], split, seed, revision, [selections[split]], skip=skip,
                    exclude=holdout, keep_hash=(split,), progress=progress, progress_every=progress_every)
            holdout |= selections[split].text_sha256
        background_path = output / 'background.jsonl.gz'
        with (output / 'train.jsonl').open('xb') as train_stream, background_path.open('xb') as raw_stream, \
                gzip.GzipFile(filename='', mode='wb', fileobj=raw_stream, compresslevel=1, mtime=0) as background_stream:
            selections['train'] = Selection('train', 0.0, label_rate, train_bytes, train_stream)
            selections['background'] = Selection('background', label_rate, label_rate + background_rate,
                                                 background_bytes, background_stream)
            report['source_files']['train']['lines'] = scan(
                paths['train'], specs['train']['sha256'], 'train', seed, revision,
                [selections['train'], selections['background']], exclude=holdout, progress=progress,
                progress_every=progress_every)
        for split in ('train', 'validation', 'test'):
            if file_sha256(output / f'{split}.jsonl') != selections[split].digest.hexdigest():
                raise ValueError(f'Written file hash differs: {split}')
        report['splits'] = {name: selections[name].summary() for name in ('background', 'train', 'validation', 'test')}
        report['splits']['background']['compressed'] = {
            'path': background_path.name, 'sha256': file_sha256(background_path), 'bytes': background_path.stat().st_size}
        report['status'] = 'prepared'
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
    finally:
        report['elapsed_seconds'] = time.time() - started
        with (output / 'manifest.json').open('x') as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261127)
    parser.add_argument('--background-bytes', type=int, default=50_000_000_000)
    parser.add_argument('--train-bytes', type=int, default=4_000_000)
    parser.add_argument('--validation-bytes', type=int, default=500_000)
    parser.add_argument('--test-bytes', type=int, default=1_500_000)
    parser.add_argument('--validation-skip', type=int, default=20000)
    parser.add_argument('--background-rate', type=float, default=0.4)
    parser.add_argument('--label-rate', type=float, default=1e-4)
    parser.add_argument('--holdout-rate', type=float, default=5e-3)
    args = parser.parse_args()
    report = sample(args.manifest, args.output, seed=args.seed, background_bytes=args.background_bytes,
                    train_bytes=args.train_bytes, validation_bytes=args.validation_bytes, test_bytes=args.test_bytes,
                    validation_skip=args.validation_skip, background_rate=args.background_rate,
                    label_rate=args.label_rate, holdout_rate=args.holdout_rate)
    print(json.dumps({key: report.get(key) for key in ('status', 'splits', 'error', 'elapsed_seconds')},
                     ensure_ascii=False), flush=True)
    return int(report['status'] != 'prepared')


if __name__ == '__main__':
    raise SystemExit(main())
