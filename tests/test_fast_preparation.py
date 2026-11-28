import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


def dependencies_available():
    return shutil.which("c++") is not None and all(
        importlib.util.find_spec(name) for name in ("datasketch", "pyarrow", "huggingface_hub"))


@unittest.skipUnless(dependencies_available(), "C++ compiler or data dependencies unavailable")
class FastPreparationTests(unittest.TestCase):
    def test_native_batch_signature_equals_datasketch(self):
        from datasketch import MinHash
        from scripts.disk_dedup import DiskDeduplicator, Signer, prepare_text
        from scripts.native_minhash import build_native

        texts = ["", "   ", "one", "one two three four", "one two three four five",
                 "one two three four five six", "Straße CAFÉ\n mixed\tspace \u3000 ideographic",
                 " ".join(f"token{index % 37}" for index in range(900)), "x" * 70 + " y" * 40,
                 "emoji 😀 and 한국어 문장 with repeated repeated repeated words words words"]
        with tempfile.TemporaryDirectory() as directory:
            library = build_native(Path(directory) / "native")
            for seed in (42, 20261019):
                signer = Signer(seed, library)
                index = DiskDeduplicator(Path(directory) / f"index-{seed}.sqlite", seed, library)
                try:
                    for threads in (1, 4):
                        signed = signer.sign([{"text": text} for text in texts], threads)
                        for document in signed:
                            normalized, digest = prepare_text(document)
                            self.assertEqual(document.prepared, (normalized, digest))
                            words = normalized.split()
                            shingles = {" ".join(words[offset:offset + 5]).encode() for offset in range(max(1, len(words) - 4))}
                            reference = MinHash(num_perm=128, seed=seed)
                            reference.update_batch(sorted(shingles))
                            self.assertEqual(document.hashvalues.tolist(), reference.hashvalues.tolist())
                            self.assertEqual(document.hashvalues.tolist(), index.signature(normalized).hashvalues.tolist())
                            self.assertEqual(json.dumps(document), json.dumps(dict(document)))
                finally:
                    index.close()

    def test_accelerated_prepare_outputs_are_byte_identical(self):
        import pyarrow as arrow
        import pyarrow.parquet as parquet
        from scripts.benchmark_count_patcher import file_hash
        from scripts.disk_dedup import build_protected_index
        from scripts.native_minhash import build_native
        from scripts.prepare_disk_background import read_documents
        from scripts.run_background_expansion import prepare

        def document(prefix, count):
            text = " ".join(f"{prefix}word{position}" for position in range(count))
            return {"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "url": prefix, "document_id": prefix}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, dataset, parent = root / "source", root / "datasets/base", root / "parent"
            for path in (source, dataset, parent):
                path.mkdir(parents=True)
            manifest = {"splits": {}}
            for split in ("background", "train", "validation", "test", "wikipedia_test"):
                path = dataset / f"{split}.jsonl"
                path.write_text(json.dumps(document(split, 50)) + "\n")
                manifest["splits"][split] = {"file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (dataset / "manifest.json").write_text(json.dumps(manifest))
            parent_documents = [document("background", 50)] + [document(f"parent{index}x", 40 + index) for index in range(30)]
            parent_bytes = sum(len(item["text"].encode()) for item in parent_documents)
            (parent / "background.jsonl").write_text("".join(json.dumps(item) + "\n" for item in parent_documents))
            (parent / "data_preparation.json").write_text(json.dumps({"file_sha256": file_hash(parent / "background.jsonl")}))
            config = {"work_root": directory, "dataset_directory": "datasets", "run_id": "base", "seed": 42,
                      "data": {"fineweb_repository": "synthetic"},
                      "budgets": {"minimum_free_disk_gib": 0, "maximum_new_artifact_storage_gib": 1}}
            config_path = source / "config.json"
            config_path.write_text(json.dumps(config))
            (source / "sources.json").write_text(json.dumps({"config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                    "sources": [{"repository": "synthetic", "resolved_revision": "pinned", "selected_shards": ["one", "two"]}]}))
            (source / "scripts/native").mkdir(parents=True)
            (source / "scripts/native/minhash.cpp").write_bytes((Path(__file__).resolve().parents[1] / "scripts/native/minhash.cpp").read_bytes())
            rows = [document(f"candidate{position}x", (30, 160, 850)[position % 3]) for position in range(120)]
            rows += [document(f"parent{index}x", 40 + index) for index in range(0, 30, 4)]
            rows += [{**document("candidate3x", 30), "url": "fresh-url"}, {**rows[5], "text": rows[5]["text"] + " tail"}]
            table = arrow.Table.from_pylist([{"text": row["text"], "url": row["url"], "id": row["document_id"]} for row in rows])
            buffer = arrow.BufferOutputStream()
            parquet.write_table(table, buffer, row_group_size=10)
            content = buffer.getvalue().to_pybytes()
            local = root / "shards"
            local.mkdir()
            for shard in ("one", "two"):
                (local / shard).write_bytes(content)
            pinned = {shard: file_hash(local / shard) for shard in ("one", "two")}
            index_directory = root / "index"
            index_directory.mkdir()
            paths = {split: dataset / f"{split}.jsonl" for split in ("background", "train", "validation", "test", "wikipedia_test")}
            paths["background"] = parent / "background.jsonl"
            reports = {}
            for compress in (False, True):
                database = index_directory / f"protected-{compress}.sqlite"
                summary = build_protected_index({split: read_documents(path) for split, path in paths.items()}, 42, database,
                                                build_native(index_directory / f"native-{compress}"), compress_payload=compress, threads=3)
                index_report = {**summary, "database": database.name, "database_sha256": file_hash(database),
                                "split_sha256": {split: file_hash(path) for split, path in paths.items()}}
                report_path = index_directory / f"protected-{compress}.json"
                report_path.write_text(json.dumps(index_report))
                base = {"run_id": "test", "tmux_session": "test", "baseline_config": "config.json", "sources": "sources.json",
                        "background_utf8_bytes": parent_bytes + 400000, "sampling_seed": 99, "parent_background_run_directory": "parent",
                        "preparation_backend": "sqlite_cpp_v1", "candidate_quota_policy": "retained_unique_v3",
                        "compress_dedup_payload": compress}
                variants = {
                    "reference": {}, "signatures": {"signature_workers": 3},
                    "local": {"local_shard_directory": "shards", "local_shard_sha256": pinned},
                    "index": {"protected_index_report": f"index/{report_path.name}", "protected_index_report_sha256": file_hash(report_path)},
                }
                variants["all"] = {**variants["signatures"], **variants["local"], **variants["index"],
                                   "delete_protected_index_after_prepare": True}
                for name, extra in variants.items():
                    run = root / f"{name}-{compress}"
                    run.mkdir()
                    with patch("huggingface_hub.HfFileSystem") as filesystem:
                        filesystem.return_value.open.side_effect = lambda *args, **kwargs: io.BytesIO(content)
                        reports[name, compress] = (prepare({**base, **extra}, config, run, root, source), run)
                reference, reference_run = reports["reference", compress]
                self.assertGreater(reference["duplicates_removed"].get("exact_text_or_url", 0), 0)
                for name in ("signatures", "local", "index", "all"):
                    actual, run = reports[name, compress]
                    self.assertEqual((run / "background.jsonl").read_bytes(), (reference_run / "background.jsonl").read_bytes(), name)
                    for key in ("file_sha256", "documents", "utf8_bytes", "length_bands", "candidate_documents",
                                "duplicates_removed", "row_groups_read", "shard_sampling", "original_background_documents_retained"):
                        self.assertEqual(actual[key], reference[key], (name, key))
                    self.assertFalse((run / "dedup.sqlite").exists())
                self.assertNotIn("acceleration", reference)
                self.assertEqual(reports["all", compress][0]["acceleration"]["signature_workers"], 3)
                self.assertFalse(database.exists())
                self.assertTrue(report_path.exists())
            changed = root / "changed"
            changed.mkdir()
            (local / "one").write_bytes(content + b"x")
            with self.assertRaisesRegex(ValueError, "Pinned local shard"):
                prepare({**base, **variants["local"]}, config, changed, root, source)
            (local / "one").write_bytes(content)
            mismatch = root / "mismatch"
            mismatch.mkdir()
            with self.assertRaisesRegex(ValueError, "Pinned protected index"):
                prepare({**base, "protected_index_report": f"index/{report_path.name}", "protected_index_report_sha256": "0" * 64},
                        config, mismatch, root, source)
            for case, (extra, message) in enumerate((({"selection_policy": "other"}, "selection_policy"),
                                   ({"selection_policy": "shard_uniform_v1", "candidate_quota_policy": "equal_v1"}, "selection_policy"),
                                   ({"candidate_oversample": 0.5}, "candidate_oversample"),
                                   ({"candidate_quota_policy": "equal_v1", "candidate_oversample": 2}, "candidate_oversample"))):
                invalid = root / f"invalid-{case}"
                invalid.mkdir()
                with self.assertRaisesRegex(ValueError, message):
                    prepare({**base, **extra}, config, invalid, root, source)
            wired = root / "wired"
            wired.mkdir()
            with patch("scripts.disk_dedup.expand_to_disk", side_effect=RuntimeError("stop")) as expand, \
                    patch("huggingface_hub.HfFileSystem"), self.assertRaisesRegex(RuntimeError, "stop"):
                prepare({**base, "selection_policy": "shard_uniform_v1", "candidate_oversample": 1.5}, config, wired, root, source)
            self.assertEqual(expand.call_args.kwargs["shards"], ["one", "two"])
            self.assertFalse((wired / "data_preparation.json").exists())

    def test_shard_uniform_selection(self):
        from scripts.disk_dedup import expand_to_disk
        from scripts.native_minhash import build_native

        def document(name, size, shard=None):
            words, text = [], ""
            while len(text) < size:
                words.append(f"{name}w{len(words)}")
                text = " ".join(words)
            return {"text": text, "url": name, "document_id": name, **({"shard": shard} if shard else {})}

        sizes = (600, 3000, 12000)
        pools = {"a": 400, "b": 120, "c": 120}
        candidates = [document(f"{shard}{index}", sizes[index % 3], shard) for shard, count in pools.items() for index in range(count)]
        existing = {"background": [document("parent", 2000)], "train": [document("train", 700)]}
        parent = len(existing["background"][0]["text"].encode())

        def run(name, target, shards, pool=candidates):
            return expand_to_disk({split: iter(items) for split, items in existing.items()}, iter(pool), parent + target, 7,
                                  root / f"{name}.sqlite", library, root / f"{name}.jsonl", shards=shards)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = build_native(root / "native")
            result = run("a", 900000, ["a", "b", "c"])
            selection = result["shard_selection"]
            self.assertLessEqual(selection["max_minus_min_added_bytes"], 12100)
            self.assertEqual(sum(selection["added_utf8_bytes"].values()), result["utf8_bytes"] - parent)
            lines = [json.loads(line) for line in (root / "a.jsonl").read_text().splitlines()]
            self.assertEqual(lines[0]["url"], "parent")
            self.assertEqual(len(lines), result["documents"])
            for shard in pools:
                written = sum(len(item["text"].encode()) for item in lines[1:] if item["shard"] == shard)
                self.assertEqual(written, selection["added_utf8_bytes"][shard])
            run("b", 900000, ["a", "b", "c"])
            self.assertEqual((root / "a.jsonl").read_bytes(), (root / "b.jsonl").read_bytes())
            with self.assertRaisesRegex(ValueError, "Shard exhausted before target: [bc];"):
                run("c", 2400000, ["a", "b", "c"])
            with self.assertRaisesRegex(ValueError, "unpinned shard"):
                run("d", 900000, ["a", "b"])
            with self.assertRaisesRegex(ValueError, "Shard exhausted before target: z"):
                run("e", 900000, ["a", "b", "c", "z"])
            for invalid in ([], ["a", "a"], "abc"):
                with self.assertRaisesRegex(ValueError, "shards must"):
                    run("f", 900000, invalid)

    def test_budget_overrides_are_explicit_storage_only(self):
        from unittest.mock import patch as mock_patch
        import scripts.run_background_expansion as expansion

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            config = {"work_root": directory, "run_directory": "base", "budgets": {
                "peak_host_ram_gib": 48, "maximum_new_artifact_storage_gib": 100, "minimum_free_disk_gib": 100}}
            (source / "config.json").write_text(json.dumps(config))
            seen = {}

            def fake_prepare(plan, effective, run, baseline, source_root):
                seen.update(effective["budgets"])
                return {"status": "prepared"}

            for overrides, expected in (({}, None), ({"maximum_new_artifact_storage_gib": 200, "minimum_free_disk_gib": 30}, None),
                                        ({"peak_host_ram_gib": 96}, "budget_overrides"),
                                        ({"minimum_free_disk_gib": 0}, "budget_overrides")):
                plan_path = source / "plan.json"
                plan_path.write_text(json.dumps({"run_id": "test", "baseline_config": "config.json", "budget_overrides": overrides}))
                seen.clear()
                with mock_patch.object(expansion, "__file__", str(source / "scripts/run_background_expansion.py")), \
                        mock_patch.object(expansion, "prepare", fake_prepare), \
                        mock_patch.object(expansion.resource, "setrlimit"), \
                        mock_patch("sys.argv", ["run", "--plan", str(plan_path), "--stage", "prepare"]):
                    if expected:
                        with self.assertRaisesRegex(ValueError, expected):
                            expansion.main()
                        continue
                    self.assertEqual(expansion.main(), 0)
                self.assertEqual(seen["peak_host_ram_gib"], 48)
                self.assertEqual(seen["maximum_new_artifact_storage_gib"], overrides.get("maximum_new_artifact_storage_gib", 100))
                self.assertEqual(seen["minimum_free_disk_gib"], overrides.get("minimum_free_disk_gib", 100))
            self.assertEqual(json.loads((source / "config.json").read_text()), config)


if __name__ == "__main__":
    unittest.main()
