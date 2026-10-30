"""Opt-in NIKL audit and deterministic document-group splitting, without raw-file edits."""
import argparse
from contextlib import closing, ExitStack
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import unicodedata

from .entropy_data import MAX_RECORD_BYTES, file_sha256, inspect_dataset


GROUP_POLICY = 'document-id-or-NFC-whitespace-text-connected-components-v1'
MIN_FREE_BYTES = 100 * 1024**3


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _space(path, minimum, reserve=0):
    if type(minimum) is not int or minimum < 0:
        raise ValueError('Nonnegative minimum free bytes required')
    if shutil.disk_usage(path).free < minimum + reserve:
        raise ValueError('Free disk reserve would be exceeded')


def _write_json(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def _find(parents, number):
    while parents[number] != number:
        parents[number] = parents[parents[number]]
        number = parents[number]
    return number


def audit_corpus(input_root, sources_path, output, min_free_bytes=MIN_FREE_BYTES, *,
                 empty_document_policy='error'):
    if empty_document_policy not in ('error', 'quarantine'):
        raise ValueError('Empty document policy must be error or quarantine')
    input_root, sources_path, output = (Path(path).resolve() for path in (input_root, sources_path, output))
    if output.is_relative_to(input_root):
        raise ValueError('Audit output must be outside input root')
    catalog = json.loads(sources_path.read_text(encoding='utf-8'))
    sources = catalog.get('sources', [])
    excluded = catalog.get('excluded_directories', [])
    if not sources or len({spec['source'] for spec in sources}) != len(sources):
        raise ValueError('Nonempty, unique explicit sources required')
    if len({spec['directory'] for spec in sources}) != len(sources):
        raise ValueError('Source directories must be unique')
    for spec in sources:
        directory = spec['directory']
        if (not isinstance(directory, str) or not directory or Path(directory).name != directory or
                directory in ('.', '..') or directory in excluded or
                not isinstance(spec['source'], str) or not spec['source']):
            raise ValueError('Invalid or excluded source directory')
        if spec['format'] not in ('nikl_paragraph', 'nikl_utterance'):
            raise ValueError('Only explicit NIKL paragraph/utterance formats supported')
    output.mkdir(parents=True, exist_ok=False)
    _space(output, min_free_bytes)
    database = output / 'index.sqlite'
    parents, source_counts = [], {}
    file_count, normalized_links, identity_links = 0, 0, 0
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executescript('''
            PRAGMA cache_size=-16384;
            PRAGMA temp_store=FILE;
            CREATE TABLE files(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
            CREATE TABLE records(number INTEGER PRIMARY KEY, source TEXT, document_id TEXT,
                                 text TEXT, exact_sha TEXT, group_id TEXT, file_path TEXT, position INTEGER);
            CREATE INDEX identities ON records(source, document_id);
            CREATE INDEX exact_text ON records(exact_sha);
            CREATE TABLE links(kind TEXT, token TEXT, owner INTEGER, PRIMARY KEY(kind, token));
            CREATE TABLE quarantine(source TEXT, document_id TEXT, text TEXT, exact_sha TEXT,
                                    file_path TEXT, position INTEGER, parts INTEGER, empty_form_parts INTEGER,
                                    reason TEXT, PRIMARY KEY(file_path, position));
            CREATE INDEX quarantine_identity ON quarantine(source, document_id);
        ''')
        for spec in sorted(sources, key=lambda value: value['source']):
            folder = input_root / spec['directory']
            if folder.is_symlink() or not folder.resolve().is_relative_to(input_root):
                raise ValueError('Missing or linked input directory')
            if not folder.is_dir():
                raise ValueError(f'Missing source directory: {spec["directory"]}')
            paths = sorted(path for path in folder.rglob('*') if path.suffix.lower() == '.json')
            if not paths:
                raise ValueError(f'No JSON files in source: {spec["source"]}')
            if 'expected_files' in spec and len(paths) != spec['expected_files']:
                raise ValueError(f'Source file count mismatch: {spec["source"]}')
            counts = {'files': 0, 'documents': 0, 'utf8_bytes': 0, 'empty_form_parts': 0,
                      'usable_documents': 0, 'quarantined_documents': 0, 'quarantined_utf8_bytes': 0}
            source_counts[spec['source']] = counts
            for path in paths:
                if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
                    raise ValueError('Refusing linked input JSON')
                if not path.is_file() or path.stat().st_size > 512 * 1024**2:
                    raise ValueError('NIKL input must be a regular JSON file no larger than 512MiB')
                _space(output, min_free_bytes, reserve=path.stat().st_size * 2)
                raw = path.read_bytes()
                payload = json.loads(raw.decode('utf-8-sig'))
                relative = str(path.relative_to(input_root))
                connection.execute('INSERT INTO files VALUES (?, ?)',
                                   (relative, hashlib.sha256(raw).hexdigest()))
                del raw
                records = payload.get('document') if isinstance(payload, dict) else None
                if not isinstance(records, list) or not records:
                    raise ValueError(f'Nonempty document list required: {relative}')
                field = 'paragraph' if spec['format'] == 'nikl_paragraph' else 'utterance'
                for position, document in enumerate(records):
                    if not isinstance(document, dict) or not isinstance(document.get('id'), str) or not document['id']:
                        raise ValueError(f'Nonempty document id required: {relative}:{position}')
                    parts = document.get(field)
                    if not isinstance(parts, list) or not parts:
                        raise ValueError(f'Expected nonempty {field} list: {relative}:{position}')
                    for part_index, part in enumerate(parts):
                        if not isinstance(part, dict) or not isinstance(part.get('form'), str):
                            form_type = ('missing' if isinstance(part, dict) and 'form' not in part else
                                         type(part.get('form') if isinstance(part, dict) else part).__name__)
                            raise ValueError(f'Expected form string: {relative}:{position} '
                                             f'{field}[{part_index}] form_type={form_type}')
                    empty_parts = sum(part['form'] == '' for part in parts)
                    text = '\n'.join(part['form'] for part in parts)
                    normalized = ' '.join(unicodedata.normalize('NFC', text).split())
                    if not normalized and empty_document_policy == 'error':
                        raise ValueError(f'Empty or whitespace-only document: {relative}:{position} '
                                         f'{field}_parts={len(parts)} empty_form_parts={empty_parts}')
                    row = {'id': document['id'], 'source': spec['source'], 'text': text}
                    if len((json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8')) > MAX_RECORD_BYTES:
                        raise ValueError(f'Record exceeds 16MiB: {relative}:{position}')
                    exact_sha = _digest(text)
                    previous = connection.execute('''SELECT exact_sha FROM records WHERE source=? AND document_id=?
                                                     UNION ALL SELECT exact_sha FROM quarantine
                                                     WHERE source=? AND document_id=? LIMIT 1''',
                                                  (spec['source'], document['id'], spec['source'], document['id'])).fetchone()
                    if previous and previous[0] != exact_sha:
                        raise ValueError(f'Conflicting document identity: {relative}:{position}')
                    counts['documents'] += 1
                    counts['utf8_bytes'] += len(text.encode('utf-8'))
                    counts['empty_form_parts'] += empty_parts
                    if not normalized:
                        connection.execute('INSERT INTO quarantine VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                           (spec['source'], document['id'], text, exact_sha, relative,
                                            position, len(parts), empty_parts, 'no_non_whitespace_form_text'))
                        counts['quarantined_documents'] += 1
                        counts['quarantined_utf8_bytes'] += len(text.encode('utf-8'))
                        continue
                    number = len(parents)
                    parents.append(number)
                    connection.execute('INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                       (number, spec['source'], document['id'], text, exact_sha, '', relative, position))
                    for kind, token in [('id', _digest(document['id'])), ('normalized', _digest(normalized))]:
                        owner = connection.execute('SELECT owner FROM links WHERE kind=? AND token=?', (kind, token)).fetchone()
                        if owner:
                            left, right = _find(parents, number), _find(parents, owner[0])
                            parents[max(left, right)] = min(left, right)
                            identity_links += kind == 'id'
                            normalized_links += kind == 'normalized'
                        else:
                            connection.execute('INSERT INTO links VALUES (?, ?, ?)', (kind, token, number))
                    counts['usable_documents'] += 1
                counts['files'] += 1
                file_count += 1
                connection.commit()
                if file_count % 500 == 0:
                    print(json.dumps({'stage': 'audit', 'files': file_count,
                                      'documents': sum(item['documents'] for item in source_counts.values()),
                                      'quarantined_documents': sum(item['quarantined_documents'] for item in source_counts.values())}), flush=True)
        group_keys = {}
        for number, exact_sha in connection.execute('SELECT number, exact_sha FROM records'):
            group = _find(parents, number)
            group_keys[group] = min(group_keys.get(group, exact_sha), exact_sha)
        connection.executemany('UPDATE records SET group_id=? WHERE number=?',
                               ((group_keys[_find(parents, number)], number) for number in range(len(parents))))
        connection.execute('CREATE INDEX group_lookup ON records(group_id)')
        unique = connection.execute('SELECT COUNT(DISTINCT exact_sha) FROM records').fetchone()[0]
        largest = connection.execute('SELECT MAX(size) FROM (SELECT COUNT(DISTINCT exact_sha) AS size FROM records GROUP BY group_id)').fetchone()[0] or 0
    _space(output, min_free_bytes)
    report = {'schema_version': 1, 'status': 'complete', 'group_policy': GROUP_POLICY,
              'code_sha256': file_sha256(Path(__file__)), 'catalog_sha256': file_sha256(sources_path),
              'index_sha256': file_sha256(database), 'sources': source_counts,
              'excluded_directories': excluded, 'files': file_count,
              'input_documents': sum(item['documents'] for item in source_counts.values()),
              'usable_documents': len(parents), 'empty_document_policy': empty_document_policy,
              'quarantined_documents': sum(item['quarantined_documents'] for item in source_counts.values()),
              'quarantined_utf8_bytes': sum(item['quarantined_utf8_bytes'] for item in source_counts.values()),
              'quarantine_ledger': 'index.sqlite:quarantine',
              'unique_exact_documents': unique, 'exact_duplicate_documents': len(parents) - unique,
              'groups': len(group_keys), 'largest_group_unique_documents': largest,
              'identity_links': identity_links, 'normalized_links': normalized_links,
              'normalization': 'NFC and whitespace collapse for grouping only; output text unchanged',
              'limitations': ['No fuzzy or partial-overlap near-duplicate search',
                              'Shared document IDs may conservatively group different bodies',
                              'No PII review; SQLite contains private corpus text and provenance']}
    _write_json(output / 'audit.json', report)
    return report


def split_corpus(audit, output, validation_percent, test_percent, seed, min_free_bytes=MIN_FREE_BYTES):
    if (any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
            for value in (validation_percent, test_percent)) or validation_percent + test_percent >= 100):
        raise ValueError('Positive validation/test percentages with sum below 100 required')
    if type(seed) is not int or seed < 0:
        raise ValueError('Nonnegative integer seed required')
    audit, output = Path(audit).resolve(), Path(output).resolve()
    if output.is_relative_to(audit):
        raise ValueError('Split output must be outside audit directory')
    report = json.loads((audit / 'audit.json').read_text(encoding='utf-8'))
    if report['status'] != 'complete' or report['group_policy'] != GROUP_POLICY:
        raise ValueError('Completed compatible audit required')
    if report['code_sha256'] != file_sha256(Path(__file__)):
        raise ValueError('Audit code changed; use a new audit directory')
    database = audit / 'index.sqlite'
    if file_sha256(database) != report['index_sha256']:
        raise ValueError('Audit index hash mismatch')
    output.mkdir(parents=True, exist_ok=False)
    _space(output, min_free_bytes)
    summaries = {split: {'documents': 0, 'utf8_bytes': 0, 'groups': 0, 'sources': {}}
                 for split in ('train', 'validation', 'test')}
    assignments = {}
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection, ExitStack() as stack:
        handles = {split: stack.enter_context((output / f'{split}.jsonl').open('x', encoding='utf-8'))
                   for split in summaries}
        rows = connection.execute('''SELECT source, document_id, text, group_id FROM records
                                     WHERE number IN (SELECT MIN(number) FROM records GROUP BY exact_sha)
                                     ORDER BY exact_sha''')
        for source, identity, text, group in rows:
            if group not in assignments:
                score = int(_digest(f'{seed}:{group}')[:16], 16) / 2**64 * 100
                split = 'test' if score < test_percent else 'validation' if score < test_percent + validation_percent else 'train'
                assignments[group] = split
                summaries[split]['groups'] += 1
            split = assignments[group]
            encoded = json.dumps({'id': identity, 'source': source, 'text': text}, ensure_ascii=False) + '\n'
            _space(output, min_free_bytes, reserve=len(encoded.encode('utf-8')))
            handles[split].write(encoded)
            summary = summaries[split]
            summary['documents'] += 1
            summary['utf8_bytes'] += len(text.encode('utf-8'))
            summary['sources'][source] = summary['sources'].get(source, 0) + 1
    if any(not summary['documents'] for summary in summaries.values()):
        raise ValueError('Empty split; inspect group sizes or explicitly choose another seed/percentages')
    specs = {split: {'path': f'{split}.jsonl', 'sha256': file_sha256(output / f'{split}.jsonl')}
             for split in summaries}
    policy = {'seed': seed, 'validation_percent': validation_percent, 'test_percent': test_percent,
              'assignment': 'SHA256(seed:group-min-exact-sha); approximate group proportions, not byte quotas',
              'exact_duplicates': 'One representative in sorted source/file/document order; aliases retained in audit index'}
    manifest = {'schema_version': 1, 'source_audit_sha256': file_sha256(audit / 'audit.json'),
                'audit_index_sha256': report['index_sha256'], 'group_policy': GROUP_POLICY,
                'empty_document_policy': report['empty_document_policy'],
                'quarantined_documents': report['quarantined_documents'],
                'split_policy': policy, 'pii_review_approved': False,
                'near_duplicate_split_review_approved': False,
                'preprocessing': 'form fields joined by LF; no Unicode normalization of output text',
                'splits': {split: specs[split] for split in ('train', 'validation')},
                'held_out_test': specs['test']}
    _write_json(output / 'manifest.json', manifest)
    inspect_dataset(output / 'manifest.json')
    result = {'schema_version': 1, 'status': 'complete', 'documents': sum(item['documents'] for item in summaries.values()),
              'empty_document_policy': report['empty_document_policy'],
              'quarantined_documents': report['quarantined_documents'],
              'splits': summaries, 'policy': policy, 'manifest_sha256': file_sha256(output / 'manifest.json'),
              'limitations': report['limitations']}
    _write_json(output / 'report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    audit_parser = commands.add_parser('audit')
    audit_parser.add_argument('--input-root', required=True)
    audit_parser.add_argument('--sources', required=True)
    audit_parser.add_argument('--empty-document-policy', choices=('error', 'quarantine'), default='error',
                              help='Explicitly preserve contentless documents in a private ledger, not training JSONL')
    split_parser = commands.add_parser('split')
    split_parser.add_argument('--audit', required=True)
    split_parser.add_argument('--validation-percent', required=True, type=float)
    split_parser.add_argument('--test-percent', required=True, type=float)
    split_parser.add_argument('--seed', required=True, type=int)
    for command in (audit_parser, split_parser):
        command.add_argument('--output', required=True)
        command.add_argument('--min-free-gib', type=int, default=100)
    args = parser.parse_args()
    if args.command == 'audit':
        result = audit_corpus(args.input_root, args.sources, args.output, args.min_free_gib * 1024**3,
                      empty_document_policy=args.empty_document_policy)
    else:
        result = split_corpus(args.audit, args.output, args.validation_percent, args.test_percent,
                              args.seed, args.min_free_gib * 1024**3)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()