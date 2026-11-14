import json
from pathlib import Path
import tempfile
import unittest

from blt_hf.patcher_compare import chunk_ids, parse_patchers, sample_documents

try:
    import torch
    import numpy
except ImportError:
    torch = numpy = None


def write_lines(path, texts):
    path.write_text(''.join(json.dumps({'id': str(index), 'source': 's', 'text': text}, ensure_ascii=False) + '\n'
                            for index, text in enumerate(texts)), encoding='utf-8')


class PatcherCompareContracts(unittest.TestCase):
    def test_chunks_carry_bos_and_shifted_bytes(self):
        data = '한글a'.encode()
        chunks = chunk_ids('한글a', 4)
        self.assertEqual([len(chunk) - 1 for chunk in chunks], [4, 3])
        self.assertTrue(all(chunk[0] == 1 for chunk in chunks))
        self.assertEqual([value - 4 for chunk in chunks for value in chunk[1:]], list(data))

    def test_sample_takes_whole_lines_starting_after_the_region(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'train.jsonl'
            texts = [f'문서{index}' * (index % 7 + 1) for index in range(400)]
            write_lines(path, texts)
            raw = path.read_bytes()
            starts = [0] + [index + 1 for index, value in enumerate(raw) if value == 10][:-1]
            region = starts[150] + 3
            sample = sample_documents(path, region, 2000, seed=3)
            self.assertEqual(sample, sample_documents(path, region, 2000, seed=3))
            self.assertGreaterEqual(sum(len(text.encode()) for _, text in sample), 2000)
            for offset, text in sample:
                self.assertIn(offset, starts)
                self.assertGreater(offset, region)
                self.assertEqual(texts[starts.index(offset)], text)
            self.assertEqual(len({offset for offset, _ in sample}), len(sample))
            with self.assertRaises(ValueError):
                sample_documents(path, len(raw), 10, seed=3)
            with self.assertRaises(ValueError):
                sample_documents(path, starts[-3], 10 ** 9, seed=3, max_attempts=200)

    def test_patcher_names_are_unique_and_not_public(self):
        self.assertEqual(parse_patchers(['run1=/a.pt', 'run2=/b.pt']), {'run1': Path('/a.pt'), 'run2': Path('/b.pt')})
        for values in (['public=/a.pt'], ['run1=/a.pt', 'run1=/b.pt'], ['run1'], ['Run=/a.pt']):
            with self.assertRaises(ValueError):
                parse_patchers(values)


@unittest.skipUnless(torch is not None and numpy is not None, 'Torch and NumPy required')
class PatcherCompareTensors(unittest.TestCase):
    def entropies(self, seed, lengths):
        generator = torch.Generator().manual_seed(seed)
        return [(torch.rand((1, length), generator=generator) * 4).to(torch.bfloat16) for length in lengths]

    def test_selected_threshold_reproduces_patch_counts_and_is_nearest(self):
        from blt_hf.patcher_compare import entropy_histogram, select_threshold, threshold_curve
        from blt_hf.patching import entropy_patch_lengths
        rows = self.entropies(1, [2, 5, 300, 2048, 777])
        counts = sum(entropy_histogram(row) for row in rows).numpy()
        scored, chunks = sum(row.shape[1] - 1 for row in rows), len(rows)
        values, means = threshold_curve(counts, chunks, scored)
        self.assertTrue(numpy.all(numpy.diff(means) > 0))
        for target in (1.5, 3, 4.5, 8, 40):
            threshold, mean = select_threshold(counts, chunks, scored, target)
            patches = sum(entropy_patch_lengths(row, threshold).shape[1] for row in rows)
            self.assertAlmostEqual(mean, scored / patches)
            brute = min(values, key=lambda value: abs(scored / sum(
                entropy_patch_lengths(row, float(value)).shape[1] for row in rows) - target))
            self.assertEqual(threshold, float(brute))
            self.assertEqual(float(torch.tensor(threshold).to(torch.bfloat16)), threshold)

    def test_histogram_rejects_nonfinite_and_wrong_dtype(self):
        from blt_hf.patcher_compare import entropy_histogram
        with self.assertRaises(ValueError):
            entropy_histogram(torch.tensor([[1., float('nan')]], dtype=torch.bfloat16))
        with self.assertRaises(ValueError):
            entropy_histogram(torch.ones((1, 3)))

    def test_boundaries_quantiles_and_bootstrap(self):
        from blt_hf.patcher_compare import boundaries, length_quantiles, paired_bootstrap
        lengths = torch.tensor([[1, 1, 3, 2, 1]])
        self.assertEqual(boundaries(lengths).tolist(), [2, 5, 7])
        self.assertEqual(length_quantiles(numpy.bincount([1, 1, 1, 1, 2, 2, 3, 9])),
                         {'p50': 1, 'p90': 9, 'p99': 9, 'max': 9})
        nll = numpy.array([[10., 10., 12.], [20., 20., 19.], [5., 5., 7.]])
        utf8 = [10, 20, 5]
        same, shifted = paired_bootstrap(nll, utf8, [(1, 0), (2, 0)], replicates=200, seed=4)
        self.assertEqual(same, {'delta_bpb': 0., 'ci95': [0., 0.]})
        self.assertAlmostEqual(shifted['delta_bpb'], 3 / (35 * numpy.log(2)))
        self.assertLessEqual(shifted['ci95'][0], shifted['ci95'][1])

    def test_checkpoint_patcher_loads_master_weights_from_a_real_training_checkpoint(self):
        from transformers.models.blt.configuration_blt import BltPatcherConfig
        from blt_hf.entropy_train import save_state
        from blt_hf.patched.modeling_blt import BltPatcher
        from blt_hf.patcher_compare import checkpoint_patcher
        config = BltPatcherConfig(vocab_size=260, hidden_size=32, num_hidden_layers=2, num_attention_heads=4,
                                  intermediate_size=64, max_position_embeddings=64)
        config.attention_mode = 'osc'
        config.original_spec = {'entropy_sliding_window': 8, 'eos_id': 2}
        config._attn_implementation = 'eager'
        torch.manual_seed(7)
        base = BltPatcher(config).to(torch.bfloat16).eval()
        names = [name for name, _ in base.named_parameters()]
        master = [parameter.detach().float().clone().requires_grad_(True) for parameter in base.parameters()]
        optimizer = torch.optim.AdamW(master, lr=1e-2, betas=(.9, .95), weight_decay=.1)
        sum(weight.square().sum() for weight in master).backward()
        optimizer.step()
        progress = {'step': 3, 'stream': {'epoch': 0, 'offset': 123, 'next_target': 1, 'documents': 2},
                    'exposed_bytes': 9, 'evaluations': [[1, 2.]], 'decay': None}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'final-00000003.pt'
            save_state(path, names, master, optimizer, progress, 'signature')
            patcher, digest, loaded = checkpoint_patcher(base, path)
            self.assertEqual(loaded, progress)
            self.assertEqual(path.with_suffix('.sha256').read_text().strip(), digest)
            for (name, parameter), weight in zip(patcher.named_parameters(), master):
                self.assertEqual(parameter.dtype, torch.bfloat16)
                self.assertTrue(torch.equal(parameter, weight.detach().to(torch.bfloat16)), name)
            self.assertFalse(torch.equal(next(patcher.parameters()), next(base.parameters())))
            path.with_suffix('.sha256').write_text('0' * 64 + '\n')
            with self.assertRaises(ValueError):
                checkpoint_patcher(base, path)


if __name__ == '__main__':
    unittest.main()
