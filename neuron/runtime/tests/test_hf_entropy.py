import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

from blt_hf.entropy_data import byte_examples, file_sha256, inspect_dataset, prepare

try:
    import torch
except ImportError:
    torch = None


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
                      max_steps=4, max_train_bytes=100, max_seconds=100,
                      max_run_bytes=100, max_gpu_memory_bytes=100)
        with tempfile.TemporaryDirectory() as directory:
            config['model_path'] = directory
            (Path(directory) / 'model.safetensors').touch()
            manifest = {'pii_review_approved': True, 'near_duplicate_split_review_approved': True}
            with patch('blt_hf.entropy_train.inspect_dataset', return_value=(manifest, {})):
                self.assertIs(preflight(config)['training_ready'], True)
                for key in tuple(manifest):
                    manifest[key] = False
                    report = preflight(config)
                    self.assertIs(report['training_ready'], False)
                    self.assertEqual(report['blockers'], [f'dataset {key} required'])
                    manifest[key] = True

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


@unittest.skipIf(torch is None, 'Torch runtime test runs in the existing itcerdo environment')
class EntropyOptimizerContracts(unittest.TestCase):
    def test_loss_and_next_update_match_after_checkpoint_restore(self):
        from blt_hf.entropy_train import update, save_state, restore_state, loss_sums

        class TinyPatcher(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.embedding = torch.nn.Embedding(260, 8)
                self.dropout = torch.nn.Dropout(.2)
                self.head = torch.nn.Linear(8, 260)

            def forward(self, input_ids, use_cache=False):
                return None, None, self.head(self.dropout(self.embedding(input_ids)))

        torch.manual_seed(7)
        model = TinyPatcher().train()
        optimizer = torch.optim.AdamW(model.parameters(), lr=.01)
        batch = list(byte_examples('합성 자료', 8))
        update(model, optimizer, batch, 'cpu', 1.)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'step.pt'
            progress = {'step': 1, 'cursor': len(batch), 'epoch': 0, 'exposed_bytes': 13}
            save_state(path, model, optimizer, progress, 'synthetic')
            expected = update(model, optimizer, batch, 'cpu', 1.)
            weights = {name: value.clone() for name, value in model.state_dict().items()}
            restored = TinyPatcher().train()
            restored_optimizer = torch.optim.AdamW(restored.parameters(), lr=.01)
            self.assertEqual(restore_state(path, restored, restored_optimizer, 'synthetic'), progress)
            actual = update(restored, restored_optimizer, batch, 'cpu', 1.)
            self.assertEqual(expected, actual)
            for name, value in restored.state_dict().items():
                self.assertTrue(torch.equal(value, weights[name]), name)
            with self.assertRaisesRegex(ValueError, 'contract mismatch'):
                restore_state(path, restored, restored_optimizer, 'wrong')
            with self.assertRaises(FileExistsError):
                save_state(path, model, optimizer, progress, 'synthetic')
            with path.open('ab') as handle:
                handle.write(b'corruption')
            with self.assertRaisesRegex(ValueError, 'file hash mismatch'):
                restore_state(path, restored, restored_optimizer, 'synthetic')
        model.eval()
        item = batch[0]
        with torch.no_grad():
            total, _, count = loss_sums(model, item, 'cpu')
            logits = model(torch.tensor([item['inputs']]))[2][0]
            direct = torch.nn.functional.cross_entropy(logits, torch.tensor(item['targets']), reduction='sum')
            torch.testing.assert_close(total, direct, rtol=1e-6, atol=1e-6)
            self.assertEqual(count, len(item['targets']))


if __name__ == '__main__':
    unittest.main()