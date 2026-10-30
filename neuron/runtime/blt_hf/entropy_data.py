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
    summary = {}
    for split, spec in manifest['splits'].items():
        path = (manifest_path.parent / spec['path']).resolve()
        if file_sha256(path) != spec['sha256']:
            raise ValueError(f'Dataset hash mismatch: {split}')
        count = total_bytes = 0
        for record in documents(path):
            identity = (record['source'], record['id'])
            if identity in seen_ids:
                raise ValueError(f'Duplicate document identity: {identity}')
            seen_ids.add(identity)
            digest = hashlib.sha256(record['text'].encode('utf-8')).hexdigest()
            if digest in seen_text:
                raise ValueError(f'Duplicate text across {seen_text[digest]} and {split}')
            seen_text[digest] = split
            count += 1
            total_bytes += len(record['text'].encode('utf-8'))
        if not count:
            raise ValueError(f'Empty split: {split}')
        summary[split] = {'documents': count, 'utf8_bytes': total_bytes, 'path': str(path)}
    return manifest, summary


def examples(path, chunk_bytes):
    for record in documents(path):
        yield from byte_examples(record['text'], chunk_bytes)


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