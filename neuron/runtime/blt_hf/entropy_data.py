"""Document-isolated byte sequences and an explicit, hashed CPT data contract."""
import hashlib
import json
from pathlib import Path


MAX_RECORD_BYTES = 16 * 1024 * 1024


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def documents(path):
    with Path(path).open('rb') as handle:
        line_number = 0
        while True:
            raw = handle.readline(MAX_RECORD_BYTES + 1)
            if not raw:
                break
            line_number += 1
            if len(raw) > MAX_RECORD_BYTES:
                raise ValueError(f'Record exceeds 16MiB: {path}:{line_number}')
            record = json.loads(raw.decode('utf-8'))
            if (not isinstance(record, dict) or
                    any(not isinstance(record.get(key), str) or not record[key]
                        for key in ('id', 'source', 'text'))):
                raise ValueError(f'Expected nonempty id/source/text: {path}:{line_number}')
            yield record


def byte_examples(text, chunk_bytes):
    if type(chunk_bytes) is not int or chunk_bytes < 1:
        raise ValueError('Positive chunk byte count required')
    data = text.encode('utf-8', errors='strict')
    for offset in range(0, len(data), chunk_bytes):
        payload = list(data[offset:offset + chunk_bytes])
        ids = [1] + [value + 4 for value in payload]
        if offset + len(payload) == len(data):
            ids.append(2)
        yield {'inputs': ids[:-1], 'targets': ids[1:],
               'utf8_bytes': len(payload), 'offset': offset}


def inspect_dataset(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    if set(manifest.get('splits', {})) != {'train', 'validation'}:
        raise ValueError('Only explicit train/validation files allowed; final test stays unopened')
    seen_ids, seen_text = set(), {}
    allowed = set()
    policy = manifest.get('fineweb_id_conflict_policy')
    if policy:
        ledger = (manifest_path.parent / policy['ledger']).resolve()
        if not ledger.is_relative_to(manifest_path.parent) or file_sha256(ledger) != policy['ledger_sha256']:
            raise ValueError('ID conflict ledger hash/path changed')
        for line in ledger.read_text(encoding='utf-8').split('\n'):
            if line:
                row = json.loads(line)
                allowed.add((row['document_id'], row['exact_sha']))
    summary = {}
    for split, spec in manifest['splits'].items():
        path = (manifest_path.parent / spec['path']).resolve()
        if file_sha256(path) != spec['sha256']:
            raise ValueError(f'Dataset hash mismatch: {split}')
        count = total_bytes = 0
        for record in documents(path):
            identity = (record['source'], record['id'])
            digest = hashlib.sha256(record['text'].encode('utf-8')).hexdigest()
            if identity in seen_ids and (record['id'], digest) not in allowed:
                raise ValueError(f'Duplicate document identity: {identity}')
            seen_ids.add(identity)
            if digest in seen_text:
                raise ValueError(f'Duplicate text across {seen_text[digest]} and {split}')
            seen_text[digest] = split
            count += 1
            total_bytes += len(record['text'].encode('utf-8'))
        if not count:
            raise ValueError(f'Empty split: {split}')
        summary[split] = {'documents': count, 'utf8_bytes': total_bytes, 'path': str(path)}
    return manifest, summary


def _file_stat(path):
    stat = Path(path).stat()
    return [stat.st_size, stat.st_mtime_ns]


def inspect_dataset_cached(manifest_path):
    """Full inspection once, then reuse it while the manifest hash and split size/mtime are unchanged."""
    manifest_path = Path(manifest_path).resolve()
    cache = manifest_path.with_name(manifest_path.stem + '.inspection.json')
    digest = file_sha256(manifest_path)
    if cache.is_file():
        record = json.loads(cache.read_text())
        if (record['manifest_sha256'] == digest and
                all(_file_stat(spec['path']) == record['stat'][split] for split, spec in record['summary'].items())):
            return json.loads(manifest_path.read_text()), record['summary']
    manifest, summary = inspect_dataset(manifest_path)
    record = {'manifest_sha256': digest, 'summary': summary,
              'stat': {split: _file_stat(spec['path']) for split, spec in summary.items()},
              'trust': 'Split SHA256 and contract verified once; later runs trust unchanged size and mtime'}
    temporary = cache.with_suffix('.partial')
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    temporary.replace(cache)
    return manifest, summary


def examples(path, chunk_bytes):
    for record in documents(path):
        yield from byte_examples(record['text'], chunk_bytes)


BOS, EOS, PAD = 1, 2, 3


def document_tokens(text):
    import numpy as np
    data = np.frombuffer(text.encode('utf-8', errors='strict'), dtype=np.uint8)
    tokens = np.empty(len(data) + 2, dtype=np.int64)
    tokens[0], tokens[-1] = BOS, EOS
    tokens[1:-1] = data
    tokens[1:-1] += 4
    return tokens


class PackedStream:
    """Fixed-length sequences of BOS+bytes+EOS documents isolated by the EOS mask.

    A document cut at a sequence end resumes at the start of the next sequence behind its
    previous `context` tokens (loss masked). That fills each target's per-layer attention window;
    deeper layers still lose the earlier receptive field, as at any sequence start.
    State is (epoch, byte offset of the current document line, next target index in it).
    """

    def __init__(self, path, sequence_length, context, state=None, max_documents=None, wrap=False):
        if type(sequence_length) is not int or type(context) is not int or not 0 < context < sequence_length:
            raise ValueError('Sequence length must exceed a positive context')
        self.path, self.length, self.context = Path(path), sequence_length, context
        self.max_documents, self.wrap = max_documents, wrap
        self.state = dict(state or {'epoch': 0, 'offset': 0, 'next_target': 1, 'documents': 0})
        self._handle = self._document = None

    def close(self):
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def _load(self):
        if self._document is not None:
            return True
        if self.max_documents is not None and self.state['next_target'] == 1 and self.state['documents'] >= self.max_documents:
            return False
        if self._handle is None:
            self._handle = self.path.open('rb')
        self._handle.seek(self.state['offset'])
        raw = self._handle.readline(MAX_RECORD_BYTES + 1)
        if not raw:
            if not self.wrap or self.state['offset'] == 0:
                return False
            self.state.update(epoch=self.state['epoch'] + 1, offset=0, next_target=1, documents=0)
            return self._load()
        if len(raw) > MAX_RECORD_BYTES:
            raise ValueError(f'Record exceeds 16MiB at byte {self.state["offset"]}: {self.path}')
        record = json.loads(raw.decode('utf-8'))
        if not isinstance(record, dict) or not isinstance(record.get('text'), str) or not record['text']:
            raise ValueError(f'Expected nonempty text at byte {self.state["offset"]}: {self.path}')
        self._document, self._next_offset = document_tokens(record['text']), self.state['offset'] + len(raw)
        return True

    def next_sequence(self):
        """Returns (tokens[length+1], keep[length]) where keep marks targets tokens[1:] to train, or None."""
        import numpy as np
        size = self.length + 1
        tokens = np.full(size, PAD, dtype=np.int64)
        keep = np.zeros(self.length, dtype=bool)
        fill = 0
        while fill < size and self._load():
            document, target = self._document, self.state['next_target']
            if fill and target != 1:
                raise AssertionError('Continuations must start a sequence')
            start = max(0, target - self.context)
            piece = document[start:start + size - fill]
            tokens[fill:fill + len(piece)] = piece
            keep[fill + target - start - 1:fill + len(piece) - 1] = True
            fill += len(piece)
            end = start + len(piece)
            if end == len(document):
                self.state.update(offset=self._next_offset, next_target=1, documents=self.state['documents'] + 1)
                self._document = None
            else:
                self.state['next_target'] = end
        return (tokens, keep) if fill else None


def prepare(plan_path, output):
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text())
    output = Path(output).resolve()
    if not plan.get('files'):
        raise ValueError('Explicit input files and document-level split assignment required')
    for spec in plan['files']:
        if spec['split'] not in ('train', 'validation'):
            raise ValueError('Only train/validation inputs accepted; final test must remain separate')
        if spec['format'] not in ('jsonl', 'nikl_paragraph', 'nikl_utterance'):
            raise ValueError('Unsupported input format; inspect the actual schema before conversion')
    output.mkdir(parents=True, exist_ok=False)
    provenance = []
    for split in ('train', 'validation'):
        with (output / f'{split}.jsonl').open('x', encoding='utf-8') as destination:
            for spec in plan['files']:
                if spec['split'] != split:
                    continue
                path = (plan_path.parent / spec['path']).resolve()
                provenance.append({'path': str(path), 'sha256': file_sha256(path), **spec})
                if spec['format'] == 'jsonl':
                    records = documents(path)
                else:
                    if path.stat().st_size > 512 * 1024 * 1024:
                        raise ValueError('NIKL JSON larger than 512MiB requires a reviewed streaming reader')
                    with path.open(encoding='utf-8') as source:
                        payload = json.load(source)
                    field = 'paragraph' if spec['format'] == 'nikl_paragraph' else 'utterance'
                    records = ({'id': document['id'], 'source': spec['source'],
                                'text': '\n'.join(part['form'] for part in document[field])}
                               for document in payload['document'])
                for record in records:
                    if record['source'] != spec['source']:
                        raise ValueError('Source identity mismatch')
                    destination.write(json.dumps(record, ensure_ascii=False) + '\n')
    manifest = {'schema_version': 1, 'source_plan_sha256': file_sha256(plan_path),
                'pii_review_approved': False,
                'near_duplicate_split_review_approved': False,
                'preprocessing': 'No Unicode normalization; NIKL form fields joined by LF; no speaker metadata',
                'source_files': provenance,
                'splits': {split: {'path': f'{split}.jsonl', 'sha256': file_sha256(output / f'{split}.jsonl')}
                           for split in ('train', 'validation')}}
    manifest_path = output / 'manifest.json'
    with manifest_path.open('x') as handle:
        handle.write(json.dumps(manifest, indent=2) + '\n')
    _, summary = inspect_dataset(manifest_path)
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, help='Explicit files/source/split/format JSON; no automatic split')
    parser.add_argument('--output', required=True, help='Fresh directory, never overwritten')
    args = parser.parse_args()
    print(json.dumps(prepare(args.plan, args.output), indent=2))


if __name__ == '__main__':
    main()