import gzip
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest

from blt_hf.count_sample import LENGTH_FILTER, line_value, sample


def write_split(path, prefix, count, generator):
    lines = []
    for index in range(count):
        size = generator.choice([40, 120, 300, 700, 2000, 30000]) if index % 97 else 90000
        text = ('가나다라 ' * (size // 13 + 1))[:size // 3] + f' {prefix}{index}'
        lines.append(json.dumps({'id': f'{prefix}-{index}', 'source': f'src{index % 3}', 'text': text},
                                ensure_ascii=False))
    path.write_text(''.join(line + '\n' for line in lines), encoding='utf-8')
    return lines


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(lines, seed, ranges, targets, skip=0):
    """Independent selection: first in-range eligible lines per role until each byte target."""
    picked = {name: [] for name in ranges}
    totals = {name: 0 for name in ranges}
    for number, line in enumerate(lines, 1):
        if all(totals[name] >= targets[name] for name in ranges):
            break
        if number <= skip:
            continue
        value = line_value(seed, line.encode('utf-8'))
        name = next((key for key, (low, high) in ranges.items() if low <= value < high), None)
        if name is None or totals[name] >= targets[name]:
            continue
        size = len(json.loads(line)['text'].encode('utf-8'))
        if LENGTH_FILTER[0] <= size <= LENGTH_FILTER[1]:
            picked[name].append(number)
            totals[name] += size
    return picked


class CountSampleContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        data = self.root / 'data'
        data.mkdir()
        generator = random.Random(5)
        self.lines = {split: write_split(data / f'{split}.jsonl', split[:2], count, generator)
                      for split, count in (('train', 3000), ('validation', 600), ('test', 600))}
        self.manifest = data / 'manifest.json'
        self.manifest.write_text(json.dumps({
            'splits': {split: {'path': f'{split}.jsonl', 'sha256': sha256(data / f'{split}.jsonl')}
                       for split in ('train', 'validation')},
            'held_out_test': {'path': 'test.jsonl', 'sha256': sha256(data / 'test.jsonl')}}))
        self.options = dict(seed=7, background_bytes=400_000, train_bytes=30_000, validation_bytes=20_000,
                            test_bytes=20_000, validation_skip=50, background_rate=0.5, label_rate=0.1,
                            holdout_rate=0.5, progress_every=10 ** 9)

    def tearDown(self):
        self.directory.cleanup()

    def rows(self, path):
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as stream:
            return [json.loads(line) for line in stream]

    def test_roles_match_an_independent_selection_and_hashes(self):
        output = self.root / 'sample'
        report = sample(self.manifest, output, **self.options)
        self.assertEqual(report['status'], 'prepared', report.get('error'))
        self.assertEqual(json.loads((output / 'manifest.json').read_text())['splits'], report['splits'])
        revision = sha256(self.manifest)
        selected = {}
        for name in ('background', 'train', 'validation', 'test'):
            path = output / (f'{name}.jsonl.gz' if name == 'background' else f'{name}.jsonl')
            raw = gzip.decompress(path.read_bytes()) if name == 'background' else path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), report['splits'][name]['file_sha256'])
            rows = self.rows(path)
            source = 'train' if name == 'background' else name
            for row in rows:
                original = json.loads(self.lines[source][row['source_line'] - 1])
                data = row['text'].encode('utf-8')
                self.assertEqual((row['document_id'], row['source'], row['text']),
                                 (original['id'], original['source'], original['text']))
                self.assertEqual(row['text_sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual((row['revision'], row['source_split']), (revision, source))
                self.assertTrue(LENGTH_FILTER[0] <= len(data) <= LENGTH_FILTER[1])
            sizes = [len(row['text'].encode('utf-8')) for row in rows]
            self.assertEqual(sum(sizes), report['splits'][name]['utf8_bytes'])
            self.assertGreaterEqual(sum(sizes), report['targets'][name])
            self.assertLess(sum(sizes) - sizes[-1], report['targets'][name])
            selected[name] = [row['source_line'] for row in rows]
        self.assertEqual(report['splits']['background']['compressed']['sha256'],
                         sha256(output / 'background.jsonl.gz'))
        expected = reference(self.lines['train'], 7, {'train': (0, 0.1), 'background': (0.1, 0.6)},
                             {'train': 30_000, 'background': 400_000})
        self.assertEqual({name: selected[name] for name in ('train', 'background')}, expected)
        self.assertEqual(selected['validation'], reference(self.lines['validation'], 7, {'validation': (0, 0.5)},
                                                           {'validation': 20_000}, skip=50)['validation'])
        self.assertEqual(selected['test'], reference(self.lines['test'], 7, {'test': (0, 0.5)},
                                                     {'test': 20_000})['test'])
        self.assertTrue(all(line > 50 for line in selected['validation']))
        texts = [row['text_sha256'] for name in ('train', 'validation', 'test') for row in self.rows(
            output / f'{name}.jsonl')] + [row['text_sha256'] for row in self.rows(output / 'background.jsonl.gz')]
        self.assertEqual(len(texts), len(set(texts)))

    def test_same_seed_reproduces_files_and_other_seed_differs(self):
        first = sample(self.manifest, self.root / 'a', **self.options)
        second = sample(self.manifest, self.root / 'b', **self.options)
        other = sample(self.manifest, self.root / 'c', **{**self.options, 'seed': 8})
        self.assertEqual(first['splits'], second['splits'])
        for name in ('train.jsonl', 'validation.jsonl', 'test.jsonl', 'background.jsonl.gz'):
            self.assertEqual(sha256(self.root / 'a' / name), sha256(self.root / 'b' / name))
        self.assertNotEqual(first['splits']['train']['file_sha256'], other['splits']['train']['file_sha256'])

    def test_failures_are_reported_and_outputs_preserved(self):
        report = sample(self.manifest, self.root / 'short', **{**self.options, 'background_bytes': 10 ** 9})
        self.assertEqual(report['status'], 'failed')
        self.assertIn('background', report['error'])
        self.assertEqual(json.loads((self.root / 'short' / 'manifest.json').read_text())['status'], 'failed')
        manifest = json.loads(self.manifest.read_text())
        manifest['held_out_test']['sha256'] = '0' * 64
        tampered = self.manifest.with_name('tampered.json')
        tampered.write_text(json.dumps(manifest))
        report = sample(tampered, self.root / 'tampered', **self.options)
        self.assertEqual((report['status'], report['error']), ('failed', 'Source split hash mismatch: test'))
        with self.assertRaises(FileExistsError):
            sample(self.manifest, self.root / 'short', **self.options)
        with self.assertRaises(ValueError):
            sample(self.manifest, self.root / 'rates', **{**self.options, 'label_rate': 0.6})
        del manifest['held_out_test']
        tampered.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'held_out_test'):
            sample(tampered, self.root / 'no-test', **self.options)
        self.assertFalse((self.root / 'no-test').exists())


if __name__ == '__main__':
    unittest.main()
