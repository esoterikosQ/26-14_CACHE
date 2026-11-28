"""Build a reusable protected-split dedup index for a parent background (explicit opt-in)."""

import argparse
import json
from pathlib import Path
import resource
import time

from scripts.benchmark_count_patcher import file_hash
from scripts.disk_dedup import build_protected_index
from scripts.native_minhash import build_native
from scripts.prepare_disk_background import read_documents


def protected_paths(config, parent):
    dataset = Path(config["work_root"]) / config["dataset_directory"] / config["run_id"]
    manifest = json.loads((dataset / "manifest.json").read_text())
    paths = {}
    for split in ("background", "train", "validation", "test", "wikipedia_test"):
        paths[split] = dataset / f"{split}.jsonl"
        if file_hash(paths[split]) != manifest["splits"][split]["file_sha256"]:
            raise ValueError("Existing split hash changed")
    if parent is not None:
        report = json.loads((parent / "data_preparation.json").read_text())
        paths["background"] = parent / "background.jsonl"
        if file_hash(paths["background"]) != report["file_sha256"]:
            raise ValueError("Parent background hash changed")
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--parent-run", type=Path)
    parser.add_argument("--compress-payload", action="store_true")
    parser.add_argument("--threads", type=int, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    resource.setrlimit(resource.RLIMIT_AS, (config["budgets"]["peak_host_ram_gib"] * 2**30,) * 2)
    args.output_directory.mkdir(exist_ok=False)
    started = time.perf_counter()
    paths = protected_paths(config, args.parent_run)
    library = build_native(args.output_directory / "native")
    database = args.output_directory / "protected.sqlite"
    summary = build_protected_index({split: read_documents(path) for split, path in paths.items()}, config["seed"],
                                    database, library, compress_payload=args.compress_payload, threads=args.threads)
    source = Path(__file__).resolve().parents[1]
    report = {
        **summary, "format": "protected_dedup_index_v1", "database": database.name, "database_sha256": file_hash(database),
        "database_bytes": database.stat().st_size, "parent_run": str(args.parent_run) if args.parent_run else None,
        "split_sha256": {split: file_hash(path) for split, path in paths.items()}, "threads": args.threads,
        "native_library_sha256": file_hash(library),
        "code_sha256": {name: file_hash(source / name) for name in (
            "scripts/disk_dedup.py", "scripts/native_minhash.py", "scripts/native/minhash.cpp", "scripts/build_protected_index.py")},
        "elapsed_seconds": time.perf_counter() - started,
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    with (args.output_directory / "protected_index.json").open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("protected_documents", "background_utf8_bytes", "elapsed_seconds")}), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
