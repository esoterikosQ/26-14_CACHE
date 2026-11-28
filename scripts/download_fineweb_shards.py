"""Download pinned FineWeb shards once and verify them against Hugging Face LFS SHA256."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from huggingface_hub import HfFileSystem

from scripts.benchmark_count_patcher import file_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--shards", nargs="*")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text())
    selected = next(item for item in sources["sources"] if item["repository"] == args.repository)
    shards = args.shards or selected["selected_shards"]
    revision = selected["resolved_revision"]
    output = args.output_root / revision
    filesystem = HfFileSystem(token=False)
    started = time.perf_counter()

    def fetch(shard):
        remote = f"datasets/{args.repository}@{revision}/{shard}"
        info = filesystem.info(remote)
        lfs = info["lfs"]
        expected = lfs["sha256"] if isinstance(lfs, dict) else lfs.sha256
        target = output / shard
        target.parent.mkdir(parents=True, exist_ok=True)
        began = time.perf_counter()
        if not target.exists():
            partial = target.with_name(target.name + ".partial")
            partial.unlink(missing_ok=True)
            filesystem.get_file(remote, str(partial))
            partial.rename(target)
        digest = file_hash(target)
        if digest != expected or target.stat().st_size != info["size"]:
            raise ValueError(f"LFS hash mismatch: {shard}")
        print(json.dumps({"shard": shard, "bytes": info["size"], "seconds": time.perf_counter() - began}), flush=True)
        return shard, digest, info["size"]

    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(fetch, shards))
    manifest_path = output / "shards.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"sha256": {}}
    manifest = {"repository": args.repository, "revision": revision,
                "sha256": {**previous["sha256"], **{shard: digest for shard, digest, _ in results}},
                "verification": "Local SHA256 equals Hugging Face LFS SHA256 and size"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"shards": len(results), "bytes": sum(size for _, _, size in results),
                      "seconds": time.perf_counter() - started}), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
