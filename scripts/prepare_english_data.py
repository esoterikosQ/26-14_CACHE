"""Sample pinned Parquet row groups and split deduplicated whole documents."""

import argparse
from collections import Counter, deque
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import resource
import shutil
import time

from datasketch import MinHash, MinHashLSH
from huggingface_hub import HfFileSystem
import pyarrow.parquet as parquet


def length_band(document):
    size = len(document["text"].encode("utf-8"))
    return "short" if size <= 1024 else "medium" if size <= 8192 else "long"


def deduplicate(documents, seed):
    index = MinHashLSH(threshold=0.8, num_perm=128)
    signatures = {}
    hashes = set()
    urls = set()
    retained = []
    rejected = Counter()
    for document in documents:
        normalized = " ".join(document["text"].casefold().split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        url = document.get("url")
        if digest in hashes or (url and url in urls):
            rejected["exact_text_or_url"] += 1
            continue
        words = normalized.split()
        shingles = {" ".join(words[offset:offset + 5]).encode("utf-8") for offset in range(max(1, len(words) - 4))}
        signature = MinHash(num_perm=128, seed=seed)
        signature.update_batch(sorted(shingles))
        if any(signature.jaccard(signatures[key]) >= 0.8 for key in index.query(signature)):
            rejected["near_duplicate"] += 1
            continue
        index.insert(digest, signature)
        signatures[digest] = signature
        hashes.add(digest)
        if url:
            urls.add(url)
        retained.append(document)
    return retained, dict(rejected)


def stratified_order(documents, randomizer):
    buckets = {}
    for band in ("short", "medium", "long"):
        group = [document for document in documents if length_band(document) == band]
        randomizer.shuffle(group)
        buckets[band] = deque(group)
    ordered = []
    while any(buckets.values()):
        for group in buckets.values():
            if group:
                ordered.append(group.popleft())
    return ordered


def background_and_label_pools(documents, fraction, randomizer):
    background = []
    labels = []
    for band in ("short", "medium", "long"):
        group = [document for document in documents if length_band(document) == band]
        randomizer.shuffle(group)
        boundary = round(len(group) * fraction)
        background.extend(group[:boundary])
        labels.extend(group[boundary:])
    return stratified_order(background, randomizer), stratified_order(labels, randomizer)


def take_bytes(documents, target):
    selected = []
    total = 0
    for document in documents:
        selected.append(document)
        total += len(document["text"].encode("utf-8"))
        if total >= target:
            return selected, documents[len(selected):]
    raise ValueError(f"Not enough deduplicated text: {total} bytes, need {target}")


def split_labels(documents, randomizer):
    splits = {"train": [], "validation": [], "test": []}
    for band in ("short", "medium", "long"):
        group = [document for document in documents if length_band(document) == band]
        randomizer.shuffle(group)
        train_end = round(len(group) * 0.8)
        validation_end = round(len(group) * 0.9)
        splits["train"].extend(group[:train_end])
        splits["validation"].extend(group[train_end:validation_end])
        splits["test"].extend(group[validation_end:])
    return splits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    sources = json.loads(args.sources.read_text())
    if sources["config_sha256"] != hashlib.sha256(args.config.read_bytes()).hexdigest():
        raise ValueError("Source manifest does not match the experiment configuration")
    if config["data"]["label_split_ratios"] != {"train": 0.8, "validation": 0.1, "test": 0.1}:
        raise ValueError("This pilot implements only the preregistered 8:1:1 split")
    root = Path(config["work_root"]).resolve()
    output = (root / config["dataset_directory"] / config["run_id"]).resolve()
    if not output.is_relative_to(root):
        raise ValueError("Dataset output must stay inside work_root")
    if shutil.disk_usage(root).free < config["budgets"]["minimum_free_disk_gib"] * 2**30:
        raise RuntimeError("Free disk budget not met")
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "run_id": config["run_id"], "status": "running",
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "sources_sha256": hashlib.sha256(args.sources.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sources": sources["sources"], "sampled_row_groups": [],
        "utf8_length_filter": [256, 65536],
        "sampling": "Random row groups and row order within each pinned shard; separate background/label pools within each length band before whole-document byte quotas",
        "deduplication": "Global casefold/whitespace-normalized SHA256 and exact URL; 5-word MinHash 128 permutations, LSH and estimated Jaccard >= 0.8; approximate detection, not an exhaustive guarantee",
        "raw_text_preserved": True,
        "whole_document_budget_overshoot_max_bytes": 65535,
        "packages": {name: importlib.metadata.version(name) for name in ("pyarrow", "datasketch", "huggingface-hub", "numpy", "scipy")},
    }
    started = time.perf_counter()
    try:
        randomizer = random.Random(config["seed"])
        filesystem = HfFileSystem(token=False)
        documents = []
        fineweb_target = config["data"]["background_utf8_bytes"] + config["data"]["label_utf8_bytes"]
        for source in sources["sources"]:
            target = fineweb_target if source["repository"] == config["data"]["fineweb_repository"] else config["data"]["wikipedia_utf8_bytes"]
            per_shard = math.ceil(2 * target / len(source["selected_shards"]))
            for shard in source["selected_shards"]:
                remote = f"datasets/{source['repository']}@{source['resolved_revision']}/{shard}"
                selected_bytes = 0
                with filesystem.open(remote, "rb", block_size=2**20) as stream:
                    reader = parquet.ParquetFile(stream)
                    row_groups = list(range(reader.num_row_groups))
                    randomizer.shuffle(row_groups)
                    for row_group in row_groups:
                        if time.perf_counter() - started > config["budgets"]["maximum_initial_build_and_label_seconds"]:
                            raise RuntimeError("Data preparation time budget exceeded")
                        rows = reader.read_row_group(row_group, columns=["text", "id", "url"]).to_pylist()
                        positions = list(range(len(rows)))
                        randomizer.shuffle(positions)
                        report["sampled_row_groups"].append({"source": source["repository"], "shard": shard, "row_group": row_group})
                        for position in positions:
                            row = rows[position]
                            text = row["text"]
                            if not isinstance(text, str) or not text.strip():
                                continue
                            size = len(text.encode("utf-8"))
                            if not 256 <= size <= 65536:
                                continue
                            documents.append({
                                "source": source["repository"], "revision": source["resolved_revision"],
                                "shard": shard, "row_group": row_group, "row_in_group": position,
                                "document_id": row["id"], "url": row["url"], "text": text,
                                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            })
                            selected_bytes += size
                            if selected_bytes >= per_shard:
                                break
                        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > config["budgets"]["peak_host_ram_gib"] * 2**30:
                            raise RuntimeError("Host RAM budget exceeded")
                        if selected_bytes >= per_shard:
                            break
                print(json.dumps({"shard": shard, "candidate_utf8_bytes": selected_bytes}), flush=True)
        report["candidate_documents"] = len(documents)
        randomizer.shuffle(documents)
        documents, rejected = deduplicate(documents, config["seed"])
        report["duplicates_removed"] = rejected
        fineweb = [document for document in documents if document["source"] == config["data"]["fineweb_repository"]]
        wikipedia = stratified_order([document for document in documents if document["source"] == config["data"]["wikipedia_repository"]], randomizer)
        background_pool, label_pool = background_and_label_pools(fineweb, config["data"]["background_utf8_bytes"] / fineweb_target, randomizer)
        background, _ = take_bytes(background_pool, config["data"]["background_utf8_bytes"])
        labels, _ = take_bytes(label_pool, config["data"]["label_utf8_bytes"])
        wiki_evaluation, _ = take_bytes(wikipedia, config["data"]["wikipedia_utf8_bytes"])
        splits = {"background": background, **split_labels(labels, randomizer), "wikipedia_test": wiki_evaluation}
        hashes = [document["text_sha256"] for split in splits.values() for document in split]
        if len(hashes) != len(set(hashes)) or any(not split for split in splits.values()):
            raise ValueError("Overlapping documents or empty split")
        report["splits"] = {}
        for name, split in splits.items():
            path = output / f"{name}.jsonl"
            with path.open("x", encoding="utf-8") as stream:
                for document in split:
                    stream.write(json.dumps(document, ensure_ascii=False) + "\n")
            report["splits"][name] = {
                "documents": len(split), "utf8_bytes": sum(len(document["text"].encode("utf-8")) for document in split),
                "length_bands": dict(Counter(length_band(document) for document in split)),
                "shards": dict(Counter(document["shard"] for document in split)),
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        report["status"] = "prepared"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
    finally:
        report["elapsed_seconds"] = time.perf_counter() - started
        report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        with (output / "manifest.json").open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    print(json.dumps({key: report[key] for key in ("status", "elapsed_seconds", "peak_host_rss_bytes")}), flush=True)
    if report["status"] == "failed":
        print(report["error"], flush=True)
    return int(report["status"] != "prepared")


if __name__ == "__main__":
    raise SystemExit(main())