"""Frozen 10GB train/validation analysis; independent F1/F0.5 selection and ablations."""

import argparse
import copy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

if __name__ == "__main__" and os.environ.get("OPENBLAS_NUM_THREADS") != "8":
    raise RuntimeError("Launch with OPENBLAS_NUM_THREADS=8 before importing NumPy")

import numpy as np

from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountModel, fit_boundary, rollout
from scripts.benchmark_cpp_count_patcher import build_native, paired_summary
from scripts.fit_count_patcher import average_precision, boundary_metrics, confusion, load_chunks
from scripts.patcher_preflight import file_hash


def metrics_with_f05(counts):
    result = boundary_metrics(counts)
    positive, false_positive, false_negative = (int(value) for value in counts)
    denominator = 1.25 * positive + false_positive + .25 * false_negative
    result["f0_5"] = 1.25 * positive / denominator if denominator else 0.
    return result


def fit_ablation(features, labels, zero_columns, *, rho, maximum_iterations=500):
    if any(type(column) is not int or column not in (1, 2, 3, 4) for column in zero_columns):
        raise ValueError("Only non-intercept feature columns can be removed")
    modified = np.array(features, dtype=np.float64, copy=True)
    modified[:, zero_columns] = 0.
    fitted = fit_boundary(modified, labels, rho=rho, maximum_iterations=maximum_iterations)
    if any(fitted["coefficients"][column] != 0. for column in zero_columns):
        raise ValueError("Removed features retained nonzero coefficients")
    return fitted


def cached_rollout(entropy, repeated, rule):
    if len(entropy) < 3 or len(repeated) != len(entropy):
        raise ValueError("Aligned features must include forced0/1 and a virtual slot")
    boundaries = np.zeros(len(entropy), dtype=bool)
    scores = np.empty(len(entropy), dtype=np.float64)
    distances = np.empty(len(entropy), dtype=np.int64)
    last_boundary = 0
    for position in range(len(entropy)):
        distance = position - last_boundary
        scores[position] = rule.score(distance, entropy[position], repeated[position])
        distances[position] = distance
        boundaries[position] = position < 2 or scores[position] > rule.threshold
        if boundaries[position]:
            last_boundary = position
    return boundaries, scores, distances


def paired_intervals(candidate, reference, *, seed=20261019, replicates=2000):
    candidate, reference = np.asarray(candidate), np.asarray(reference)
    if candidate.shape != reference.shape or candidate.ndim != 2 or candidate.shape[1] != 3:
        raise ValueError("Expected aligned per-document confusion counts")
    if not len(candidate) or (candidate < 0).any() or (reference < 0).any():
        raise ValueError("Confusion counts must be nonempty and nonnegative")
    indices = np.random.default_rng(seed).integers(0, len(candidate), size=(replicates, len(candidate)))
    differences = {metric: [] for metric in ("f1", "f0_5")}
    for sample in indices:
        current = metrics_with_f05(candidate[sample].sum(axis=0))
        baseline = metrics_with_f05(reference[sample].sum(axis=0))
        for metric in differences:
            differences[metric].append(current[metric] - baseline[metric])
    return {metric: np.quantile(values, [.025, .975]).tolist() for metric, values in differences.items()}


def count_features(token_ids, config, background, module=None, rule=None):
    if module is not None and config.window is None:
        state = module.create(asdict(config), asdict(rule), background.lookup)
        _, rows = module.run(state, token_ids.tolist(), True)
        values = np.asarray(rows, dtype=np.float64)
        return values[:, 0], values[:, 2]
    model = CountModel(config, background)
    values = []
    for position in range(len(token_ids) + 1):
        values.append(model.features())
        if position < len(token_ids):
            model.observe(token_ids[position])
    values = np.asarray(values, dtype=np.float64)
    return values[:, 0], values[:, 1]


def fixed_training_features(chunk, entropy, repeated, mean_length):
    positions = np.arange(len(chunk["labels"]))
    previous = np.r_[0, np.maximum.accumulate(np.where(chunk["labels"], positions, 0))[:-1]]
    distance = positions - previous
    return np.column_stack((np.ones(len(positions)), distance,
                            np.maximum(distance - mean_length, 0.) ** 2, entropy, -repeated))[2:]


def evaluate_cached(chunks, values, rule, details=False):
    by_document = {}
    records = []
    for chunk, (entropy, repeated) in zip(chunks, values):
        predicted, scores, distance = cached_rollout(entropy, repeated, rule)
        document = chunk["document_id"]
        by_document[document] = by_document.get(document, np.zeros(3, dtype=np.int64)) + confusion(predicted[2:], chunk["labels"][2:])
        if details:
            records.append({"prediction": predicted, "scores": scores, "distance": distance,
                            "entropy": entropy, "repeated": repeated})
    counts = np.asarray(list(by_document.values()))
    result = metrics_with_f05(counts.sum(axis=0))
    result.update(threshold=rule.threshold, document_ids=list(by_document), document_counts=counts.tolist())
    return result, records


def stratum_diagnostics(chunks, records, threshold, teacher_threshold):
    from scipy.stats import spearmanr

    lengths = {}
    for chunk in chunks:
        lengths[chunk["document_id"]] = max(lengths.get(chunk["document_id"], 0), chunk["byte_offset"] + chunk["byte_length"])
    groups = {}
    for chunk, record in zip(chunks, records):
        size = len(chunk["labels"])
        document_length = lengths[chunk["document_id"]]
        masks = {
            "document_position": np.minimum(2, (chunk["byte_offset"] + np.arange(size) - 1) * 3 // document_length),
            "document_length": np.full(size, np.searchsorted([1024, 4096], document_length, side="right")),
            "repeated_suffix": np.searchsorted([1, 4], record["repeated"], side="right"),
            "candidate_distance": np.searchsorted([5, 9], record["distance"], side="right"),
            "teacher_margin": np.searchsorted([.01, .1], np.abs(chunk["entropy"] - teacher_threshold), side="right"),
            "candidate_margin": np.searchsorted([.01, .1], np.abs(record["scores"] - threshold), side="right"),
        }
        for axis, bins in masks.items():
            for bucket in range(3):
                selected = (bins[2:] == bucket)
                key = f"{axis}:{bucket}"
                stats = groups.setdefault(key, {"positions": 0, "counts": np.zeros(3, dtype=np.int64)})
                stats["positions"] += int(selected.sum())
                stats["counts"] += confusion(record["prediction"][2:][selected], chunk["labels"][2:][selected])
    scores = np.concatenate([record["scores"][2:] for record in records])
    labels = np.concatenate([chunk["labels"][2:] for chunk in chunks])
    entropy = np.concatenate([record["entropy"][2:] for record in records])
    teacher = np.concatenate([chunk["entropy"][2:] for chunk in chunks])
    clipped = np.clip(scores, 1e-15, 1 - 1e-15)
    candidate_patches = [int(record["prediction"].sum()) for record in records]
    teacher_patches = [int(chunk["labels"].sum()) for chunk in chunks]
    slots = sum(len(chunk["labels"]) for chunk in chunks)
    return {"strata": {key: dict(positions=value["positions"], **metrics_with_f05(value["counts"])) for key, value in groups.items()},
            "candidate_patch_count": sum(candidate_patches), "teacher_patch_count": sum(teacher_patches),
            "candidate_mean_patch_length": slots / sum(candidate_patches), "teacher_mean_patch_length": slots / sum(teacher_patches),
            "mean_absolute_chunk_patch_count_error": float(np.abs(np.asarray(candidate_patches) - teacher_patches).mean()),
            "entropy_mae": float(np.abs(entropy - teacher).mean()),
            "entropy_rmse": float(np.sqrt(np.mean((entropy - teacher) ** 2))),
            "entropy_spearman": float(spearmanr(entropy, teacher).statistic),
            "log_loss": float(-(labels * np.log(clipped) + (~labels) * np.log1p(-clipped)).mean()),
            "average_precision": average_precision(scores, labels)}


def benchmark_patchers(report, validation, background, pilot, destination, save, check_budget):
    import torch
    import transformers
    from phdq_blt_cache.blt_patcher import CountPatcherAdapter
    from scripts.compare_blt_patchers import timed_replay

    project = Path("/home/itcmaster/projects/phdq3")
    sys.path.insert(0, str(project))
    from blt_hf.model import load_model

    expected_hashes = {Path(pilot["baseline"]["model_checkpoint"]) / "model.safetensors": "4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061",
                       Path(pilot["baseline"]["conversion_report"]): "00805ed1d402de791c531df2d124d47333a4199b8853516f4b01c06c85cdd441"}
    for path, digest in expected_hashes.items():
        if file_hash(path) != digest:
            raise ValueError("Frozen BLT checkpoint or conversion changed")
    torch.set_num_threads(8)
    torch.cuda.set_device(0)
    model = load_model(Path(pilot["baseline"]["model_checkpoint"]), Path(pilot["baseline"]["conversion_report"]),
                       attention_mode="osc", backend="eager", device="cpu")
    model.eval().requires_grad_(False)
    if model.dtype != torch.bfloat16 or model.config.vocab_size != 260 or model.config.max_patch_length is not None:
        raise ValueError("Expected frozen BF16 byte model without patch cap")
    teacher = model.model.patcher.to("cuda")
    backgrounds = {f"{variant['name']}:{metric}": copy.copy(background)
                   for variant in report["variants"] for metric in variant["selections"]}
    for candidate in backgrounds.values():
        candidate._cached_lookup = lru_cache(maxsize=4096)(candidate._read)
    adapters = {f"{variant['name']}:{metric}": CountPatcherAdapter(
        CountConfig(**variant["count_config"]), BoundaryRule(**selection["rule"]), backgrounds[f"{variant['name']}:{metric}"])
        for variant in report["variants"] for metric, selection in variant["selections"].items()}
    modes = ["teacher"] + list(adapters)
    timing = {"status": "running", "scope": "Patcher only, train/validation analysis; not full-model time or heldout quality",
              "runtime": {"torch": torch.__version__, "transformers": transformers.__version__, "gpu": torch.cuda.get_device_name(),
                          "dtype": "bfloat16", "batch": 1, "warmups": 3, "repeats": 10}, "cases": []}

    def telemetry():
        return subprocess.check_output(["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,clocks.sm,memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True).strip()

    with torch.inference_mode():
        for length in (256, 512, 1024, 2048):
            eligible = [chunk for chunk in validation if chunk["byte_offset"] == 0 and len(chunk["input_ids"]) >= length][:2]
            if len(eligible) != 2:
                raise ValueError("Insufficient validation-only timing inputs")
            for chunk in eligible:
                ids = torch.as_tensor(chunk["input_ids"][:length].astype(np.int64), device="cuda").unsqueeze(0)
                case = {"document_id": chunk["document_id"], "input_ids": length, "initial_input_ids": length - 32,
                        "telemetry_fields": "temperature_C,power_W,SM_MHz,memory_MiB,utilization_percent",
                        "telemetry_before": telemetry(), "samples": []}

                def measure(mode):
                    torch.cuda.reset_peak_memory_stats()
                    if mode == "teacher":
                        def forward(current):
                            return teacher(current, patch_size=model.config.patch_size, threshold=model.config.patching_threshold,
                                           max_patch_length=model.config.max_patch_length, use_cache=False)
                    else:
                        adapters[mode].reset()
                        forward = adapters[mode].patch_lengths
                    values = timed_replay(ids[:, :-32], tuple(ids[:, :endpoint] for endpoint in range(length - 31, length + 1)), forward, torch.cuda.synchronize)
                    if torch.cuda.max_memory_reserved() > pilot["budgets"]["peak_gpu_memory_gib"] * 2**30:
                        raise RuntimeError("GPU memory budget exceeded")
                    return {key.replace("model_", "patcher_"): value for key, value in values.items()} | {"peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated()}

                for _ in range(3):
                    for mode in modes:
                        measure(mode)
                for repeat in range(10):
                    order = modes[repeat % len(modes):] + modes[:repeat % len(modes)]
                    if repeat % 2:
                        order = list(reversed(order))
                    sample = {"repeat": repeat, "order": order, "modes": {mode: measure(mode) for mode in order}}
                    case["samples"].append(sample)
                    check_budget()
                case["telemetry_after"] = telemetry()
                case["summaries"] = {}
                for mode in modes:
                    case["summaries"][mode] = {}
                    for kind in ("patcher_initial", "patcher_incremental32", "patcher_total32"):
                        values = [sample["modes"][mode][kind] for sample in case["samples"]]
                        summary = {"mean": float(np.mean(values)), "std_sample": float(np.std(values, ddof=1)),
                                   "p50": float(np.median(values)), "p95": float(np.percentile(values, 95))}
                        if mode != "teacher":
                            summary["teacher_ratio"] = paired_summary([{"python": sample["modes"]["teacher"][kind], "cpp": sample["modes"][mode][kind]} for sample in case["samples"]])
                        case["summaries"][mode][kind] = summary
                timing["cases"].append(case)
                path = destination / "timing.json"
                path.write_text(json.dumps(timing, indent=2) + "\n")
                save(f"Timing case completed: {length} IDs", {"cases": len(timing["cases"])})
    timing["status"] = "completed"
    path.write_text(json.dumps(timing, indent=2) + "\n")
    report["timing"] = {"path": str(path), "sha256": file_hash(path), "cases": len(timing["cases"]),
                        "telemetry_limit": "Before/after each case, not continuous telemetry or a proof of thermal stability"}


def main():
    from phdq_blt_cache.lmdb_counts import LMDBCountTable

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.config.read_text())
    pilot = json.loads(Path(plan["pilot_config"]).read_text())
    budgets = pilot["budgets"]
    if plan["splits"] != ["train", "validation"] or len(plan["variants"]) > budgets["maximum_configuration_trials"]:
        raise ValueError("Split or configuration budget changed")
    destination = Path(plan["output_directory"])
    destination.mkdir(parents=True, exist_ok=False)
    parent_path = Path(plan["parent_fit"])
    parent = json.loads(parent_path.read_text())
    label_run = Path(plan["label_run"])
    label_path = label_run / "label_generation.json"
    labels = json.loads(label_path.read_text())
    if file_hash(label_path) != parent["label_report_sha256"]:
        raise ValueError("Frozen label report changed")
    report = {"status": "running", "stage": "T08-T09-10GB-analysis", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "plan": plan, "sources": {str(path): file_hash(path) for path in (args.config, parent_path, label_path, Path(__file__), Path("src/phdq_blt_cache/count_patcher.py"), Path("scripts/fit_count_patcher.py"))},
              "limitations": "Reused train/validation, no heldout access. Post-selection validation bootstrap is descriptive. No F0.5 acceptance gate was supplied. No20GB or Neuron job is launched.",
              "variants": [], "feature_caches": {}, "controls": []}
    started = time.perf_counter()

    def check_budget():
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > budgets["peak_host_ram_gib"] * 2**30:
            raise RuntimeError("Host RSS budget exceeded")
        if shutil.disk_usage(destination).free < budgets["minimum_free_disk_gib"] * 2**30:
            raise RuntimeError("Free disk protection reached")
        size = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
        if size > budgets["maximum_new_artifact_storage_gib"] * 2**30:
            raise RuntimeError("Artifact storage budget exceeded")

    def save(stage, details):
        report["last_stage"] = stage
        temporary = destination / "result.partial.json"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(destination / "result.json")
        entry = f"\n## {datetime.now(timezone.utc).isoformat()} / {plan['run_id']} / {stage}\n\n- {json.dumps(details)}\n- Report: {destination / 'result.json'}\n"
        with (destination / "progress.md").open("a") as output:
            output.write(entry)
        with Path("log.md").open("a") as output:
            output.write(entry)
        print(json.dumps({"stage": stage, **details}), flush=True)

    save("Analysis started", {"plan_sha256": file_hash(args.config)})
    try:
        train = load_chunks(label_run, "train", labels)
        validation = load_chunks(label_run, "validation", labels)
        features_path = parent_path.parent / "train_features.npy"
        targets_path = parent_path.parent / "train_labels.npy"
        for path in (features_path, targets_path):
            if file_hash(path) != parent["feature_artifacts"][path.name]:
                raise ValueError("Parent feature artifact changed")
        train_targets = np.load(targets_path, mmap_mode="r")
        module, build_command, library = build_native(destination / "native")
        report["native"] = {"library": str(library), "sha256": file_hash(library), "build_command": build_command,
                            "source_sha256": file_hash(Path("scripts/native/count_patcher.cpp"))}
        mean = parent["teacher_mean_patch_length_from_training"]
        original_rule = BoundaryRule(**parent["selected_rule"])
        caches = {}
        with LMDBCountTable(plan["background"]) as background:
            if background.metadata["source_report_sha256"] != parent["background_report_sha256"]:
                raise ValueError("LMDB source differs from parent fit")
            report["background_metadata"] = background.metadata
            for variant in plan["variants"]:
                config = replace(CountConfig(**parent["count_config"]), online_weight=variant["online_weight"], window=variant["window"])
                key = f"eta{config.online_weight}-window{config.window}"
                if key not in caches:
                    validation_values = []
                    training_path = features_path if key == "eta1.0-windowNone" else destination / f"train-{key}.npy"
                    training = (np.load(training_path, mmap_mode="r") if training_path == features_path else
                                np.lib.format.open_memmap(training_path, mode="w+", dtype=np.float64, shape=(len(train_targets), 5)))
                    for split, chunks in (("train", train), ("validation", validation)):
                        offset = 0
                        for chunk_index, chunk in enumerate(chunks):
                            if split == "train" and training_path == features_path and chunk_index >= 3:
                                break
                            entropy, repeated = count_features(chunk["input_ids"], config, background, module, original_rule)
                            if chunk_index == 0 and config.window is None:
                                reference_entropy, reference_repeated = count_features(chunk["input_ids"], config, background)
                                if not np.allclose(entropy, reference_entropy, rtol=0, atol=2e-13) or not np.array_equal(repeated, reference_repeated):
                                    raise ValueError("Native feature extraction differs from Python")
                                report["controls"].append({"cache": key, "split": split, "positions": len(entropy), "native_python_features_agree": True})
                            if split == "train":
                                current = fixed_training_features(chunk, entropy, repeated, mean)
                                stop = offset + len(current)
                                if training_path == features_path:
                                    if not np.allclose(training[offset:stop], current, rtol=0, atol=2e-13):
                                        raise ValueError("Preserved training features differ")
                                else:
                                    training[offset:stop] = current
                                offset = stop
                            else:
                                validation_values.append((entropy, repeated))
                            if (chunk_index + 1) % 100 == 0:
                                save("Feature extraction progress", {"cache": key, "split": split, "chunks": chunk_index + 1})
                            check_budget()
                        if split == "train" and training_path != features_path and offset != len(train_targets):
                            raise ValueError("Training feature position count differs")
                    if training_path != features_path:
                        training.flush()
                    del training
                    caches[key] = (training_path, validation_values)
                    report["feature_caches"][key] = {"training": str(training_path), "sha256": file_hash(training_path)}
                    save("Feature cache completed", {"cache": key})
                training_path, values = caches[key]
                training = np.load(training_path, mmap_mode="r")
                fitted = fit_ablation(training, train_targets, variant["zero_columns"], rho=.001, maximum_iterations=budgets["maximum_optimizer_iterations"])
                del training
                if variant["name"] == "full" and fitted["coefficients"] != parent["fit"]["coefficients"]:
                    raise ValueError("Parent coefficients did not reproduce exactly")
                result = {"name": variant["name"], "count_config": asdict(config), "fit": fitted, "zero_columns": variant["zero_columns"], "trials": [], "selections": {}}
                report["variants"].append(result)
                rules = lambda threshold: BoundaryRule(tuple(fitted["coefficients"]), mean, threshold)
                coarse = np.linspace(0, 1, 9).tolist()
                trials = {}

                def trial(threshold):
                    if threshold not in trials:
                        if len(trials) >= budgets["maximum_threshold_trials_per_configuration"]:
                            raise RuntimeError("Threshold trial budget exceeded")
                        metrics, _ = evaluate_cached(validation, values, rules(threshold))
                        trials[threshold] = metrics
                        result["trials"].append({key: value for key, value in metrics.items() if key not in ("document_ids", "document_counts")})
                        check_budget()
                        save("Sequential threshold completed", {"variant": variant["name"], **result["trials"][-1]})
                    return trials[threshold]

                for threshold in coarse:
                    trial(threshold)
                grids = {}
                for metric in plan["selection_metrics"]:
                    best = max(coarse, key=lambda threshold: (trials[threshold][metric], threshold))
                    grids[metric] = sorted(set(coarse + np.linspace(max(0., best - .125), min(1., best + .125), 9).tolist()))
                for grid in grids.values():
                    for threshold in grid:
                        trial(threshold)
                for metric, grid in grids.items():
                    best = max(grid, key=lambda threshold: (trials[threshold][metric], threshold))
                    rule = rules(best)
                    selected, records = evaluate_cached(validation, values, rule, details=True)
                    if selected != trials[best]:
                        raise ValueError("Selected cached replay changed")
                    for chunk, record in zip(validation, records):
                        if config.window is None:
                            state = module.create(asdict(config), asdict(rule), background.lookup)
                            _, fresh = module.run(state, chunk["input_ids"].tolist(), True)
                            fresh_boundaries = [bool(row[4]) for row in fresh]
                        else:
                            fresh_boundaries = [item.boundary for item in rollout(chunk["input_ids"], config=config, rule=rule, background=background)]
                        if not np.array_equal(fresh_boundaries, record["prediction"]):
                            raise ValueError("Cached threshold replay differs from fresh count rollout")
                    selected.update(rule=asdict(rule), selection_grid=grid,
                                    diagnostics=stratum_diagnostics(validation, records, best, 1.3359375),
                                    document_bootstrap_95ci=paired_intervals(selected["document_counts"], np.zeros_like(selected["document_counts"]), seed=plan["bootstrap_seed"], replicates=plan["bootstrap_replicates"]),
                                    fresh_count_replay_positions=sum(len(chunk["labels"]) - 2 for chunk in validation))
                    if variant["name"] == "full" and metric == "f1":
                        if best != original_rule.threshold or selected["document_counts"] != parent["validation_document_counts"]:
                            raise ValueError("Parent F1 validation did not reproduce exactly")
                        report["controls"].append({"parent_f1_exact": True, "threshold": best})
                    result["selections"][metric] = selected
                    del records
                save("Variant completed", {"variant": variant["name"], "f1_selection": result["selections"]["f1"]["f1"], "f05_selection": result["selections"]["f0_5"]["f0_5"]})
            reference = report["variants"][0]
            for variant in report["variants"]:
                for metric, selection in variant["selections"].items():
                    control = reference["selections"][metric]
                    if selection["document_ids"] != control["document_ids"]:
                        raise ValueError("Document bootstrap alignment differs")
                    interval = paired_intervals(selection["document_counts"], control["document_counts"], seed=plan["bootstrap_seed"], replicates=plan["bootstrap_replicates"])
                    selection["paired_delta_95ci"] = interval
                    selection["f1_noninferior"] = interval["f1"][0] > -pilot["gates"]["ablation_f1_noninferiority_margin"] if metric == "f1" else None
            save("Statistical analysis completed", {"variants": len(report["variants"]), "next": "Isolated patcher timing"})
            benchmark_patchers(report, validation, background, pilot, destination, save, check_budget)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = time.perf_counter() - started
        report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        save("Analysis finished", {"status": report["status"], "error": report.get("error")})


if __name__ == "__main__":
    main()