import ctypes
import gzip
import json
from pathlib import Path
import random
import shutil
import tempfile
import unicodedata
import unittest

from blt_hf.entropy_data import file_sha256


def native_available():
    return shutil.which('c++') is not None


@unittest.skipUnless(native_available(), 'C++ compiler unavailable')
class NativeCombineContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from blt_hf.entropy_combine import build_native, load_native
        cls.directory = tempfile.TemporaryDirectory()
        cls.library_path, cls.build = build_native(Path(cls.directory.name) / 'native')
        cls.library = load_native(cls.library_path)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def hashed(self, text):
        raw = text.encode('utf-8')
        exact, normalized = ctypes.create_string_buffer(32), ctypes.create_string_buffer(32)
        state = ctypes.c_int()
        self.library.bltc_hash_text(raw, len(raw), exact, normalized, ctypes.byref(state))
        return exact.raw, normalized.raw, state.value

    def assert_python_grouping(self, text):
        import hashlib
        exact, normalized, state = self.hashed(text)
        self.assertEqual(exact, hashlib.sha256(text.encode('utf-8')).digest())
        expected = ' '.join(unicodedata.normalize('NFC', text).split())
        if state == 0:
            self.assertEqual(normalized, hashlib.sha256(expected.encode('utf-8')).digest(), repr(text))
        elif state == 1:
            self.assertEqual(expected, '', repr(text))
        return state

    def test_every_code_point_matches_python_or_falls_back(self):
        states = [0, 0, 0]
        for code in range(0x110000):
            if 0xD800 <= code <= 0xDFFF:
                continue
            states[self.assert_python_grouping(chr(code))] += 1
            if code % 7 == 0:
                self.assert_python_grouping('\uac00' + chr(code) + ' x')
        self.assertGreater(states[0], 1000000)
        self.assertEqual(self.build['unicode_version'], unicodedata.unidata_version)

    def test_random_mixed_strings_match_python(self):
        generator = random.Random(20261105)
        pool = (['한', '국', '어', 'a', 'Z', '1', 'é', 'e', '\u0301', '\u0308', '\u1100', '\u1161', '\u11a8', '\uac00',
                 '\uac01', ' ', '\t', '\n', '\u3000', '\u2028', '\x85', '\xa0', '\x1c', '\u200b', '😀', '\U0001d15e',
                 '\u00c5', '\u212b', '\u0344', '\uf900', '\x00'])
        fallback = 0
        for _ in range(30000):
            text = ''.join(generator.choice(pool) for _ in range(generator.randint(0, 12)))
            fallback += self.assert_python_grouping(text) == 2
        self.assertLess(fallback, 30000)

    def test_json_roundtrip_matches_python_and_fails_closed(self):
        generator = random.Random(7)
        pool = ['a', '"', '\\', '/', '\n', '\r', '\t', '\b', '\f', '\x00', '\x01', '\x1f', '\x7f', '\u2028', '\u2029',
                '한', 'é', '😀', '\U0010ffff', '\ufeff', ' ', '<', '&']
        output = ctypes.create_string_buffer(1 << 16)
        written = ctypes.c_uint64()
        error = ctypes.create_string_buffer(256)
        for number in range(5000):
            row = {'id': f'id{number}', 'source': 'src', 'text': ''.join(generator.choice(pool) for _ in range(generator.randint(0, 20)))}
            keys = list(row)
            generator.shuffle(keys)
            line = json.dumps({key: row[key] for key in keys}, ensure_ascii=bool(number % 2)).encode('utf-8')
            self.assertEqual(self.library.bltc_roundtrip(line, len(line), output, len(output), ctypes.byref(written), error, len(error)), 0, error.value)
            self.assertEqual(output.raw[:written.value], (json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8'))
        invalid = [b'{"id": "a", "source": "s", "text": "\\ud800"}', b'{"id": "a", "source": "s", "text": "\xff"}',
                   b'{"id": "a", "source": "s", "text": "\xed\xa0\x80"}', b'{"id": "a", "source": "s"}',
                   b'{"id": "", "source": "s", "text": ""}', b'{"id": "a", "source": "s", "text": "x", "extra": "y"}',
                   b'{"id": "a", "source": "s", "text": "\x01"}', b'{"id": "a", "source": "s", "text": 1}', b'',
                   b'[]', b'{"id": "a", "source": "s", "text": "x"} x', b'{"id": "a", "source": "s", "text": "\\x"}']
        for line in invalid:
            self.assertEqual(self.library.bltc_roundtrip(line, len(line), output, len(output), ctypes.byref(written), error, len(error)), 1, line)

    def corpus(self, root, extra=()):
        from blt_hf import entropy_fineweb as module
        from blt_hf.entropy_corpus import audit_corpus, split_corpus
        from blt_hf.entropy_fineweb import catalog_from_tree, SOURCE, REVISION, REPOSITORY, OFFICIAL_TEST
        from tests.test_hf_entropy import EntropyCorpusContracts
        incoming, catalog_path = EntropyCorpusContracts().corpus_fixture(root)
        audit = root / 'audit'
        audit_corpus(incoming, catalog_path, audit, min_free_bytes=0)
        split_corpus(audit, root / 'nikl', 20, 20, 42, min_free_bytes=0)
        nikl = {split: list(module._json_rows(root / f'nikl/{split}.jsonl')) for split in ('train', 'validation', 'test')}
        fineweb = root / 'fineweb'
        fineweb.mkdir()
        tree = [{'type': 'file', 'path': f'data/kor_Hang/train/{number:03d}.parquet',
                 'size': 100, 'lfs': {'oid': 'a' * 64, 'size': 100}} for number in range(25)]
        catalog = catalog_from_tree(tree)
        (fineweb / 'catalog.json').write_text(json.dumps(catalog))
        generator = random.Random(42)
        alphabet = ['한', '국', '어', '문', '장', 'a', 'b', ' ', '\n', 'é', 'e\u0301', '\u1112\u1161\u11ab', '"', '\\', '😀']
        protected, train = nikl['test'][0]['text'], nikl['train'][0]['text']
        shards = []
        for number, spec in enumerate(catalog['train_shards']):
            rows = [{'id': f'web-{number}', 'source': SOURCE, 'text': f'web unique {number} e\u0301\n'},
                    {'id': f'hangul-{number}', 'source': SOURCE, 'text': f'한국어 문장 {number}'}]
            rows += [{'id': f'random-{number}-{index}', 'source': SOURCE,
                      'text': generator.choice('한a') + ''.join(generator.choice(alphabet) for _ in range(generator.randint(0, 30)))}
                     for index in range(80)]
            if number == 0:
                rows += [{'id': 'exact-copy', 'source': SOURCE, 'text': protected},
                         {'id': 'normalized-copy', 'source': SOURCE, 'text': '  ' + protected + '  '},
                         {'id': 'empty', 'source': SOURCE, 'text': '\n'}, {'id': 'blank', 'source': SOURCE, 'text': ''},
                         {'id': 'ideographic', 'source': SOURCE, 'text': '\u3000\u2028 '},
                         {'id': 'decomposed', 'source': SOURCE, 'text': '\u1112\u1161\u11ab\u1100\u1173\u11af'},
                         {'id': 'controls', 'source': SOURCE, 'text': 'q"\\\t\x01\x7f\u2028😀'},
                         {'id': 'repeat-id', 'source': SOURCE, 'text': 'same body via id'}]
            if number == 7:
                rows += [{'id': 'train-copy', 'source': SOURCE, 'text': train},
                         {'id': 'precomposed', 'source': SOURCE, 'text': '한글'},
                         {'id': 'repeat-id', 'source': SOURCE, 'text': 'same body via id'},
                         {'id': 'web-dup', 'source': SOURCE, 'text': 'web unique 0 e\u0301\n'}]
            if number == 12:
                rows += [{'id': 'train-spaced', 'source': SOURCE, 'text': ' ' + train.replace(' ', '\u3000 ') + '\t'},
                         {'id': 'quarantine-tail', 'source': SOURCE, 'text': ' \u3000'}]
            rows += [row for shard, row in extra if shard == number]
            path = fineweb / f'{number:03d}.jsonl.gz'
            with gzip.open(path, 'wb') as handle:
                for position, row in enumerate(rows):
                    if position % 5 == 3:
                        row = {'text': row['text'], 'id': row['id'], 'source': row['source']}
                    handle.write((json.dumps(row, ensure_ascii=bool((number + position) % 2)) + '\n').encode('utf-8'))
            shards.append({'source': spec, 'path': path.name, 'sha256': file_sha256(path), 'documents': len(rows),
                           'utf8_bytes': sum(len(row['text'].encode('utf-8')) for row in rows)})
        report = {'status': 'complete', 'revision': REVISION, 'repository': REPOSITORY, 'configuration': 'kor_Hang',
                  'reserved_official_test': [OFFICIAL_TEST], 'shards': shards,
                  'identity': {'catalog_sha256': file_sha256(fineweb / 'catalog.json'), 'code_sha256': file_sha256(Path(module.__file__))}}
        (fineweb / 'report.json').write_text(json.dumps(report))
        return audit, root / 'nikl/manifest.json', fineweb / 'report.json'

    def test_native_combine_is_byte_identical_to_reference(self):
        from blt_hf.entropy_combine import combine_native
        from blt_hf.entropy_fineweb import combine_corpora
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit, manifest, report = self.corpus(root)
            audit_hash = file_sha256(audit / 'index.sqlite')
            reference = combine_corpora(audit, manifest, report, root / 'reference', 10**9, 0)
            native = combine_native(audit, manifest, report, root / 'native', 10**9, 3, 0)
            for name in ('train.jsonl', 'validation.jsonl', 'test.jsonl', 'manifest.json'):
                self.assertEqual((root / 'native' / name).read_bytes(), (root / 'reference' / name).read_bytes(), name)
            for key in ('splits', 'documents', 'fineweb_input_documents', 'fineweb_input_utf8_bytes', 'quarantined_documents',
                        'quarantined_utf8_bytes', 'exact_duplicate_documents', 'policy', 'manifest_sha256'):
                self.assertEqual(native[key], reference[key], key)
            self.assertEqual(json.dumps(native['splits']), json.dumps(reference['splits']))
            self.assertEqual(native['quarantined_documents'] - reference['quarantined_documents'], 0)
            ledger = [json.loads(line) for line in (root / 'native/quarantine.jsonl').read_bytes().split(b'\n') if line]
            self.assertEqual([row['document_id'] for row in ledger], ['empty', 'blank', 'ideographic', 'quarantine-tail'])
            self.assertFalse((root / 'native/work').exists())
            self.assertEqual(file_sha256(audit / 'index.sqlite'), audit_hash)
            self.assertEqual(json.loads((root / 'native/progress.json').read_text())['status'], 'complete')
            with self.assertRaises(FileExistsError):
                combine_native(audit, manifest, report, root / 'native', 10**9, 2, 0)

    def test_native_combine_fails_closed_like_reference(self):
        from blt_hf.entropy_combine import combine_native
        from blt_hf.entropy_fineweb import combine_corpora, SOURCE
        cases = {'Conflicting FineWeb document identity': [(3, {'id': 'clash', 'source': SOURCE, 'text': 'body A'}),
                                                           (5, {'id': 'clash', 'source': SOURCE, 'text': 'body B'})]}
        for message, extra in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                audit, manifest, report = self.corpus(root, extra)
                with self.assertRaisesRegex(ValueError, message):
                    combine_corpora(audit, manifest, report, root / 'reference', 10**9, 0)
                with self.assertRaisesRegex(ValueError, message):
                    combine_native(audit, manifest, report, root / 'native', 10**9, 2, 0)
                import subprocess, sys
                diagnosis = json.loads(subprocess.run(
                    [sys.executable, '-m', 'blt_hf.entropy_combine_diagnose', '--fineweb-report', str(report),
                     '--output', str(root / 'native')], check=True, capture_output=True, text=True,
                    cwd=Path(__file__).resolve().parents[1]).stdout)
                self.assertEqual((diagnosis['conflicting_ids'], diagnosis['documents']), (1, 2))
                self.assertEqual(diagnosis['examples'][0]['id'], 'clash')
                self.assertEqual([row['prefix'] for row in diagnosis['examples'][0]['documents']], ['body A', 'body B'])
                self.assertFalse(diagnosis['examples'][0]['normalized_equal'])
        from blt_hf import entropy_fineweb as module
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.corpus(root)
            nikl = {split: list(module._json_rows(root / f'nikl/{split}.jsonl')) for split in ('train', 'test')}
        bridge = [(9, {'id': nikl['train'][0]['id'], 'source': SOURCE, 'text': ' ' + nikl['test'][0]['text']})]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit, manifest, report = self.corpus(root, bridge)
            with self.assertRaisesRegex(ValueError, 'bridges'):
                combine_corpora(audit, manifest, report, root / 'reference', 10**9, 0)
            with self.assertRaisesRegex(ValueError, 'bridges'):
                combine_native(audit, manifest, report, root / 'native', 10**9, 2, 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit, manifest, report = self.corpus(root)
            with self.assertRaisesRegex(ValueError, 'Positive worker'):
                combine_native(audit, manifest, report, root / 'native', 10**9, 0, 0)
            payload = json.loads(report.read_text())
            shard = report.parent / payload['shards'][4]['path']
            with gzip.open(shard, 'ab') as handle:
                handle.write(b'{"id": "late", "source": "FineWeb2:kor_Hang", "text": "late"}\n')
            with self.assertRaisesRegex(ValueError, 'hash/path changed'):
                combine_native(audit, manifest, report, root / 'tampered', 10**9, 2, 0)

    def test_linked_id_conflicts_keep_both_bodies_in_one_split(self):
        from blt_hf.entropy_combine import combine_native
        from blt_hf.entropy_fineweb import combine_corpora, SOURCE, _assigned
        from blt_hf.entropy_corpus import _digest
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit, manifest, report = self.corpus(root)
            policy = json.loads(manifest.read_text())['split_policy']
            # Train/validation are what inspect_dataset checks, so force the linked pair into train.
            suffix = next(k for k in range(1000) if _assigned(min(_digest(f'body A{k}'), _digest(f'body B{k}')), policy) == 'train')
            bodies = {f'body A{suffix}', f'body B{suffix}'}
            combine_corpora(audit, manifest, report, root / 'reference', 10**9, 0)
            plain = combine_native(audit, manifest, report, root / 'plain', 10**9, 2, 0, link_id_conflicts=True)
            self.assertEqual(json.loads((root / 'plain/manifest.json').read_text())['fineweb_id_conflict_policy']['documents'], 0)
            self.assertEqual(plain['splits'], json.loads((root / 'reference/report.json').read_text())['splits'])
        clash = [(3, {'id': 'clash', 'source': SOURCE, 'text': f'body A{suffix}'}),
                 (5, {'id': 'clash', 'source': SOURCE, 'text': f'body B{suffix}'})]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit, manifest, report = self.corpus(root, clash)
            result = combine_native(audit, manifest, report, root / 'native', 10**9, 2, 0, link_id_conflicts=True)
            reference = Path(directory) / 'reference'
            (root / 'base').mkdir()
            audit2, manifest2, report2 = self.corpus(root / 'base')
            combine_corpora(audit2, manifest2, report2, reference, 10**9, 0)
            ledger = [json.loads(line) for line in (root / 'native/id_conflicts.jsonl').read_text().split('\n') if line]
            self.assertEqual([(row['document_id'], row['file_path'], row['position']) for row in ledger],
                             [('clash', 'fineweb2/003.jsonl.gz', 82), ('clash', 'fineweb2/005.jsonl.gz', 82)])
            self.assertEqual(len({row['split'] for row in ledger}), 1)
            split = ledger[0]['split']
            self.assertEqual(split, 'train')
            for name in ('train', 'validation', 'test'):
                lines = set((root / f'native/{name}.jsonl').read_text().split('\n')) - {''}
                found = {json.loads(line)['text'] for line in lines if json.loads(line)['id'] == 'clash'}
                self.assertEqual(found, bodies if name == split else set(), name)
                rest = {line for line in lines if json.loads(line)['id'] != 'clash'}
                self.assertEqual(rest, set((reference / f'{name}.jsonl').read_text().split('\n')) - {''}, name)
            policy = json.loads((root / 'native/manifest.json').read_text())['fineweb_id_conflict_policy']
            self.assertEqual((policy['ids'], policy['documents']), (1, 2))
            self.assertEqual(policy['ledger_sha256'], file_sha256(root / 'native/id_conflicts.jsonl'))
            self.assertEqual(result['fineweb_id_conflicts'], policy)


if __name__ == '__main__':
    unittest.main()
