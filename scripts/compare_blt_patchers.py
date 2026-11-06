"""Compare a frozen count patcher with the OSC neural patcher without cache reuse."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
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
from scripts.patcher_preflight import file_hash
from scripts.smoke_blt_count_patcher import sample_generate, timing_summary


def evaluation_documents(directory, split):
    with (Path(directory) / f"{split}.jsonl").open() as stream:
        seen = set()
        for line in stream:
            row = json.loads(line)
            raw = row["text"].encode("utf-8")
            if not raw or hashlib.sha256(raw).hexdigest() != row["text_sha256"]:
                raise ValueError("Invalid evaluation document content hash")
            identity = (row["source"], row["document_id"])
            if identity in seen:
                raise ValueError("Repeated evaluation document identity")
            seen.add(identity)
            metadata = {key: row[key] for key in ("source", "revision", "document_id", "text_sha256")}
            chunks = [[1] + [value + 4 for value in raw[start:start + 2047]]
                      for start in range(0, len(raw), 2047)]
            yield dict(metadata, split=split, utf8_bytes=len(raw)), chunks


def boundary_comparison(reference, candidate, input_length):
    def starts(lengths):
        if not lengths or any(type(value) is not int or value <= 0 for value in lengths):
            raise ValueError("Expected positive integral OSC patch lengths")
        if sum(lengths) != input_length + 1:
            raise ValueError("Patch lengths must include the virtual next-byte slot")
        offset = 0
        result = set()
        for length in lengths:
            if 2 <= offset <= input_length:
                result.add(offset)
            offset += length
        return result

    original, proposed = starts(reference), starts(candidate)
    return {"tp": len(original & proposed), "fp": len(proposed - original),
            "fn": len(original - proposed), "positions": input_length - 1}


def boundary_summary(counts):
    tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
    return {**counts, "precision": tp / (tp + fp) if tp + fp else 0.,
            "recall": tp / (tp + fn) if tp + fn else 0.,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.,
            "f0_5": 1.25 * tp / (1.25 * tp + fp + .25 * fn) if tp + fp + fn else 0.}


def bpb_summary(documents):
    import numpy as np

    if len(documents) < 2:
        raise ValueError("Document bootstrap requires at least two documents")
    values = np.asarray([[doc["modes"][mode]["nll_nats"] for mode in ("original", "count_lmdb")]
                         + [doc["utf8_bytes"]] for doc in documents], dtype=np.float64)
    if not np.isfinite(values).all() or (values[:, 2] <= 0).any():
        raise ValueError("Invalid document losses or byte counts")
    total = values.sum(axis=0)
    indices = np.random.default_rng(20261019).integers(0, len(values), size=(2000, len(values)))
    samples = values[indices].sum(axis=1)
    differences = (samples[:, 1] - samples[:, 0]) / (samples[:, 2] * math.log(2))
    lower, upper = np.percentile(differences, [2.5, 97.5]).tolist()
    return {"documents": len(documents), "scored_bytes": int(total[2]),
            "original_bpb": total[0] / (total[2] * math.log(2)),
            "count_bpb": total[1] / (total[2] * math.log(2)),
            "delta_bpb": (total[1] - total[0]) / (total[2] * math.log(2)),
            "paired_document_bootstrap95": [lower, upper], "bootstrap_replicates": 2000,
            "bootstrap_seed": 20261019, "maximum_bpb_increase": .01,
            "bpb_criterion_passed": upper <= .01}


def incremental_prefixes(input_ids, steps=32):
    if type(steps) is not int or steps <= 0:
        raise ValueError("Incremental steps must be a positive integer")
    if input_ids.ndim != 2 or input_ids.shape[0] != 1 or input_ids.shape[1] - steps < 2:
        raise ValueError("Expected a single prefix with at least two priming IDs")
    start = input_ids.shape[1] - steps
    return input_ids[:, :start], tuple(input_ids[:, :endpoint]
                                      for endpoint in range(start + 1, input_ids.shape[1] + 1))


def timed_replay(priming, extensions, forward, synchronize, clock=time.perf_counter):
    synchronize()
    started = clock()
    result = forward(priming)
    del result
    synchronize()
    initial_finished = clock()
    for current in extensions:
        result = forward(current)
        del result
    synchronize()
    finished = clock()
    return {"model_initial": initial_finished - started,
            "model_incremental32": finished - initial_finished,
            "model_total32": finished - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("quality", "timing", "generation", "incremental", "total"), required=True)
    for name in ("blt-project", "model-checkpoint", "conversion-report", "fit-report", "background",
                 "dataset-directory", "preparation-report", "label-report", "pilot-config", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--prompt-report", type=Path)
    parser.add_argument("--sampling-reference", type=Path)
    parser.add_argument("--timing-reference", type=Path)
    args = parser.parse_args()
    if args.stage == "generation" and (args.prompt_report is None or args.sampling_reference is None):
        parser.error("Generation requires --prompt-report and --sampling-reference")
    if args.stage in ("incremental", "total") and args.timing_reference is None:
        parser.error("Replay requires --timing-reference")
    if args.output.exists() or args.output.with_suffix(".progress.json").exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import torch
    import transformers

    torch.set_num_threads(8)
    torch.cuda.set_device(0)
    sys.path.insert(0, str(args.blt_project.resolve()))
    from blt_hf.model import load_model

    fitted = json.loads(args.fit_report.read_text())
    preparation = json.loads(args.preparation_report.read_text())
    labels = json.loads(args.label_report.read_text())
    pilot = json.loads(args.pilot_config.read_text())
    config, rule = CountConfig(**fitted["count_config"]), BoundaryRule(**fitted["selected_rule"])
    if fitted["label_report_sha256"] != file_hash(args.label_report):
        raise ValueError("Fitted label report changed")
    if labels["contract"]["conversion_sha256"] != file_hash(args.conversion_report):
        raise ValueError("Fitted conversion changed")
    gates = pilot["gates"]
    if (gates["maximum_bpb_increase"], gates["bootstrap_replicates"]) != (.01, 2000):
        raise ValueError("Preserved BPB contract differs")
    if (pilot["baseline"]["warmup_repetitions"], pilot["baseline"]["timed_repetitions"]) != (3, 10):
        raise ValueError("Preserved timing contract differs")
    split_hashes = {}
    for split in ("background", "train", "validation", "test", "wikipedia_test"):
        digest = file_hash(args.dataset_directory / f"{split}.jsonl")
        if digest != preparation["original_split_hashes"][split]:
            raise ValueError(f"Protected split changed: {split}")
        split_hashes[split] = digest
    prohibited = set()
    for split in ("train", "validation"):
        for metadata, _ in evaluation_documents(args.dataset_directory, split):
            prohibited.add(metadata["text_sha256"])
    report = {"status": "running", "stage": args.stage,
              "scope": "Frozen neural/count patcher comparison; no cache reuse or refitting",
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "model_checkpoint": str(args.model_checkpoint), "rule": fitted["selected_rule"],
              "count_config": fitted["count_config"], "split_sha256": split_hashes,
              "sources": {str(path): file_hash(path) for path in (
                  args.fit_report, args.preparation_report, args.label_report, args.conversion_report, args.pilot_config)},
              "code_sha256": {str(path): file_hash(path) for path in (
                  Path(__file__), Path(inspect.getfile(sample_generate)), Path(inspect.getfile(CountPatcherAdapter)),
                  Path(inspect.getfile(CountConfig)), Path(inspect.getfile(LMDBCountTable)),
                  args.blt_project / "blt_hf/model.py", args.blt_project / "blt_hf/attention.py",
                  args.blt_project / "blt_hf/patching.py", args.blt_project / "blt_hf/patched/modeling_blt.py")},
              "runtime": {"torch": torch.__version__, "transformers": transformers.__version__,
                          "gpu": torch.cuda.get_device_name(0), "threads": 8, "dtype": "bfloat16",
                          "attention": "osc", "backend": "eager", "batch": 1, "beam": 1, "cache": False},
              "limitations": "Protected exact/URL/MinHash128 approximate dedup reused, not exhaustive or unseen model-pretraining proof. Frozen F1-selected rule; F0.5 reporting is not retuning. Warm LMDB and original patcher weights stay resident. No full candidate adoption follows from a single criterion.",
              "protocol": {"quality": "Entire test and wikipedia_test; nonoverlapping 2047-byte chunks with BOS per chunk; no appended special target; all original bytes scored; reset count state per chunk",
                           "boundary_positions": "2..input_length inclusive; starts 0/1 excluded, virtual next-byte position included, same label contract",
                           "sampling": {"do_sample": True, "temperature": 1., "top_p": 1., "top_k": 0,
                                        "seeds": [42, 20261027], "max_new_tokens": 2048},
                           "timing": "One first eligible first-chunk per split/length; 256/512/1024/2048 IDs; warmup3/repeat10, alternate modes per repeat. Separate patcher prefill, full-model last-logit prefill and patcher 32-step same-prefix continuation. Continuation priming excluded; count prefix reuse enabled, model cache disabled."},
              "documents": [], "timing_cases": [], "generations": []}

    reference = None
    if args.stage in ("incremental", "total"):
        reference = json.loads(args.timing_reference.read_text())
        if reference["status"] != "completed" or reference["stage"] != "timing":
            raise ValueError("Expected completed original timing evidence")
        for key in ("model_checkpoint", "rule", "count_config", "split_sha256", "sources", "runtime"):
            if reference[key] != report[key]:
                raise ValueError(f"Timing reference differs: {key}")
        for path, digest in reference["code_sha256"].items():
            if Path(path).name != Path(__file__).name and file_hash(Path(path)) != digest:
                raise ValueError(f"Frozen dependency changed: {path}")
        report["sources"][str(args.timing_reference)] = file_hash(args.timing_reference)
        report["protocol"]["timing"] = {
            "measurement": "Full-model last-logit teacher-forced same-byte replay; not free generation",
            "steps": 32, "warmup_repetitions": 3, "timed_repetitions": 10,
            "order": "original/count on even repeat indices, reversed on odd indices; warmups included",
            "inputs": "Exact eight split/length/document/ID cases from timing reference",
            "priming": "One full-model forward on prefix ending 32 IDs before endpoint, excluded from timing",
            "timed_work": "32 full-model forwards on identical growing prefixes, ending at recorded input length",
            "cache": False, "count_prefix_state_reused": True,
            "excluded": "Model loading, priming, sampling, byte selection, output decoding and correctness controls",
            "included": "Count lookup, CPU work, transfers, patcher, encoder, global transformer and decoder",
            "controls": "Every count replay step must exactly match fresh-prefix patch lengths and logits",
            "time_unit": "seconds for the entire 32-forward block; not single-step percentiles"}
        if args.stage == "total":
            report["protocol"]["timing"].update(
                measurement="Full-model initial prefix plus same-byte replay, measured in one execution",
                priming="Initial full-model prefix forward included in model_total32 and separately recorded as model_initial",
                timed_work="One initial prefix forward followed by 32 identical growing-prefix forwards; 33 forwards per block",
                excluded="Model loading, adapter reset, sampling, byte selection, decoding, warmups and correctness controls",
                time_unit="seconds; model_initial plus model_incremental32 equals model_total32 per paired sample",
                synchronization="GPU synchronized at start, initial/incremental boundary and end")

    def checkpoint():
        temporary = args.output.with_suffix(".progress.tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(args.output.with_suffix(".progress.json"))

    try:
        with LMDBCountTable(args.background) as background:
            if background.config != config or background.metadata["source_report_sha256"] != fitted["background_report_sha256"]:
                raise ValueError("Fitted background and LMDB differ")
            if reference is not None and background.metadata != reference["background"]:
                raise ValueError("Timing reference background differs")
            report["background"] = background.metadata
            model = load_model(args.model_checkpoint, args.conversion_report,
                               attention_mode="osc", backend="eager", device="cuda").eval()
            if not torch.cuda.is_bf16_supported() or model.dtype != torch.bfloat16 or model.config.vocab_size != 260:
                raise ValueError("Expected BF16 byte model")
            adapter = CountPatcherAdapter(config, rule, background)
            cap = model.config.max_patch_length

            def forward(ids, candidate, last_only=False):
                lengths = adapter.patch_lengths(ids, max_patch_length=cap) if candidate else None
                output = model(input_ids=ids, patch_lengths=lengths, use_cache=False,
                               logits_to_keep=1 if last_only else 0)
                return output.logits, lengths

            def inspect_forward(ids, candidate):
                captured = {}

                def hook(module, inputs, output):
                    captured["lengths"] = output[1].detach().cpu().tolist()[0]

                handle = model.model.patcher.register_forward_hook(hook) if not candidate else None
                adapter.reset()
                try:
                    logits, lengths = forward(ids, candidate)
                    if not torch.isfinite(logits).all():
                        raise ValueError("Nonfinite model logits")
                    loss = torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1, 260),
                                                             ids[:, 1:].reshape(-1), reduction="sum")
                    return loss.item(), (lengths.detach().cpu().tolist()[0] if candidate else captured["lengths"])
                finally:
                    if handle is not None:
                        handle.remove()

            with torch.inference_mode():
                if args.stage == "quality":
                    boundary_totals = Counter()
                    length_histograms = {mode: Counter() for mode in ("original", "count_lmdb")}
                    seen = set(prohibited)
                    for split in ("test", "wikipedia_test"):
                        for metadata, chunks in evaluation_documents(args.dataset_directory, split):
                            if metadata["text_sha256"] in seen:
                                raise ValueError("Evaluation document overlaps another split")
                            seen.add(metadata["text_sha256"])
                            document = {**metadata, "chunks": [], "modes": {
                                mode: {"nll_nats": 0.} for mode in ("original", "count_lmdb")}}
                            for index, original in enumerate(chunks):
                                ids = torch.tensor([original], device="cuda", dtype=torch.long)
                                chunk = {"index": index, "byte_offset": index * 2047,
                                         "scored_bytes": len(original) - 1, "modes": {}}
                                for candidate in (False, True):
                                    mode = "count_lmdb" if candidate else "original"
                                    nll, lengths = inspect_forward(ids, candidate)
                                    document["modes"][mode]["nll_nats"] += nll
                                    chunk["modes"][mode] = {"nll_nats": nll, "patch_lengths": lengths}
                                    length_histograms[mode].update(lengths)
                                counts = boundary_comparison(chunk["modes"]["original"]["patch_lengths"],
                                                             chunk["modes"]["count_lmdb"]["patch_lengths"], len(original))
                                chunk["boundaries"] = counts
                                boundary_totals.update(counts)
                                document["chunks"].append(chunk)
                            for mode in document["modes"]:
                                document["modes"][mode]["bpb"] = document["modes"][mode]["nll_nats"] / (metadata["utf8_bytes"] * math.log(2))
                            document["delta_bpb"] = document["modes"]["count_lmdb"]["bpb"] - document["modes"]["original"]["bpb"]
                            report["documents"].append(document)
                            checkpoint()
                        print(json.dumps({"completed_split": split, "documents": len(report["documents"])}), flush=True)
                    report["quality_summary"] = {split: bpb_summary([
                        doc for doc in report["documents"] if doc["split"] == split]) for split in ("test", "wikipedia_test")}
                    report["quality_summary"]["combined"] = bpb_summary(report["documents"])
                    report["boundary_summary"] = boundary_summary(dict(boundary_totals))
                    report["patch_length_histograms"] = {mode: dict(sorted(hist.items())) for mode, hist in length_histograms.items()}
                elif args.stage in ("timing", "incremental", "total"):
                    reference_cases = {}
                    if reference is not None:
                        reference_cases = {(case["split"], case["input_length"]): case
                                           for case in reference["timing_cases"]}
                        expected_cases = {(split, length) for split in ("test", "wikipedia_test")
                                          for length in (256, 512, 1024, 2048)}
                        if len(reference["timing_cases"]) != 8 or set(reference_cases) != expected_cases:
                            raise ValueError("Expected exact eight reference timing cases")
                    for split in ("test", "wikipedia_test"):
                        documents = list(evaluation_documents(args.dataset_directory, split))
                        for length in (256, 512, 1024, 2048):
                            metadata, chunks = next((meta, chunks) for meta, chunks in documents if len(chunks[0]) >= length)
                            ids = torch.tensor([chunks[0][:length]], device="cuda", dtype=torch.long)
                            captured = {}

                            def save_call(module, inputs, kwargs):
                                bound = inspect.signature(module.forward).bind(*inputs, **kwargs)
                                captured.update(bound.arguments)

                            handle = model.model.patcher.register_forward_pre_hook(save_call, with_kwargs=True)
                            try:
                                forward(ids, False, last_only=True)
                            finally:
                                handle.remove()
                            options = {**captured.pop("kwargs", {}), **captured}
                            options.update(position_ids=None, attention_mask=None, use_cache=False, past_key_values=None)

                            def neural_lengths(current):
                                return model.model.patcher(**{**options, "input_ids": current})[1]

                            _, expected = inspect_forward(ids, False)
                            if neural_lengths(ids).tolist()[0] != expected:
                                raise AssertionError("Standalone neural patcher differs from model call")
                            case = {**metadata, "input_length": length, "input_ids": ids.tolist()[0], "measurements": {}}
                            priming, extensions = incremental_prefixes(ids)
                            if reference is not None:
                                previous = reference_cases[(split, length)]
                                if any(case[key] != previous[key] for key in case if key != "measurements"):
                                    raise ValueError("Replay inputs differ from timing reference")
                                adapter.reset()
                                forward(priming, True, last_only=True)
                                warm_outputs = []
                                for current in extensions:
                                    logits, lengths = forward(current, True, last_only=True)
                                    if logits.shape != (1, 1, 260) or not torch.isfinite(logits).all():
                                        raise ValueError("Invalid count replay logits")
                                    warm_outputs.append((logits.detach().clone(), lengths.detach().clone()))
                                for current, (expected_logits, expected_lengths) in zip(extensions, warm_outputs):
                                    adapter.reset()
                                    logits, lengths = forward(current, True, last_only=True)
                                    if not torch.equal(lengths, expected_lengths) or not torch.equal(logits, expected_logits):
                                        raise AssertionError("Incremental count state differs from fresh-prefix forward")
                                del warm_outputs, logits, lengths, expected_logits, expected_lengths
                                case["replay_control"] = {"steps": len(extensions), "priming_length": priming.shape[1],
                                                          "first_timed_length": extensions[0].shape[1],
                                                          "last_timed_length": extensions[-1].shape[1],
                                                          "reference_input_ids_match": True,
                                                          "count_warm_fresh_boundaries_equal": True,
                                                          "count_warm_fresh_logits_equal": True}
                            kinds = (("model_total32",) if args.stage == "total" else
                                     ("model_incremental32",) if reference is not None else
                                     ("patcher_prefill", "model_prefill", "patcher_incremental32"))
                            for kind in kinds:
                                samples = {mode: [] for mode in ("original", "count_lmdb")}
                                peaks = {mode: 0 for mode in samples}
                                parts = ({name: {mode: [] for mode in samples}
                                          for name in ("model_initial", "model_incremental32")}
                                         if kind == "model_total32" else {})
                                for repeat in range(13):
                                    for candidate in ((False, True) if repeat % 2 == 0 else (True, False)):
                                        mode = "count_lmdb" if candidate else "original"
                                        adapter.reset()
                                        patcher = (lambda current: adapter.patch_lengths(current, max_patch_length=cap)) if candidate else neural_lengths
                                        if kind == "patcher_incremental32":
                                            patcher(priming)
                                        elif kind == "model_incremental32":
                                            forward(priming, candidate, last_only=True)
                                        torch.cuda.reset_peak_memory_stats()
                                        if kind == "model_total32":
                                            durations = timed_replay(
                                                priming, extensions,
                                                lambda current: forward(current, candidate, last_only=True),
                                                torch.cuda.synchronize)
                                            elapsed = durations[kind]
                                        else:
                                            torch.cuda.synchronize()
                                            started = time.perf_counter()
                                            if kind == "model_prefill":
                                                result = forward(ids, candidate, last_only=True)
                                                del result
                                            elif kind == "patcher_prefill":
                                                result = patcher(ids)
                                                del result
                                            else:
                                                for current in extensions:
                                                    result = (forward(current, candidate, last_only=True)
                                                              if kind == "model_incremental32" else patcher(current))
                                                    del result
                                            torch.cuda.synchronize()
                                            elapsed = time.perf_counter() - started
                                        if repeat >= 3:
                                            samples[mode].append(elapsed)
                                            peaks[mode] = max(peaks[mode], torch.cuda.max_memory_allocated())
                                            for name in parts:
                                                parts[name][mode].append(durations[name])
                                case["measurements"][kind] = {mode: {**timing_summary(times), "peak_cuda_allocated_bytes": peaks[mode]}
                                                              for mode, times in samples.items()}
                                for name, modes in parts.items():
                                    case["measurements"][name] = {mode: timing_summary(times) for mode, times in modes.items()}
                            report["timing_cases"].append(case)
                            checkpoint()
                            print(json.dumps({"completed_timing_cases": len(report["timing_cases"]), "length": length}), flush=True)
                else:
                    prompts = json.loads(args.prompt_report.read_text())
                    reference = json.loads(args.sampling_reference.read_text())
                    if prompts["model_checkpoint"] != str(args.model_checkpoint) or reference["model_checkpoint"] != str(args.model_checkpoint):
                        raise ValueError("Recorded model checkpoint differs")
                    recorded = {(run["name"], run["seed"]): run for run in reference["decoding_runs"] if run["policy"] == "full_sampling"}
                    controls = prompts["simple_controls"]
                    if len(controls) != 9 or set(recorded) != {(case["name"], seed) for case in controls for seed in (42, 20261027)}:
                        raise ValueError("Expected fixed nine prompts and two sampling seeds")
                    report["sources"].update({str(path): file_hash(path) for path in (args.prompt_report, args.sampling_reference)})
                    for case in controls:
                        original = case["input_ids"]
                        if original[0] != 1 or any(not 4 <= value < 260 for value in original[1:]) or len(original) + 2048 > model.config.max_position_embeddings:
                            raise ValueError("Invalid prompt or context budget")
                        ids = torch.tensor([original], device="cuda", dtype=torch.long)
                        for candidate in (False, True):
                            adapter.reset()
                            sample_generate(ids, lambda current: forward(current, candidate, last_only=True), max_new_tokens=16, seed=42)
                        for index, seed in enumerate((42, 20261027)):
                            for candidate in ((False, True) if index == 0 else (True, False)):
                                mode = "count_lmdb" if candidate else "original"
                                if recorded[(case["name"], seed)]["input_ids"] != original:
                                    raise ValueError("Recorded sampling prompt differs")
                                adapter.reset()
                                torch.cuda.reset_peak_memory_stats()
                                torch.cuda.synchronize()
                                started = time.perf_counter()
                                result = sample_generate(ids, lambda current: forward(current, candidate, last_only=True), max_new_tokens=2048, seed=seed)
                                torch.cuda.synchronize()
                                result.update(name=case["name"], mode=mode, seed=seed, input_ids=original,
                                              generation_seconds=time.perf_counter() - started,
                                              peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated())
                                report["generations"].append(result)
                                checkpoint()
                                if not candidate:
                                    result["matches_recorded_sampling"] = result["generated_ids"] == recorded[(case["name"], seed)]["generated_ids"]
                                    if not result["matches_recorded_sampling"]:
                                        raise AssertionError("Manual baseline differs from recorded HF sampling")
                                print(json.dumps({"case": case["name"], "mode": mode, "seed": seed,
                                                  "new_ids": len(result["generated_ids"]), "seconds": result["generation_seconds"]}), flush=True)
            report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()