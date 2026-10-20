"""Build only the T05-screened K=8 background with bounded host resources."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import resource
import shutil
import time

from benchmark_count_patcher import file_hash
from phdq_blt_cache.count_patcher import CountConfig, CountTable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    budgets = config["budgets"]
    resource.setrlimit(resource.RLIMIT_AS, (budgets["peak_host_ram_gib"] * 2**30,) * 2)
    root = Path(config["work_root"])
    run = root / config["run_directory"]
    dataset = root / config["dataset_directory"] / config["run_id"]
    pilot = json.loads((run / "count_pilot.json").read_text())
    if not any(item["max_context"] == 8 for item in pilot["screened_configurations"]):
        raise ValueError("K=8 did not pass T05")
    source = dataset / "background.jsonl"
    manifest = json.loads((dataset / "manifest.json").read_text())
    source_hash = file_hash(source)
    if source_hash != manifest["splits"]["background"]["file_sha256"]:
        raise ValueError("Background source hash mismatch")
    path = run / "background_k8.jsonl"
    temporary = run / "background_k8.partial.jsonl"
    if path.exists() or temporary.exists():
        raise FileExistsError("Existing background artifacts are preserved")
    count_config = CountConfig(max_context=8)
    report = {
        "stage": "T06-background", "run_id": config["run_id"], "status": "running",
        "config_sha256": file_hash(args.config), "source_sha256": source_hash,
        "count_config": asdict(count_config), "documents": 0, "input_ids": 0,
        "protocol": "BOS plus original UTF-8 IDs, no appended EOS; reset context per original document; no pruning",
        "code_sha256": {str(item): file_hash(item) for item in (Path(__file__), Path(__file__).parents[1] / "src/phdq_blt_cache/count_patcher.py")},
    }
    started = time.perf_counter()
    with (run / "background_build.json").open("x") as output:
        try:
            table = CountTable(count_config)
            with source.open() as stream:
                for line in stream:
                    document = json.loads(line)
                    token_ids = [1] + [value + 4 for value in document["text"].encode("utf-8")]
                    table.add_document(token_ids)
                    report["documents"] += 1
                    report["input_ids"] += len(token_ids)
                    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > budgets["peak_host_ram_gib"] * 2**30:
                        raise RuntimeError("Host RAM budget exceeded")
                    if time.perf_counter() - started > budgets["maximum_initial_build_and_label_seconds"]:
                        raise RuntimeError("Background build time budget exceeded")
                    if report["documents"] % 500 == 0:
                        print(json.dumps({"documents": report["documents"], "contexts": len(table._rows)}), flush=True)
            table.freeze()
            report["build_seconds"] = time.perf_counter() - started
            report["contexts"] = len(table._rows)
            report["edges"] = sum(len(row) for row in table._rows.values())
            estimated_disk = pilot["candidates"][0]["projected_background_serialized_bytes"]
            if shutil.disk_usage(root).free - estimated_disk < budgets["minimum_free_disk_gib"] * 2**30:
                raise RuntimeError("Insufficient disk headroom")
            table.save(temporary)
            if temporary.stat().st_size > budgets["maximum_new_artifact_storage_gib"] * 2**30:
                raise RuntimeError("Background storage budget exceeded")
            temporary.rename(path)
            report.update(status="built", table_path=str(path), table_sha256=file_hash(path), table_bytes=path.stat().st_size)
        except Exception as error:
            report.update(status="failed", error_type=type(error).__name__, error=str(error))
        finally:
            report["elapsed_seconds"] = time.perf_counter() - started
            report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            json.dump(report, output, indent=2)
            output.write("\n")
    print(json.dumps(report), flush=True)
    return int(report["status"] != "built")


if __name__ == "__main__":
    raise SystemExit(main())