import importlib.util
import random
import unittest


@unittest.skipUnless(
    all(importlib.util.find_spec(name) for name in ("datasketch", "pyarrow", "huggingface_hub")),
    "experiment data dependencies are installed on the research host",
)
class DataPreparationTests(unittest.TestCase):
    def test_duplicates_are_removed_without_changing_text(self):
        from scripts.prepare_english_data import deduplicate

        text = " ".join(f"word{index}" for index in range(200))
        documents = [
            {"text": text, "url": "https://example.org/original"},
            {"text": text.upper().replace(" ", "\n"), "url": "https://example.org/copy"},
            {"text": text + " extra ending", "url": "https://example.org/near"},
            {"text": " ".join(f"other{index}" for index in range(200)), "url": "https://example.org/other"},
        ]
        retained, rejected = deduplicate(documents, 42)
        self.assertEqual([document["text"] for document in retained], [text, documents[-1]["text"]])
        self.assertEqual(rejected, {"exact_text_or_url": 1, "near_duplicate": 1})

    def test_byte_budget_and_splits_are_disjoint_and_repeatable(self):
        from scripts.prepare_english_data import background_and_label_pools, length_band, split_labels, take_bytes

        documents = [{"text": "x" * size, "document_id": f"{size}-{index}"} for size in (300, 2000, 9000) for index in range(30)]
        background_pool, label_pool = background_and_label_pools(documents, 2 / 3, random.Random(42))
        for pool in (background_pool, label_pool):
            self.assertEqual({length_band(document) for document in pool}, {"short", "medium", "long"})
        background, unused = take_bytes(background_pool, 15000)
        self.assertGreaterEqual(sum(len(document["text"]) for document in background), 15000)
        splits = split_labels(label_pool, random.Random(42))
        self.assertEqual(splits, split_labels(label_pool, random.Random(42)))
        groups = [background, unused, *splits.values()]
        identities = [document["document_id"] for group in groups for document in group]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(set(identities), {document["document_id"] for document in documents})
        self.assertTrue(all(groups))

    def test_expansion_preserves_background_and_excludes_protected_splits(self):
        import hashlib
        from scripts.run_background_expansion import expanded_background

        def document(prefix, identifier):
            text = " ".join(f"{prefix}{index}" for index in range(60))
            return {"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "document_id": identifier, "url": f"https://example.org/{identifier}"}

        original = document("base", "base")
        validation = document("held", "held")
        fresh = [document("fresh" + str(index), "fresh" + str(index)) for index in range(6)]
        existing = {"background": [original], "validation": [validation]}
        target = len(original["text"].encode()) + 1
        expanded, rejected = expanded_background(existing, [validation, original, *fresh], target, 42)
        self.assertEqual(expanded[0], original)
        self.assertEqual(len(expanded), 2)
        self.assertNotIn(validation, expanded)
        self.assertEqual(rejected["exact_text_or_url"], 2)
        self.assertEqual(expanded, expanded_background(existing, [validation, original, *fresh], target, 42)[0])

    def test_block_builder_preserves_whole_document_counts_and_byte_totals(self):
        import hashlib
        import json
        from pathlib import Path
        import tempfile
        from phdq_blt_cache.count_patcher import CountConfig, CountTable
        from scripts.fit_count_patcher import load_background
        from scripts.run_background_expansion import build_blocks

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, source = root / "run", root / "source"
            run.mkdir()
            source.mkdir()
            texts = ["first repeated text", "second repeated text", "first repeated text"]
            documents = [{"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()} for text in texts]
            (run / "background.jsonl").write_text("".join(json.dumps(item) + "\n" for item in documents))
            preparation = {"documents": 3, "utf8_bytes": sum(len(text.encode()) for text in texts)}
            config = {"work_root": directory, "budgets": {"minimum_free_disk_gib": 0, "maximum_new_artifact_storage_gib": 1}}
            plan = {"run_id": "test", "tmux_session": "test", "background_block_utf8_bytes": 20}
            report = build_blocks(plan, config, run, source, preparation)
            self.assertEqual(report["documents"], 3)
            self.assertEqual(report["utf8_bytes"], preparation["utf8_bytes"])
            self.assertEqual(len(report["blocks"]), 2)
            full = CountTable(CountConfig(max_context=8))
            for text in texts:
                full.add_document([1] + [value + 4 for value in text.encode()])
            self.assertEqual(load_background(report).to_dict(), full.freeze().to_dict())
            with self.assertRaises(FileExistsError):
                build_blocks(plan, config, run, source, preparation)
            compressed_run = root / "compressed"
            compressed_run.mkdir()
            (compressed_run / "background.jsonl").write_bytes((run / "background.jsonl").read_bytes())
            compressed_report = build_blocks({**plan, "compress_background_blocks": True}, config, compressed_run, source, preparation)
            self.assertEqual(load_background(compressed_report).to_dict(), full.to_dict())
            self.assertTrue(all(block["compression"] == "gzip" for block in compressed_report["blocks"]))
            self.assertFalse(list((compressed_run / "background_blocks").glob("block-*.jsonl")))

    def test_block_parent_verification_and_comparison_replay(self):
        from dataclasses import asdict
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        import numpy as np
        from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountTable, teacher_features
        from scripts.fit_count_patcher import block_manifest_hash, evaluate_threshold, file_hash
        from scripts.run_background_expansion import compare, verify

        count_config = CountConfig(max_context=8)
        rule = BoundaryRule((-2, 0.1, 0, 1, 0.1), 3, 0.3)
        tokens = [1, 4, 5, 4, 6, 2, 4, 7]
        labels = np.array([True, True, False, True, False, False, True, False, True])
        chunks = [{"input_ids": tokens, "labels": labels, "entropy": np.arange(9, dtype=float), "document_id": "synthetic"}]
        table = CountTable(count_config)
        table.add_document(tokens)
        table.freeze()
        features, mask = teacher_features(tokens, labels, config=count_config, mean_patch_length=3, background=table)
        metrics, counts = evaluate_threshold(chunks, count_config, rule, table, details=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent, baseline, result = root / "parent", root / "baseline", root / "result"
            for path in (parent / "fit", baseline, result / "fit"):
                path.mkdir(parents=True)
            (baseline / "label_generation.json").write_text("{}")
            table_path = parent / "counts.jsonl"
            table.save(table_path)
            blocks = [{"table_path": str(table_path), "table_sha256": file_hash(table_path)}]
            background = {"storage": "document_blocks_v1", "blocks": blocks, "table_sha256": block_manifest_hash(blocks), "count_config": asdict(count_config)}
            (parent / "background_build.json").write_text(json.dumps(background))
            feature_path = parent / "fit/train_features.npy"
            np.save(feature_path, features[mask])
            fitted = {"status": "validation_gate_failed", "count_config": asdict(count_config), "selected_rule": asdict(rule), "validation": metrics, "validation_document_counts": counts.tolist(), "background_sha256": background["table_sha256"], "label_report_sha256": file_hash(baseline / "label_generation.json"), "feature_artifacts": {"train_features.npy": file_hash(feature_path)}}
            for path in (parent / "fit/report.json", result / "fit/report.json"):
                path.write_text(json.dumps(fitted))
            plan = {"run_id": "test", "comparison_run_directory": "parent"}
            config = {"work_root": directory, "seed": 42, "gates": {"bootstrap_replicates": 20, "minimum_validation_f1": 0.9}}
            with patch("scripts.run_background_expansion.load_chunks", return_value=chunks):
                verification = verify(plan, config, result, baseline, root)
                self.assertEqual(verification["status"], "verified")
                comparison = compare(plan, config, result, baseline, root)
                self.assertEqual(comparison["f1_difference"], 0)
                self.assertEqual(comparison["paired_document_bootstrap_difference_95ci"], [0, 0])
                with feature_path.open("ab") as stream:
                    stream.write(b"changed")
                with self.assertRaises(ValueError):
                    verify(plan, config, result, baseline, root)


if __name__ == "__main__":
    unittest.main()