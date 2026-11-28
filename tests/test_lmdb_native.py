from dataclasses import asdict
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from phdq_blt_cache.count_patcher import CountConfig

from tests.test_native_counts import python_table, random_texts


def available():
    return shutil.which("c++") is not None and any(Path(path).exists() for path in (
        "/usr/lib/x86_64-linux-gnu/liblmdb.so.0", "/usr/lib/liblmdb.so.0", "/usr/lib64/liblmdb.so.0"))


@unittest.skipUnless(available(), "C++ compiler or liblmdb.so.0 unavailable")
class NativeLmdbBuildTests(unittest.TestCase):
    def fixture(self, root, blocks=5, mutate=None):
        from scripts.benchmark_count_patcher import file_hash
        from scripts.fit_count_patcher import block_manifest_hash

        config = CountConfig(max_context=8)
        texts = random_texts(21, 150)
        entries = []
        for index in range(blocks):
            path = root / f"block-{index:05d}.jsonl"
            table = python_table(texts[index::blocks], config)
            table.save(path)
            if mutate and index == 1:
                mutate(path)
            compressed = path.with_suffix(".jsonl.gz")
            compressed.write_bytes(gzip.compress(path.read_bytes(), compresslevel=1))
            path.unlink()
            entries.append({"table_path": str(compressed), "table_sha256": file_hash(compressed), "compression": "gzip",
                            "contexts": len(table._rows), "utf8_bytes": sum(len(text) for text in texts[index::blocks])})
        report = root / "background_build.json"
        report.write_text(json.dumps({"storage": "document_blocks_v1", "blocks": entries,
                                      "table_sha256": block_manifest_hash(entries), "count_config": asdict(config)}))
        return report, python_table(texts, config)

    def native(self, report, output, **options):
        from scripts.build_lmdb_native import build

        settings = dict(map_size_bytes=64 * 1024 ** 2, threads=3, memory_budget_bytes=1 << 30, max_rss_bytes=0,
                        min_free_bytes=0, max_output_bytes=1 << 30, sample_modulus=1, progress=lambda value: None)
        settings.update(options)
        return build(report, output, **settings)

    def rows(self, path):
        import lmdb
        from phdq_blt_cache.lmdb_counts import _decode

        environment = lmdb.open(str(path), readonly=True, lock=False)
        try:
            with environment.begin() as transaction:
                metadata = json.loads(transaction.get(b"\x00metadata"))
                rows = {key: _decode(value) for key, value in transaction.cursor() if key != b"\x00metadata"}
                raw = {key: value for key, value in transaction.cursor() if key != b"\x00metadata"}
                keys = [key for key, _ in transaction.cursor()]
        finally:
            environment.close()
        return metadata, rows, raw, keys

    def test_native_lmdb_matches_python_builder(self):
        from phdq_blt_cache.lmdb_counts import LMDBCountTable, build_lmdb_background

        identity = ("format", "status", "config", "source_report_sha256", "source_manifest_sha256", "source_manifest_encoding",
                    "source_blocks", "selected_blocks", "complete_source", "completed_blocks", "input_rows",
                    "completed_input_rows", "current_block_rows", "source_utf8_bytes", "contexts")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, full = self.fixture(root)
            build_lmdb_background(report, root / "python.lmdb", map_size_bytes=64 * 1024 ** 2)
            reference, expected, _, reference_keys = self.rows(root / "python.lmdb")
            outputs = {}
            for passes in (1, 3, 7):
                result = self.native(report, root / f"native-{passes}.lmdb", passes=passes)
                self.assertEqual(result["builder"]["passes"], passes)
                metadata, actual, raw, keys = self.rows(root / f"native-{passes}.lmdb")
                self.assertEqual(actual, expected)
                self.assertEqual(keys, reference_keys)
                self.assertEqual({key: metadata[key] for key in identity}, {key: reference[key] for key in identity})
                self.assertFalse((root / f"native-{passes}.lmdb.native").exists())
                outputs[passes] = raw
            self.assertEqual(outputs[1], outputs[3])
            self.assertEqual(outputs[1], outputs[7])
            with LMDBCountTable(root / "native-3.lmdb") as disk:
                for context in full._rows:
                    self.assertEqual(disk.lookup(context), full.lookup(context))
                self.assertEqual(disk.lookup(b"absent"), ({}, 0))
            planned = self.native(report, root / "planned.lmdb", memory_budget_bytes=1 << 16)
            self.assertGreater(planned["builder"]["passes"], 1)
            self.assertEqual(self.rows(root / "planned.lmdb")[1], expected)
            partial = self.native(report, root / "partial.lmdb", block_limit=2, passes=2)
            build_lmdb_background(report, root / "python-partial.lmdb", map_size_bytes=64 * 1024 ** 2, block_limit=2)
            self.assertFalse(partial["complete_source"])
            self.assertEqual(self.rows(root / "partial.lmdb")[1], self.rows(root / "python-partial.lmdb")[1])
            with self.assertRaises(FileExistsError):
                self.native(report, root / "native-3.lmdb", passes=3)

    def test_native_lmdb_fails_closed(self):
        from scripts.benchmark_count_patcher import file_hash

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, _ = self.fixture(root)
            payload = json.loads(report.read_text())
            block = Path(payload["blocks"][2]["table_path"])
            original = block.read_bytes()
            block.write_bytes(original + b"x")
            with self.assertRaisesRegex(ValueError, "Background block hash mismatch"):
                self.native(report, root / "tampered.lmdb", passes=2)
            block.write_bytes(original)
            payload["blocks"][0]["contexts"] += 1
            report.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "manifest hash mismatch"):
                self.native(report, root / "manifest.lmdb", passes=2)
        cases = {
            "unpadded": lambda path: path.write_text(path.read_text() + '["0300",[[5,1]]]\n'),
            "cannot cross EOS": lambda path: path.write_text(path.read_text() + '["0200",[[5,1]]]\n'),
            "Invalid serialized count": lambda path: path.write_text(path.read_text() + '["ff00",[[5,1],[5,2]]]\n'),
            "configuration mismatch": lambda path: path.write_text(path.read_text().replace('"max_context": 8', '"max_context": 7', 1)),
        }
        for message, mutate in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                report, _ = self.fixture(root, mutate=mutate)
                with self.assertRaisesRegex(ValueError, message):
                    self.native(report, root / "invalid.lmdb", passes=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, _ = self.fixture(root)
            payload = json.loads(report.read_text())
            from scripts.fit_count_patcher import block_manifest_hash
            payload["blocks"][3]["contexts"] += 1
            payload["table_sha256"] = block_manifest_hash(payload["blocks"])
            report.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "row count mismatch"):
                self.native(report, root / "rows.lmdb", passes=2)
            self.assertTrue(file_hash(report))


if __name__ == "__main__":
    unittest.main()
