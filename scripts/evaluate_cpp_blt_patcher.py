"""Evaluate the opt-in package C++ backend against neural and Python patchers."""

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
from phdq_blt_cache.native_patcher import load_count_native
from scripts.benchmark_cpp_count_patcher import build_native, paired_summary, sha256
from scripts.compare_blt_patchers import boundary_comparison, boundary_summary, bpb_summary, evaluation_documents, incremental_prefixes, timed_replay
from scripts.smoke_blt_count_patcher import sample_generate


def compare_logits(python_logits, cpp_logits, python_lengths, cpp_lengths, torch):
    if not torch.equal(python_lengths, cpp_lengths):
        raise ValueError("Package C++/Python patch lengths differ")
    if not torch.equal(python_logits, cpp_logits):
        raise ValueError("Package C++/Python model logits differ")


def save_report(directory, stage, report):
    temporary = directory / (stage + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(directory / (stage + (".json" if report["status"] == "completed" else ".progress.json")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("quality-reference", "total-reference", "generation-reference", "native-reference",
                 "dataset-directory", "background", "blt-project", "conversion-report", "output-directory"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output_directory.exists():
        raise FileExistsError(args.output_directory)
    quality_reference = json.loads(args.quality_reference.read_text())
    total_reference = json.loads(args.total_reference.read_text())
    generation_reference = json.loads(args.generation_reference.read_text())
    native_reference = json.loads(args.native_reference.read_text())
    for reference in (quality_reference, total_reference, generation_reference, native_reference):
        if reference["status"] != "completed":
            raise ValueError("Expected completed frozen references")
        # The native reference only certifies the kernel; Python/C++ equality is rechecked on every chunk below.
        for key in ("count_config",) if reference is native_reference else ("rule", "count_config"):
            if reference[key] != quality_reference[key]:
                raise ValueError("Frozen candidate differs: " + key)
    for reference in (total_reference, generation_reference):
        for key in ("model_checkpoint", "sources", "split_sha256", "runtime"):
            if key == "sources":
                for path, digest in quality_reference[key].items():
                    if reference[key].get(path) != digest:
                        raise ValueError("Reference source differs")
            elif reference[key] != quality_reference[key]:
                raise ValueError("Frozen reference differs: " + key)
    for path, digest in quality_reference["sources"].items():
        if sha256(path) != digest:
            raise ValueError("Frozen source changed: " + path)
    for split, digest in quality_reference["split_sha256"].items():
        if sha256(args.dataset_directory / (split + ".jsonl")) != digest:
            raise ValueError("Protected split changed: " + split)
    for symbol in (CountConfig, LMDBCountTable):
        source = Path(inspect.getfile(symbol)).resolve()
        expected = [digest for path, digest in quality_reference["code_sha256"].items() if path.endswith("/" + source.name)]
        if expected != [sha256(source)]:
            raise ValueError("Frozen count math/DB changed")
    cpp_source = Path(__file__).parent / "native/count_patcher.cpp"
    if sha256(cpp_source) != native_reference["cpp_sha256"]:
        raise ValueError("Measured C++ kernel changed")
    import torch
    import transformers

    torch.set_num_threads(8)
    torch.cuda.set_device(0)
    if (torch.__version__, torch.cuda.get_device_name(0), transformers.__version__) != (
            quality_reference["runtime"]["torch"], quality_reference["runtime"]["gpu"], quality_reference["runtime"]["transformers"]):
        raise ValueError("Runtime differs")
    for path, digest in quality_reference["code_sha256"].items():
        if "/blt_hf/" in path and sha256(path) != digest:
            raise ValueError("Model dependency changed")
    module, command, library = build_native(args.output_directory / "native")
    sys.path.insert(0, str(args.blt_project.resolve()))
    from blt_hf.model import load_model

    identity = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_checkpoint": quality_reference["model_checkpoint"],
        "model_safetensors_sha256": sha256(Path(quality_reference["model_checkpoint"]) / "model.safetensors"),
        "rule": quality_reference["rule"], "count_config": quality_reference["count_config"],
        "split_sha256": quality_reference["split_sha256"], "runtime": quality_reference["runtime"],
        "sources": {str(path): sha256(path) for path in (args.quality_reference, args.total_reference, args.generation_reference, args.native_reference, args.conversion_report)},
        "code_sha256": {str(Path(path).resolve()): sha256(path) for path in (
            Path(__file__), inspect.getfile(CountPatcherAdapter), inspect.getfile(CountConfig),
            inspect.getfile(LMDBCountTable), inspect.getfile(inspect.unwrap(load_count_native)), inspect.getfile(build_native),
            inspect.getfile(timed_replay), inspect.getfile(sample_generate), cpp_source)},
        "library": str(library.resolve()), "library_sha256": sha256(library), "build_command": command,
        "scope": "Actual package CountPatcherAdapter backend=cpp; frozen rule; no model cache or retuning",
        "limitations": "One model/GPU/batch1/beam1; original neural weights stay resident; no automatic adoption or task-quality improvement claim",
    }
    if identity["model_safetensors_sha256"] != "4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061":
        raise ValueError("Frozen model weights differ")
    model = load_model(Path(identity["model_checkpoint"]), args.conversion_report,
                       attention_mode="osc", backend="eager", device="cuda").eval()
    if model.dtype != torch.bfloat16 or model.config.vocab_size != 260 or model.config.max_patch_length is not None:
        raise ValueError("Expected frozen BF16 byte model without patch cap")
    config, rule = CountConfig(**identity["count_config"]), BoundaryRule(**identity["rule"])
    with LMDBCountTable(args.background) as background, torch.inference_mode():
        if background.metadata != total_reference["background"]:
            raise ValueError("Background metadata differs")
        identity["background"] = background.metadata
        backgrounds = {mode: copy.copy(background) for mode in ("count_lmdb", "count_cpp")}
        for candidate in backgrounds.values():
            candidate._cached_lookup = lru_cache(maxsize=4096)(candidate._read)
        adapters = {mode: CountPatcherAdapter(config, rule, candidate,
                    backend="cpp" if mode == "count_cpp" else "python",
                    native_library=library if mode == "count_cpp" else None)
                    for mode, candidate in backgrounds.items()}

        def forward(ids, mode, last_only=True):
            lengths = adapters[mode].patch_lengths(ids) if mode in adapters else None
            output = model(input_ids=ids, patch_lengths=lengths, use_cache=False,
                           logits_to_keep=1 if last_only else 0)
            return output.logits, lengths

        report = {**identity, "status": "running", "stage": "quality", "documents": [],
                  "protocol": "All frozen test/Wikipedia documents, nonoverlapping2047-byte chunks+BOS; three full-model modes; Python/C++ exact boundaries and full logits required",
                  "controls": {"chunks": 0, "prior_patch_length_mismatches": 0, "max_prior_nll_abs_difference": 0.}}
        prior_documents = {(doc["split"], doc["text_sha256"]): doc for doc in quality_reference["documents"]}
        seen = set()
        totals = Counter()
        for split in ("test", "wikipedia_test"):
            for metadata, chunks in evaluation_documents(args.dataset_directory, split):
                key = (split, metadata["text_sha256"])
                if key not in prior_documents or key in seen:
                    raise ValueError("Evaluation document differs from frozen reference")
                seen.add(key)
                prior = prior_documents[key]
                if len(chunks) != len(prior["chunks"]):
                    raise ValueError("Evaluation chunk count differs")
                document = {**metadata, "chunks": [], "modes": {mode: {"nll_nats": 0.} for mode in ("original", "count_lmdb", "count_cpp")}}
                for index, values in enumerate(chunks):
                    ids = torch.tensor([values], dtype=torch.long, device="cuda")
                    entry = {"index": index, "scored_bytes": len(values) - 1, "modes": {}}
                    python_logits = python_lengths = None
                    for mode in ("original", "count_lmdb", "count_cpp"):
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
                        if mode == "count_lmdb":
                            python_logits, python_lengths = logits, lengths
                        elif mode == "count_cpp":
                            compare_logits(python_logits, logits, python_lengths, lengths, torch)
                        nll = torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1, 260), ids[:, 1:].reshape(-1), reduction="sum").item()
                        patch_lengths = captured["lengths"] if mode == "original" else lengths.tolist()[0]
                        entry["modes"][mode] = {"nll_nats": nll, "patch_lengths": patch_lengths}
                        document["modes"][mode]["nll_nats"] += nll
                        if mode != "count_cpp":
                            expected = prior["chunks"][index]["modes"][mode]
                            report["controls"]["prior_patch_length_mismatches"] += int(expected["patch_lengths"] != patch_lengths)
                            report["controls"]["max_prior_nll_abs_difference"] = max(report["controls"]["max_prior_nll_abs_difference"], abs(expected["nll_nats"] - nll))
                    del logits, python_logits, python_lengths, lengths
                    counts = boundary_comparison(entry["modes"]["original"]["patch_lengths"], entry["modes"]["count_cpp"]["patch_lengths"], len(values))
                    totals.update(counts)
                    document["chunks"].append(entry)
                    report["controls"]["chunks"] += 1
                for mode in document["modes"]:
                    document["modes"][mode]["bpb"] = document["modes"][mode]["nll_nats"] / (metadata["utf8_bytes"] * math.log(2))
                document["delta_bpb"] = document["modes"]["count_cpp"]["bpb"] - document["modes"]["original"]["bpb"]
                report["documents"].append(document)
                save_report(args.output_directory, "quality", report)
                if len(report["documents"]) % 20 == 0:
                    print("quality_progress", len(report["documents"]), flush=True)
            print("quality", split, len(report["documents"]), flush=True)
        if seen != set(prior_documents):
            raise ValueError("Missing frozen evaluation documents")
        report["quality_summary"] = {split: bpb_summary([doc for doc in report["documents"] if split == "combined" or doc["split"] == split]) for split in ("test", "wikipedia_test", "combined")}
        report["boundary_summary"] = boundary_summary(dict(totals))
        report["controls"]["python_cpp_all_boundaries_logits_nll_exact"] = True
        report["status"] = "completed"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save_report(args.output_directory, "quality", report)

        report = {**identity, "status": "running", "stage": "timing", "cases": [],
                  "protocol": {"work": "Initial prefix + identical32 byte extensions in one full-model block; initial/incremental/total timestamps", "warmups": 3, "repeats": 10,
                               "order": "Rotate three modes and reverse on odd repeats", "included": "Whole model, count lookup/compute/transfers; final logits only",
                               "excluded": "Loading/build/reset, diagnostics, sampling/selection/decoding", "cache": "Independent identical4096 LRUs; same warmups and matched count hit/miss; model cache disabled"}}
        for case in total_reference["timing_cases"]:
            ids = torch.tensor([case["input_ids"]], dtype=torch.long, device="cuda")
            priming, extensions = incremental_prefixes(ids)
            for adapter in adapters.values():
                adapter.reset()
            for current in (priming, *extensions):
                python_logits, python_lengths = forward(current, "count_lmdb")
                cpp_logits, cpp_lengths = forward(current, "count_cpp")
                compare_logits(python_logits, cpp_logits, python_lengths, cpp_lengths, torch)
                del python_logits, cpp_logits, python_lengths, cpp_lengths
            for candidate in backgrounds.values():
                candidate._cached_lookup.cache_clear()
            record = {key: value for key, value in case.items() if key != "measurements"}
            record["initial_length"] = priming.shape[1]
            samples = []
            for repetition in range(-3, 10):
                order = ["original", "count_lmdb", "count_cpp"]
                offset = repetition % 3
                order = order[offset:] + order[:offset]
                if repetition % 2:
                    order.reverse()
                sample = {"repetition": repetition, "order": order, "modes": {}}
                for mode in order:
                    if mode in adapters:
                        adapters[mode].reset()
                    before = backgrounds[mode].cache_info() if mode in backgrounds else None
                    torch.cuda.reset_peak_memory_stats()
                    durations = timed_replay(priming, extensions, lambda current: forward(current, mode), torch.cuda.synchronize)
                    durations["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated()
                    if before is not None:
                        after = backgrounds[mode].cache_info()
                        durations["cache"] = {"hits": after.hits - before.hits, "misses": after.misses - before.misses}
                    sample["modes"][mode] = durations
                if sample["modes"]["count_lmdb"]["cache"] != sample["modes"]["count_cpp"]["cache"]:
                    raise ValueError("Whole-model timing cache workloads differ")
                if repetition >= 0:
                    samples.append(sample)
            record["samples"] = samples
            record["comparisons"] = {kind: {baseline: paired_summary([
                {"python": sample["modes"][baseline][kind], "cpp": sample["modes"]["count_cpp"][kind]} for sample in samples])
                for baseline in ("original", "count_lmdb")} for kind in ("model_initial", "model_incremental32", "model_total32")}
            record["python_cpp_replay_controls"] = 33
            report["cases"].append(record)
            save_report(args.output_directory, "timing", report)
            print("timing", case["split"], case["input_length"], flush=True)
        report["status"] = "completed"
        report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save_report(args.output_directory, "timing", report)

        report = {**identity, "status": "running", "stage": "generation", "generations": [],
                  "protocol": "Same18 recorded Python count prompts/seeds, T1/top_p1/top_k0/cap2048; C++ fresh replay; exact full IDs/text required, no length-mismatched speedup claim"}
        references = [row for row in generation_reference["generations"] if row["mode"] == "count_lmdb"]
        if len(references) != 18:
            raise ValueError("Expected18 frozen count generations")
        for reference in references:
            ids = torch.tensor([reference["input_ids"]], device="cuda", dtype=torch.long)
            adapters["count_cpp"].reset()
            sample_generate(ids, lambda current: forward(current, "count_cpp"), max_new_tokens=16, seed=reference["seed"])
            adapters["count_cpp"].reset()
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            generated = sample_generate(ids, lambda current: forward(current, "count_cpp"), max_new_tokens=reference["max_new_tokens"], seed=reference["seed"])
            torch.cuda.synchronize()
            generated.update(name=reference["name"], seed=reference["seed"], input_ids=reference["input_ids"], mode="count_cpp",
                             generation_seconds=time.perf_counter() - started, peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
                             matches_python_reference_ids=generated["generated_ids"] == reference["generated_ids"], matches_python_reference_text=generated["text"] == reference["text"])
            report["generations"].append(generated)
            save_report(args.output_directory, "generation", report)
            if not generated["matches_python_reference_ids"] or not generated["matches_python_reference_text"]:
                raise ValueError("C++ generation differs from frozen Python count output")
            print("generation", generated["name"], generated["seed"], len(generated["generated_ids"]), flush=True)
        report["status"] = "completed"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save_report(args.output_directory, "generation", report)


if __name__ == "__main__":
    main()