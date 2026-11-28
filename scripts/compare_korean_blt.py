"""Korean BLT comparison: a trained body with its frozen entropy patcher versus the frozen T14 count patcher.

Teacher-forced test-split quality and paired timings only; no model cache, refitting or adoption decision. The
count patcher runs through the Python and C++ package backends, which must agree exactly on every input.
"""

import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import inspect
import json
import math
from pathlib import Path
import resource
import sys
import time

from phdq_blt_cache.blt_patcher import CountPatcherAdapter
from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig
from phdq_blt_cache.lmdb_counts import LMDBCountTable
from scripts.benchmark_cpp_count_patcher import build_native
from scripts.compare_blt_patchers import (boundary_comparison, boundary_summary, evaluation_documents,
                                          incremental_prefixes, timed_replay)
from scripts.patcher_preflight import file_hash
from scripts.smoke_blt_count_patcher import timing_summary


MODES = ("original", "count_python", "count_cpp")
COUNT_MODES = ("count_python", "count_cpp")
WARMUPS, REPEATS = 3, 10
BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED = 2000, 20261128


def paired_bpb(documents, *, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED):
    """Byte-weighted BPB per mode and count_cpp minus original with a paired document bootstrap."""
    import numpy as np

    if len(documents) < 2:
        raise ValueError("Document bootstrap requires at least two documents")
    values = np.asarray([[doc["modes"][mode]["nll_nats"] for mode in MODES] + [doc["utf8_bytes"]]
                         for doc in documents], dtype=np.float64)
    if not np.isfinite(values).all() or (values[:, -1] <= 0).any():
        raise ValueError("Invalid document losses or byte counts")
    total = values.sum(axis=0)
    denominator = total[-1] * math.log(2)
    indices = np.random.default_rng(seed).integers(0, len(values), size=(replicates, len(values)))
    samples = values[indices].sum(axis=1)
    differences = (samples[:, 2] - samples[:, 0]) / (samples[:, -1] * math.log(2))
    lower, upper = np.percentile(differences, [2.5, 97.5]).tolist()
    return {"documents": len(documents), "scored_bytes": int(total[-1]),
            "bpb": {mode: total[index] / denominator for index, mode in enumerate(MODES)},
            "delta_bpb_count_minus_original": (total[2] - total[0]) / denominator,
            "paired_document_bootstrap95": [lower, upper],
            "bootstrap_replicates": replicates, "bootstrap_seed": seed}


def patch_statistics(histogram):
    patches = sum(histogram.values())
    if patches <= 0:
        raise ValueError("Empty patch-length histogram")
    return {"patches": patches, "mean_patch_length": sum(length * count for length, count in histogram.items()) / patches,
            "histogram": {str(length): histogram[length] for length in sorted(histogram)}}


def select_timing_inputs(documents, lengths):
    """First test document, in file order, whose first chunk has at least each requested number of IDs."""
    selected = []
    for length in lengths:
        match = next(((metadata, chunks[0][:length]) for metadata, chunks in documents if len(chunks[0]) >= length), None)
        if match is None:
            raise ValueError(f"No first chunk with {length} IDs")
        selected.append(match)
    return selected


def ratio_summary(baseline, candidate, *, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED):
    """Median baseline time over median candidate time with a paired bootstrap; above 1 means the candidate is faster."""
    import numpy as np

    baseline, candidate = np.asarray(baseline, dtype=np.float64), np.asarray(candidate, dtype=np.float64)
    if baseline.shape != candidate.shape or baseline.ndim != 1 or len(baseline) < 2 or (baseline <= 0).any() or (candidate <= 0).any():
        raise ValueError("Expected paired positive timing samples")
    indices = np.random.default_rng(seed).integers(0, len(baseline), size=(replicates, len(baseline)))
    ratios = np.median(baseline[indices], axis=1) / np.median(candidate[indices], axis=1)
    return {"median_ratio": float(np.median(baseline) / np.median(candidate)),
            "paired_bootstrap95": np.percentile(ratios, [2.5, 97.5]).tolist()}


def save_report(directory, stage, report):
    temporary = directory / (stage + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(directory / (stage + (".json" if report["status"] == "completed" else ".progress.json")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("quality", "timing"), required=True)
    for name in ("blt-project", "model-path", "fit-report", "label-report", "background", "dataset-directory",
                 "output-directory"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--body-export", type=Path, help="Exported trained body (blt_hf.body_export)")
    parser.add_argument("--public-body", action="store_true", help="Pipeline check with the public body instead")
    parser.add_argument("--patcher-checkpoint", type=Path, help="Local copy of the label teacher checkpoint")
    parser.add_argument("--max-documents", type=int, help="Pipeline check only; default is the whole test split")
    parser.add_argument("--lengths", default="256,512,1024,2048")
    args = parser.parse_args()
    if args.public_body == (args.body_export is not None):
        parser.error("Choose exactly one of --body-export and --public-body")
    if args.public_body and args.patcher_checkpoint is None:
        parser.error("--public-body needs the label teacher's --patcher-checkpoint")
    if args.max_documents is not None and args.max_documents < 2:
        parser.error("--max-documents must be at least 2")
    timing_lengths = tuple(int(value) for value in args.lengths.split(","))
    if (not timing_lengths or len(set(timing_lengths)) != len(timing_lengths) or min(timing_lengths) < 34
            or max(timing_lengths) > 2048):
        parser.error("Distinct timing lengths between 34 and 2048 IDs required")
    if (args.output_directory / (args.stage + ".json")).exists() or (args.output_directory / (args.stage + ".progress.json")).exists():
        raise FileExistsError(args.output_directory / args.stage)
    args.output_directory.mkdir(parents=True, exist_ok=True)

    fitted = json.loads(args.fit_report.read_text())
    labels = json.loads(args.label_report.read_text())
    manifest = json.loads((args.dataset_directory / "manifest.json").read_text())
    if fitted["status"] != "fitted" or labels["status"] != "generated" or manifest["status"] != "prepared":
        raise ValueError("Expected a fitted rule, generated labels and a prepared dataset")
    if fitted["label_report_sha256"] != file_hash(args.label_report):
        raise ValueError("Fitted label report changed")
    teacher = labels["contract"].get("teacher_patcher")
    if teacher is None:
        raise ValueError("Label report has no explicit teacher patcher")
    split_sha256 = {}
    for split in ("train", "validation", "test"):
        split_sha256[split] = file_hash(args.dataset_directory / f"{split}.jsonl")
        if split_sha256[split] != manifest["splits"][split]["file_sha256"]:
            raise ValueError(f"Dataset split changed: {split}")
    prohibited = {metadata["text_sha256"] for split in ("train", "validation")
                  for metadata, _ in evaluation_documents(args.dataset_directory, split)}

    import torch
    import transformers

    torch.set_num_threads(8)
    torch.cuda.set_device(0)
    sys.path.insert(0, str(args.blt_project.resolve()))
    from blt_hf.body_export import load_exported_body
    from blt_hf.body_train import load_body

    body = {"kind": "public" if args.public_body else "export"}
    if args.public_body:
        patcher = {"checkpoint": str(args.patcher_checkpoint), "sha256": teacher["checkpoint_sha256"],
                   "threshold": teacher["threshold"]}
        model = load_body(args.model_path, patcher, "eager").requires_grad_(False).eval()
        body.update(model_safetensors_sha256=file_hash(args.model_path / "model.safetensors"),
                    patcher_checkpoint=str(args.patcher_checkpoint))
    else:
        model, exported = load_exported_body(args.model_path, args.body_export, args.patcher_checkpoint, "eager")
        trained = exported["contract"]["config"]["patcher"]
        if (trained["sha256"], trained["threshold"]) != (teacher["checkpoint_sha256"], teacher["threshold"]):
            raise ValueError("Body patcher differs from the count patcher's label teacher")
        body.update({key: exported[key] for key in ("source_checkpoint", "source_checkpoint_sha256", "signature",
                                                    "body_sha256", "parameters", "validation_final")},
                    export=str(args.body_export), run_dir=exported["run_dir"], step=exported["progress"]["step"],
                    public_model_safetensors_sha256=exported["contract"]["weights_sha256"])
    if model.dtype != torch.bfloat16 or model.config.vocab_size != 260 or model.config.max_patch_length is not None:
        raise ValueError("Expected a BF16 byte model without a patch cap")
    if model.config.patching_threshold != teacher["threshold"]:
        raise ValueError("Model threshold differs from the label teacher")
    _, command, library = build_native(args.output_directory / f"native-{args.stage}")
    config, rule = CountConfig(**fitted["count_config"]), BoundaryRule(**fitted["selected_rule"])
    report = {
        "status": "running", "stage": args.stage, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Korean test split; trained body with its frozen entropy patcher (original) versus the frozen T14 count patcher; no cache reuse or refitting",
        "body": body, "teacher_patcher": teacher, "rule": fitted["selected_rule"], "count_config": fitted["count_config"],
        "split_sha256": split_sha256, "document_limit": args.max_documents,
        "timing_lengths": list(timing_lengths) if args.stage == "timing" else None,
        "sources": {str(path): file_hash(path) for path in (args.fit_report, args.label_report,
                                                             args.dataset_directory / "manifest.json")},
        "code_sha256": {str(Path(path).resolve()): file_hash(path) for path in (
            Path(__file__), inspect.getfile(CountPatcherAdapter), inspect.getfile(CountConfig),
            inspect.getfile(LMDBCountTable), inspect.getfile(build_native), inspect.getfile(timed_replay),
            Path(__file__).parent / "native/count_patcher.cpp", args.blt_project / "blt_hf/body_export.py",
            args.blt_project / "blt_hf/body_train.py", args.blt_project / "blt_hf/model.py",
            args.blt_project / "blt_hf/patched/modeling_blt.py")},
        "library": str(library.resolve()), "library_sha256": file_hash(library), "build_command": command,
        "runtime": {"torch": torch.__version__, "transformers": transformers.__version__,
                    "gpu": torch.cuda.get_device_name(0), "threads": 8, "dtype": "bfloat16", "attention": "osc",
                    "backend": "eager", "batch": 1, "beam": 1, "cache": False},
        "limitations": "One body, GPU, batch 1 and beam 1; test documents are checked against the label train/validation texts only and otherwise rely on the CPT split; no pass/fail criterion or adoption decision",
    }
    try:
        run_stage(args, report, model, fitted, config, rule, library, prohibited, timing_lengths)
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error),
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        save_report(args.output_directory, args.stage, report)
        raise


def run_stage(args, report, model, fitted, config, rule, library, prohibited, timing_lengths):
    import torch

    with LMDBCountTable(args.background) as background, torch.inference_mode():
        if background.config != config or background.metadata["source_report_sha256"] != fitted["background_report_sha256"]:
            raise ValueError("Fitted background and LMDB differ")
        report["background"] = background.metadata
        backgrounds = {mode: copy.copy(background) for mode in COUNT_MODES}
        for candidate in backgrounds.values():
            candidate._cached_lookup = lru_cache(maxsize=4096)(candidate._read)
        adapters = {mode: CountPatcherAdapter(config, rule, backgrounds[mode],
                                              backend="cpp" if mode == "count_cpp" else "python",
                                              native_library=library if mode == "count_cpp" else None)
                    for mode in COUNT_MODES}

        def forward(ids, mode, last_only=True):
            lengths = adapters[mode].patch_lengths(ids) if mode in adapters else None
            output = model(input_ids=ids, patch_lengths=lengths, use_cache=False, logits_to_keep=1 if last_only else 0)
            return output.logits, lengths

        def exact(python, cpp):
            if not torch.equal(python[1], cpp[1]):
                raise ValueError("Package C++/Python patch lengths differ")
            if not torch.equal(python[0], cpp[0]):
                raise ValueError("Package C++/Python model logits differ")

        if args.stage == "quality":
            report.update(documents=[], protocol={
                "documents": "Whole test split in file order (or the recorded pipeline-check limit); nonoverlapping 2047-byte chunks with BOS per chunk; all original bytes scored; count state reset per chunk",
                "boundary_positions": "2..input_length inclusive, virtual next-byte slot included (label contract)",
                "controls": "Python and C++ count backends must give identical patch lengths and full logits on every chunk"})
            totals, histograms = Counter(), {mode: Counter() for mode in ("original", "count_cpp")}
            seen = set(prohibited)
            for metadata, chunks in evaluation_documents(args.dataset_directory, "test"):
                if args.max_documents is not None and len(report["documents"]) >= args.max_documents:
                    break
                if metadata["text_sha256"] in seen:
                    raise ValueError("Test document repeats or overlaps the label train/validation texts")
                seen.add(metadata["text_sha256"])
                document = {**metadata, "chunks": [], "modes": {mode: {"nll_nats": 0.} for mode in MODES}}
                for index, values in enumerate(chunks):
                    ids = torch.tensor([values], dtype=torch.long, device="cuda")
                    entry = {"index": index, "scored_bytes": len(values) - 1, "nll_nats": {}}
                    outputs = {}
                    for mode in MODES:
                        captured = {}

                        def hook(module, inputs, output):
                            captured["lengths"] = output[1].detach().cpu().tolist()[0]

                        handle = model.model.patcher.register_forward_hook(hook) if mode == "original" else None
                        if mode in adapters:
                            adapters[mode].reset()
                        try:
                            logits, lengths = forward(ids, mode, last_only=False)
                        finally:
                            if handle is not None:
                                handle.remove()
                        if not torch.isfinite(logits).all():
                            raise ValueError("Nonfinite quality logits")
                        outputs[mode] = (logits, lengths)
                        nll = torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1, 260),
                                                                ids[:, 1:].reshape(-1), reduction="sum").item()
                        entry["nll_nats"][mode] = nll
                        document["modes"][mode]["nll_nats"] += nll
                        if mode == "original":
                            entry["original_patch_lengths"] = captured["lengths"]
                    exact(outputs["count_python"], outputs["count_cpp"])
                    entry["count_patch_lengths"] = outputs["count_cpp"][1].tolist()[0]
                    del outputs, logits, lengths
                    entry["boundaries"] = boundary_comparison(entry["original_patch_lengths"], entry["count_patch_lengths"],
                                                              len(values))
                    totals.update(entry["boundaries"])
                    histograms["original"].update(entry["original_patch_lengths"])
                    histograms["count_cpp"].update(entry["count_patch_lengths"])
                    document["chunks"].append(entry)
                for mode in MODES:
                    document["modes"][mode]["bpb"] = document["modes"][mode]["nll_nats"] / (metadata["utf8_bytes"] * math.log(2))
                document["delta_bpb"] = document["modes"]["count_cpp"]["bpb"] - document["modes"]["original"]["bpb"]
                report["documents"].append(document)
                save_report(args.output_directory, args.stage, report)
                if len(report["documents"]) % 20 == 0:
                    print(json.dumps({"quality_documents": len(report["documents"])}), flush=True)
            report["quality_summary"] = paired_bpb(report["documents"])
            report["boundary_summary"] = boundary_summary(dict(totals))
            report["patch_statistics"] = {mode: patch_statistics(histogram) for mode, histogram in histograms.items()}
            report["controls"] = {"chunks": sum(len(doc["chunks"]) for doc in report["documents"]),
                                  "python_cpp_boundaries_and_logits_exact": True}
        else:
            documents = list(evaluation_documents(args.dataset_directory, "test"))
            report.update(cases=[], protocol={
                "inputs": "For each length, the first test document whose first chunk has that many IDs (BOS included)",
                "kinds": {"patcher_prefill": "Patcher alone on the whole input",
                          "patcher_incremental32": "Patcher alone on 32 growing prefixes after an untimed priming call (count state reused)",
                          "model_total32": "Full model: initial prefix forward plus 32 growing-prefix forwards, last logits only"},
                "warmups": WARMUPS, "repeats": REPEATS,
                "order": "Rotate the three modes each repetition and reverse on odd repetitions",
                "cache": "Separate 4096-entry LRU per count backend; equal hit/miss workloads required; model cache disabled",
                "excluded": "Loading, native build, resets, controls, sampling and decoding"})
            for metadata, values in select_timing_inputs(documents, timing_lengths):
                ids = torch.tensor([values], dtype=torch.long, device="cuda")
                captured = {}

                def save_call(module, inputs, kwargs):
                    captured.update(inspect.signature(module.forward).bind(*inputs, **kwargs).arguments)

                handle = model.model.patcher.register_forward_pre_hook(save_call, with_kwargs=True)
                try:
                    _, _ = forward(ids, "original")
                finally:
                    handle.remove()
                options = {**captured.pop("kwargs", {}), **captured}
                options.update(position_ids=None, attention_mask=None, use_cache=False, past_key_values=None)

                def neural_lengths(current):
                    return model.model.patcher(**{**options, "input_ids": current})[1]

                recorded = {}

                def record_lengths(module, inputs, output):
                    recorded["lengths"] = output[1].detach().clone()

                handle = model.model.patcher.register_forward_hook(record_lengths)
                try:
                    forward(ids, "original", last_only=False)
                finally:
                    handle.remove()
                if not torch.equal(neural_lengths(ids), recorded["lengths"]):
                    raise AssertionError("Standalone neural patcher differs from the model call")
                priming, extensions = incremental_prefixes(ids)
                for adapter in adapters.values():
                    adapter.reset()
                warm = []
                for current in (priming, *extensions):
                    python, cpp = forward(current, "count_python"), forward(current, "count_cpp")
                    exact(python, cpp)
                    warm.append(cpp)
                for current, (logits, lengths) in zip((priming, *extensions), warm):
                    adapters["count_cpp"].reset()
                    fresh = forward(current, "count_cpp")
                    if not torch.equal(fresh[1], lengths) or not torch.equal(fresh[0], logits):
                        raise AssertionError("Reused count state differs from a fresh-prefix forward")
                del warm
                for candidate in backgrounds.values():
                    candidate._cached_lookup.cache_clear()
                case = {**metadata, "input_length": ids.shape[1], "priming_length": priming.shape[1],
                        "controls": {"python_cpp_exact_forwards": 33, "warm_fresh_exact_forwards": 33,
                                     "standalone_neural_patcher_matches_model": True}, "measurements": {}}
                for kind in ("patcher_prefill", "patcher_incremental32", "model_total32"):
                    samples = {mode: [] for mode in MODES}
                    parts = {name: {mode: [] for mode in MODES} for name in ("model_initial", "model_incremental32")}
                    peaks = {mode: 0 for mode in MODES}
                    for repetition in range(-WARMUPS, REPEATS):
                        offset = repetition % len(MODES)
                        order = list(MODES[offset:] + MODES[:offset])
                        if repetition % 2:
                            order.reverse()
                        workloads = {}
                        for mode in order:
                            if mode in adapters:
                                adapters[mode].reset()
                                before = backgrounds[mode].cache_info()
                            patcher = (lambda current, mode=mode: adapters[mode].patch_lengths(current)) if mode in adapters else neural_lengths
                            if kind == "patcher_incremental32":
                                patcher(priming)
                            torch.cuda.reset_peak_memory_stats()
                            if kind == "model_total32":
                                durations = timed_replay(priming, extensions, lambda current, mode=mode: forward(current, mode),
                                                         torch.cuda.synchronize)
                                elapsed = durations["model_total32"]
                            else:
                                torch.cuda.synchronize()
                                started = time.perf_counter()
                                for current in ((ids,) if kind == "patcher_prefill" else extensions):
                                    result = patcher(current)
                                    del result
                                torch.cuda.synchronize()
                                elapsed = time.perf_counter() - started
                            if mode in adapters:
                                after = backgrounds[mode].cache_info()
                                workloads[mode] = (after.hits - before.hits, after.misses - before.misses)
                            if repetition >= 0:
                                samples[mode].append(elapsed)
                                peaks[mode] = max(peaks[mode], torch.cuda.max_memory_allocated())
                                if kind == "model_total32":
                                    for name in parts:
                                        parts[name][mode].append(durations[name])
                        if workloads["count_python"] != workloads["count_cpp"]:
                            raise ValueError("Count backends saw different lookup workloads")
                    measured = {mode: {**timing_summary(times), "peak_cuda_allocated_bytes": peaks[mode]}
                                for mode, times in samples.items()}
                    measured["ratios"] = {"original_over_count_cpp": ratio_summary(samples["original"], samples["count_cpp"]),
                                          "original_over_count_python": ratio_summary(samples["original"], samples["count_python"]),
                                          "count_python_over_count_cpp": ratio_summary(samples["count_python"], samples["count_cpp"])}
                    case["measurements"][kind] = measured
                    if kind == "model_total32":
                        for name, modes in parts.items():
                            case["measurements"][name] = {mode: timing_summary(times) for mode, times in modes.items()}
                report["cases"].append(case)
                save_report(args.output_directory, args.stage, report)
                print(json.dumps({"timing_case": len(report["cases"]), "input_length": case["input_length"]}), flush=True)
        report["status"] = "completed"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        save_report(args.output_directory, args.stage, report)


if __name__ == "__main__":
    main()
