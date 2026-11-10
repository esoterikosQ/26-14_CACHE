import json
from pathlib import Path
import random
import signal
import tempfile
import unittest
from unittest.mock import patch

from blt_hf.entropy_data import byte_examples, file_sha256, inspect_dataset, prepare

try:
    import torch
except ImportError:
    torch = None
try:
    import numpy
except ImportError:
    numpy = None


def write_corpus(path, texts, prefix=''):
    path.write_text(''.join(json.dumps({'id': f'{prefix}{index}', 'source': 's', 'text': text}, ensure_ascii=False) + '\n'
                            for index, text in enumerate(texts)), encoding='utf-8')


def random_texts(seed, count, longest):
    generator = random.Random(seed)
    return [''.join(generator.choice('ab한 \n"') for _ in range(generator.randint(1, longest))) for _ in range(count)]


def drain(stream):
    rows, states = [], []
    while (row := stream.next_sequence()) is not None:
        rows.append(row)
        states.append(dict(stream.state))
    stream.close()
    return rows, states


def segment_start(tokens, position):
    ends = [index for index in range(position) if tokens[index] == 2]
    return ends[-1] + 1 if ends else 0


def visible_window(tokens, position, window):
    """Positions the osc mask lets `position` attend to directly: same EOS segment, distance < window."""
    return max(segment_start(tokens, position), position - window + 1)


class EntropyDataContracts(unittest.TestCase):
    def test_stop_request_defers_signal_and_restores_handlers(self):
        from blt_hf.entropy_train import StopRequest
        previous = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGUSR1)}
        stop = StopRequest()
        stop.install()
        try:
            self.assertFalse(stop.requested)
            signal.raise_signal(signal.SIGUSR1)
            self.assertTrue(stop.requested)
            signal.raise_signal(signal.SIGTERM)
            self.assertTrue(stop.requested)
        finally:
            stop.restore()
        self.assertEqual(previous, {number: signal.getsignal(number) for number in previous})
        import time
        self.assertFalse(StopRequest(time.time() + 60).requested)
        late = StopRequest(time.time() - 1)
        self.assertEqual((late.requested, late.signaled), (True, False))

    def test_bytes_are_preserved_and_shifted_once(self):
        text = '한글 e\u0301\n'
        rows = list(byte_examples(text, 4))
        targets = [value for row in rows for value in row['targets'] if value >= 4]
        self.assertEqual(bytes(value - 4 for value in targets), text.encode('utf-8'))
        self.assertEqual(sum(row['utf8_bytes'] for row in rows), len(text.encode('utf-8')))
        self.assertTrue(all(row['inputs'][0] == 1 for row in rows))
        self.assertEqual(rows[-1]['targets'][-1], 2)
        self.assertTrue(all(2 not in row['targets'] for row in rows[:-1]))
        for row in rows:
            self.assertEqual(row['inputs'][1:], row['targets'][:-1])

    def test_no_document_packing_or_empty_examples(self):
        self.assertEqual(list(byte_examples('', 8)), [])
        self.assertEqual(list(byte_examples('a', 8))[0]['inputs'], [1, 101])
        with self.assertRaises(ValueError):
            list(byte_examples('a', 0))

    def test_manifest_rejects_leakage_and_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {'splits': {}}
            for split, text in [('train', '학습'), ('validation', '검증')]:
                path = root / f'{split}.jsonl'
                path.write_text(json.dumps({'id': split, 'source': 'synthetic', 'text': text}) + '\n')
                manifest['splits'][split] = {'path': path.name, 'sha256': file_sha256(path)}
            config = root / 'manifest.json'
            config.write_text(json.dumps(manifest))
            _, report = inspect_dataset(config)
            self.assertEqual(report['train']['utf8_bytes'], 6)
            (root / 'train.jsonl').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                inspect_dataset(config)
            manifest['splits']['final_test'] = manifest['splits']['validation']
            config.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'final test'):
                inspect_dataset(config)

    def test_manifest_allows_duplicate_ids_only_from_conflict_ledger(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = {'train': [('clash', 'body A'), ('other', 'x')], 'validation': [('clash', 'body B')]}
            manifest = {'splits': {}}
            for split, items in rows.items():
                path = root / f'{split}.jsonl'
                path.write_text(''.join(json.dumps({'id': i, 'source': 's', 'text': t}) + '\n' for i, t in items))
                manifest['splits'][split] = {'path': path.name, 'sha256': file_sha256(path)}
            config = root / 'manifest.json'
            config.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Duplicate document identity'):
                inspect_dataset(config)
            ledger = root / 'id_conflicts.jsonl'

            def allow(texts):
                ledger.write_text(''.join(json.dumps({'document_id': 'clash', 'exact_sha': hashlib.sha256(t.encode()).hexdigest()}) + '\n'
                                          for t in texts))
                manifest['fineweb_id_conflict_policy'] = {'ledger': ledger.name, 'ledger_sha256': file_sha256(ledger)}
                config.write_text(json.dumps(manifest))
            allow(['body A', 'body B'])
            self.assertEqual(inspect_dataset(config)[1]['validation']['documents'], 1)
            allow(['body A'])
            with self.assertRaisesRegex(ValueError, 'Duplicate document identity'):
                inspect_dataset(config)
            allow(['body A', 'body B'])
            ledger.write_text('')
            with self.assertRaisesRegex(ValueError, 'ledger hash'):
                inspect_dataset(config)

    def test_explicit_nikl_conversion_and_cross_split_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {'files': []}
            for split, field in [('train', 'paragraph'), ('validation', 'utterance')]:
                path = root / f'{split}.json'
                text = '동일 문서 e\u0301'
                path.write_text(json.dumps({'document': [{'id': split, field: [{'form': text}]}]}))
                plan['files'].append({'path': path.name, 'split': split, 'source': 'synthetic',
                                      'format': f'nikl_{field}'})
            plan_path = root / 'plan.json'
            plan_path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Duplicate text'):
                prepare(plan_path, root / 'duplicate')
            validation = root / 'validation.json'
            validation.write_text(json.dumps({'document': [{'id': 'val', 'utterance': [{'form': '별도 검증'}]}]}))
            report = prepare(plan_path, root / 'accepted')
            self.assertEqual(report['train']['documents'], 1)
            manifest = json.loads((root / 'accepted/manifest.json').read_text())
            self.assertNotIn('license_approved', manifest)
            self.assertIs(manifest['pii_review_approved'], False)
            self.assertIs(manifest['near_duplicate_split_review_approved'], False)
            with self.assertRaises(FileExistsError):
                prepare(plan_path, root / 'accepted')

    def test_preflight_requires_privacy_and_split_review_only(self):
        from blt_hf.entropy_train import preflight
        config = json.loads((Path(__file__).resolve().parents[1] /
                             'plan/korean_entropy_preparation.json').read_text())
        config.update(training_authorized=True, dataset_manifest='synthetic-manifest.json',
                      max_steps=20000, max_train_bytes=100, max_seconds=100,
                      max_run_bytes=100, max_gpu_memory_bytes=100)
        with tempfile.TemporaryDirectory() as directory:
            config['model_path'] = directory
            (Path(directory) / 'model.safetensors').touch()
            manifest = {'pii_review_approved': True, 'near_duplicate_split_review_approved': True}
            with patch('blt_hf.entropy_train.inspect_dataset_cached', return_value=(manifest, {})):
                self.assertIs(preflight(config)['training_ready'], True)
                for key in tuple(manifest):
                    manifest[key] = False
                    report = preflight(config)
                    self.assertIs(report['training_ready'], False)
                    self.assertEqual(report['blockers'], [f'dataset {key} required'])
                    manifest[key] = True
                config['max_steps'] = 10000
                self.assertEqual(preflight(config)['blockers'], ['max_steps must exceed warmup_steps + min_decay_steps'])
                config.update(max_steps=20000, sequence_length=512, attention_backend='flash')
                self.assertEqual(len(preflight(config)['blockers']), 3)
                config.update(sequence_length=8192, attention_backend='flex_attention')
                checkpoint = Path(directory) / 'final.pt'
                checkpoint.write_text('x')
                checkpoint.with_suffix('.sha256').write_text('a' * 64 + '\n')
                config['init_from'] = {'checkpoint': str(checkpoint), 'sha256': 'a' * 64}
                self.assertIs(preflight(config)['training_ready'], True)
                config['init_from']['sha256'] = 'b' * 64
                self.assertEqual(preflight(config)['blockers'], ['init_from sha256 differs from the checkpoint sidecar'])
                config['init_from'] = {'checkpoint': 'relative.pt', 'sha256': 'a' * 64}
                self.assertEqual(len(preflight(config)['blockers']), 1)

    def test_preflight_stays_blocked_without_data_and_budgets(self):
        from blt_hf.entropy_train import preflight
        config = json.loads((Path(__file__).resolve().parents[1] /
                             'plan/korean_entropy_preparation.json').read_text())
        report = preflight(config)
        self.assertIs(report['training_ready'], False)
        self.assertIn('dataset_manifest missing; corpus has not been ingested', report['blockers'])
        self.assertEqual(len([value for value in report['blockers'] if 'approved max_' in value]), 5)

    def test_storage_reserves_space_before_checkpoint(self):
        from blt_hf.entropy_train import check_storage
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'min_free_disk_bytes': 1, 'max_run_bytes': 4}
            check_storage(root, config, reserve=4)
            with self.assertRaisesRegex(ValueError, 'artifact budget'):
                check_storage(root, config, reserve=5)
            config['min_free_disk_bytes'] = 1 << 60
            with self.assertRaisesRegex(ValueError, 'Free disk'):
                check_storage(root, config)

    def test_warmup_stable_decay_and_plateau_rule(self):
        from blt_hf.entropy_train import decay_length, learning_rate, plateaued
        config = {'lr': 3e-4, 'warmup_steps': 5000, 'min_lr_ratio': .1, 'decay_fraction': .1,
                  'min_decay_steps': 5000, 'plateau_patience': 3, 'plateau_min_delta': .002}
        self.assertAlmostEqual(learning_rate(0, config, None), 3e-4 / 5000)
        self.assertAlmostEqual(learning_rate(4999, config, None), 3e-4)
        self.assertEqual(learning_rate(10 ** 6, config, None), 3e-4)
        decay = {'start': 100000, 'length': 10000}
        self.assertEqual(learning_rate(100000, config, decay), 3e-4)
        self.assertAlmostEqual(learning_rate(105000, config, decay), 3e-4 * .55)
        self.assertAlmostEqual(learning_rate(110000, config, decay), 3e-5)
        self.assertEqual((decay_length(20000, config), decay_length(200000, config)), (5000, 20000))
        history = [[5000, 1.0], [10000, .9], [15000, .899], [20000, .8985], [25000, .8984]]
        self.assertFalse(plateaued(history[:3], config))
        self.assertFalse(plateaued(history[:4], config))
        self.assertFalse(plateaued(history[:4] + [[25000, .85]], config))
        self.assertTrue(plateaued(history, config))
        self.assertTrue(plateaued(history + [[30000, .95]], config))

    @unittest.skipIf(numpy is None, 'NumPy runs in the existing conda environment')
    def test_packed_stream_gives_every_target_its_isolated_document_window(self):
        from collections import Counter
        from blt_hf.entropy_data import PackedStream, document_tokens
        texts = random_texts(3, 60, 60) + ['x' * 200, 'y']
        length, window = 32, 8
        expected = Counter()
        for text in texts:
            document = document_tokens(text)
            for target in range(1, len(document)):
                expected[(tuple(document[max(0, target - window):target]), int(document[target]))] += 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'train.jsonl'
            write_corpus(path, texts)
            rows, states = drain(PackedStream(path, length, window))
            actual = Counter()
            for tokens, keep in rows:
                self.assertEqual((tokens.shape, keep.shape), ((length + 1,), (length,)))
                for position in numpy.flatnonzero(keep):
                    start = visible_window(tokens, position, window)
                    actual[(tuple(tokens[start:position + 1]), int(tokens[position + 1]))] += 1
            self.assertEqual(actual, expected)
            self.assertEqual(states[-1]['documents'], len(texts))
            for index in (0, 5, len(rows) // 2, len(rows) - 2):
                resumed, _ = drain(PackedStream(path, length, window, states[index]))
                self.assertEqual(len(resumed), len(rows) - index - 1)
                for (tokens, keep), (other_tokens, other_keep) in zip(resumed, rows[index + 1:]):
                    numpy.testing.assert_array_equal(tokens, other_tokens)
                    numpy.testing.assert_array_equal(keep, other_keep)
            limited, limited_states = drain(PackedStream(path, length, window, max_documents=7))
            self.assertEqual(limited_states[-1]['documents'], 7)
            wrapped = PackedStream(path, length, window, wrap=True)
            for _ in range(len(rows) + 3):
                self.assertIsNotNone(wrapped.next_sequence())
            self.assertEqual(wrapped.state['epoch'], 1)
            wrapped.close()
            with self.assertRaises(ValueError):
                PackedStream(path, 8, 8)

    @unittest.skipIf(numpy is None, 'NumPy runs in the existing conda environment')
    def test_cached_inspection_reuses_only_unchanged_splits(self):
        from blt_hf.entropy_data import inspect_dataset_cached
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {'splits': {}}
            for split, text in [('train', '학습'), ('validation', '검증')]:
                write_corpus(root / f'{split}.jsonl', [text + split], prefix=split)
                manifest['splits'][split] = {'path': f'{split}.jsonl', 'sha256': file_sha256(root / f'{split}.jsonl')}
            config = root / 'manifest.json'
            config.write_text(json.dumps(manifest))
            _, summary = inspect_dataset_cached(config)
            self.assertTrue((root / 'manifest.inspection.json').is_file())
            with patch('blt_hf.entropy_data.inspect_dataset', side_effect=AssertionError('not cached')):
                self.assertEqual(inspect_dataset_cached(config)[1], summary)
            write_corpus(root / 'train.jsonl', ['변조'], prefix='train')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                inspect_dataset_cached(config)


class EntropyCorpusContracts(unittest.TestCase):
    def test_shipped_catalog_excludes_duplicate_copy(self):
        path = Path(__file__).resolve().parents[1] / 'plan/nikl_sources.json'
        catalog = json.loads(path.read_text())
        self.assertEqual(len(catalog['sources']), 10)
        self.assertEqual(sum(spec['expected_files'] for spec in catalog['sources']), 110611)
        self.assertNotIn('NIKL_DIALOGUE_v1.2', [spec['directory'] for spec in catalog['sources']])
        self.assertIn('NIKL_DIALOGUE_v1.2', catalog['excluded_directories'])

    def corpus_fixture(self, root):
        incoming = root / 'incoming'
        sources = []
        for source, field in [('spoken', 'utterance'), ('written', 'paragraph')]:
            folder = incoming / source
            folder.mkdir(parents=True)
            records = [{'id': f'{source}-{number}', field: [{'form': f'{source} unique {number}'}]}
                       for number in range(60)]
            if source == 'spoken':
                records += [{'id': 'shared', field: [{'form': 'Original e\u0301\ntext'}]},
                            {'id': 'alias', field: [{'form': 'Original e\u0301\ntext'}]},
                            {'id': 'normalized', field: [{'form': 'Original é text'}]}]
            else:
                records += [{'id': 'shared', field: [{'form': 'Different body'}]},
                            {'id': 'copy', field: [{'form': 'Original e\u0301\ntext'}]}]
            (folder / 'sample.JSON').write_text(json.dumps({'document': records}))
            sources.append({'directory': source, 'source': source, 'format': f'nikl_{field}'})
        catalog = root / 'sources.json'
        catalog.write_text(json.dumps({'sources': sources, 'excluded_directories': ['excluded']}))
        (incoming / 'excluded').mkdir()
        (incoming / 'excluded/invalid.json').write_text('not read')
        return incoming, catalog

    def test_audit_and_group_split_preserve_bytes_and_hold_out_test(self):
        from blt_hf.entropy_corpus import audit_corpus, split_corpus
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming, catalog = self.corpus_fixture(root)
            audit = root / 'audit'
            report = audit_corpus(incoming, catalog, audit, min_free_bytes=0)
            self.assertEqual(report['input_documents'], 125)
            self.assertEqual(report['unique_exact_documents'], 123)
            self.assertEqual(report['exact_duplicate_documents'], 2)
            self.assertEqual(report['groups'], 121)
            self.assertEqual(report['largest_group_unique_documents'], 3)
            index_hash = file_sha256(audit / 'index.sqlite')
            result = split_corpus(audit, root / 'prepared', 20, 20, 42, min_free_bytes=0)
            self.assertEqual(result['documents'], 123)
            self.assertEqual(file_sha256(audit / 'index.sqlite'), index_hash)
            assignments, all_text = {}, []
            for split in ('train', 'validation', 'test'):
                rows = [json.loads(line) for line in (root / f'prepared/{split}.jsonl').read_text().splitlines()]
                self.assertTrue(rows)
                for row in rows:
                    assignments[row['text']] = split
                    all_text.append(row['text'])
            self.assertEqual(len(all_text), len(set(all_text)))
            related = ('Original e\u0301\ntext', 'Original é text', 'Different body')
            self.assertTrue(all(text in all_text for text in related))
            self.assertEqual(len({assignments[text] for text in related}), 1)
            manifest = json.loads((root / 'prepared/manifest.json').read_text())
            self.assertEqual(set(manifest['splits']), {'train', 'validation'})
            self.assertEqual(manifest['held_out_test']['path'], 'test.jsonl')
            self.assertIs(manifest['near_duplicate_split_review_approved'], False)
            self.assertIs(manifest['pii_review_approved'], False)
            inspect_dataset(root / 'prepared/manifest.json')
            split_corpus(audit, root / 'repeated', 20, 20, 42, min_free_bytes=0)
            for split in ('train', 'validation', 'test'):
                self.assertEqual(file_sha256(root / f'prepared/{split}.jsonl'),
                                 file_sha256(root / f'repeated/{split}.jsonl'))
            with self.assertRaises(FileExistsError):
                split_corpus(audit, root / 'prepared', 20, 20, 42, min_free_bytes=0)

    def test_empty_form_parts_preserve_document_separators(self):
        from blt_hf.entropy_corpus import audit_corpus, split_corpus
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming, catalog = self.corpus_fixture(root)
            expected, original_hashes = [], {}
            for source, field in [('spoken', 'utterance'), ('written', 'paragraph')]:
                path = incoming / source / 'sample.JSON'
                payload = json.loads(path.read_text())
                parts = payload['document'][0][field]
                parts.insert(0, {'form': ''})
                parts.append({'form': ''})
                expected.append('\n'.join(part['form'] for part in parts))
                path.write_text(json.dumps(payload))
                original_hashes[path] = file_sha256(path)
            report = audit_corpus(incoming, catalog, root / 'audit', min_free_bytes=0)
            self.assertEqual(report['input_documents'], 125)
            for source in ('spoken', 'written'):
                self.assertEqual(report['sources'][source]['empty_form_parts'], 2)
            split_corpus(root / 'audit', root / 'prepared', 20, 20, 42, min_free_bytes=0)
            texts = [json.loads(line)['text'] for split in ('train', 'validation', 'test')
                     for line in (root / f'prepared/{split}.jsonl').read_text().splitlines()]
            self.assertTrue(all(text in texts for text in expected))
            self.assertEqual({path: file_sha256(path) for path in original_hashes}, original_hashes)

    def test_quarantine_empty_documents_preserves_ledger_and_groups(self):
        import sqlite3
        from blt_hf.entropy_corpus import audit_corpus, split_corpus
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming, catalog = self.corpus_fixture(root)
            path = incoming / 'spoken/sample.JSON'
            payload = json.loads(path.read_text())
            payload['document'] += [
                {'id': 'empty-four', 'utterance': [{'form': ''} for _ in range(4)]},
                {'id': 'whitespace', 'utterance': [{'form': ' \t'}, {'form': ''}]},
                {'id': 'empty-alias', 'utterance': [{'form': ''} for _ in range(4)]}]
            path.write_text(json.dumps(payload))
            original_hash = file_sha256(path)
            with self.assertRaisesRegex(ValueError, 'Empty or whitespace-only document'):
                audit_corpus(incoming, catalog, root / 'strict', min_free_bytes=0)
            report = audit_corpus(incoming, catalog, root / 'audit', min_free_bytes=0,
                                  empty_document_policy='quarantine')
            self.assertEqual(report['input_documents'], 128)
            self.assertEqual(report['usable_documents'], 125)
            self.assertEqual(report['quarantined_documents'], 3)
            self.assertEqual(report['quarantined_utf8_bytes'], 9)
            self.assertEqual(report['groups'], 121)
            self.assertEqual(report['unique_exact_documents'], 123)
            self.assertEqual(report['exact_duplicate_documents'], 2)
            self.assertEqual(report['empty_document_policy'], 'quarantine')
            source = report['sources']['spoken']
            self.assertEqual(source['documents'], 66)
            self.assertEqual(source['usable_documents'], 63)
            self.assertEqual(source['quarantined_documents'], 3)
            self.assertEqual(source['empty_form_parts'], 9)
            with sqlite3.connect(root / 'audit/index.sqlite') as connection:
                rows = connection.execute('SELECT document_id, text, file_path, position, reason '
                                          'FROM quarantine ORDER BY position').fetchall()
            self.assertEqual([row[0] for row in rows], ['empty-four', 'whitespace', 'empty-alias'])
            self.assertEqual([row[1] for row in rows], ['\n\n\n', ' \t\n', '\n\n\n'])
            self.assertTrue(all(row[2] == 'spoken/sample.JSON' and row[3] >= 63 and row[4] for row in rows))
            result = split_corpus(root / 'audit', root / 'prepared', 20, 20, 42, min_free_bytes=0)
            self.assertEqual(result['documents'], 123)
            self.assertEqual(result['quarantined_documents'], 3)
            manifest = json.loads((root / 'prepared/manifest.json').read_text())
            self.assertEqual(manifest['empty_document_policy'], 'quarantine')
            self.assertEqual(manifest['quarantined_documents'], 3)
            for split in ('train', 'validation', 'test'):
                records = [json.loads(line) for line in (root / f'prepared/{split}.jsonl').read_text().splitlines()]
                self.assertTrue(all(record['text'].strip() for record in records))
            self.assertEqual(file_sha256(path), original_hash)
            path.write_text(json.dumps({'document': [
                {'id': 'clash', 'utterance': [{'form': ''}]},
                {'id': 'clash', 'utterance': [{'form': 'different'}]}]}))
            with self.assertRaisesRegex(ValueError, 'Conflicting document identity'):
                audit_corpus(incoming, catalog, root / 'conflict-empty', min_free_bytes=0,
                             empty_document_policy='quarantine')
            for number, bad_part in enumerate(({}, {'form': None}, {'form': 1})):
                path.write_text(json.dumps({'document': [
                    {'id': 'bad-form', 'utterance': [bad_part]}]}))
                with self.assertRaisesRegex(ValueError, 'Expected form string'):
                    audit_corpus(incoming, catalog, root / f'bad-form-{number}', min_free_bytes=0,
                                 empty_document_policy='quarantine')
            with self.assertRaisesRegex(ValueError, 'Empty document policy'):
                audit_corpus(incoming, catalog, root / 'bad-policy', min_free_bytes=0,
                             empty_document_policy='skip')

    def test_corpus_fails_closed_on_conflicting_identity_and_bad_schema(self):
        from blt_hf.entropy_corpus import audit_corpus
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming, catalog = self.corpus_fixture(root)
            path = incoming / 'spoken/sample.JSON'
            payload = json.loads(path.read_text())
            payload['document'].append({'id': 'shared', 'utterance': [{'form': 'Conflicting body'}]})
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'Conflicting document identity'):
                audit_corpus(incoming, catalog, root / 'conflict', min_free_bytes=0)
            self.assertFalse((root / 'conflict/audit.json').exists())
            payload['document'].pop()
            for value in (None, 7, False, [], {}):
                payload['document'][0]['utterance'][0]['form'] = value
                path.write_text(json.dumps(payload))
                kind = type(value).__name__
                with self.assertRaisesRegex(ValueError, f'Expected form string: .*utterance\\[0\\] form_type={kind}'):
                    audit_corpus(incoming, catalog, root / f'invalid-{kind}', min_free_bytes=0)
            del payload['document'][0]['utterance'][0]['form']
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'form_type=missing'):
                audit_corpus(incoming, catalog, root / 'missing-form', min_free_bytes=0)
            for number, value in enumerate(('', ' \t')):
                payload['document'][0]['utterance'][0]['form'] = value
                path.write_text(json.dumps(payload))
                with self.assertRaisesRegex(ValueError, 'Empty or whitespace-only document: .*utterance_parts=1'):
                    audit_corpus(incoming, catalog, root / f'empty-document-{number}', min_free_bytes=0)
            payload['document'][0]['utterance'][0]['form'] = 'valid'
            path.write_text(json.dumps(payload))
            (incoming / 'spoken/escape.json').symlink_to(catalog)
            with self.assertRaisesRegex(ValueError, 'linked input'):
                audit_corpus(incoming, catalog, root / 'linked', min_free_bytes=0)

    def test_split_rejects_bad_percentages_tampering_and_source_mutation(self):
        from blt_hf.entropy_corpus import audit_corpus, split_corpus
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming, catalog = self.corpus_fixture(root)
            with self.assertRaisesRegex(ValueError, 'outside input'):
                audit_corpus(incoming, catalog, incoming / 'output', min_free_bytes=0)
            plan = json.loads(catalog.read_text())
            plan['sources'][0]['expected_files'] = 2
            catalog.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'file count mismatch'):
                audit_corpus(incoming, catalog, root / 'missing-file', min_free_bytes=0)
            del plan['sources'][0]['expected_files']
            catalog.write_text(json.dumps(plan))
            audit_corpus(incoming, catalog, root / 'audit', min_free_bytes=0)
            for validation, test in [(float('nan'), 1), (-1, 1), (50, 50), (0, 1)]:
                with self.assertRaisesRegex(ValueError, 'percent'):
                    split_corpus(root / 'audit', root / 'bad', validation, test, 42, min_free_bytes=0)
            (incoming / 'spoken/sample.JSON').write_text('raw input changed after frozen audit')
            split_corpus(root / 'audit', root / 'frozen', 20, 20, 42, min_free_bytes=0)
            with (root / 'audit/index.sqlite').open('ab') as handle:
                handle.write(b'tamper')
            with self.assertRaisesRegex(ValueError, 'Audit index hash mismatch'):
                split_corpus(root / 'audit', root / 'tampered', 20, 20, 42, min_free_bytes=0)


class FineWebCorpusContracts(unittest.TestCase):
    def test_real_parquet_conversion_and_download_resume(self):
        try:
            import pyarrow as arrow
            import pyarrow.parquet as parquet
        except ImportError:
            self.skipTest('Real Parquet test runs in the existing preparation environment')
        import hashlib
        from io import BytesIO
        from blt_hf.entropy_fineweb import catalog_from_tree, download_corpus, _json_rows
        rows = [{'id': 'first', 'text': 'Original e\u0301\ntext'}, {'id': 'empty', 'text': '\n'}]
        buffer = BytesIO()
        parquet.write_table(arrow.Table.from_pylist(rows), buffer)
        payload = buffer.getvalue()
        class Response(BytesIO):
            status = 200
            headers = {}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = catalog_from_tree([
                {'type': 'file', 'path': f'data/kor_Hang/train/{number:03d}.parquet', 'size': len(payload),
                 'lfs': {'oid': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}} for number in range(25)])
            (root / 'catalog.json').write_text(json.dumps(catalog))
            with patch('blt_hf.entropy_fineweb.urlopen', side_effect=[Response(payload), OSError('synthetic interruption')]):
                with self.assertRaises(OSError):
                    download_corpus(root / 'catalog.json', root / 'download', 10**9, 0)
            first_hash = file_sha256(root / 'download/documents/000.jsonl.gz')
            with patch('blt_hf.entropy_fineweb.urlopen', side_effect=lambda *args, **kwargs: Response(payload)) as request:
                report = download_corpus(root / 'catalog.json', root / 'download', 10**9, 0, resume=True)
                self.assertEqual(request.call_count, 24)
            self.assertEqual(report['documents'], 50)
            self.assertEqual(len(report['shards']), 25)
            self.assertEqual(file_sha256(root / 'download/documents/000.jsonl.gz'), first_hash)
            self.assertEqual([row['text'] for row in _json_rows(root / 'download/documents/000.jsonl.gz')],
                             [row['text'] for row in rows])
            self.assertTrue(report['original_parquet_preserved'])
            self.assertFalse(report['pii_review_approved'])
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                download_corpus(root / 'catalog.json', root / 'download', 10**9 + 1, 0, resume=True)

    def test_combined_corpus_preserves_nikl_roles_and_original_bytes(self):
        import gzip
        from blt_hf import entropy_fineweb as module
        from blt_hf.entropy_corpus import audit_corpus, split_corpus
        from blt_hf.entropy_fineweb import catalog_from_tree, combine_corpora, SOURCE, REVISION, REPOSITORY, OFFICIAL_TEST
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming, catalog_path = EntropyCorpusContracts().corpus_fixture(root)
            audit = root / 'audit'
            audit_corpus(incoming, catalog_path, audit, min_free_bytes=0)
            split_corpus(audit, root / 'nikl', 20, 20, 42, min_free_bytes=0)
            original_hash = file_sha256(audit / 'index.sqlite')
            original = {split: list(module._json_rows(root / f'nikl/{split}.jsonl'))
                        for split in ('train', 'validation', 'test')}
            protected = original['test'][0]
            fineweb = root / 'fineweb'
            fineweb.mkdir()
            tree = [{'type': 'file', 'path': f'data/kor_Hang/train/{number:03d}.parquet',
                     'size': 100, 'lfs': {'oid': 'a' * 64, 'size': 100}} for number in range(25)]
            catalog = catalog_from_tree(tree)
            (fineweb / 'catalog.json').write_text(json.dumps(catalog))
            shards = []
            for number, spec in enumerate(catalog['train_shards']):
                rows = [{'id': f'web-{number}', 'source': SOURCE, 'text': f'web unique {number} e\u0301\n'}]
                if number == 0:
                    rows += [{'id': 'exact-copy', 'source': SOURCE, 'text': protected['text']},
                             {'id': 'normalized-copy', 'source': SOURCE, 'text': '  ' + protected['text'] + '  '},
                             {'id': 'empty', 'source': SOURCE, 'text': '\n'}]
                path = fineweb / f'{number:03d}.jsonl.gz'
                with gzip.open(path, 'wt') as handle:
                    for row in rows:
                        handle.write(json.dumps(row) + '\n')
                shards.append({'source': spec, 'path': path.name, 'sha256': file_sha256(path),
                               'documents': len(rows), 'utf8_bytes': sum(len(row['text'].encode('utf-8')) for row in rows)})
            report = {'status': 'complete', 'revision': REVISION, 'repository': REPOSITORY, 'configuration': 'kor_Hang',
                      'reserved_official_test': [OFFICIAL_TEST], 'shards': shards,
                      'identity': {'catalog_sha256': file_sha256(fineweb / 'catalog.json'), 'code_sha256': file_sha256(module.__file__)}}
            (fineweb / 'report.json').write_text(json.dumps(report))
            result = combine_corpora(audit, root / 'nikl/manifest.json', fineweb / 'report.json', root / 'combined', 10**9, 0)
            self.assertTrue(result['nikl_original_roles_preserved'])
            self.assertEqual(result['quarantined_documents'], 1)
            self.assertEqual(result['quarantined_utf8_bytes'], 1)
            self.assertEqual(file_sha256(audit / 'index.sqlite'), original_hash)
            for split in original:
                rows = list(module._json_rows(root / f'combined/{split}.jsonl'))
                self.assertEqual([row for row in rows if row['source'] != SOURCE], sorted(original[split], key=lambda row: module._digest(row['text'])))
                if split == 'test':
                    self.assertIn('  ' + protected['text'] + '  ', [row['text'] for row in rows])
                else:
                    self.assertNotIn('  ' + protected['text'] + '  ', [row['text'] for row in rows])
            manifest = json.loads((root / 'combined/manifest.json').read_text())
            self.assertEqual(set(manifest['splits']), {'train', 'validation'})
            self.assertIn('held_out_test', manifest)
            self.assertFalse(manifest['pii_review_approved'])
            self.assertFalse(manifest['near_duplicate_split_review_approved'])
            with self.assertRaises(FileExistsError):
                combine_corpora(audit, root / 'nikl/manifest.json', fineweb / 'report.json', root / 'combined', 10**9, 0)
            with self.assertRaisesRegex(ValueError, 'bridges'):
                module._join_groups([0, 1, 2], {0: 'train', 1: 'test'}, 2, [0, 1])

    def test_download_sha_range_and_preservation(self):
        import hashlib
        from io import BytesIO
        from unittest.mock import patch
        from blt_hf.entropy_fineweb import DiskBudget, _download_shard
        payload = b'pinned synthetic bytes'
        spec = {'path': 'data/kor_Hang/train/fixture.parquet', 'size_bytes': len(payload),
                'sha256': hashlib.sha256(payload).hexdigest()}
        class Response(BytesIO):
            status = 206
            headers = {'Content-Range': f'bytes 3-{len(payload) - 1}/{len(payload)}'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            partial = root / 'fixture.parquet.partial'
            partial.write_bytes(payload[:3])
            with patch('blt_hf.entropy_fineweb.urlopen', return_value=Response(payload[3:])) as request:
                result = _download_shard(spec, root, DiskBudget([root], 1000, 0))
                self.assertEqual(request.call_args.args[0].headers['Range'], 'bytes=3-')
            self.assertEqual(result.read_bytes(), payload)
            with patch('blt_hf.entropy_fineweb.urlopen') as request:
                self.assertEqual(_download_shard(spec, root, DiskBudget([root], 1000, 0)), result)
                request.assert_not_called()
            with self.assertRaises(ValueError):
                _download_shard({**spec, 'sha256': '0' * 64}, root, DiskBudget([root], 1000, 0))
            self.assertEqual(result.read_bytes(), payload)
            with self.assertRaises(ValueError):
                _download_shard({**spec, 'path': 'data/kor_Hang/test/fixture.parquet'}, root, DiskBudget([root], 1000, 0))
            with self.assertRaises(ValueError):
                DiskBudget([root], 1, 0).check()

    def test_pinned_catalog_excludes_official_test_and_rejects_unhashed_files(self):
        from blt_hf.entropy_fineweb import catalog_from_tree
        entries = [{'type': 'file', 'path': f'data/kor_Hang/train/{number:03d}.parquet',
                    'size': 100, 'lfs': {'oid': 'a' * 64, 'size': 100}}
                   for number in range(25)]
        entries.append({'type': 'file', 'path': 'data/kor_Hang/test/000_00000.parquet',
                        'size': 200, 'lfs': {'oid': 'b' * 64, 'size': 200}})
        catalog = catalog_from_tree(entries)
        self.assertEqual(catalog['revision'], 'af9c13333eb981300149d5ca60a8e9d659b276b9')
        self.assertEqual(len(catalog['train_shards']), 25)
        self.assertTrue(all('/train/' in item['path'] for item in catalog['train_shards']))
        entries[0]['lfs']['oid'] = ''
        with self.assertRaises(ValueError):
            catalog_from_tree(entries)


@unittest.skipIf(torch is None or numpy is None, 'Torch runtime test runs in the existing itcerdo environment')
class EntropyOptimizerContracts(unittest.TestCase):
    def packed(self, directory, texts, length=32, window=8):
        from blt_hf.entropy_data import PackedStream
        from blt_hf.entropy_train import sequences
        path = Path(directory) / 'train.jsonl'
        write_corpus(path, texts)
        stream = PackedStream(path, length, window)
        batch = sequences(stream, 6)
        stream.close()
        return batch

    def test_master_weight_step_and_checkpoint_restore_are_exact(self):
        from blt_hf.entropy_train import train_step, save_state, restore_state

        class TinyPatcher(torch.nn.Module):
            def __init__(self, dropout=.2):
                super().__init__()
                self.embedding = torch.nn.Embedding(260, 8)
                self.dropout = torch.nn.Dropout(dropout)
                self.head = torch.nn.Linear(8, 260)

            def forward(self, input_ids, use_cache=False):
                return None, None, self.head(self.dropout(self.embedding(input_ids)))

        def setup(model):
            names = [name for name, _ in model.named_parameters()]
            master = [value.detach().float().clone().requires_grad_(True) for value in model.parameters()]
            return names, master, torch.optim.AdamW(master, lr=.01)

        with tempfile.TemporaryDirectory() as directory:
            tokens, keep = self.packed(directory, random_texts(5, 12, 40))
            torch.manual_seed(7)
            model = TinyPatcher().to(torch.bfloat16).train()
            names, master, optimizer = setup(model)
            train_step(model, master, optimizer, tokens, keep, 2, 1., 'cpu')
            for weight, parameter in zip(master, model.parameters()):
                self.assertEqual(weight.dtype, torch.float32)
                self.assertTrue(torch.equal(parameter, weight.to(torch.bfloat16)))
            path = Path(directory) / 'step.pt'
            progress = {'step': 1, 'stream': {'epoch': 0, 'offset': 9, 'next_target': 1, 'documents': 1}}
            save_state(path, names, master, optimizer, progress, 'synthetic')
            expected = train_step(model, master, optimizer, tokens, keep, 2, 1., 'cpu')
            weights = [value.clone() for value in master]
            restored = TinyPatcher().to(torch.bfloat16).train()
            restored_names, restored_master, restored_optimizer = setup(restored)
            self.assertEqual(restore_state(path, restored, restored_names, restored_master, restored_optimizer,
                                           'synthetic'), progress)
            self.assertEqual(train_step(restored, restored_master, restored_optimizer, tokens, keep, 2, 1., 'cpu'), expected)
            for value, weight in zip(restored_master, weights):
                self.assertTrue(torch.equal(value, weight))
            with self.assertRaisesRegex(ValueError, 'contract mismatch'):
                restore_state(path, restored, restored_names, restored_master, restored_optimizer, 'wrong')
            with self.assertRaises(FileExistsError):
                save_state(path, names, master, optimizer, progress, 'synthetic')
            with path.open('ab') as handle:
                handle.write(b'corruption')
            with self.assertRaisesRegex(ValueError, 'file hash mismatch'):
                restore_state(path, restored, restored_names, restored_master, restored_optimizer, 'synthetic')
            from blt_hf.entropy_train import initialize_from
            source = Path(directory) / 'final.pt'
            save_state(source, names, master, optimizer, progress, 'other-run')
            digest = file_sha256(source)
            fresh = TinyPatcher().to(torch.bfloat16).train()
            fresh_names, fresh_master, fresh_optimizer = setup(fresh)
            self.assertEqual(initialize_from(source, digest, fresh, fresh_names, fresh_master, fresh_optimizer)['stream'],
                             progress['stream'])
            for value, weight, parameter in zip(fresh_master, master, fresh.parameters()):
                self.assertTrue(torch.equal(value, weight))
                self.assertTrue(torch.equal(parameter, weight.to(torch.bfloat16)))
            self.assertEqual(float(fresh_optimizer.state_dict()['state'][0]['step']),
                             float(optimizer.state_dict()['state'][0]['step']))
            with self.assertRaisesRegex(ValueError, 'init_from checkpoint hash'):
                initialize_from(source, '0' * 64, fresh, fresh_names, fresh_master, fresh_optimizer)
            results = []
            for micro_batch in (1, len(tokens)):
                torch.manual_seed(11)
                model = TinyPatcher(dropout=0.).train()
                names, master, optimizer = setup(model)
                results.append((train_step(model, master, optimizer, tokens, keep, micro_batch, 1., 'cpu'),
                                [value.clone() for value in master]))
            self.assertAlmostEqual(results[0][0][0], results[1][0][0], places=3)
            for one, many in zip(results[0][1], results[1][1]):
                torch.testing.assert_close(one, many, rtol=1e-5, atol=1e-6)

    def test_real_patcher_packed_logits_match_each_isolated_segment_for_both_backends(self):
        """Stacked windows reach beyond one window, so compare with the whole in-sequence segment prefix."""
        from transformers.models.blt.configuration_blt import BltPatcherConfig
        from blt_hf.patched.modeling_blt import BltPatcher
        window = 8
        config = BltPatcherConfig(vocab_size=260, hidden_size=32, num_hidden_layers=2, num_attention_heads=4,
                                  intermediate_size=64, max_position_embeddings=256)
        config.attention_mode = 'osc'
        config.original_spec = {'entropy_sliding_window': window, 'eos_id': 2}
        config._attn_implementation = 'eager'
        torch.manual_seed(5)
        model = BltPatcher(config).float().eval()
        with tempfile.TemporaryDirectory() as directory:
            tokens, keep = self.packed(directory, random_texts(9, 20, 30), window=window)
        inputs = torch.from_numpy(tokens[:, :-1])
        with torch.no_grad():
            eager = model(input_ids=inputs, use_cache=False)[2]
            config._attn_implementation = 'sdpa'
            sdpa = model(input_ids=inputs, use_cache=False)[2]
            config._attn_implementation = 'eager'
            torch.testing.assert_close(sdpa, eager, rtol=1e-4, atol=1e-5)
            checked = 0
            for row in range(len(tokens)):
                for position in numpy.flatnonzero(keep[row]):
                    start = segment_start(tokens[row], position)
                    if position == start:
                        continue
                    alone = model(input_ids=torch.from_numpy(tokens[row, start:position + 1])[None], use_cache=False)[2]
                    torch.testing.assert_close(eager[row, position], alone[0, -1], rtol=1e-4, atol=1e-5)
                    checked += 1
        self.assertGreater(checked, 100)

    @unittest.skipUnless(torch is not None and torch.cuda.is_available(), 'Flex attention check needs CUDA')
    def test_flex_window_block_mask_matches_dense_osc_mask_and_gradients(self):
        from transformers.models.blt.configuration_blt import BltPatcherConfig
        from blt_hf.patched.modeling_blt import BltPatcher
        from blt_hf.entropy_train import compile_patcher, patcher_logits
        config = BltPatcherConfig(vocab_size=260, hidden_size=64, num_hidden_layers=2, num_attention_heads=4,
                                  intermediate_size=128, max_position_embeddings=1024)
        config.attention_mode = 'osc'
        config.original_spec = {'entropy_sliding_window': 64, 'eos_id': 2}
        torch.manual_seed(13)
        model = BltPatcher(config).float().cuda().train()
        names = [name for name, _ in model.named_parameters()]
        with tempfile.TemporaryDirectory() as directory:
            tokens, _ = self.packed(directory, random_texts(17, 40, 200), length=512, window=64)
        ids = torch.from_numpy(tokens[:, :-1]).cuda()
        results = []
        for backend in ('eager', 'flex_attention', 'compiled'):
            if backend == 'compiled':
                compile_patcher(model)
            else:
                model.config._attn_implementation = backend
            model.zero_grad(set_to_none=True)
            logits = patcher_logits(model, ids)
            logits.float().square().mean().backward()
            results.append((logits.detach(), [value.grad.clone() for value in model.parameters()]))
        for other in results[1:]:
            torch.testing.assert_close(other[0], results[0][0], rtol=1e-3, atol=1e-4)
            for flex, eager in zip(other[1], results[0][1]):
                torch.testing.assert_close(flex, eager, rtol=1e-3, atol=1e-5)
        self.assertEqual([name for name, _ in model.named_parameters()], names)


if __name__ == '__main__':
    unittest.main()