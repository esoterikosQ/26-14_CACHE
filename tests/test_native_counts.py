from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from phdq_blt_cache.count_patcher import CountConfig, CountTable


def native_available():
    return shutil.which("c++") is not None


def random_texts(seed, count):
    generator = random.Random(seed)
    alphabet = b"ab ab\nxyz" + bytes(range(256))
    return [bytes(generator.choice(alphabet) for _ in range(generator.randint(0, 120))) for _ in range(count)]


def python_table(texts, config):
    table = CountTable(config)
    for text in texts:
        table.add_document([1] + [value + 4 for value in text])
    return table.freeze()


@unittest.skipUnless(native_available(), "C++ compiler unavailable")
class NativeCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.native_counts import NativeCounts, build_native_counts

        cls.directory = tempfile.TemporaryDirectory()
        cls.native = NativeCounts(build_native_counts(Path(cls.directory.name) / "native"))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_block_bytes_and_statistics_match_python(self):
        root = Path(self.directory.name)
        texts = random_texts(7, 40)
        for max_context in (0, 1, 3, 8):
            config = CountConfig(max_context=max_context)
            table = python_table(texts, config)
            expected = root / f"python-{max_context}.jsonl"
            table.save(expected)
            plain = root / f"native-{max_context}.jsonl"
            compressed = root / f"native-{max_context}.jsonl.gz"
            statistics = self.native.build_block(texts, config, plain, 0)
            self.assertEqual(plain.read_bytes(), expected.read_bytes())
            self.assertEqual(statistics, {"contexts": len(table._rows), "edges": sum(len(row) for row in table._rows.values()),
                                          "uncompressed_table_bytes": expected.stat().st_size})
            self.assertEqual(self.native.build_block(texts, config, compressed, 1), statistics)
            self.assertEqual(gzip.decompress(compressed.read_bytes()), expected.read_bytes())
            with self.assertRaisesRegex(ValueError, "output exists"):
                self.native.build_block(texts, config, plain, 0)

    def projection_fixture(self, root, blocks=5):
        from scripts.fit_count_patcher import block_manifest_hash, query_contexts
        from scripts.benchmark_count_patcher import file_hash

        config = CountConfig(max_context=8)
        texts = random_texts(11, 60)
        entries = []
        for index in range(blocks):
            path = root / f"block-{index:05d}.jsonl"
            python_table(texts[index::blocks], config).save(path)
            compressed = path.with_suffix(".jsonl.gz")
            compressed.write_bytes(gzip.compress(path.read_bytes(), compresslevel=1))
            path.unlink()
            entries.append({"table_path": str(compressed), "table_sha256": file_hash(compressed), "compression": "gzip"})
        report = {"storage": "document_blocks_v1", "blocks": entries, "table_sha256": block_manifest_hash(entries),
                  "count_config": asdict(config)}
        chunks = [{"input_ids": [1] + [value + 4 for value in text]} for text in random_texts(13, 20)]
        required = query_contexts(chunks, config) | {b"\x99\x00", bytes(18)}
        return report, required, config

    def test_projection_matches_python_loader_including_order(self):
        from scripts.fit_count_patcher import load_background

        with tempfile.TemporaryDirectory() as directory:
            report, required, _ = self.projection_fixture(Path(directory))
            expected = load_background(report, required)
            for workers in (1, 3):
                actual = load_background(report, required, native=self.native, workers=workers)
                self.assertEqual(list(actual._rows.items()), list(expected._rows.items()))
                self.assertEqual(actual._rows, expected._rows)
                self.assertEqual(actual._totals, expected._totals)
                self.assertTrue(actual._frozen)
            with self.assertRaisesRegex(ValueError, "explicit required"):
                load_background(report, None, native=self.native)

    def test_seeded_parent_projection_equals_direct_projection(self):
        from scripts.fit_count_patcher import block_manifest_hash, load_background
        from scripts.benchmark_count_patcher import file_hash
        from scripts.native_counts import load_projection, save_projection

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, required, config = self.projection_fixture(root)
            parent = {**report, "blocks": report["blocks"][:3], "table_sha256": block_manifest_hash(report["blocks"][:3])}
            saved = {}
            load_background(parent, required, native=self.native, workers=2,
                            projection_sink=lambda projection, details: saved.update(projection=projection))
            report_path, _ = save_projection(root / "parent.npz", saved["projection"], required, {
                "count_config": report["count_config"], "blocks": 3, "block_manifest_sha256": parent["table_sha256"]})
            seed = load_projection(report_path, file_hash(report_path))
            direct = load_background(report, required)
            reused = load_background(report, required, native=self.native, workers=2, seed=seed)
            self.assertEqual(list(reused._rows.items()), list(direct._rows.items()))
            self.assertEqual(reused._totals, direct._totals)
            subset = set(sorted(required)[::3])
            filtered = load_background(report, subset, native=self.native, workers=2, seed=seed)
            self.assertEqual(list(filtered._rows.items()), list(load_background(report, subset)._rows.items()))
            with self.assertRaisesRegex(ValueError, "exceed"):
                load_background(report, required | {bytes(16)}, native=self.native, seed=seed)
            changed = {**report, "blocks": report["blocks"][1:], "table_sha256": block_manifest_hash(report["blocks"][1:])}
            with self.assertRaisesRegex(ValueError, "prefix"):
                load_background(changed, required, native=self.native, seed=seed)
            with self.assertRaisesRegex(ValueError, "Pinned projection"):
                load_projection(report_path, "0" * 64)

    def test_parallel_build_blocks_matches_python_builder(self):
        from scripts.fit_count_patcher import load_background
        from scripts.run_background_expansion import build_blocks

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            texts = [text.decode("latin-1") for text in random_texts(17, 30)]
            documents = [{"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()} for text in texts]
            preparation = {"documents": len(texts), "utf8_bytes": sum(len(text.encode()) for text in texts)}
            config = {"work_root": directory, "budgets": {"minimum_free_disk_gib": 0, "maximum_new_artifact_storage_gib": 1}}
            reports = {}
            for name, extra in (("python", {}), ("native", {"count_backend": "cpp_v1", "count_workers": 3})):
                for compress in (False, True):
                    run = root / f"{name}-{compress}"
                    run.mkdir()
                    (run / "background.jsonl").write_text("".join(json.dumps(item) + "\n" for item in documents))
                    plan = {"run_id": "test", "tmux_session": "test", "background_block_utf8_bytes": 300,
                            "compress_background_blocks": compress, **extra}
                    reports[name, compress] = build_blocks(plan, config, run, root, preparation)
            for compress in (False, True):
                python, native = reports["python", compress], reports["native", compress]
                self.assertGreater(len(native["blocks"]), 3)
                self.assertEqual(native["count_backend"], "cpp_v1")
                for key in ("documents", "input_ids", "utf8_bytes", "block_context_rows"):
                    self.assertEqual(native[key], python[key])
                for expected, actual in zip(python["blocks"], native["blocks"], strict=True):
                    self.assertEqual(Path(actual["table_path"]).name, Path(expected["table_path"]).name)
                    ignored = ("table_path",) if not compress else ("table_path", "table_sha256", "table_bytes")
                    self.assertEqual({key: value for key, value in actual.items() if key not in ignored},
                                     {key: value for key, value in expected.items() if key not in ignored})
                    if compress:
                        self.assertEqual(gzip.decompress(Path(actual["table_path"]).read_bytes()),
                                         gzip.decompress(Path(expected["table_path"]).read_bytes()))
                    metadata = Path(actual["table_path"]).with_suffix(".metadata.json")
                    self.assertEqual(json.loads(metadata.read_text()), actual)
                self.assertEqual(load_background(native).to_dict(), load_background(python).to_dict())
            with self.assertRaisesRegex(ValueError, "count_workers"):
                bad = root / "bad"
                bad.mkdir()
                build_blocks({"run_id": "test", "tmux_session": "test", "background_block_utf8_bytes": 300,
                              "count_backend": "cpp_v1", "count_workers": 0}, config, bad, root, preparation)


if __name__ == "__main__":
    unittest.main()
