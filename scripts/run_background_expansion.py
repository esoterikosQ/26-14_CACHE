"""Run a bounded, nested-background experiment inside a remote tmux session."""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime
import gc
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import shutil
import subprocess
import sys
import time

import numpy as np

from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountTable, teacher_features
from scripts.benchmark_count_patcher import file_hash
from scripts.fit_count_patcher import block_manifest_hash, boundary_metrics, evaluate_threshold, load_background, load_chunks, query_contexts
from scripts.prepare_english_data import deduplicate, length_band, stratified_order, take_bytes


def write_json(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")


def record_progress(plan, run, source, stage, details, started):
    entry = f"\n## {datetime.now().astimezone().isoformat(timespec='seconds')} / {plan['run_id']} / {stage}\n\n"
    entry += f"- Server tmux: `{plan['tmux_session']}`; elapsed: {time.perf_counter() - started:.1f}s.\n"
    entry += f"- Result: {json.dumps(details, ensure_ascii=False)}\n"
    for path in (source / "log.md", run / "progress.md"):
        with path.open("a") as stream:
            stream.write(entry)
            stream.flush()


def expanded_background(existing, candidates, target, seed):
    protected = [document for split in existing.values() for document in split]
    retained, rejected = deduplicate(protected + candidates, seed)
    protected_hashes = {document["text_sha256"] for document in protected}
    if not protected_hashes.issubset({document["text_sha256"] for document in retained}):
        raise ValueError("Existing splits are not disjoint under the declared deduplication policy")
    background = list(existing["background"])
    size = sum(len(document["text"].encode("utf-8")) for document in background)
    if target <= size:
        raise ValueError("Expanded background must exceed the original size")
    available = [document for document in retained if document["text_sha256"] not in protected_hashes]
    additional, _ = take_bytes(stratified_order(available, random.Random(seed)), target - size)
    return background + additional, rejected


def prepare(plan, config, run, baseline, source):
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as parquet

    started = time.perf_counter()
    dataset = Path(config["work_root"]) / config["dataset_directory"] / config["run_id"]
    manifest = json.loads((dataset / "manifest.json").read_text())
    existing = {}
    for split in ("background", "train", "validation", "test", "wikipedia_test"):
        path = dataset / f"{split}.jsonl"
        if file_hash(path) != manifest["splits"][split]["file_sha256"]:
            raise ValueError("Existing split hash changed")
        with path.open() as stream:
            existing[split] = [json.loads(line) for line in stream]
    parent_identity = None
    if plan.get("parent_background_run_directory"):
        parent = Path(config["work_root"]) / plan["parent_background_run_directory"]
        parent_report = json.loads((parent / "data_preparation.json").read_text())
        if file_hash(parent / "background.jsonl") != parent_report["file_sha256"]:
            raise ValueError("Parent background hash changed")
        with (parent / "background.jsonl").open() as stream:
            parent_documents = [json.loads(line) for line in stream]
        if not {item["text_sha256"] for item in existing["background"]}.issubset({item["text_sha256"] for item in parent_documents}):
            raise ValueError("Parent background does not contain the original background")
        existing["background"] = parent_documents
        parent_identity = {"run": str(parent), "report_sha256": file_hash(parent / "data_preparation.json"), "file_sha256": parent_report["file_sha256"]}
    sources = json.loads((source / plan["sources"]).read_text())
    if sources["config_sha256"] != file_hash(source / plan["baseline_config"]):
        raise ValueError("Source/config identity changed")
    selected_source = next(item for item in sources["sources"] if item["repository"] == config["data"]["fineweb_repository"])
    target = plan["background_utf8_bytes"]
    remaining = target - sum(len(document["text"].encode("utf-8")) for document in existing["background"])
    if remaining <= 0:
        raise ValueError("Expanded target must exceed parent background")
    per_shard = math.ceil(2 * remaining / len(selected_source["selected_shards"]))
    generator = random.Random(plan["sampling_seed"])
    filesystem = HfFileSystem(token=False)
    candidates = []
    row_groups_read = []
    for shard in selected_source["selected_shards"]:
        remote = f"datasets/{selected_source['repository']}@{selected_source['resolved_revision']}/{shard}"
        selected_bytes = 0
        with filesystem.open(remote, "rb", block_size=2**20) as stream:
            reader = parquet.ParquetFile(stream)
            row_groups = list(range(reader.num_row_groups))
            generator.shuffle(row_groups)
            for row_group in row_groups:
                rows = reader.read_row_group(row_group, columns=["text", "id", "url"]).to_pylist()
                positions = list(range(len(rows)))
                generator.shuffle(positions)
                row_groups_read.append({"shard": shard, "row_group": row_group})
                for position in positions:
                    row = rows[position]
                    text = row["text"]
                    if not isinstance(text, str) or not text.strip():
                        continue
                    raw = text.encode("utf-8")
                    if not 256 <= len(raw) <= 65536:
                        continue
                    candidates.append({
                        "source": selected_source["repository"], "revision": selected_source["resolved_revision"],
                        "shard": shard, "row_group": row_group, "row_in_group": position,
                        "document_id": row["id"], "url": row["url"], "text": text,
                        "text_sha256": hashlib.sha256(raw).hexdigest(),
                    })
                    selected_bytes += len(raw)
                    if selected_bytes >= per_shard:
                        break
                if selected_bytes >= per_shard:
                    break
        if selected_bytes < per_shard:
            raise ValueError("Insufficient candidate bytes in pinned shard")
        print(json.dumps({"stage": "sample", "shard": shard, "candidate_bytes": selected_bytes}), flush=True)
        record_progress(plan, run, source, "Shard sampled", {"shard": shard, "candidate_bytes": selected_bytes}, started)
    documents, rejected = expanded_background(existing, candidates, target, config["seed"])
    path = run / "background.jsonl"
    with path.open("x") as stream:
        for document in documents:
            stream.write(json.dumps(document, ensure_ascii=False) + "\n")
    report = {
        "status": "prepared", "run_id": plan["run_id"], "documents": len(documents),
        "utf8_bytes": sum(len(document["text"].encode("utf-8")) for document in documents),
        "length_bands": dict(Counter(length_band(document) for document in documents)),
        "candidate_documents": len(candidates), "duplicates_removed": rejected,
        "source": selected_source, "row_groups_read": row_groups_read,
        "original_background_documents_retained": len(existing["background"]),
        "parent_background": parent_identity,
        "original_split_hashes": {split: details["file_sha256"] for split, details in manifest["splits"].items()},
        "deduplication": "Same normalized-text/URL and 5-word MinHash128 LSH .8 policy; existing five splits protected; approximate, not exhaustive",
        "file_sha256": file_hash(path), "elapsed_seconds": time.perf_counter() - started,
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    write_json(run / "data_preparation.json", report)
    return report


def build_blocks(plan, config, run, source, preparation):
    started = time.perf_counter()
    block_limit = plan["background_block_utf8_bytes"]
    if type(block_limit) is not int or block_limit <= 0:
        raise ValueError("Block byte budget must be positive")
    directory = run / "background_blocks"
    directory.mkdir(exist_ok=False)
    count_config = CountConfig(max_context=8)
    table = CountTable(count_config)
    blocks = []
    documents = input_ids = block_bytes = block_documents = total_bytes = total_storage = 0
    budgets = config["budgets"]

    def save_block():
        nonlocal table, block_bytes, block_documents, total_storage
        root = Path(config["work_root"])
        if shutil.disk_usage(root).free < budgets["minimum_free_disk_gib"] * 2**30:
            raise RuntimeError("Disk headroom budget exhausted")
        path = directory / f"block-{len(blocks):05d}.jsonl"
        table.freeze().save(path)
        uncompressed_bytes = path.stat().st_size
        compression = "none"
        if plan.get("compress_background_blocks"):
            compressed = path.with_suffix(".jsonl.gz")
            with path.open("rb") as input_stream, gzip.open(compressed, "xb", compresslevel=1) as output_stream:
                shutil.copyfileobj(input_stream, output_stream, length=2**20)
            path.unlink()
            path = compressed
            compression = "gzip"
        metadata = {
            "table_path": str(path), "table_sha256": file_hash(path), "table_bytes": path.stat().st_size,
            "compression": compression, "uncompressed_table_bytes": uncompressed_bytes,
            "documents": block_documents, "utf8_bytes": block_bytes,
            "contexts": len(table._rows), "edges": sum(len(row) for row in table._rows.values()),
        }
        write_json(path.with_suffix(".metadata.json"), metadata)
        blocks.append(metadata)
        total_storage += metadata["table_bytes"]
        record_progress(plan, run, source, "Background block saved", {**metadata, "completed_documents": documents, "completed_utf8_bytes": total_bytes, "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}, started)
        print(json.dumps({"stage": "build_block", "blocks": len(blocks), "documents": documents, "utf8_bytes": total_bytes, "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}), flush=True)
        if total_storage > budgets["maximum_new_artifact_storage_gib"] * 2**30 or shutil.disk_usage(root).free < budgets["minimum_free_disk_gib"] * 2**30:
            raise RuntimeError("Background storage budget exceeded")
        table = None
        gc.collect()
        table = CountTable(count_config)
        block_bytes = block_documents = 0

    with (run / "background.jsonl").open() as stream:
        for line in stream:
            document = json.loads(line)
            raw = document["text"].encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != document["text_sha256"]:
                raise ValueError("Source text hash mismatch")
            table.add_document([1] + [value + 4 for value in raw])
            documents += 1
            input_ids += len(raw) + 1
            total_bytes += len(raw)
            block_bytes += len(raw)
            block_documents += 1
            if block_bytes >= block_limit:
                save_block()
    if block_documents:
        save_block()
    if documents != preparation["documents"] or total_bytes != preparation["utf8_bytes"]:
        raise ValueError("Background totals mismatch")
    report = {
        "status": "built", "run_id": plan["run_id"], "storage": "document_blocks_v1",
        "count_config": asdict(count_config), "documents": documents, "input_ids": input_ids,
        "utf8_bytes": total_bytes, "blocks": blocks, "table_sha256": block_manifest_hash(blocks),
        "table_bytes": total_storage, "block_context_rows": sum(block["contexts"] for block in blocks),
        "protocol": "Whole documents per block; BOS plus UTF-8 IDs, no appended EOS; no pruning. Repeated contexts are summed across blocks, not distinct global context counts.",
        "elapsed_seconds": time.perf_counter() - started,
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    write_json(run / "background_build.json", report)
    return report


def build(plan, config, run, baseline, source):
    started = time.perf_counter()
    preparation = json.loads((run / "data_preparation.json").read_text())
    path = run / "background.jsonl"
    if file_hash(path) != preparation["file_sha256"]:
        raise ValueError("Expanded source hash mismatch")
    if plan.get("background_block_utf8_bytes"):
        return build_blocks(plan, config, run, source, preparation)
    table = CountTable(CountConfig(max_context=8))
    documents = input_ids = 0
    with path.open() as stream:
        for line in stream:
            document = json.loads(line)
            raw = document["text"].encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != document["text_sha256"]:
                raise ValueError("Source text hash mismatch")
            tokens = [1] + [value + 4 for value in raw]
            table.add_document(tokens)
            documents += 1
            input_ids += len(tokens)
            if documents % 2000 == 0:
                print(json.dumps({"stage": "build", "documents": documents, "contexts": len(table._rows), "rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}), flush=True)
    if documents != preparation["documents"]:
        raise ValueError("Background document count mismatch")
    table.freeze()
    build_seconds = time.perf_counter() - started
    destination = run / "background_k8.jsonl"
    table.save(destination)
    report = {
        "status": "built", "run_id": plan["run_id"], "count_config": asdict(table.config),
        "documents": documents, "input_ids": input_ids, "utf8_bytes": preparation["utf8_bytes"],
        "contexts": len(table._rows), "edges": sum(len(row) for row in table._rows.values()),
        "table_path": str(destination), "table_sha256": file_hash(destination), "table_bytes": destination.stat().st_size,
        "build_seconds": build_seconds, "elapsed_seconds": time.perf_counter() - started,
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    write_json(run / "background_build.json", report)
    return report


def comparison_parent(plan, config, baseline):
    if plan.get("comparison_run_directory"):
        parent = Path(config["work_root"]) / plan["comparison_run_directory"]
        return parent, parent / "fit/report.json"
    return baseline, baseline / "fits/k8_wunlimited/report.json"


def verify(plan, config, run, baseline, source):
    started = time.perf_counter()
    parent, previous_path = comparison_parent(plan, config, baseline)
    previous = json.loads(previous_path.read_text())
    labels = json.loads((baseline / "label_generation.json").read_text())
    validation = load_chunks(baseline, "validation", labels)
    train = load_chunks(baseline, "train", labels)
    offsets = np.cumsum([0] + [len(chunk["labels"]) - 2 for chunk in train])
    selected_indices = sorted(set(list(range(min(3, len(train)))) + list(range(max(0, len(train) - 3), len(train)))))
    train = [train[index] for index in selected_indices]
    background_report = json.loads((parent / "background_build.json").read_text())
    if background_report["table_sha256"] != previous["background_sha256"]:
        raise ValueError("Parent background identity changed")
    if file_hash(baseline / "label_generation.json") != previous["label_report_sha256"]:
        raise ValueError("Parent labels changed")
    count_config = CountConfig(**previous["count_config"])
    required = query_contexts(train + validation, count_config)
    full = None
    reference_features = None
    if background_report.get("storage") == "document_blocks_v1":
        blocked = background_report
        reference_path = previous_path.parent / "train_features.npy"
        if file_hash(reference_path) != previous["feature_artifacts"]["train_features.npy"]:
            raise ValueError("Parent training features changed")
        reference_features = np.load(reference_path, mmap_mode="r", allow_pickle=False)
    else:
        full = load_background(background_report)
        block = {"table_path": background_report["table_path"], "table_sha256": background_report["table_sha256"]}
        blocked = {"storage": "document_blocks_v1", "blocks": [block], "table_sha256": block_manifest_hash([block]), "count_config": background_report["count_config"]}
    projected = load_background(blocked, required)
    rule = BoundaryRule(**previous["selected_rule"])
    for index, chunk in zip(selected_indices, train):
        features, mask = teacher_features(chunk["input_ids"], chunk["labels"], config=count_config, mean_patch_length=rule.mean_patch_length, background=projected)
        if full is not None:
            original_features, original_mask = teacher_features(chunk["input_ids"], chunk["labels"], config=count_config, mean_patch_length=rule.mean_patch_length, background=full)
            np.testing.assert_array_equal(original_features, features)
            np.testing.assert_array_equal(original_mask, mask)
        else:
            np.testing.assert_array_equal(reference_features[offsets[index]:offsets[index + 1]], features[mask])
    if full is not None:
        original, original_counts = evaluate_threshold(validation, count_config, rule, full, details=True)
    else:
        original, original_counts = previous["validation"], np.asarray(previous["validation_document_counts"])
    reduced, reduced_counts = evaluate_threshold(validation, count_config, rule, projected, details=True)
    if original["document_ids"] != reduced["document_ids"]:
        raise ValueError("Parent validation document order changed")
    np.testing.assert_array_equal(original_counts, reduced_counts)
    for key in ("f1", "entropy_mae", "entropy_rmse", "log_loss", "auprc_average_precision"):
        if original[key] != reduced[key] or original[key] != previous["validation"][key]:
            raise ValueError("Projected background changed baseline validation")
    report = {
        "status": "verified", "parent_report_sha256": file_hash(previous_path),
        "validation_f1": original["f1"], "validation_documents": len(original_counts),
        "training_feature_chunks": len(train), "required_contexts": len(required),
        "loaded_contexts": len(projected._rows), "full_contexts": len(full._rows) if full is not None else None,
        "verification_kind": "full_table_equivalence" if full is not None else "block_parent_saved_features_and_validation_replay",
        "elapsed_seconds": time.perf_counter() - started,
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    write_json(run / "storage_equivalence.json", report)
    return report


def compare(plan, config, run, baseline, source):
    parent, previous_path = comparison_parent(plan, config, baseline)
    previous = json.loads(previous_path.read_text())
    current = json.loads((run / "fit/report.json").read_text())
    if current["status"] not in ("validation_gate_passed", "validation_gate_failed"):
        raise ValueError("Expanded-background fitting did not complete")
    labels = json.loads((baseline / "label_generation.json").read_text())
    if current["label_report_sha256"] != file_hash(baseline / "label_generation.json"):
        raise ValueError("Label report changed")
    background_report = json.loads((parent / "background_build.json").read_text())
    if background_report["table_sha256"] != previous["background_sha256"]:
        raise ValueError("Baseline background changed")
    chunks = load_chunks(baseline, "validation", labels)
    required = query_contexts(chunks, CountConfig(**previous["count_config"]))
    table = load_background(background_report, required)
    metrics, old_counts = evaluate_threshold(chunks, CountConfig(**previous["count_config"]), BoundaryRule(**previous["selected_rule"]), table, details=True)
    if abs(metrics["f1"] - previous["validation"]["f1"]) > 1e-12:
        raise ValueError("Baseline F1 replay mismatch")
    if metrics["document_ids"] != current["validation"]["document_ids"]:
        raise ValueError("Paired document order differs")
    new_counts = np.asarray(current["validation_document_counts"], dtype=np.int64)
    generator = np.random.default_rng(config["seed"])
    differences = []
    for _ in range(config["gates"]["bootstrap_replicates"]):
        indices = generator.integers(0, len(old_counts), size=len(old_counts))
        differences.append(boundary_metrics(new_counts[indices].sum(axis=0))["f1"] - boundary_metrics(old_counts[indices].sum(axis=0))["f1"])
    selected = ("f1", "precision", "recall", "entropy_mae", "entropy_rmse", "entropy_spearman", "log_loss", "auprc_average_precision", "candidate_patch_count", "teacher_patch_count", "candidate_mean_patch_length")
    report = {
        "status": "compared", "run_id": plan["run_id"],
        "comparison_parent": str(parent),
        "baseline_report_sha256": file_hash(previous_path), "candidate_report_sha256": file_hash(run / "fit/report.json"),
        "baseline": {name: previous["validation"][name] for name in selected},
        "expanded": {name: current["validation"][name] for name in selected},
        "baseline_threshold": previous["selected_rule"]["threshold"], "expanded_threshold": current["selected_rule"]["threshold"],
        "f1_difference": current["validation"]["f1"] - previous["validation"]["f1"],
        "paired_document_bootstrap_difference_95ci": np.quantile(differences, [0.025, 0.975]).tolist(),
        "baseline_replay_matches": True, "documents": len(old_counts),
        "quality_gate_passed": current["validation"]["f1"] >= config["gates"]["minimum_validation_f1"],
        "limitations": "Same validation reused for threshold selection; descriptive paired interval, not independent test evidence. Sampling composition may change with volume. No downstream BPB/speed or heldout evaluation.",
    }
    write_json(run / "comparison.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--stage", choices=("verify", "prepare", "build", "compare"))
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    plan = json.loads(args.plan.read_text())
    config_path = source / plan["baseline_config"]
    config = json.loads(config_path.read_text())
    root = Path(config["work_root"])
    run = root / "runs" / plan["run_id"]
    baseline = root / config["run_directory"]
    resource.setrlimit(resource.RLIMIT_AS, (config["budgets"]["peak_host_ram_gib"] * 2**30,) * 2)
    if args.stage:
        result = {"verify": verify, "prepare": prepare, "build": build, "compare": compare}[args.stage](plan, config, run, baseline, source)
        print(json.dumps({key: value for key, value in result.items() if key in ("status", "documents", "utf8_bytes", "f1_difference", "peak_host_rss_bytes")}), flush=True)
        return 0
    if not os.environ.get("TMUX"):
        raise RuntimeError("Long experiment must run inside tmux")
    if shutil.disk_usage(root).free < config["budgets"]["minimum_free_disk_gib"] * 2**30:
        raise RuntimeError("Insufficient free disk")
    run.mkdir(exist_ok=False)
    write_json(run / "plan.json", plan)
    started = time.perf_counter()
    log_path = source / "log.md"

    def record(stage, details):
        record_progress(plan, run, source, stage, details, started)

    report = {"run_id": plan["run_id"], "status": "running", "plan_sha256": file_hash(args.plan), "baseline_config_sha256": file_hash(config_path), "stages": []}
    report["code_sha256"] = {str(path.relative_to(source)): file_hash(path) for path in (Path(__file__).resolve(), source / "scripts/fit_count_patcher.py", source / "src/phdq_blt_cache/count_patcher.py")}
    record("Started", {"target_utf8_bytes": plan["background_utf8_bytes"], "next": "Nested background sampling", "wall_clock_limit": None, "host_ram_gib": config["budgets"]["peak_host_ram_gib"]})
    try:
        stages = [("prepare", "data_preparation.json"), ("build", "background_build.json"), ("fit", "fit/report.json"), ("compare", "comparison.json")]
        if plan.get("verify_projection"):
            stages.insert(0, ("verify", "storage_equivalence.json"))
        for stage, artifact in stages:
            record(stage + " started", {"artifact": str(run / artifact)})
            command = [sys.executable, "-m", "scripts.run_background_expansion", "--plan", str(args.plan.resolve()), "--stage", stage]
            if stage == "fit":
                command = [sys.executable, "-m", "scripts.fit_count_patcher", "--config", str(config_path), "--window", "unlimited", "--background-report", str(run / "background_build.json"), "--output-directory", str(run / "fit"), "--progress-log", str(log_path), "--no-time-limit"]
            subprocess.run(command, cwd=source, check=True)
            result = json.loads((run / artifact).read_text())
            report["stages"].append({"stage": stage, "artifact": str(run / artifact), "sha256": file_hash(run / artifact)})
            record(stage + " completed", {key: value for key, value in result.items() if key in ("status", "documents", "utf8_bytes", "contexts", "table_bytes", "elapsed_seconds", "peak_host_rss_bytes", "f1_difference", "quality_gate_passed")})
            if shutil.disk_usage(root).free < config["budgets"]["minimum_free_disk_gib"] * 2**30:
                raise RuntimeError("Disk headroom budget exhausted")
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        record("Failure or blocker", {"error": str(error), "next": "Preserve artifacts and inspect failure; no automatic model change"})
    finally:
        report["elapsed_seconds"] = time.perf_counter() - started
        write_json(run / "run_report.json", report)
        record("Finished", {"status": report["status"], "report": str(run / "run_report.json"), "next": "Review measured comparison or failure"})
    return int(report["status"] != "completed")


if __name__ == "__main__":
    raise SystemExit(main())