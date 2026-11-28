import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("pyarrow", "scipy")), "pyarrow/scipy unavailable")
class BackgroundCompositionTests(unittest.TestCase):
    def test_nested_segments_quality_join_and_prefix_checks(self):
        import pyarrow as arrow
        import pyarrow.parquet as parquet

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shards = root / "rev1"
            (shards / "data/dump").mkdir(parents=True)
            rows = [{"id": f"id{index}", "text": "word " * (60 + 400 * (index % 3)), "url": f"https://www.site{index % 7}.org/p",
                     "language_score": 0.5 + index / 10000, "token_count": 10 + index} for index in range(3000)]
            parquet.write_table(arrow.Table.from_pylist(rows), shards / "data/dump/a.parquet", row_group_size=500)

            def document(index):
                group, position = divmod(index, 500)
                return {"revision": "rev1", "shard": "data/dump/a.parquet", "row_group": group, "row_in_group": position,
                        "document_id": rows[index]["id"], "url": rows[index]["url"], "text": rows[index]["text"]}

            original = [{"text": "original " * (30 + index), "url": f"https://orig{index}.com"} for index in range(1200)]
            parent_documents = original + [document(index) for index in range(0, 2400, 2)]
            child_documents = parent_documents + [document(index) for index in range(1, 2400, 2)]
            runs = {}
            for name, documents, parent, parent_count in (("parent", parent_documents, None, len(original)),
                                                         ("child", child_documents, "parent", len(parent_documents))):
                run = root / name
                run.mkdir()
                content = "".join(json.dumps(item) + "\n" for item in documents)
                (run / "background.jsonl").write_text(content)
                (run / "data_preparation.json").write_text(json.dumps({
                    "documents": len(documents), "utf8_bytes": sum(len(item["text"].encode()) for item in documents),
                    "file_sha256": hashlib.sha256(content.encode()).hexdigest(), "original_background_documents_retained": parent_count,
                    "parent_background": {"run": str(runs[parent])} if parent else None}))
                runs[name] = run
            output = root / "composition.json"
            command = [sys.executable, "-m", "scripts.analyze_background_composition", "--run-directory", str(runs["child"]),
                       "--local-shard-directory", str(shards), "--natural-reference", "--output", str(output)]
            subprocess.run(command, check=True, cwd=Path(__file__).resolve().parents[1], capture_output=True)
            report = json.loads(output.read_text())
            self.assertEqual([item["documents"] for item in report["verification"]], [1200, 2400, 3600])
            self.assertEqual([item["prefix_sha256_match"] for item in report["verification"]], [None, True, True])
            self.assertEqual([item["documents"] for item in report["segments"]], [1200, 1200, 1200])
            self.assertEqual(report["scored_documents"], 2400)
            self.assertEqual(report["segments"][0]["unscored_documents"], 1200)
            self.assertAlmostEqual(report["segments"][2]["language_score_mean"],
                                   sum(rows[index]["language_score"] for index in range(1, 2400, 2)) / 1200)
            self.assertEqual(report["segments"][1]["distinct_hosts"], 7)
            self.assertEqual(report["natural_reference"]["documents"], 3000)
            self.assertLess(report["increment_versus_previous_increment"][0]["js_band_bytes"], 0.01)
            self.assertGreater(report["increment_versus_parent"][0]["js_host"], 0.5)
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess.run(command, check=True, cwd=Path(__file__).resolve().parents[1], capture_output=True)
            report_path = runs["parent"] / "data_preparation.json"
            broken = json.loads(report_path.read_text())
            report_path.write_text(json.dumps({**broken, "utf8_bytes": broken["utf8_bytes"] + 1}))
            failed = subprocess.run(command[:-1] + [str(root / "broken.json")], cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("Nested prefix verification failed", failed.stderr)


if __name__ == "__main__":
    unittest.main()
