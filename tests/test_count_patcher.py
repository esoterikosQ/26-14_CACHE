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
    def test_analysis_ablation_refits_and_cached_rollout_uses_own_boundaries(self):
        import numpy as np
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountTable, rollout, teacher_features
        from scripts.analyze_count_patcher import cached_rollout, count_features, evaluate_cached, fit_ablation, fixed_training_features, metrics_with_f05, paired_intervals, stratum_diagnostics

        config = CountConfig()
        background = CountTable(config).freeze()
        tokens = [1] + [value + 4 for value in b"abc abc abc abc"]
        rule = BoundaryRule((-3., .2, .1, 1., .2), 4.5, .375)
        expected = rollout(tokens, config=config, rule=rule, background=background)
        entropy = np.asarray([item.entropy for item in expected])
        repeated = np.asarray([item.repeated_length for item in expected])
        boundaries, scores, distances = cached_rollout(entropy, repeated, rule)
        np.testing.assert_array_equal(boundaries, [item.boundary for item in expected])
        np.testing.assert_array_equal(scores, [item.score for item in expected])
        np.testing.assert_array_equal(distances, [item.distance for item in expected])
        other_rule = BoundaryRule(rule.coefficients, rule.mean_patch_length, 1.)
        alternative = rollout(tokens, config=config, rule=other_rule, background=background)
        actual = cached_rollout(entropy, repeated, other_rule)
        np.testing.assert_array_equal(actual[0], [item.boundary for item in alternative])
        np.testing.assert_array_equal(actual[1], [item.score for item in alternative])
        np.testing.assert_array_equal(actual[2], [item.distance for item in alternative])
        self.assertFalse(np.array_equal(actual[0], boundaries))
        features, mask = teacher_features(tokens, boundaries, config=config, mean_patch_length=4.5, background=background)
        original = features.copy()
        chunk = {"input_ids": np.asarray(tokens), "labels": boundaries, "entropy": entropy,
                 "document_id": "fixture", "byte_offset": 0, "byte_length": len(tokens) - 1}
        cached_entropy, cached_repeated = count_features(chunk["input_ids"], config, background)
        np.testing.assert_array_equal(cached_entropy, entropy)
        np.testing.assert_array_equal(cached_repeated, repeated)
        np.testing.assert_array_equal(fixed_training_features(chunk, entropy, repeated, 4.5), features[mask])
        measured, records = evaluate_cached([chunk], [(entropy, repeated)], rule, details=True)
        self.assertEqual(measured["f1"], 1.)
        self.assertEqual(measured["tp"], int(boundaries[2:].sum()))
        diagnostics = stratum_diagnostics([chunk], records, rule.threshold, 1.3359375)
        for axis in ("document_position", "document_length", "repeated_suffix", "candidate_distance", "teacher_margin", "candidate_margin"):
            self.assertEqual(sum(value["positions"] for key, value in diagnostics["strata"].items() if key.startswith(axis + ":")), len(tokens) - 1)
        self.assertEqual(diagnostics["candidate_patch_count"], int(boundaries.sum()))
        self.assertEqual(diagnostics["entropy_mae"], 0.)
        fitted = fit_ablation(features[mask], boundaries[mask], [1, 2, 4], rho=.001)
        self.assertEqual([fitted["coefficients"][column] for column in (1, 2, 4)], [0., 0., 0.])
        np.testing.assert_array_equal(original, features)
        self.assertAlmostEqual(metrics_with_f05([2, 1, 3])["f0_5"], 2.5 / 4.25)
        counts = np.asarray([[2, 1, 3], [4, 2, 1]])
        self.assertEqual(paired_intervals(counts, counts, replicates=20), {"f1": [0., 0.], "f0_5": [0., 0.]})
        with self.assertRaises(ValueError):
            fit_ablation(features[mask], boundaries[mask], [0], rho=.001)

    def test_teacher_prefix_diagnostic_separates_virtual_and_past_labels(self):
        import numpy as np
        from scripts.diagnose_teacher_prefix_labels import compare_teacher_prefixes

        token_ids = np.asarray([1, 100, 101, 102, 103], dtype=np.uint16)
        full = np.asarray([0., 0., .5, 2., .25, 2.], dtype=np.float32)

        def evaluate(current):
            entropy = full[:len(current) + 1].copy()
            if len(current) == 2:
                entropy[2] = 1.5
            if len(current) == 3:
                entropy[2], entropy[3] = 1.5, .5
            labels = entropy > 1.
            labels[:2] = True
            return entropy, labels

        result, arrays = compare_teacher_prefixes(token_ids, evaluate)
        self.assertEqual(result["endpoint_positions"], 4)
        self.assertEqual(result["endpoint_mismatches"], 2)
        self.assertEqual(result["past_positions"], 6)
        self.assertEqual(result["past_mismatches"], 1)
        self.assertEqual(result["all_visible_positions"], 10)
        self.assertEqual(result["all_visible_mismatches"], 3)
        self.assertEqual(result["endpoint_mismatch_rate"], .5)
        self.assertEqual(result["all_visible_mismatch_rate"], .3)
        self.assertTrue(result["same_input_replay_exact"])
        for row_index, length in enumerate(range(2, 6)):
            actual = np.unpackbits(arrays["prefix_labels_packed_little"][row_index], bitorder="little")
            np.testing.assert_array_equal(actual[:length + 1], evaluate(token_ids[:length])[1])
        with self.assertRaises(ValueError):
            compare_teacher_prefixes(token_ids[:1], evaluate)

    def test_lookup_returns_counts_and_total_without_inserting_missing_context(self):
        from phdq_blt_cache.count_patcher import CountConfig, CountTable

        table = CountTable(CountConfig())
        table.add_document([1, 4, 5, 4, 2])
        table.freeze()
        before = table.to_dict()
        for context, expected in table._rows.items():
            row, total = table.lookup(context)
            self.assertEqual(row, expected)
            self.assertEqual(total, sum(expected.values()))
        self.assertEqual(table.lookup(b"missing"), ({}, 0))
        self.assertEqual(table.to_dict(), before)

    @unittest.skipUnless(importlib.util.find_spec("lmdb"), "LMDB is an opt-in background dependency")
    def test_lmdb_counts_match_unrestricted_memory_background(self):
        from dataclasses import asdict
        import gzip
        import hashlib
        import numpy as np
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountModel, CountTable, rollout
        from phdq_blt_cache.lmdb_counts import LMDBCountTable, build_lmdb_background

        config = CountConfig(max_context=3)
        full = CountTable(config)
        documents = [[1, 4, 5, 4, 6, 2, 4], [1, 8, 9, 8, 259], [1, 4, 5, 8, 2]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocks = []
            for index, tokens in enumerate(documents):
                full.add_document(tokens)
                table = CountTable(config)
                table.add_document(tokens)
                path = root / f"block-{index}.jsonl.gz"
                with gzip.open(path, "wt") as stream:
                    stream.write(json.dumps({"version": 1, "config": asdict(config)}) + "\n")
                    for context, row in table._rows.items():
                        stream.write(json.dumps([context.hex(), list(row.items())]) + "\n")
                blocks.append({"table_path": str(path), "table_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "compression": "gzip"})
            full.freeze()
            report = root / "background.json"
            payload = {"storage": "document_blocks_v1", "blocks": blocks, "count_config": asdict(config),
                       "table_sha256": hashlib.sha256(json.dumps(blocks, sort_keys=True).encode()).hexdigest()}
            report.write_text(json.dumps(payload))
            output = root / "background.lmdb"
            result = build_lmdb_background(report, output, map_size_bytes=4 * 1024 ** 2, batch_rows=2)
            self.assertTrue(result["complete_source"])
            self.assertEqual(result["contexts"], len(full._rows))
            with LMDBCountTable(output, cache_size=2) as disk:
                for context in full._rows:
                    self.assertEqual(disk.lookup(context), full.lookup(context))
                self.assertEqual(disk.lookup(b"absent"), ({}, 0))
                with self.assertRaises(TypeError):
                    disk.lookup(b"")[0][4] = 999
                with self.assertRaises(TypeError):
                    CountModel(config, disk).state_dict()
                for window in (None, 1, 5):
                    current = CountConfig(max_context=3, window=window)
                    memory_model, disk_model = CountModel(current, full), CountModel(current, disk)
                    for token_id in [1, 8, 9, 4, 259, 2, 4, 5, 7, 4, 5]:
                        np.testing.assert_array_equal(memory_model.probabilities(), disk_model.probabilities())
                        self.assertEqual(memory_model.features(), disk_model.features())
                        memory_model.observe(token_id)
                        disk_model.observe(token_id)
                    rule = BoundaryRule((-2, 0.1, 0.1, 1, 0.1), 3, 0.375)
                    self.assertEqual(rollout(documents[1], config=current, rule=rule, background=full),
                                     rollout(documents[1], config=current, rule=rule, background=disk))
                self.assertLessEqual(disk.cache_info().currsize, 2)
            with self.assertRaises(ValueError):
                disk.lookup(b"")
            with self.assertRaises(FileExistsError):
                build_lmdb_background(report, output, map_size_bytes=4 * 1024 ** 2)
            payload["table_sha256"] = hashlib.sha256(json.dumps(blocks, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            report.write_text(json.dumps(payload))
            partial = root / "partial.lmdb"
            partial_result = build_lmdb_background(report, partial, map_size_bytes=4 * 1024 ** 2, block_limit=1)
            self.assertEqual(partial_result["source_manifest_encoding"], "json_compact")
            with self.assertRaises(ValueError):
                LMDBCountTable(partial)
            with LMDBCountTable(partial, allow_partial=True) as disk:
                self.assertFalse(disk.metadata["complete_source"])
            parent_report = root / "parent-background.json"
            parent_payload = {**payload, "blocks": blocks[:1],
                              "table_sha256": hashlib.sha256(json.dumps(blocks[:1], sort_keys=True).encode()).hexdigest()}
            parent_report.write_text(json.dumps(parent_payload))
            parent = root / "parent.lmdb"
            parent_result = build_lmdb_background(parent_report, parent, map_size_bytes=4 * 1024 ** 2)
            parent_hash = hashlib.sha256((parent / "data.mdb").read_bytes()).hexdigest()
            seeded = root / "seeded.lmdb"
            seeded_result = build_lmdb_background(report, seeded, map_size_bytes=8 * 1024 ** 2,
                                                 parent_background=parent, parent_report=parent_report, batch_rows=2)
            self.assertEqual(seeded_result["parent_reuse"]["completed_blocks"], 1)
            self.assertEqual(seeded_result["input_rows"], result["input_rows"])
            self.assertEqual(seeded_result["contexts"], result["contexts"])
            self.assertEqual(seeded_result["completed_blocks"], 3)
            self.assertTrue(seeded_result["complete_source"])
            self.assertEqual(parent_hash, hashlib.sha256((parent / "data.mdb").read_bytes()).hexdigest())
            with LMDBCountTable(seeded) as disk:
                for context in full._rows:
                    self.assertEqual(disk.lookup(context), full.lookup(context))
                rule = BoundaryRule((-2, 0.1, 0.1, 1, 0.1), 3, 0.375)
                self.assertEqual(rollout(documents[1], config=config, rule=rule, background=full),
                                 rollout(documents[1], config=config, rule=rule, background=disk))
            self.assertEqual(parent_result["status"], "complete")
            interrupted_seed = root / "interrupted-seed.lmdb"

            def stop_seed(details):
                if details.get("stage") == "started":
                    raise KeyboardInterrupt

            with self.assertRaises(KeyboardInterrupt):
                build_lmdb_background(report, interrupted_seed, map_size_bytes=8 * 1024 ** 2,
                    parent_background=parent, parent_report=parent_report, progress=stop_seed)
            resumed_seed = build_lmdb_background(report, interrupted_seed, map_size_bytes=8 * 1024 ** 2, resume=True)
            self.assertEqual(resumed_seed["input_rows"], result["input_rows"])
            with LMDBCountTable(interrupted_seed) as disk:
                for context in full._rows:
                    self.assertEqual(disk.lookup(context), full.lookup(context))
            with self.assertRaises(RuntimeError):
                build_lmdb_background(report, root / "parent-space-guard.lmdb", map_size_bytes=8 * 1024 ** 2,
                    parent_background=parent, parent_report=parent_report, max_output_bytes=1)
            with self.assertRaises(ValueError):
                build_lmdb_background(report, root / "bad-parent.lmdb", map_size_bytes=8 * 1024 ** 2,
                                      parent_background=parent, parent_report=report)
            with self.assertRaises(ValueError):
                build_lmdb_background(report, root / "partial-parent.lmdb", map_size_bytes=8 * 1024 ** 2,
                                      parent_background=partial, parent_report=parent_report)
            with self.assertRaises(ValueError):
                build_lmdb_background(report, root / "missing-parent-report.lmdb", map_size_bytes=8 * 1024 ** 2,
                                      parent_background=parent)
            with self.assertRaises(ValueError):
                build_lmdb_background(report, root / "seed-resume.lmdb", map_size_bytes=8 * 1024 ** 2,
                                      parent_background=parent, parent_report=parent_report, resume=True)
            reordered = root / "reordered.json"
            reordered_blocks = list(reversed(blocks))
            reordered.write_text(json.dumps({**payload, "blocks": reordered_blocks,
                "table_sha256": hashlib.sha256(json.dumps(reordered_blocks, sort_keys=True).encode()).hexdigest()}))
            with self.assertRaises(ValueError):
                build_lmdb_background(reordered, root / "wrong-prefix.lmdb", map_size_bytes=8 * 1024 ** 2,
                                      parent_background=parent, parent_report=parent_report)
            guarded = root / "guarded.lmdb"
            with self.assertRaises(RuntimeError):
                build_lmdb_background(report, guarded, map_size_bytes=4 * 1024 ** 2, max_output_bytes=1, batch_rows=2)
            with self.assertRaises(ValueError):
                LMDBCountTable(guarded)
            payload["blocks"][0]["table_sha256"] = "changed"
            payload["table_sha256"] = hashlib.sha256(json.dumps(payload["blocks"], sort_keys=True).encode()).hexdigest()
            report.write_text(json.dumps(payload))
            failed = root / "failed.lmdb"
            with self.assertRaises(ValueError):
                build_lmdb_background(report, failed, map_size_bytes=4 * 1024 ** 2)
            with self.assertRaises(ValueError):
                LMDBCountTable(failed)

    @unittest.skipUnless(importlib.util.find_spec("lmdb"), "LMDB is an opt-in background dependency")
    def test_lmdb_resume_preserves_committed_rows_and_legacy_checkpoints(self):
        from dataclasses import asdict
        import hashlib
        import lmdb
        import os
        import subprocess
        import sys
        from unittest.mock import patch
        import numpy as np
        from phdq_blt_cache import lmdb_counts
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountModel, CountTable, rollout

        config = CountConfig(max_context=3)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocks = []
            expected = CountTable(config)
            for index, tokens in enumerate(([1, 4, 5, 4, 6, 2, 4, 5], [1, 8, 9, 4, 8, 2], [1, 4, 5, 8, 259])):
                expected.add_document(tokens)
                table = CountTable(config)
                table.add_document(tokens)
                path = root / f"block-{index}.jsonl"
                table.freeze().save(path)
                blocks.append({"table_path": str(path), "table_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "contexts": len(table._rows), "utf8_bytes": len(tokens)})
            expected.freeze()
            payload = {"storage": "document_blocks_v1", "blocks": blocks, "count_config": asdict(config),
                       "table_sha256": hashlib.sha256(json.dumps(blocks, sort_keys=True).encode()).hexdigest()}
            report = root / "background.json"
            report.write_text(json.dumps(payload))
            uninterrupted = root / "uninterrupted.lmdb"
            lmdb_counts.build_lmdb_background(report, uninterrupted, map_size_bytes=4 * 1024 ** 2)
            for mode in ("mid_commit", "uncommitted", "block_end", "legacy"):
                output = root / f"{mode}.lmdb"

                def stop(value):
                    if value.get("stage") == "started":
                        return
                    if mode == "block_end" and value["completed_blocks"] == 0:
                        return
                    raise KeyboardInterrupt

                original_decode = lmdb_counts._decode
                calls = 0

                def fail_decode(value):
                    nonlocal calls
                    calls += 1
                    if calls == 5:
                        raise RuntimeError("injected failure with uncommitted rows")
                    return original_decode(value)

                with self.assertRaises((KeyboardInterrupt, RuntimeError)):
                    if mode == "uncommitted":
                        with patch.object(lmdb_counts, "_decode", side_effect=fail_decode):
                            lmdb_counts.build_lmdb_background(report, output, map_size_bytes=2 * 1024 ** 2, batch_rows=3)
                    else:
                        lmdb_counts.build_lmdb_background(report, output, map_size_bytes=2 * 1024 ** 2, batch_rows=3, progress=stop)
                with lmdb.open(str(output)) as environment:
                    with environment.begin(write=mode == "legacy") as transaction:
                        saved = json.loads(transaction.get(lmdb_counts._METADATA))
                        self.assertEqual(saved["status"], "building")
                        if mode == "uncommitted":
                            self.assertEqual(saved["input_rows"], 3)
                        if mode == "legacy":
                            saved.pop("completed_input_rows")
                            saved.pop("current_block_rows")
                            transaction.put(lmdb_counts._METADATA, json.dumps(saved).encode())
                result = lmdb_counts.build_lmdb_background(report, output, map_size_bytes=8 * 1024 ** 2, batch_rows=2, resume=True)
                self.assertEqual(result["resume_history"][-1]["input_rows"], saved["input_rows"])
                self.assertEqual(result["input_rows"], sum(block["contexts"] for block in blocks))
                self.assertEqual(result["map_size_bytes"], 8 * 1024 ** 2)
                with lmdb_counts.LMDBCountTable(output) as disk:
                    self.assertEqual(disk.metadata["contexts"], len(expected._rows))
                    for context in expected._rows:
                        self.assertEqual(disk.lookup(context), expected.lookup(context))
                    memory_model, disk_model = CountModel(config, expected), CountModel(config, disk)
                    for token_id in [1, 4, 8, 5, 2, 259, 7]:
                        np.testing.assert_array_equal(memory_model.probabilities(), disk_model.probabilities())
                        memory_model.observe(token_id)
                        disk_model.observe(token_id)
                    rule = BoundaryRule((-2, 0.1, 0.1, 1, 0.1), 3, 0.375)
                    self.assertEqual(rollout([1, 4, 8, 5, 259], config=config, rule=rule, background=expected),
                                     rollout([1, 4, 8, 5, 259], config=config, rule=rule, background=disk))
                with self.assertRaises(ValueError):
                    lmdb_counts.build_lmdb_background(report, output, map_size_bytes=8 * 1024 ** 2, resume=True)

            interrupted = root / "cli-interrupted.lmdb"
            code = """import signal
import scripts.build_lmdb_background as cli
original = cli.build_lmdb_background
def wrapped(*args, **kwargs):
    callback = kwargs['progress']
    def pause(value):
        callback(value)
        if value.get('input_rows', 0) > 0:
            signal.pause()
    kwargs['progress'] = pause
    kwargs['batch_rows'] = 3
    return original(*args, **kwargs)
cli.build_lmdb_background = wrapped
cli.main()
"""
            arguments = ["--report", str(report), "--output", str(interrupted),
                         "--min-free-gib", "0", "--max-output-gib", "1"]
            process = subprocess.Popen([sys.executable, "-c", code, *arguments, "--map-size-gib", "1",
                                        "--memory-limit-gib", "2"], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, env={**os.environ, "OPENBLAS_NUM_THREADS": "8"})
            try:
                while True:
                    line = process.stdout.readline()
                    self.assertTrue(line, "CLI exited before a committed checkpoint")
                    if json.loads(line).get("input_rows", 0) >= 3:
                        break
                process.terminate()
                stdout, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 130, stderr)
                self.assertIn('"status": "interrupted"', stdout)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=30)
            with lmdb.open(str(interrupted)) as environment:
                with environment.begin() as transaction:
                    saved = json.loads(transaction.get(lmdb_counts._METADATA))
                    self.assertEqual(saved["input_rows"], 3)
            bad_report = root / "different-report.json"
            bad_report.write_text(report.read_text() + "\n")
            with self.assertRaises(ValueError):
                lmdb_counts.build_lmdb_background(bad_report, interrupted, map_size_bytes=8 * 1024 ** 2, resume=True)
            bad = dict(saved, input_rows=saved["input_rows"] + 1)
            with self.assertRaises(ValueError):
                lmdb_counts._resume_position(bad, saved, blocks)
            with self.assertRaises(ValueError):
                lmdb_counts.build_lmdb_background(report, interrupted, map_size_bytes=8 * 1024 ** 2,
                                                  block_limit=1, resume=True)
            with self.assertRaises(RuntimeError):
                lmdb_counts.build_lmdb_background(report, root / "rss-guard.lmdb",
                                                  map_size_bytes=4 * 1024 ** 2, max_rss_bytes=1)
            resumed = subprocess.run([sys.executable, "-m", "scripts.build_lmdb_background", *arguments,
                                      "--resume", "--map-size-gib", "128", "--memory-limit-gib", "160"],
                                     capture_output=True, text=True, timeout=30,
                                     env={**os.environ, "OPENBLAS_NUM_THREADS": "8"})
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            cli_result = json.loads(interrupted.with_suffix(".report.json").read_text())
            self.assertEqual(cli_result["map_size_bytes"], 128 * 1024 ** 3)
            self.assertEqual(cli_result["address_space_limit_bytes"], 160 * 1024 ** 3)
            with lmdb_counts.LMDBCountTable(interrupted) as disk:
                for context in expected._rows:
                    self.assertEqual(disk.lookup(context), expected.lookup(context))

            abrupt = root / "legacy-sigterm.lmdb"
            abrupt_code = """import json
import signal
import sys
from phdq_blt_cache import lmdb_counts
original = lmdb_counts._decode
calls = 0
def pause_uncommitted(value):
    global calls
    calls += 1
    if calls == 5:
        print(json.dumps({'stage': 'uncommitted'}), flush=True)
        signal.pause()
    return original(value)
lmdb_counts._decode = pause_uncommitted
lmdb_counts.build_lmdb_background(sys.argv[1], sys.argv[2], map_size_bytes=2*1024**2, batch_rows=3)
"""
            process = subprocess.Popen([sys.executable, "-c", abrupt_code, str(report), str(abrupt)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(json.loads(process.stdout.readline())["stage"], "uncommitted")
                process.terminate()
                _, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, -15, stderr)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=30)
            with lmdb.open(str(abrupt)) as environment:
                with environment.begin(write=True) as transaction:
                    legacy = json.loads(transaction.get(lmdb_counts._METADATA))
                    self.assertEqual(legacy["input_rows"], 3)
                    legacy.pop("completed_input_rows")
                    legacy.pop("current_block_rows")
                    transaction.put(lmdb_counts._METADATA, json.dumps(legacy).encode())
            lmdb_counts.build_lmdb_background(report, abrupt, map_size_bytes=8 * 1024 ** 2, resume=True)
            with lmdb_counts.LMDBCountTable(abrupt) as disk:
                for context in expected._rows:
                    self.assertEqual(disk.lookup(context), expected.lookup(context))

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