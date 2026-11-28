import importlib.util
import random
import unittest


class NativeMinHashTests(unittest.TestCase):
    def test_uint64_overflow_and_empty_signature(self):
        import shutil
        import tempfile
        from scripts.native_minhash import NativeMinHash, build_native

        if not shutil.which("c++"):
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            kernel = NativeMinHash(build_native(directory))
            multipliers = [(2**61 - 2) - index for index in range(128)]
            offsets = [2**60 + index for index in range(128)]
            hashes = [0, 1, 2**32 - 1, 92345]
            expected = [min((((factor * value + offset) % 2**64) % (2**61 - 1)) & (2**32 - 1)
                            for value in hashes) for factor, offset in zip(multipliers, offsets)]
            self.assertEqual(kernel.values(hashes, multipliers, offsets), expected)
            self.assertEqual(kernel.values([], multipliers, offsets), [2**32 - 1] * 128)


class CandidateSamplingTests(unittest.TestCase):
    def test_retained_unique_quota_reads_past_protected_duplicates(self):
        from scripts.prepare_disk_background import sample_shards

        available = {'small': ['old', 'held', 'new1'], 'large': ['old', 'new2', 'unused']}
        retained = 0
        seen = {'old', 'held'}
        reports = []

        def read_shard(shard):
            yield from ({'text': text} for text in available[shard])

        legacy = list(sample_shards(['small', 'large'], read_shard, 4,
                                    'redistribute_remaining_v2', lambda _: None))
        self.assertEqual(sum(len(text.encode('utf-8')) for text in
                             {item['text'] for item in legacy} - seen), 0)
        actual = []
        for document in sample_shards(['small', 'large'], read_shard, 4,
                                     'retained_unique_v3', reports.append,
                                     retained_bytes=lambda: retained):
            actual.append(document['text'])
            if document['text'] not in seen:
                seen.add(document['text'])
                retained += len(document['text'].encode('utf-8'))
        self.assertEqual(actual, ['old', 'held', 'new1', 'old', 'new2'])
        self.assertEqual(retained, 8)
        self.assertEqual([report['retained_unique_bytes'] for report in reports], [4, 4])
        self.assertEqual(reports[-1]['total_candidate_bytes'], 18)
        self.assertEqual(reports[-1]['total_retained_unique_bytes'], 8)
        self.assertEqual([report['shortfall_bytes'] for report in reports], [0, 0])
        with self.assertRaisesRegex(ValueError, 'retained_bytes'):
            list(sample_shards(['small'], read_shard, 4, 'retained_unique_v3', reports.append))

    def test_retained_unique_quota_fails_when_pinned_shards_are_exhausted(self):
        from scripts.prepare_disk_background import sample_shards

        reports = []
        with self.assertRaisesRegex(ValueError, 'Insufficient retained unique bytes'):
            list(sample_shards(['only'], lambda _: ({'text': 'duplicate'} for unused in range(1)), 4,
                               'retained_unique_v3', reports.append,
                               retained_bytes=lambda: 0))
        self.assertEqual(reports[0]['shortfall_bytes'], 4)

    def test_retained_unique_quota_redistributes_and_is_repeatable(self):
        from scripts.prepare_disk_background import sample_shards

        def run():
            available = {'small': ['old'], 'large': ['old', '\u00e9', 'new2', 'unused']}
            retained = 0
            seen = {'old'}
            reports = []

            def read_shard(shard):
                yield from ({'text': text} for text in available[shard])

            actual = []
            for document in sample_shards(['small', 'large'], read_shard, 3,
                                         'retained_unique_v3', reports.append,
                                         retained_bytes=lambda: retained):
                actual.append(document['text'])
                if document['text'] not in seen:
                    seen.add(document['text'])
                    retained += len(document['text'].encode('utf-8'))
            return actual, reports, retained

        actual, reports, retained = run()
        self.assertEqual((actual, reports, retained), run())
        self.assertEqual(actual, ['old', 'old', '\u00e9', 'new2'])
        self.assertEqual(retained, 6)
        self.assertEqual([report['requested_bytes'] for report in reports], [3, 6])
        self.assertEqual([report['shortfall_bytes'] for report in reports], [3, 0])

    def test_candidate_quota_redistributes_only_with_explicit_opt_in(self):
        from scripts.prepare_disk_background import sample_shards

        available = {'small': ['aa'], 'large': ['bbbb', 'cccc', 'dddd']}

        def read_shard(shard):
            yield from ({'text': text} for text in available[shard])

        reports = []
        actual = list(sample_shards(['small', 'large'], read_shard, 5,
                                  'redistribute_remaining_v2', reports.append))
        self.assertEqual([item['text'] for item in actual], ['aa', 'bbbb', 'cccc'])
        self.assertEqual([item['requested_bytes'] for item in reports], [5, 8])
        self.assertEqual(reports[0]['shortfall_bytes'], 3)
        with self.assertRaisesRegex(ValueError, 'pinned shard small'):
            list(sample_shards(['small', 'large'], read_shard, 5, 'equal_v1', lambda _: None))
        with self.assertRaisesRegex(ValueError, 'across all pinned shards'):
            list(sample_shards(['small', 'large'], read_shard, 10,
                              'redistribute_remaining_v2', lambda _: None))
        available['small'] = ['aaaaa']
        original = list(sample_shards(['small', 'large'], read_shard, 5, 'equal_v1', lambda _: None))
        corrected = list(sample_shards(['small', 'large'], read_shard, 5,
                                      'redistribute_remaining_v2', lambda _: None))
        self.assertEqual(original, corrected)


@unittest.skipUnless(
    all(importlib.util.find_spec(name) for name in ("datasketch", "pyarrow", "huggingface_hub")),
    "experiment data dependencies are installed on the research host",
)
class DataPreparationTests(unittest.TestCase):
    def test_pinned_parent_fit_report_is_required_for_comparison(self):
        from pathlib import Path
        import tempfile
        from scripts.fit_count_patcher import file_hash
        from scripts.run_background_expansion import comparison_parent

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "parent/fit/report.json"
            report.parent.mkdir(parents=True)
            report.write_text("{}")
            plan = {"comparison_run_directory": "parent", "parent_fit_report_sha256": file_hash(report)}
            self.assertEqual(comparison_parent(plan, {"work_root": directory}, root), (root / "parent", report))
            report.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, "Pinned parent fit"):
                comparison_parent(plan, {"work_root": directory}, root)

    def test_numerical_environment_is_explicit_and_checked_before_work(self):
        from unittest.mock import patch
        from scripts.run_background_expansion import validate_numerical_environment

        with patch.dict("os.environ", {}, clear=True):
            validate_numerical_environment({})
            with self.assertRaisesRegex(RuntimeError, "before NumPy import"):
                validate_numerical_environment({"openblas_num_threads": 8})
        with patch.dict("os.environ", {"OPENBLAS_NUM_THREADS": "8"}, clear=True):
            validate_numerical_environment({"openblas_num_threads": 8})
            with self.assertRaises(RuntimeError):
                validate_numerical_environment({"openblas_num_threads": 24})
            for invalid in (True, 0, -1, "8"):
                with self.assertRaises(ValueError):
                    validate_numerical_environment({"openblas_num_threads": invalid})

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

    def test_disk_cpp_matches_python_signatures_dedup_and_selection(self):
        import hashlib
        import json
        from pathlib import Path
        import tempfile
        from datasketch import MinHash
        from scripts.disk_dedup import DiskDeduplicator, expand_to_disk
        from scripts.native_minhash import build_native
        from scripts.run_background_expansion import expanded_background

        def document(prefix, count, url):
            text = " ".join(f"{prefix}{position}" for position in range(count))
            return {"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "url": url}

        original = document("original", 90, "original")
        held = document("held", 90, "held")
        existing = {"background": [original], "validation": [held]}
        candidates = [original, held, document("sameurl", 60, "original")]
        for position in range(45):
            candidates.append(document(f"fresh{position}token", (30, 180, 1100)[position % 3], f"url{position}"))
        candidates.extend([{**candidates[3], "text": candidates[3]["text"].upper(), "url": "copy"},
                           {**candidates[4], "text": candidates[4]["text"] + " ending", "url": "near"}])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = build_native(root)
            index = DiskDeduplicator(root / "signatures.sqlite", 42, library)
            try:
                for text in ["", "one two", "Straße CAFÉ\n mixed\tspace", candidates[4]["text"]]:
                    normalized = " ".join(text.casefold().split())
                    words = normalized.split()
                    shingles = {" ".join(words[offset:offset + 5]).encode() for offset in range(max(1, len(words) - 4))}
                    reference = MinHash(num_perm=128, seed=42)
                    reference.update_batch(sorted(shingles))
                    self.assertEqual(index.signature(normalized).hashvalues.tolist(), reference.hashvalues.tolist())
            finally:
                index.close()
            for trial, target in enumerate((len(original["text"].encode()) + 1, 40000, 130000)):
                expected, rejected = expanded_background(existing, candidates, target, 42)
                output = root / f"background{trial}.jsonl"
                report = expand_to_disk({name: iter(items) for name, items in existing.items()}, iter(candidates), target, 42,
                                        root / f"dedup{trial}.sqlite", library, output)
                actual = [json.loads(line) for line in output.read_text().splitlines()]
                self.assertEqual(actual, expected)
                self.assertEqual(report["duplicates_removed"], rejected)
                self.assertEqual(report["candidate_documents"], len(candidates))
                self.assertEqual(report["utf8_bytes"], sum(len(item["text"].encode()) for item in expected))
                compressed_output = root / f"compressed{trial}.jsonl"
                compressed_report = expand_to_disk({name: iter(items) for name, items in existing.items()},
                    iter(candidates), target, 42, root / f"compressed{trial}.sqlite", library, compressed_output,
                    compress_payload=True)
                self.assertEqual(compressed_output.read_bytes(), output.read_bytes())
                self.assertEqual(compressed_report["duplicates_removed"], rejected)
                self.assertEqual(compressed_report["utf8_bytes"], report["utf8_bytes"])
                self.assertEqual(compressed_report["payload_storage"], "zlib_json_utf8_v1")
                import sqlite3
                with sqlite3.connect(root / f"compressed{trial}.sqlite") as connection:
                    self.assertEqual(connection.execute("SELECT DISTINCT typeof(payload) FROM documents").fetchall(), [("blob",)])
                    compressed_bytes = connection.execute("SELECT SUM(length(payload)) FROM documents").fetchone()[0]
                with sqlite3.connect(root / f"dedup{trial}.sqlite") as connection:
                    original_bytes = connection.execute("SELECT SUM(length(CAST(payload AS BLOB))) FROM documents").fetchone()[0]
                self.assertLess(compressed_bytes, original_bytes)
            with self.assertRaises(ValueError):
                DiskDeduplicator(root / "bad-compression.sqlite", 42, library, compress_payload=1)
            with self.assertRaises(ValueError):
                expand_to_disk({"background": iter([original]), "validation": iter([original])}, [], 40000, 42,
                               root / "conflict.sqlite", library, root / "conflict.jsonl")
            self.assertTrue((root / "conflict.sqlite").exists())
            with self.assertRaises(ValueError):
                expand_to_disk({"validation": [held], "background": [original]}, [], 40000, 42,
                               root / "wrongorder.sqlite", library, root / "wrongorder.jsonl")
            with self.assertRaises(FileExistsError):
                DiskDeduplicator(root / "conflict.sqlite", 42, library)

    def test_streaming_prepare_matches_original_parquet_sampling(self):
        import hashlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        import pyarrow as arrow
        import pyarrow.parquet as parquet
        from scripts.run_background_expansion import prepare

        def document(prefix, count):
            text = " ".join(f"{prefix}word{position}" for position in range(count))
            return {"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "url": prefix, "document_id": prefix}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, dataset, original, disk, parent = [root / name for name in ("source", "datasets/base", "original", "disk", "parent")]
            for path in (source, dataset, original, disk, parent):
                path.mkdir(parents=True)
            manifest = {"splits": {}}
            for split in ("background", "train", "validation", "test", "wikipedia_test"):
                path = dataset / f"{split}.jsonl"
                path.write_text(json.dumps(document(split, 50)) + "\n")
                manifest["splits"][split] = {"file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (dataset / "manifest.json").write_text(json.dumps(manifest))
            (parent / "background.jsonl").write_bytes((dataset / "background.jsonl").read_bytes())
            (parent / "data_preparation.json").write_text(json.dumps({"file_sha256": manifest["splits"]["background"]["file_sha256"]}))
            config = {"work_root": directory, "dataset_directory": "datasets", "run_id": "base", "seed": 42,
                      "data": {"fineweb_repository": "synthetic"},
                      "budgets": {"minimum_free_disk_gib": 0, "maximum_new_artifact_storage_gib": 1}}
            config_path = source / "config.json"
            config_path.write_text(json.dumps(config))
            (source / "sources.json").write_text(json.dumps({"config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                    "sources": [{"repository": "synthetic", "resolved_revision": "pinned", "selected_shards": ["one", "two"]}]}))
            (source / "scripts/native").mkdir(parents=True)
            (source / "scripts/native/minhash.cpp").write_bytes((Path(__file__).resolve().parents[1] / "scripts/native/minhash.cpp").read_bytes())
            rows = [document(f"candidate{position}x", (30, 160, 850)[position % 3]) for position in range(90)]
            table = arrow.Table.from_pylist([{"text": row["text"], "url": row["url"], "id": row["document_id"]} for row in rows])
            buffer = arrow.BufferOutputStream()
            parquet.write_table(table, buffer, row_group_size=10)
            content = buffer.getvalue().to_pybytes()
            plan = {"run_id": "test", "tmux_session": "test", "baseline_config": "config.json", "sources": "sources.json",
                    "background_utf8_bytes": 18000, "sampling_seed": 99, "parent_background_run_directory": "parent"}
            with patch("huggingface_hub.HfFileSystem") as filesystem:
                filesystem.return_value.open.side_effect = lambda *args, **kwargs: io.BytesIO(content)
                reference = prepare(plan, config, original, root, source)
                actual = prepare({**plan, "preparation_backend": "sqlite_cpp_v1"}, config, disk, root, source)
            for name in ("file_sha256", "documents", "utf8_bytes", "length_bands", "candidate_documents", "duplicates_removed", "row_groups_read", "parent_background"):
                self.assertEqual(actual[name], reference[name], name)
            self.assertFalse((disk / "dedup.sqlite").exists())
            self.assertTrue((disk / "native").is_dir())
            adaptive_plan = {**plan, "preparation_backend": "sqlite_cpp_v1",
                             "candidate_quota_policy": "retained_unique_v3", "compress_dedup_payload": True}
            adaptive_reports = []
            for name in ("adaptive", "adaptive-repeat"):
                adaptive = root / name
                adaptive.mkdir()
                with patch("huggingface_hub.HfFileSystem") as filesystem:
                    filesystem.return_value.open.side_effect = lambda *args, **kwargs: io.BytesIO(content)
                    adaptive_reports.append(prepare(adaptive_plan, config, adaptive, root, source))
                prepared = [json.loads(line) for line in (adaptive / "background.jsonl").read_text().splitlines()]
                self.assertEqual(prepared[0], document("background", 50))
                protected = {document(split, 50)["text_sha256"] for split in
                             ("train", "validation", "test", "wikipedia_test")}
                self.assertFalse(protected.intersection(row["text_sha256"] for row in prepared))
                self.assertGreaterEqual(adaptive_reports[-1]["utf8_bytes"], plan["background_utf8_bytes"])
                self.assertGreaterEqual(sum(item["retained_unique_bytes"] for item in
                                            adaptive_reports[-1]["shard_sampling"]),
                                        plan["background_utf8_bytes"] - len(document("background", 50)["text"].encode()))
                self.assertFalse((adaptive / "dedup.sqlite").exists())
            for name in ("file_sha256", "shard_sampling", "row_groups_read", "original_split_hashes"):
                self.assertEqual(adaptive_reports[0][name], adaptive_reports[1][name])
            limited = root / "limited"
            limited.mkdir()
            with self.assertRaisesRegex(RuntimeError, "storage budget"):
                prepare({**plan, "preparation_backend": "sqlite_cpp_v1"},
                        {**config, "budgets": {**config["budgets"], "maximum_new_artifact_storage_gib": 0}}, limited, root, source)
            self.assertFalse((limited / "data_preparation.json").exists())
            self.assertTrue((limited / "native").is_dir())
            with self.assertRaisesRegex(ValueError, "Unknown preparation backend"):
                prepare({"preparation_backend": "invalid"}, {}, root, root, root)

    def test_dataset_background_is_linked_after_hash_check(self):
        import hashlib
        import json
        import os
        from pathlib import Path
        import tempfile
        from scripts.run_background_expansion import prepare

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, run = root / "datasets/sample", root / "runs/test"
            dataset.mkdir(parents=True)
            run.mkdir(parents=True)
            texts = ["가나다 첫 문서", "second document"]
            rows = [{"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()} for text in texts]
            path = dataset / "background.jsonl"
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            spec = {"documents": 2, "utf8_bytes": sum(len(text.encode()) for text in texts),
                    "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (dataset / "manifest.json").write_text(json.dumps({"status": "prepared", "splits": {"background": spec}}))
            config = {"work_root": directory, "dataset_directory": "datasets", "run_id": "other", "dataset_id": "sample"}
            plan = {"run_id": "test", "preparation_backend": "dataset_background_v1"}
            report = prepare(plan, config, run, root, root)
            self.assertEqual((report["documents"], report["utf8_bytes"], report["file_sha256"]),
                             (spec["documents"], spec["utf8_bytes"], spec["file_sha256"]))
            self.assertTrue(os.path.samefile(run / "background.jsonl", path))
            self.assertEqual(json.loads((run / "data_preparation.json").read_text()), report)
            with self.assertRaises(FileExistsError):
                prepare(plan, config, run, root, root)
            path.write_text("changed\n")
            other = root / "runs/other"
            other.mkdir()
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                prepare(plan, config, other, root, root)
            self.assertFalse((other / "background.jsonl").exists())

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

    def test_explicit_parent_blocks_match_full_rebuild_and_reject_changes(self):
        import hashlib
        import json
        from pathlib import Path
        import tempfile
        from scripts.fit_count_patcher import file_hash, load_background
        from scripts.run_background_expansion import build_blocks

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent, nested, full, source = [root / name for name in ("parent", "nested", "full", "source")]
            for path in (parent, nested, full, source):
                path.mkdir()
            texts = ["first repeated text", "second repeated text", "first repeated text", "new third text"]
            documents = [{"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()} for text in texts]
            config = {"work_root": directory, "budgets": {"minimum_free_disk_gib": 0, "maximum_new_artifact_storage_gib": 1}}
            plan = {"run_id": "test", "tmux_session": "test", "background_block_utf8_bytes": 20, "compress_background_blocks": True}
            for path, items in ((parent, documents[:2]), (nested, documents), (full, documents)):
                (path / "background.jsonl").write_text("".join(json.dumps(item) + "\n" for item in items))
            preparation = {"documents": 2, "utf8_bytes": sum(len(item["text"].encode()) for item in documents[:2]),
                           "file_sha256": file_hash(parent / "background.jsonl")}
            parent_report = build_blocks(plan, config, parent, source, preparation)
            (parent / "background_build.json").write_text(json.dumps(parent_report))
            (parent / "data_preparation.json").write_text(json.dumps(preparation))
            expanded = {"documents": 4, "utf8_bytes": sum(len(item["text"].encode()) for item in documents)}
            reuse = dict(plan, reuse_parent_blocks=True, parent_background_run_directory="parent",
                         parent_background_report_sha256=file_hash(parent / "background_build.json"))
            actual = build_blocks(reuse, config, nested, source, expanded)
            expected = build_blocks(plan, config, full, source, expanded)
            self.assertEqual(load_background(actual).to_dict(), load_background(expected).to_dict())
            for key in ("documents", "input_ids", "utf8_bytes"):
                self.assertEqual(actual[key], expected[key])
            self.assertEqual(actual["blocks"][:len(parent_report["blocks"])], parent_report["blocks"])
            self.assertEqual(actual["new_table_bytes"], sum(path.stat().st_size for path in (nested / "background_blocks").glob("*.jsonl.gz")))
            self.assertLess(actual["new_table_bytes"], actual["table_bytes"])
            for name in ("prefix", "report", "block", "boolean"):
                failed = root / name
                failed.mkdir()
                (failed / "background.jsonl").write_bytes((nested / "background.jsonl").read_bytes())
                invalid = dict(reuse)
                if name == "prefix":
                    (failed / "background.jsonl").write_text("".join(json.dumps(item) + "\n" for item in reversed(documents)))
                if name == "report":
                    invalid["parent_background_report_sha256"] = "0" * 64
                if name == "boolean":
                    invalid["reuse_parent_blocks"] = "true"
                block = Path(parent_report["blocks"][0]["table_path"])
                original = block.read_bytes()
                if name == "block":
                    block.write_bytes(original + b"changed")
                try:
                    with self.assertRaises(ValueError):
                        build_blocks(invalid, config, failed, source, expanded)
                finally:
                    block.write_bytes(original)

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
                mismatch_run = root / "mismatch"
                mismatch_run.mkdir()
                changed = {**metrics, "entropy_mae": float(np.nextafter(metrics["entropy_mae"], np.inf))}
                with patch("scripts.run_background_expansion.evaluate_threshold", return_value=(changed, counts)):
                    with self.assertRaisesRegex(ValueError, "entropy_mae"):
                        verify(plan, config, mismatch_run, baseline, root)
                diagnostic = json.loads((mismatch_run / "validation_replay_mismatch.json").read_text())
                self.assertEqual(list(diagnostic["mismatches"]), ["entropy_mae"])
                self.assertTrue(diagnostic["document_counts_equal"])
                self.assertTrue((mismatch_run / "validation_replay.npz").exists())
                with feature_path.open("ab") as stream:
                    stream.write(b"changed")
                with self.assertRaises(ValueError):
                    verify(plan, config, result, baseline, root)


if __name__ == "__main__":
    unittest.main()