"""Alternate isolated 8/24-thread workers on the saved research workloads."""

import argparse
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

from scripts.benchmark_count_patcher import file_hash


def write_report(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")


def worker(args):
    import numpy as np
    from phdq_blt_cache.count_patcher import CountConfig, CountTable, fit_boundary
    from scripts.fit_count_patcher import average_precision

    if os.environ.get("OPENBLAS_NUM_THREADS") != str(args.threads):
        raise RuntimeError("BLAS thread count must be set before worker launch")
    os.nice(10)
    parent = json.loads((args.parent / "fit/report.json").read_text())
    feature_path, label_path = [args.parent / "fit" / name for name in ("train_features.npy", "train_labels.npy")]
    for path in (feature_path, label_path):
        if file_hash(path) != parent["feature_artifacts"][path.name]:
            raise ValueError("Parent feature identity changed")
    features = np.load(feature_path, allow_pickle=False)
    labels = np.load(label_path, allow_pickle=False)
    with np.load(args.replay / "validation_replay.npz", allow_pickle=False) as replay:
        scores, targets = replay["scores"], replay["labels"]
    diagnostic = json.loads((args.replay / "validation_replay_mismatch.json").read_text())
    if file_hash(args.replay / "validation_replay.npz") != diagnostic["replay_sha256"]:
        raise ValueError("Replay identity changed")
    average_precision(scores, targets)
    ap_samples = []
    ap_values = []
    for repeat in range(3):
        started = time.perf_counter()
        value = average_precision(scores, targets)
        ap_samples.append(time.perf_counter() - started)
        ap_values.append(value)
    fit_boundary(features, labels, rho=0.001)
    fit_samples = []
    fits = []
    for repeat in range(2):
        started = time.perf_counter()
        result = fit_boundary(features, labels, rho=0.001)
        fit_samples.append(time.perf_counter() - started)
        fits.append(result)
    documents = []
    raw_bytes = 0
    with (args.parent / "background.jsonl").open() as stream:
        for line in stream:
            document = json.loads(line)
            raw = document["text"].encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != document["text_sha256"]:
                raise ValueError("Background text identity changed")
            documents.append(raw)
            raw_bytes += len(raw)
            if raw_bytes >= args.count_bytes:
                break
    if raw_bytes < args.count_bytes:
        raise ValueError("Insufficient whole-document count input")
    started = time.perf_counter()
    table = CountTable(CountConfig(max_context=8))
    for raw in documents:
        table.add_document([1] + [value + 4 for value in raw])
    table.freeze()
    count_seconds = time.perf_counter() - started
    digest = hashlib.sha256()
    for context, row in sorted(table._rows.items()):
        digest.update(len(context).to_bytes(2, "little") + context)
        for token_id, count in sorted(row.items()):
            digest.update(token_id.to_bytes(2, "little") + count.to_bytes(8, "little"))
    write_report(args.output, {
        "threads": args.threads, "nice": os.nice(0), "training_positions": len(labels),
        "ap_seconds": ap_samples, "ap_values": ap_values,
        "fit_seconds": fit_samples, "fits": fits,
        "count_seconds": count_seconds, "count_documents": len(documents), "count_utf8_bytes": raw_bytes,
        "count_sha256": digest.hexdigest(), "contexts": len(table._rows),
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--count-bytes", type=int, default=1000000)
    parser.add_argument("--threads", type=int, choices=(8, 24))
    args = parser.parse_args()
    if args.rounds < 2 or args.count_bytes < 1:
        parser.error("At least two rounds and positive count bytes required")
    if args.threads:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    samples = []
    for round_index in range(args.rounds):
        for threads in ((8, 24) if round_index % 2 == 0 else (24, 8)):
            path = args.output / f"round-{round_index}-{threads}.json"
            env = {**os.environ, "OPENBLAS_NUM_THREADS": str(threads)}
            subprocess.run([sys.executable, "-m", "scripts.benchmark_blas_threads", "--parent", str(args.parent),
                            "--replay", str(args.replay), "--output", str(path), "--threads", str(threads),
                            "--count-bytes", str(args.count_bytes)], env=env, check=True)
            sample = json.loads(path.read_text())
            samples.append(sample)
            print(json.dumps({"round": round_index, "threads": threads, "ap_median": statistics.median(sample["ap_seconds"]),
                              "fit_median": statistics.median(sample["fit_seconds"]), "count_seconds": sample["count_seconds"]}), flush=True)
    if len({(sample["count_sha256"], sample["count_documents"], sample["count_utf8_bytes"]) for sample in samples}) != 1:
        raise AssertionError("Count outputs or input sizes differ")
    summary = {}
    for threads in (8, 24):
        selected = [sample for sample in samples if sample["threads"] == threads]
        summary[str(threads)] = {
            "ap_median_seconds": statistics.median([value for sample in selected for value in sample["ap_seconds"]]),
            "fit_median_seconds": statistics.median([value for sample in selected for value in sample["fit_seconds"]]),
            "count_median_seconds": statistics.median([sample["count_seconds"] for sample in selected]),
            "ap_values": sorted({value for sample in selected for value in sample["ap_values"]}),
        }
    coefficients = {threads: [result["coefficients"] for sample in samples if sample["threads"] == threads for result in sample["fits"]]
                    for threads in (8, 24)}
    maximum_difference = max(abs(left - right) for first in coefficients[8] for second in coefficients[24] for left, right in zip(first, second))
    result = {"status": "completed", "summary": summary,
              "speedup_24_over_8": {name: summary["8"][name] / summary["24"][name] for name in ("ap_median_seconds", "fit_median_seconds", "count_median_seconds")},
              "maximum_fit_coefficient_difference": maximum_difference, "count_outputs_exact": True,
              "rounds": args.rounds, "samples": samples, "elapsed_seconds": time.perf_counter() - started,
              "parent_report_sha256": file_hash(args.parent / "fit/report.json"),
              "replay_sha256": file_hash(args.replay / "validation_replay.npz"),
              "benchmark_sha256": file_hash(Path(__file__)), "python": sys.version, "logical_cpus": os.cpu_count(),
              "host": platform.node(), "limitations": "Concurrent 10GB parent verification remains running. Nice +10 benchmark workers, sequential isolated processes, alternating order. Warm AP/fit; count timer excludes parsing and fingerprinting. Small count prefix, no full 10GB ETA or new validation rollout. No running experiment or acceptance policy changed."}
    write_report(args.output / "report.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}), flush=True)


if __name__ == "__main__":
    main()