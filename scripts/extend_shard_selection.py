"""Extend the pinned FineWeb shard selection with the same sorted/excluded/seeded order."""

import argparse
import json
from pathlib import Path
import random

from huggingface_hub import HfFileSystem


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--original-sources", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--total", type=int, required=True)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text())
    selected = next(item for item in catalog["sources"] if item["repository"] == args.repository)
    original = next(item for item in json.loads(args.original_sources.read_text())["sources"]
                    if item["repository"] == args.repository)["selected_shards"]
    base = f"datasets/{args.repository}@{selected['resolved_revision']}/"
    available = sorted(path[len(base):] for path in HfFileSystem(token=False).glob(base + selected["prefix"] + "*.parquet"))
    pool = [path for path in available if path not in set(original)]
    random.Random(args.seed).shuffle(pool)
    pinned = selected["selected_shards"]
    result = {
        "available": len(available), "catalog_available": selected["available_shards"],
        "excluded_original": original, "pool": len(pool),
        "reproduces_pinned_prefix": pool[:len(pinned)] == pinned,
        "selected_shards": pool[:args.total], "added_shards": pool[len(pinned):args.total],
    }
    if not result["reproduces_pinned_prefix"] or len(available) != selected["available_shards"]:
        raise SystemExit(json.dumps({**result, "error": "Selection rule does not reproduce the pinned catalog"}))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
