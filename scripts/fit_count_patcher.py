"""T07/T08 initial two-configuration screen; all thresholds use fresh rollouts."""

import argparse
from dataclasses import asdict
from datetime import datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import time

import numpy as np
from scipy.special import expit
from scipy.stats import spearmanr

from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountTable, checked_id, contexts, fit_boundary, rollout, teacher_features
from scripts.benchmark_count_patcher import file_hash


def confusion(prediction, labels):
    prediction = np.asarray(prediction, dtype=bool)
    labels = np.asarray(labels, dtype=bool)
    return np.array([np.count_nonzero(prediction & labels), np.count_nonzero(prediction & ~labels), np.count_nonzero(~prediction & labels)], dtype=np.int64)


def boundary_metrics(counts):
    true_positive, false_positive, false_negative = [int(value) for value in counts]
    return {
        "tp": true_positive, "fp": false_positive, "fn": false_negative,
        "precision": true_positive / max(1, true_positive + false_positive),
        "recall": true_positive / max(1, true_positive + false_negative),
        "f1": 2 * true_positive / max(1, 2 * true_positive + false_positive + false_negative),
    }


def average_precision(scores, labels):
    order = np.argsort(-scores, kind="stable")
    ranked = labels[order]
    endings = np.r_[np.flatnonzero(np.diff(scores[order])), len(scores) - 1]
    true_positive = np.cumsum(ranked)[endings]
    recall = true_positive / max(1, int(labels.sum()))
    precision = true_positive / (endings + 1)
    return float(np.dot(np.diff(np.r_[0, recall]), precision))


def load_chunks(run, split, label_report):
    manifest_path = run / "labels" / f"{split}_manifest.json"
    if file_hash(manifest_path) != label_report["splits"][split]["manifest_sha256"]:
        raise ValueError("Label manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text())
    chunks = []
    for record in manifest["chunks"]:
        path = run / "labels" / record["file"]
        if file_hash(path) != record["file_sha256"]:
            raise ValueError("Label archive hash mismatch")
        with np.load(path, allow_pickle=False) as archive:
            if str(archive["contract_sha256"]) != label_report["contract_sha256"]:
                raise ValueError("Label contract mismatch")
            chunks.append({**record, "input_ids": archive["input_ids"].copy(), "entropy": archive["entropy"].copy(), "labels": archive["labels"].copy()})
    return chunks


def query_contexts(chunks, config):
    required = {b""}
    for chunk in chunks:
        history = b""
        for value in chunk["input_ids"]:
            token_id = checked_id(value, config)
            history = (history + token_id.to_bytes(2, "little"))[-2 * config.max_context:] if config.max_context else b""
            if token_id == config.eos_id:
                history = b""
            required.update(contexts(history, config.max_context))
    return required


def block_manifest_hash(blocks):
    return hashlib.sha256(json.dumps(blocks, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_background(report, required=None, progress=None):
    if report.get("storage") != "document_blocks_v1":
        if file_hash(report["table_path"]) != report["table_sha256"]:
            raise ValueError("Background table hash mismatch")
        return CountTable.load(report["table_path"])
    blocks = report["blocks"]
    if block_manifest_hash(blocks) != report["table_sha256"]:
        raise ValueError("Background block manifest hash mismatch")
    table = CountTable(CountConfig(**report["count_config"]))
    for block in blocks:
        if file_hash(block["table_path"]) != block["table_sha256"]:
            raise ValueError("Background block hash mismatch")
        if block.get("compression", "none") not in ("none", "gzip"):
            raise ValueError("Unsupported background compression")
        opener = gzip.open if block.get("compression") == "gzip" else open
        with opener(block["table_path"], "rt") as stream:
            metadata = json.loads(next(stream))
            if metadata != {"version": 1, "config": asdict(table.config)}:
                raise ValueError("Background block configuration mismatch")
            for line in stream:
                encoded, entries = json.loads(line)
                context = bytes.fromhex(encoded)
                if required is None or context in required:
                    for token_id, count in entries:
                        table._adjust(context, token_id, count)
        if progress is not None:
            progress("Background block merged", {"path": block["table_path"], "loaded_contexts": len(table._rows)})
    return table.freeze()


def evaluate_threshold(chunks, config, rule, background, details=False):
    by_document = {}
    scores, labels, predicted_entropy, teacher_entropy = [], [], [], []
    patch_counts = []
    started = time.perf_counter()
    for chunk in chunks:
        decisions = rollout(chunk["input_ids"], config=config, rule=rule, background=background)
        predicted = np.array([decision.boundary for decision in decisions])
        counts = confusion(predicted[2:], chunk["labels"][2:])
        document = chunk["document_id"]
        by_document[document] = by_document.get(document, np.zeros(3, dtype=np.int64)) + counts
        if details:
            scores.extend(decision.score for decision in decisions[2:])
            labels.extend(chunk["labels"][2:])
            predicted_entropy.extend(decision.entropy for decision in decisions[2:])
            teacher_entropy.extend(chunk["entropy"][2:])
            patch_counts.append([int(predicted.sum()), int(chunk["labels"].sum()), len(chunk["labels"])])
    metrics = boundary_metrics(np.sum(list(by_document.values()), axis=0))
    metrics.update(threshold=rule.threshold, elapsed_seconds=time.perf_counter() - started)
    if not details:
        return metrics
    scores = np.asarray(scores)
    labels = np.asarray(labels)
    predicted_entropy = np.asarray(predicted_entropy)
    teacher_entropy = np.asarray(teacher_entropy)
    error = predicted_entropy - teacher_entropy
    clipped = np.clip(scores, 1e-15, 1 - 1e-15)
    patch_counts = np.asarray(patch_counts)
    metrics.update(
        entropy_mae=float(np.abs(error).mean()), entropy_rmse=float(np.sqrt(np.mean(error ** 2))),
        entropy_spearman=float(spearmanr(predicted_entropy, teacher_entropy).statistic),
        log_loss=float(-(labels * np.log(clipped) + (~labels) * np.log1p(-clipped)).mean()),
        auprc_average_precision=average_precision(scores, labels),
        candidate_patch_count=int(patch_counts[:, 0].sum()), teacher_patch_count=int(patch_counts[:, 1].sum()),
        candidate_mean_patch_length=float(patch_counts[:, 2].sum() / patch_counts[:, 0].sum()),
        teacher_mean_patch_length=float(patch_counts[:, 2].sum() / patch_counts[:, 1].sum()),
        mean_absolute_chunk_patch_count_error=float(np.abs(patch_counts[:, 0] - patch_counts[:, 1]).mean()),
    )
    metrics["document_ids"] = list(by_document)
    return metrics, np.asarray(list(by_document.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--window", choices=("1024", "unlimited"), required=True)
    parser.add_argument("--background-report", type=Path)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--progress-log", type=Path)
    parser.add_argument("--no-time-limit", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    budgets = config["budgets"]
    resource.setrlimit(resource.RLIMIT_AS, (budgets["peak_host_ram_gib"] * 2**30,) * 2)
    run = Path(config["work_root"]) / config["run_directory"]
    pilot = json.loads((run / "count_pilot.json").read_text())
    window = None if args.window == "unlimited" else int(args.window)
    if {"max_context": 8, "window": window} not in pilot["screened_configurations"]:
        raise ValueError("Configuration did not pass T05")
    destination = args.output_directory or run / "fits" / f"k8_w{args.window}"
    destination.mkdir(parents=True, exist_ok=False)
    label_report = json.loads((run / "label_generation.json").read_text())
    background_report_path = args.background_report or run / "background_build.json"
    background_report = json.loads(background_report_path.read_text())
    count_config = CountConfig(max_context=8, window=window)
    mean_length = label_report["splits"]["train"]["teacher_mean_patch_length"]
    report = {
        "stage": "T07-T08-initial-screen", "status": "running", "run_id": config["run_id"],
        "config_sha256": file_hash(args.config), "count_config": asdict(count_config),
        "background_report_sha256": file_hash(background_report_path),
        "label_report_sha256": file_hash(run / "label_generation.json"),
        "wall_clock_limit_seconds": None if args.no_time_limit else budgets["maximum_initial_build_and_label_seconds"],
        "teacher_mean_patch_length_from_training": mean_length,
        "selection_plan": {
            "configurations": "Only K=8 with W=1024/unlimited; alpha=kappa=lambda=eta=1; rho=.001; no test data",
            "thresholds": "Coarse 0,1/8,...,1; then nine equally spaced points within +/-1/8 of best, excluding duplicates",
            "tie_break": "Highest sequential micro F1, then larger threshold",
            "state": "Fresh counts and boundaries per chunk for every threshold; fixed feature scores are not reused",
            "bootstrap": "Original-document resampling after threshold selection; descriptive validation interval, not an unbiased test interval",
        },
        "code_sha256": {str(path): file_hash(path) for path in (Path(__file__), Path(__file__).parents[1] / "src/phdq_blt_cache/count_patcher.py")},
        "threshold_trials": [],
    }
    started = time.perf_counter()

    def progress(stage, details):
        if args.progress_log is not None:
            with args.progress_log.open("a") as stream:
                stream.write(f"\n## {datetime.now().astimezone().isoformat(timespec='seconds')} / {destination.parent.name} / {stage}\n\n")
                stream.write(f"- Output: `{destination}`; elapsed: {time.perf_counter() - started:.1f}s.\n")
                stream.write(f"- Result: {json.dumps(details, ensure_ascii=False)}\n")
                stream.flush()

    def check_budget():
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > budgets["peak_host_ram_gib"] * 2**30:
            raise RuntimeError("Host RAM budget exceeded")
        if not args.no_time_limit and time.perf_counter() - started > budgets["maximum_initial_build_and_label_seconds"]:
            raise RuntimeError("Initial screen wall-clock budget exceeded")

    with (destination / "report.json").open("x") as output:
        try:
            train_chunks = load_chunks(run, "train", label_report)
            validation_chunks = load_chunks(run, "validation", label_report)
            required = None
            if background_report.get("storage") == "document_blocks_v1":
                required = query_contexts(train_chunks + validation_chunks, count_config)
                report["background_loading"] = {"storage": "document_blocks_v1", "required_contexts": len(required), "scope": "Exact row sums for every prefix of fixed train/validation inputs, including virtual slots; all counts preserved in disk blocks; not a timing benchmark or general-purpose loaded model"}
            background = load_background(background_report, required, progress)
            del required
            report["background_load_seconds"] = time.perf_counter() - started
            report["background_sha256"] = background_report["table_sha256"]
            progress("Background loaded and verified", {"seconds": report["background_load_seconds"], "sha256": report["background_sha256"]})
            positions = label_report["splits"]["train"]["positions"]
            features = np.lib.format.open_memmap(destination / "train_features.npy", mode="w+", dtype=np.float64, shape=(positions, 5))
            labels = np.lib.format.open_memmap(destination / "train_labels.npy", mode="w+", dtype=np.float64, shape=(positions,))
            offset = 0
            feature_started = time.perf_counter()
            for chunk_index, chunk in enumerate(train_chunks):
                current, mask = teacher_features(chunk["input_ids"], chunk["labels"], config=count_config, mean_patch_length=mean_length, background=background)
                stop = offset + int(mask.sum())
                features[offset:stop] = current[mask]
                labels[offset:stop] = chunk["labels"][mask]
                offset = stop
                if (chunk_index + 1) % 500 == 0:
                    print(json.dumps({"window": args.window, "feature_chunks": chunk_index + 1, "positions": offset}), flush=True)
                    check_budget()
            if offset != positions:
                raise ValueError("Feature/label position count mismatch")
            features.flush()
            labels.flush()
            report["feature_seconds"] = time.perf_counter() - feature_started
            progress("Fixed training features completed", {"positions": positions, "seconds": report["feature_seconds"], "next": "Constrained fit"})
            fit_started = time.perf_counter()
            fitted = fit_boundary(features, labels, rho=0.001, maximum_iterations=budgets["maximum_optimizer_iterations"])
            report["fit"] = fitted
            report["fit_seconds"] = time.perf_counter() - fit_started
            progress("Boundary fit completed", {"fit": fitted, "next": "Fresh sequential threshold trials"})
            report["training_positions"] = positions
            report["feature_artifacts"] = {path.name: file_hash(path) for path in (destination / "train_features.npy", destination / "train_labels.npy")}
            report["training_logit_contributions"] = {
                "mean": (np.mean(features, axis=0) * fitted["coefficients"]).tolist(),
                "min": (np.min(features, axis=0) * fitted["coefficients"]).tolist(),
                "max": (np.max(features, axis=0) * fitted["coefficients"]).tolist(),
            }
            del features, labels, train_chunks
            print(json.dumps({"window": args.window, "fit": fitted}), flush=True)
            coarse = np.linspace(0, 1, 9).tolist()
            for grid in (coarse, None):
                if grid is None:
                    best = max(report["threshold_trials"], key=lambda trial: (trial["f1"], trial["threshold"]))
                    seen = {trial["threshold"] for trial in report["threshold_trials"]}
                    grid = [float(value) for value in np.linspace(max(0, best["threshold"] - 0.125), min(1, best["threshold"] + 0.125), 9) if float(value) not in seen]
                for threshold in grid:
                    check_budget()
                    if len(report["threshold_trials"]) >= budgets["maximum_threshold_trials_per_configuration"]:
                        raise RuntimeError("Threshold trial budget exceeded")
                    rule = BoundaryRule(tuple(fitted["coefficients"]), mean_length, threshold)
                    metrics = evaluate_threshold(validation_chunks, count_config, rule, background)
                    report["threshold_trials"].append(metrics)
                    progress("Threshold validation completed", metrics)
                    print(json.dumps({"window": args.window, **metrics}), flush=True)
            best = max(report["threshold_trials"], key=lambda trial: (trial["f1"], trial["threshold"]))
            rule = BoundaryRule(tuple(fitted["coefficients"]), mean_length, best["threshold"])
            metrics, document_counts = evaluate_threshold(validation_chunks, count_config, rule, background, details=True)
            if metrics["f1"] != best["f1"]:
                raise ValueError("Selected threshold replay is not deterministic")
            generator = np.random.default_rng(config["seed"])
            replicates = [boundary_metrics(document_counts[generator.integers(0, len(document_counts), size=len(document_counts))].sum(axis=0))["f1"] for _ in range(config["gates"]["bootstrap_replicates"])]
            metrics["document_bootstrap_f1_95ci"] = np.quantile(replicates, [0.025, 0.975]).tolist()
            metrics["documents"] = len(document_counts)
            report["validation_document_counts"] = document_counts.tolist()
            diagnostic_counts = np.zeros(3, dtype=np.int64)
            for chunk in validation_chunks:
                current, mask = teacher_features(chunk["input_ids"], chunk["labels"], config=count_config, mean_patch_length=mean_length, background=background)
                diagnostic_counts += confusion(expit(current[mask] @ fitted["coefficients"]) > rule.threshold, chunk["labels"][mask])
            report["teacher_history_diagnostic"] = boundary_metrics(diagnostic_counts)
            report["prefix_diagnostics"] = []
            for item in label_report["prefix_diagnostics"]:
                chunk = next(chunk for chunk in validation_chunks if chunk["document_id"] == item["document_id"] and chunk["byte_offset"] == 0)
                decision = rollout(chunk["input_ids"][:item["prefix_input_ids"]], config=count_config, rule=rule, background=background)[-1]
                report["prefix_diagnostics"].append({**item, "candidate_entropy": decision.entropy, "candidate_label": decision.boundary})
            report.update(
                status="validation_gate_passed" if metrics["f1"] >= config["gates"]["minimum_validation_f1"] else "validation_gate_failed",
                selected_rule=asdict(rule), validation=metrics,
                remaining="No ablations, full-BLT BPB/timing, or heldout evaluation performed",
            )
        except Exception as error:
            report.update(status="failed", error_type=type(error).__name__, error=str(error))
        finally:
            report["elapsed_seconds"] = time.perf_counter() - started
            report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            json.dump(report, output, indent=2)
            output.write("\n")
            output.flush()
            progress("Fit and validation finished", {"status": report["status"], "f1": report.get("validation", {}).get("f1"), "error": report.get("error"), "next": "Paired baseline comparison if successful"})
    print(json.dumps({"status": report["status"], "window": args.window, "validation": report.get("validation"), "error": report.get("error")}), flush=True)
    return int(report["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())