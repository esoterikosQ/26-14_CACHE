"""T05 bounded development-only resource pilot on the declared research host."""

import argparse
from dataclasses import asdict
import gc
import hashlib
import json
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time

import numpy as np

from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountModel, CountTable, SequentialPatcher, rollout


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def samples(path, limit, byte_cap):
    selected = []
    with path.open() as stream:
        for line in stream:
            document = json.loads(line)
            raw = document["text"].encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != document["text_sha256"]:
                raise ValueError("Source text hash mismatch")
            selected.append({
                "document_id": document["document_id"], "text_sha256": document["text_sha256"],
                "input_ids": [1] + [value + 4 for value in raw[:byte_cap]],
                "utf8_bytes": min(len(raw), byte_cap),
            })
            if len(selected) == limit:
                break
    if len(selected) != limit:
        raise ValueError("Insufficient pilot documents")
    return selected


def summary(durations):
    return {
        "median_ms": statistics.median(durations), "mean_ms": statistics.mean(durations),
        "stdev_ms": statistics.pstdev(durations), "p95_ms": float(np.percentile(durations, 95)),
        "runs_ms": durations,
    }


def measure(callback, warmup, repetitions, synchronize=lambda: None):
    durations = []
    for repetition in range(warmup + repetitions):
        synchronize()
        started = time.perf_counter()
        callback()
        synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        if repetition >= warmup:
            durations.append(elapsed)
    return summary(durations)


def candidate_worker(config, maximum):
    resource.setrlimit(resource.RLIMIT_AS, (24 * 2**30, 24 * 2**30))
    dataset = Path(config["work_root"]) / config["dataset_directory"] / config["run_id"]
    background_docs = samples(dataset / "background.jsonl", 4, 1023)
    development = samples(dataset / "train.jsonl", 4, 1023)
    count_config = CountConfig(max_context=maximum)
    baseline_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    started = time.perf_counter()
    table = CountTable(count_config)
    for document in background_docs:
        table.add_document(document["input_ids"])
    table.freeze()
    build_seconds = time.perf_counter() - started
    built_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    source_bytes = sum(document["utf8_bytes"] for document in background_docs)
    started = time.perf_counter()
    serialized_bytes = sum(len(part.encode("utf-8")) for part in json.JSONEncoder(separators=(",", ":")).iterencode(table.to_dict()))
    serialization_seconds = time.perf_counter() - started
    rule = BoundaryRule((-4, 0.1, 0, 1, 0.1), 4)
    baseline = config["baseline"]
    cases = []
    for window in (1024, None):
        current_config = CountConfig(max_context=maximum, window=window)

        def document_pass():
            for document in development:
                rollout(document["input_ids"], config=current_config, rule=rule, background=table)

        def incremental_pass():
            for document in development:
                patcher = SequentialPatcher(current_config, rule, table)
                patcher.append(document["input_ids"][:64], start_position=0)
                patcher.predict_boundary()
                for length in range(65, 129):
                    patcher.append(document["input_ids"][length - 1:length], start_position=length - 1)
                    patcher.predict_boundary()

        document_timing = measure(document_pass, baseline["warmup_repetitions"], baseline["timed_repetitions"])
        incremental_timing = measure(incremental_pass, baseline["warmup_repetitions"], baseline["timed_repetitions"])
        model = CountModel(current_config, table)
        update_seconds = query_seconds = 0.0
        for token_id in development[0]["input_ids"]:
            started = time.perf_counter()
            model.features()
            query_seconds += time.perf_counter() - started
            started = time.perf_counter()
            model.observe(token_id)
            update_seconds += time.perf_counter() - started
        count = len(development[0]["input_ids"])
        cases.append({
            "config": asdict(current_config), "document": document_timing, "incremental": incremental_timing,
            "query_us_per_id": query_seconds / count * 1e6, "update_us_per_id": update_seconds / count * 1e6,
            "online_contexts_after_one_document": len(model.online._rows),
            "projected_one_label_feature_pass_seconds": document_timing["median_ms"] / 1000
            * config["data"]["label_utf8_bytes"] / sum(item["utf8_bytes"] for item in development),
        })
        del model
        gc.collect()
    scale = config["data"]["background_utf8_bytes"] / source_bytes
    return {
        "status": "measured", "max_context": maximum, "background_sample_bytes": source_bytes,
        "background_sample_ids": [{key: value for key, value in item.items() if key != "input_ids"} for item in background_docs],
        "development_sample_ids": [{key: value for key, value in item.items() if key != "input_ids"} for item in development],
        "background_contexts": len(table._rows), "background_edges": sum(len(row) for row in table._rows.values()),
        "build_seconds": build_seconds, "serialization_seconds": serialization_seconds, "serialized_bytes": serialized_bytes,
        "baseline_rss_bytes": baseline_rss, "built_rss_bytes": built_rss,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "linear_projection_warning": "Screening extrapolation, not a bound: context diversity and document lengths differ at full scale",
        "projected_background_rss_increment_bytes": max(0, built_rss - baseline_rss) * scale,
        "projected_background_serialized_bytes": serialized_bytes * scale,
        "projected_background_build_seconds": build_seconds * scale,
        "cases": cases,
    }


def teacher_measurements(config, project):
    import torch

    sys.path.insert(0, str(project.resolve()))
    from blt_hf.model import load_model
    from transformers import AutoTokenizer

    torch.set_num_threads(config["budgets"]["cpu_threads"])
    torch.cuda.set_device(config["budgets"]["gpu_index"])
    baseline = config["baseline"]
    dataset = Path(config["work_root"]) / config["dataset_directory"] / config["run_id"]
    development = samples(dataset / "train.jsonl", 4, 1023)
    model = load_model(Path(baseline["model_checkpoint"]), Path(baseline["conversion_report"]), attention_mode="osc", backend="eager", device="cpu")
    model.eval().requires_grad_(False)
    model.model.patcher.to("cuda")
    tokenizer = AutoTokenizer.from_pretrained(baseline["model_checkpoint"], local_files_only=True)
    if (model.config.vocab_size, tokenizer.bos_token_id, tokenizer.eos_token_id, tokenizer.pad_token_id) != (260, 1, 2, 3):
        raise ValueError("Pinned byte protocol no longer matches model")

    def patch(token_ids):
        inputs = torch.tensor([token_ids], dtype=torch.long, device="cuda")
        entropy, lengths, _ = model.model.patcher(
            inputs, patch_size=model.config.patch_size, threshold=model.config.patching_threshold,
            max_patch_length=model.config.max_patch_length, use_cache=False,
        )
        entropy.float().cpu()
        lengths.cpu()

    def document_pass():
        for document in development:
            patch(document["input_ids"])

    def incremental_pass():
        for document in development:
            for length in range(64, 129):
                patch(document["input_ids"][:length])

    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        measured = {
            "document": measure(document_pass, baseline["warmup_repetitions"], baseline["timed_repetitions"], torch.cuda.synchronize),
            "incremental": measure(incremental_pass, baseline["warmup_repetitions"], baseline["timed_repetitions"], torch.cuda.synchronize),
        }
    measured.update(
        gpu=torch.cuda.get_device_name(), torch_version=torch.__version__,
        peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
        peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(),
        checkpoint_conversion_sha256=file_hash(baseline["conversion_report"]),
    )
    if measured["peak_gpu_reserved_bytes"] > config["budgets"]["peak_gpu_memory_gib"] * 2**30:
        raise RuntimeError("Teacher exceeded GPU budget")
    return measured


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--blt-project", type=Path)
    parser.add_argument("--worker-context", type=int, choices=(8, 32, 128, 512))
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.worker_context is not None:
        print(json.dumps(candidate_worker(config, args.worker_context)))
        return 0
    if args.blt_project is None:
        parser.error("--blt-project is required for teacher measurements")
    work_root = Path(config["work_root"])
    dataset = work_root / config["dataset_directory"] / config["run_id"]
    manifest = json.loads((dataset / "manifest.json").read_text())
    for split in ("background", "train"):
        if file_hash(dataset / f"{split}.jsonl") != manifest["splits"][split]["file_sha256"]:
            raise ValueError("Dataset hash mismatch")
    output_path = work_root / config["run_directory"] / "count_pilot.json"
    started = time.perf_counter()
    report = {
        "schema_version": 1, "stage": "T05", "run_id": config["run_id"], "status": "running",
        "config_sha256": file_hash(args.config), "data_manifest_sha256": file_hash(dataset / "manifest.json"),
        "code_sha256": {str(path): file_hash(path) for path in (Path(__file__), Path(__file__).parents[1] / "src/phdq_blt_cache/count_patcher.py")},
        "protocol": {
            "background": "First four background documents, at most 1023 UTF-8 bytes plus BOS each; count reset per document",
            "document": "First four training documents, at most 1023 UTF-8 bytes plus BOS each; no EOS appended; virtual slot included",
            "incremental": "Same training documents, prefixes 64..128 inclusive; candidate prompt processing and all reset/update/query costs included",
            "outputs": "Teacher entropy and lengths transferred to CPU; no teacher KV cache; candidate retains causal state",
            "window": "1024 input IDs or unlimited; K <= W-1; EOS is an outcome ending its segment, never in following context",
            "candidate_rule": "Unfitted fixed coefficients (-4,0.1,0,1,0.1), mean=4, tau=.5; speed only, no quality claim",
            "projection": "Small-sample linear screening only; actual bounded build is still required",
        },
        "candidates": [],
    }
    with output_path.open("x") as output:
        try:
            for maximum in (8, 32, 128, 512):
                completed = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--config", str(args.config.resolve()), "--worker-context", str(maximum)],
                    capture_output=True, text=True, timeout=600, check=True,
                )
                measured = json.loads(completed.stdout)
                report["candidates"].append(measured)
                print(json.dumps({key: measured[key] for key in ("max_context", "build_seconds", "peak_rss_bytes", "projected_background_rss_increment_bytes")}), flush=True)
            report["teacher"] = teacher_measurements(config, args.blt_project)
            feasible = []
            for candidate in report["candidates"]:
                memory_ok = candidate["projected_background_rss_increment_bytes"] < config["budgets"]["peak_host_ram_gib"] * 2**30 * 0.5
                for case in candidate["cases"]:
                    case["document_speedup"] = report["teacher"]["document"]["median_ms"] / case["document"]["median_ms"]
                    case["incremental_speedup"] = report["teacher"]["incremental"]["median_ms"] / case["incremental"]["median_ms"]
                    time_ok = candidate["projected_background_build_seconds"] + case["projected_one_label_feature_pass_seconds"] < config["budgets"]["maximum_initial_build_and_label_seconds"]
                    case["resource_screen_passed"] = memory_ok and time_ok
                    case["incremental_screen_passed"] = case["incremental_speedup"] >= config["gates"]["minimum_incremental_patcher_speedup"]
                    if case["resource_screen_passed"] and case["incremental_screen_passed"]:
                        feasible.append({"max_context": candidate["max_context"], "window": case["config"]["window"]})
            report["screened_configurations"] = feasible
            report["status"] = "measured" if feasible else "no_feasible_configuration"
        except Exception as error:
            report.update(status="failed", error_type=type(error).__name__, error=str(error))
        finally:
            report["elapsed_seconds"] = time.perf_counter() - started
            report["peak_parent_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            json.dump(report, output, indent=2)
            output.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output_path), "screened": report.get("screened_configurations"), "error": report.get("error")}), flush=True)
    return int(report["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())