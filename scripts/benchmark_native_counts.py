"""Measure native count block building and projection against completed Python artifacts."""

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import time

import numpy as np

from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountTable, teacher_features
from scripts.benchmark_count_patcher import file_hash
from scripts.fit_count_patcher import block_manifest_hash, evaluate_threshold, load_background, load_chunks, query_contexts
from scripts.native_counts import NativeCounts, build_native_counts, load_projection, save_projection

MINIMUM_FREE_BYTES = 100 * 2**30


def peak_rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def log(stage, **details):
    print(json.dumps({"stage": stage, "peak_host_rss_bytes": peak_rss(), **details}), flush=True)


def decompressed_digest(path):
    digest, size = hashlib.sha256(), 0
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(2**22):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def read_blocks(source, blocks, start, stop):
    skip = sum(block["documents"] for block in blocks[:start])
    with Path(source).open() as stream:
        for _ in range(skip):
            next(stream)
        for index in range(start, stop):
            texts = []
            for _ in range(blocks[index]["documents"]):
                document = json.loads(next(stream))
                raw = document["text"].encode("utf-8")
                if hashlib.sha256(raw).hexdigest() != document["text_sha256"]:
                    raise ValueError("Source text hash mismatch")
                texts.append(raw)
            if sum(len(text) for text in texts) != blocks[index]["utf8_bytes"]:
                raise ValueError(f"Block {index} byte total mismatch")
            yield index, texts


def build_stage(args, output):
    report = json.loads(args.background_report.read_text())
    blocks = report["blocks"]
    if block_manifest_hash(blocks) != report["table_sha256"]:
        raise ValueError("Background block manifest changed")
    config = CountConfig(**report["count_config"])
    native = NativeCounts(build_native_counts(output / "native"))
    result = {"stage": "build", "background_report_sha256": file_hash(args.background_report), "blocks": [args.start, args.stop],
              "workers": args.workers, "native_library_sha256": file_hash(native.library_path), "python_blocks": []}

    def compare(index, path):
        expected, expected_size = decompressed_digest(blocks[index]["table_path"])
        actual, actual_size = decompressed_digest(path)
        return {"block": index, "content_equal": expected == actual and expected_size == actual_size,
                "content_sha256": actual, "uncompressed_bytes": actual_size}

    for index, texts in read_blocks(args.background, blocks, args.start, args.start + args.python_blocks):
        python_started = time.perf_counter()
        table = CountTable(config)
        for text in texts:
            table.add_document([1] + [value + 4 for value in text])
        python_counted = time.perf_counter()
        plain = output / f"python-{index:05d}.jsonl"
        table.freeze().save(plain)
        with plain.open("rb") as source, gzip.open(plain.with_suffix(".jsonl.gz"), "xb", compresslevel=1) as target:
            shutil.copyfileobj(source, target, length=2**20)
        python_seconds = time.perf_counter() - python_started
        contexts, edges = len(table._rows), sum(len(row) for row in table._rows.values())
        del table
        plain.unlink()
        native_path = output / f"single-{index:05d}.jsonl.gz"
        started = time.perf_counter()
        statistics = native.build_block(texts, config, native_path, 1)
        native_seconds = time.perf_counter() - started
        python_check = compare(index, plain.with_suffix(".jsonl.gz"))
        native_check = compare(index, native_path)
        plain.with_suffix(".jsonl.gz").unlink()
        native_path.unlink()
        entry = {"block": index, "python_seconds": python_seconds, "python_count_seconds": python_counted - python_started,
                 "python_contexts": contexts, "python_edges": edges, "native_single_seconds": native_seconds,
                 "native_statistics": statistics, "python_content_equal": python_check["content_equal"],
                 "native_content_equal": native_check["content_equal"],
                 "metadata_equal": statistics == {key: blocks[index][key] for key in ("contexts", "edges", "uncompressed_table_bytes")}}
        result["python_blocks"].append(entry)
        log("python_versus_single", **entry)

    pending, built, reading_seconds = deque(), [], 0.0
    started = time.perf_counter()
    with ThreadPoolExecutor(args.workers) as pool:
        reader = read_blocks(args.background, blocks, args.start, args.stop)
        while True:
            read_started = time.perf_counter()
            item = next(reader, None)
            reading_seconds += time.perf_counter() - read_started
            if item is None:
                break
            index, texts = item
            if shutil.disk_usage(output).free < MINIMUM_FREE_BYTES:
                raise RuntimeError("Minimum free disk guard reached")
            path = output / f"block-{index:05d}.jsonl.gz"
            pending.append((index, path, pool.submit(native.build_block, texts, config, path, 1)))
            while len(pending) > args.workers:
                index, path, future = pending.popleft()
                built.append((index, path, future.result()))
        while pending:
            index, path, future = pending.popleft()
            built.append((index, path, future.result()))
    result.update(parallel_wall_seconds=time.perf_counter() - started, parallel_reading_seconds=reading_seconds,
                  parallel_peak_host_rss_bytes=peak_rss())
    log("parallel_built", blocks=len(built), seconds=result["parallel_wall_seconds"])

    def verify(item):
        index, path, statistics = item
        check = compare(index, path)
        check["metadata_equal"] = statistics == {key: blocks[index][key] for key in ("contexts", "edges", "uncompressed_table_bytes")}
        path.unlink()
        return check

    with ThreadPoolExecutor(args.workers) as pool:
        checks = list(pool.map(verify, built))
    result.update(verified_blocks=len(checks), all_content_equal=all(check["content_equal"] for check in checks),
                  all_metadata_equal=all(check["metadata_equal"] for check in checks),
                  mismatched_blocks=[check["block"] for check in checks if not (check["content_equal"] and check["metadata_equal"])],
                  block_checks=checks)
    return result


def project_stage(args, output):
    config_file = json.loads(args.config.read_text())
    baseline = Path(config_file["work_root"]) / config_file["run_directory"]
    label_report = json.loads((baseline / "label_generation.json").read_text())
    fit = json.loads(args.fit_report.read_text())
    report = json.loads(args.background_report.read_text())
    if fit["background_sha256"] != report["table_sha256"] or fit["label_report_sha256"] != file_hash(baseline / "label_generation.json"):
        raise ValueError("Fit report does not match background or labels")
    config = CountConfig(**fit["count_config"])
    train = load_chunks(baseline, "train", label_report)
    validation = load_chunks(baseline, "validation", label_report)
    required = query_contexts(train + validation, config)
    if len(required) != fit["background_loading"]["required_contexts"]:
        raise ValueError("Required context count changed")
    native = NativeCounts(build_native_counts(output / "native"))
    blocks = report["blocks"]
    result = {"stage": "project", "background_report_sha256": file_hash(args.background_report),
              "fit_report_sha256": file_hash(args.fit_report), "required_contexts": len(required),
              "workers": args.workers, "native_library_sha256": file_hash(native.library_path)}

    def subset(count, offset=0):
        selected = blocks[offset:offset + count]
        return {**report, "blocks": selected, "table_sha256": block_manifest_hash(selected)}

    started = time.perf_counter()
    expected = load_background(subset(args.python_blocks), required)
    result["python_subset_seconds"] = time.perf_counter() - started
    for workers in (1, args.workers):
        started = time.perf_counter()
        actual = load_background(subset(args.python_blocks), required, native=native, workers=workers)
        result[f"native_subset_seconds_workers{workers}"] = time.perf_counter() - started
        result[f"native_subset_equal_workers{workers}"] = (list(actual._rows.items()) == list(expected._rows.items())
                                                           and actual._totals == expected._totals)
        del actual
    result.update(python_subset_blocks=args.python_blocks, python_subset_contexts=len(expected._rows))
    del expected
    log("subset_compared", **{key: value for key, value in result.items() if key.startswith(("python_", "native_"))})

    captured = {}
    started = time.perf_counter()
    full = load_background(report, required, native=native, workers=args.workers,
                           projection_sink=lambda projection, details: captured.update(projection=projection))
    result["native_full_seconds"] = time.perf_counter() - started
    result["native_full_peak_host_rss_bytes"] = peak_rss()
    path, saved = save_projection(output / "projection-full.npz", captured["projection"], required, {
        "count_config": report["count_config"], "blocks": len(blocks), "block_manifest_sha256": report["table_sha256"],
        "background_report_sha256": file_hash(args.background_report)})
    result["full_projection"] = {"report": str(path), "report_sha256": file_hash(path), **{key: saved[key] for key in ("arrays_sha256", "contexts", "edges")}}
    log("full_projected", seconds=result["native_full_seconds"], contexts=saved["contexts"], edges=saved["edges"])

    started = time.perf_counter()
    reference = np.load(args.fit_report.parent / "train_features.npy", mmap_mode="r", allow_pickle=False)
    if file_hash(args.fit_report.parent / "train_features.npy") != fit["feature_artifacts"]["train_features.npy"]:
        raise ValueError("Reference training features changed")
    offset, equal = 0, True
    mean_length = label_report["splits"]["train"]["teacher_mean_patch_length"]
    for chunk in train:
        current, mask = teacher_features(chunk["input_ids"], chunk["labels"], config=config, mean_patch_length=mean_length, background=full)
        stop = offset + int(mask.sum())
        equal = equal and np.array_equal(current[mask], reference[offset:stop])
        offset = stop
    result.update(train_features_equal=equal and offset == len(reference), train_positions=offset,
                  feature_seconds=time.perf_counter() - started)
    rule = BoundaryRule(**fit["selected_rule"])
    metrics, document_counts = evaluate_threshold(validation, config, rule, full, details=True)
    keys = ("tp", "fp", "fn", "precision", "recall", "f1", "entropy_mae", "entropy_rmse", "entropy_spearman", "log_loss",
            "auprc_average_precision", "candidate_patch_count", "teacher_patch_count", "candidate_mean_patch_length", "document_ids")
    result.update(validation_metrics_equal={key: metrics[key] == fit["validation"][key] for key in keys},
                  validation_document_counts_equal=document_counts.tolist() == fit["validation_document_counts"],
                  validation_f1=metrics["f1"])
    log("downstream_compared", train_features_equal=result["train_features_equal"], f1=metrics["f1"])
    del full

    split = args.reuse_split
    parent = subset(split)
    captured = {}
    started = time.perf_counter()
    load_background(parent, required, native=native, workers=args.workers,
                    projection_sink=lambda projection, details: captured.update(projection=projection))
    result["native_parent_seconds"] = time.perf_counter() - started
    parent_path, _ = save_projection(output / f"projection-{split}.npz", captured["projection"], required, {
        "count_config": report["count_config"], "blocks": split, "block_manifest_sha256": parent["table_sha256"]})
    seed = load_projection(parent_path, file_hash(parent_path))
    reused = {}
    started = time.perf_counter()
    load_background(report, required, native=native, workers=args.workers, seed=seed,
                    projection_sink=lambda projection, details: reused.update(projection=projection, details=details))
    result["native_seeded_seconds"] = time.perf_counter() - started
    direct, _, _ = load_projection(path, file_hash(path))
    seeded = reused["projection"]
    result["seeded_equal_direct"] = (seeded.contexts == direct.contexts and np.array_equal(seeded.row_lengths, direct.row_lengths)
                                     and np.array_equal(seeded.tokens, direct.tokens) and np.array_equal(seeded.counts, direct.counts))
    result["seed_details"] = reused["details"]
    log("reuse_compared", seeded_equal_direct=result["seeded_equal_direct"], seconds=result["native_seeded_seconds"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("build", "project"), required=True)
    parser.add_argument("--background-report", type=Path, required=True)
    parser.add_argument("--background", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--fit-report", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int)
    parser.add_argument("--python-blocks", type=int, default=2)
    parser.add_argument("--reuse-split", type=int)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("OPENBLAS_NUM_THREADS") != "8":
        raise RuntimeError("Launch with OPENBLAS_NUM_THREADS=8")
    resource.setrlimit(resource.RLIMIT_AS, (48 * 2**30,) * 2)
    args.output_directory.mkdir(parents=False, exist_ok=False)
    started = time.perf_counter()
    result = {"status": "failed", "started_unix": time.time()}
    try:
        result.update(build_stage(args, args.output_directory) if args.stage == "build" else project_stage(args, args.output_directory))
        checks = ([result["all_content_equal"], result["all_metadata_equal"]]
                  + [entry[key] for entry in result["python_blocks"] for key in ("python_content_equal", "native_content_equal", "metadata_equal")]
                  if args.stage == "build" else
                  [result[f"native_subset_equal_workers{workers}"] for workers in (1, args.workers)]
                  + [result["train_features_equal"], result["validation_document_counts_equal"], result["seeded_equal_direct"],
                     all(result["validation_metrics_equal"].values())])
        result["status"] = "verified" if all(checks) else "mismatch"
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result.update(elapsed_seconds=time.perf_counter() - started, peak_host_rss_bytes=peak_rss(), threads=8)
        with (args.output_directory / "result.json").open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    return int(result["status"] != "verified")


if __name__ == "__main__":
    raise SystemExit(main())
