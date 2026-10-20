from collections import Counter
import importlib.util
import json
import math
import random
from pathlib import Path
import tempfile
import unittest


def oracle_counts(tokens, maximum, window, eos_id):
    counts = {}
    beginning = max(0, len(tokens) - window) if window is not None else 0
    segment_start = 0
    for position, token_id in enumerate(tokens):
        for length in range(min(maximum, position - segment_start) + 1):
            start = position - length
            if start >= beginning:
                context = b"".join(value.to_bytes(2, "little") for value in tokens[start:position])
                counts.setdefault(context, Counter())[token_id] += 1
        if token_id == eos_id:
            segment_start = position + 1
    return counts


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy is an opt-in patcher dependency")
class CountPatcherTests(unittest.TestCase):
    def test_online_counts_match_full_tuple_window_oracle(self):
        from phdq_blt_cache.count_patcher import CountConfig, CountModel

        generator = random.Random(7)
        tokens = [generator.choice([1, 2, 4, 5, 6, 259]) for _ in range(70)]
        for window in (None, 1, 3, 8):
            for maximum in (0, 2, 6):
                model = CountModel(CountConfig(max_context=maximum, window=window))
                for position, token_id in enumerate(tokens):
                    self.assertEqual(model.online._rows, oracle_counts(tokens[:position], maximum, window, 2))
                    model.observe(token_id)
                self.assertEqual(model.online._rows, oracle_counts(tokens, maximum, window, 2))

    def test_probability_matches_explicit_all_suffix_mixture(self):
        import numpy as np
        from phdq_blt_cache.count_patcher import CountConfig, CountModel, CountTable

        for decay in (1.0, 0.5, 0.01):
            config = CountConfig(max_context=4, suffix_decay=decay, online_weight=2.5, alpha=0.7, kappa=1.3)
            background = CountTable(config)
            background.add_document([1, 4, 5, 4, 6, 2, 4, 5])
            background.add_document([1, 4, 7, 2])
            model = CountModel(config, background.freeze())
            for token_id in [1, 4, 5, 4, 6, 4, 5]:
                model.observe(token_id)
            distributions = []
            for length in range(5):
                context = model._history[-2 * length:] if length else b""
                counts = np.zeros(260)
                for table, weight in ((background, 1), (model.online, 2.5)):
                    for token_id, count in table._rows.get(context, {}).items():
                        counts[token_id] += weight * count
                if length == 0:
                    expected = (counts + 0.7 / 260) / (counts.sum() + 0.7)
                else:
                    weights = np.array([decay ** (length - shorter - 1) for shorter in range(length)])
                    prior = np.average(distributions, axis=0, weights=weights)
                    expected = (counts + 1.3 * prior) / (counts.sum() + 1.3)
                distributions.append(expected)
            np.testing.assert_allclose(model.probabilities(), expected, rtol=1e-13, atol=1e-15)
            self.assertAlmostEqual(float(model.probabilities().sum()), 1)
            self.assertTrue(np.all(model.probabilities() > 0))

    def test_repeat_eos_reset_and_zero_online_weight(self):
        from phdq_blt_cache.count_patcher import CountConfig, CountModel, CountTable

        tokens = [value + 4 for value in b"abcXabc"]
        model = CountModel(CountConfig(max_context=4, online_weight=0))
        for token_id in tokens:
            model.observe(token_id)
        self.assertEqual(model.features()[1], 3)
        self.assertAlmostEqual(model.features()[0], math.log(260))
        model.observe(2)
        self.assertEqual(model._history, b"")
        self.assertGreater(model.online._totals[b""], 0)
        model.reset()
        self.assertEqual(model.position, 0)
        self.assertEqual(model.online._rows, {})
        background = CountTable(model.config)
        background.add_document(tokens)
        background.freeze()
        with self.assertRaises(ValueError):
            background.add_document(tokens)

    def test_state_roundtrip_and_read_only_prediction(self):
        import numpy as np
        from phdq_blt_cache.count_patcher import CountConfig, CountModel

        for window in (None, 1, 5):
            model = CountModel(CountConfig(max_context=3, window=window))
            for token_id in [1, 4, 5, 2, 4, 6, 5] * 4:
                model.observe(token_id)
            snapshot = json.loads(json.dumps(model.state_dict()))
            model.features()
            model.probabilities()
            self.assertEqual(model.state_dict(), snapshot)
            restored = CountModel.from_state_dict(snapshot)
            for token_id in [6, 7, 2, 4, 4]:
                np.testing.assert_array_equal(model.probabilities(), restored.probabilities())
                self.assertEqual(model.online._rows, restored.online._rows)
                model.observe(token_id)
                restored.observe(token_id)

    def test_streamed_background_roundtrip_without_overwrite(self):
        from phdq_blt_cache.count_patcher import CountConfig, CountTable

        table = CountTable(CountConfig(max_context=3))
        table.add_document([1, 4, 5, 2, 4, 5])
        table.freeze()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "counts.jsonl"
            table.save(path)
            restored = CountTable.load(path)
            self.assertEqual(table.to_dict(), restored.to_dict())
            with self.assertRaises(FileExistsError):
                table.save(path)

    def test_label_chunks_preserve_bytes_and_cached_contract(self):
        import numpy as np
        from scripts.prepare_patcher_labels import chunk_inputs, verify_cached

        text = "abc\n" * 700 + "\uac00\ub098\ub2e4"
        chunks = list(chunk_inputs(text))
        recovered = b"".join(bytes(int(value) - 4 for value in tokens[1:]) for _, tokens in chunks)
        self.assertEqual(recovered, text.encode("utf-8"))
        self.assertEqual([offset for offset, _ in chunks], [0, 2047])
        self.assertTrue(all(tokens[0] == 1 and 2 <= len(tokens) <= 2048 for _, tokens in chunks))
        with self.assertRaises(ValueError):
            list(chunk_inputs(""))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.npz"
            tokens = chunks[0][1]
            labels = np.zeros(len(tokens) + 1, dtype=bool)
            labels[:2] = True
            np.savez(path, input_ids=tokens, entropy=np.zeros(len(tokens) + 1), labels=labels, contract_sha256="fixed")
            verify_cached(path, tokens, "fixed")
            with self.assertRaises(ValueError):
                verify_cached(path, tokens, "changed")

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "SciPy is an opt-in fitting dependency")
    def test_block_background_matches_full_counts_probabilities_and_boundaries(self):
        from dataclasses import asdict
        import numpy as np
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountModel, CountTable, rollout, teacher_features
        from scripts.fit_count_patcher import block_manifest_hash, file_hash, load_background, query_contexts

        config = CountConfig(max_context=3)
        documents = [[1, 4, 5, 4, 6, 2, 4, 5], [1, 8, 9, 10], [1, 4, 5, 4, 259, 2]]
        chunks = [{"input_ids": [1, 4, 5, 2, 4, 259, 7]}, {"input_ids": [1, 5, 4, 5]}]
        full = CountTable(config)
        blocks = []
        with tempfile.TemporaryDirectory() as directory:
            for index, tokens in enumerate(documents):
                full.add_document(tokens)
                block = CountTable(config)
                block.add_document(tokens)
                path = Path(directory) / f"block-{index}.jsonl"
                block.freeze().save(path)
                blocks.append({"table_path": str(path), "table_sha256": file_hash(path)})
            full.freeze()
            report = {"storage": "document_blocks_v1", "blocks": blocks, "table_sha256": block_manifest_hash(blocks), "count_config": asdict(config)}
            self.assertEqual(load_background(report).to_dict(), full.to_dict())
            required = query_contexts(chunks, config)
            projected = load_background(report, required)
            self.assertEqual(projected._rows, {context: row for context, row in full._rows.items() if context in required})
            self.assertLess(len(projected._rows), len(full._rows))
            for chunk in chunks:
                first, second = CountModel(config, full), CountModel(config, projected)
                np.testing.assert_array_equal(first.probabilities(), second.probabilities())
                for token in chunk["input_ids"]:
                    first.observe(token)
                    second.observe(token)
                    np.testing.assert_array_equal(first.probabilities(), second.probabilities())
                labels = [True, True] + [False] * (len(chunk["input_ids"]) - 1)
                for original, reduced in zip(teacher_features(chunk["input_ids"], labels, config=config, mean_patch_length=3, background=full), teacher_features(chunk["input_ids"], labels, config=config, mean_patch_length=3, background=projected)):
                    np.testing.assert_array_equal(original, reduced)
                for threshold in (0, 0.25, 0.5, 1):
                    rule = BoundaryRule((-2, 0.1, 0.1, 1, 0.1), 3, threshold)
                    self.assertEqual(rollout(chunk["input_ids"], config=config, rule=rule, background=full), rollout(chunk["input_ids"], config=config, rule=rule, background=projected))
            blocks[0]["table_sha256"] = "corrupted"
            with self.assertRaises(ValueError):
                load_background(report, required)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "SciPy is an opt-in fitting dependency")
    def test_fixed_feature_gradient_and_constrained_optimizer(self):
        import numpy as np
        from scipy.optimize import check_grad
        from phdq_blt_cache.count_patcher import boundary_objective, fit_boundary

        generator = np.random.default_rng(42)
        features = generator.normal(size=(150, 5))
        features[:, 0] = 1
        features[:, 1:4] = np.abs(features[:, 1:4])
        features[:, 4] = -np.abs(features[:, 4])
        labels = (generator.random(150) < 0.3).astype(float)
        coefficients = np.array([-1, 0.1, 0.2, 0.3, 0.4])
        error = check_grad(lambda values: boundary_objective(values, features, labels, 0.01)[0],
                           lambda values: boundary_objective(values, features, labels, 0.01)[1], coefficients)
        self.assertLess(error, 1e-6)
        fitted = fit_boundary(features, labels, rho=0.01)
        self.assertTrue(all(value >= 0 for value in fitted["coefficients"][1:]))
        self.assertLessEqual(fitted["loss"], boundary_objective(np.zeros(5), features, labels, 0.01)[0])
        for constant in (0, 1):
            fitted = fit_boundary(features, np.full(150, constant), rho=0.01)
            self.assertTrue(np.isfinite(fitted["coefficients"]).all())
        with self.assertRaises(ValueError):
            fit_boundary(features, labels, rho=0)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "SciPy is an opt-in fitting dependency")
    def test_boundary_metrics_and_precision_ties(self):
        import numpy as np
        from scripts.fit_count_patcher import average_precision, boundary_metrics, confusion

        counts = confusion([True, True, False], [True, False, True])
        np.testing.assert_array_equal(counts, [1, 1, 1])
        self.assertEqual(boundary_metrics(counts)["f1"], 0.5)
        self.assertEqual(average_precision(np.array([0.5, 0.5]), np.array([True, False])), 0.5)
        self.assertEqual(average_precision(np.array([0.8, 0.2]), np.array([True, False])), 1.0)

    def test_reject_padding_invalid_ids_and_hyperparameters(self):
        from phdq_blt_cache.count_patcher import CountConfig, CountModel

        model = CountModel(CountConfig())
        for value in (3, 260, -1, True, 1.5):
            with self.assertRaises(ValueError):
                model.observe(value)
            self.assertEqual(model.position, 0)
        for options in ({"max_context": -1}, {"window": 0}, {"alpha": 0}, {"online_weight": -1}, {"suffix_decay": 2}):
            with self.assertRaises(ValueError):
                CountConfig(**options)

    def test_sequential_prediction_is_causal_and_rejects_replayed_prefix(self):
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, SequentialPatcher, rollout

        config = CountConfig(max_context=3, window=7)
        rule = BoundaryRule((-2, 0.5, 0.2, 0.3, 0.1), 3)
        common = [1, 4, 5, 4, 5, 6]
        first = rollout(common + [7, 8, 9], config=config, rule=rule)
        second = rollout(common + [100, 101, 102], config=config, rule=rule)
        self.assertEqual(first[:len(common) + 1], second[:len(common) + 1])
        patcher = SequentialPatcher(config, rule)
        prefix = patcher.append(common[:3], start_position=0)
        before = patcher.state_dict()
        self.assertEqual(patcher.predict_boundary(), patcher.predict_boundary())
        self.assertEqual(before, patcher.state_dict())
        with self.assertRaises(ValueError):
            patcher.append(common, start_position=0)
        restored = SequentialPatcher.from_state_dict(json.loads(json.dumps(before)))
        continued = restored.append(common[3:] + [7, 8, 9], start_position=3)
        self.assertEqual(prefix + continued + [restored.predict_boundary()], first)

    def test_teacher_distance_and_candidate_distance_are_separate(self):
        import numpy as np
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, rollout, teacher_features

        tokens = [1, 4, 5, 6, 7, 8]
        labels = [1, 1, 0, 1, 0, 0, 1]
        config = CountConfig()
        features, mask = teacher_features(tokens, labels, config=config, mean_patch_length=3)
        np.testing.assert_array_equal(features[:, 1], [0, 1, 1, 2, 1, 2, 3])
        np.testing.assert_array_equal(mask, [False, False, True, True, True, True, True])
        low = rollout(tokens, config=config, rule=BoundaryRule((0, 1, 0, 0, 0), 3, 0.5))
        high = rollout(tokens, config=config, rule=BoundaryRule((0, 1, 0, 0, 0), 3, 0.95))
        self.assertNotEqual([item.distance for item in low], [item.distance for item in high])
        self.assertNotEqual([item.score for item in low], [item.score for item in high])
        self.assertEqual(low, rollout(tokens, config=config, rule=BoundaryRule((0, 1, 0, 0, 0), 3, 0.5)))

    def test_strict_threshold_virtual_slot_and_invalid_batch(self):
        from phdq_blt_cache import patch_starts
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, SequentialPatcher, decision_patch_lengths, rollout

        config = CountConfig()
        for threshold, expected in ((0, [0, 1, 2, 3]), (0.5, [0, 1]), (1, [0, 1])):
            rule = BoundaryRule((0, 0, 0, 0, 0), 3, threshold)
            decisions = rollout([1, 4, 2], config=config, rule=rule)
            lengths = decision_patch_lengths(decisions)
            self.assertEqual(sum(lengths), 4)
            self.assertEqual(patch_starts(lengths, input_length=3), expected)
        patcher = SequentialPatcher(config, rule)
        with self.assertRaises(ValueError):
            patcher.append([1, 4, 3], start_position=0)
        self.assertEqual(patcher.model.position, 0)
        for tokens in ([], [1]):
            with self.assertRaises(ValueError):
                rollout(tokens, config=config, rule=rule)
        with self.assertRaises(ValueError):
            BoundaryRule((0, -1, 0, 0, 0), 3)


if __name__ == "__main__":
    unittest.main()