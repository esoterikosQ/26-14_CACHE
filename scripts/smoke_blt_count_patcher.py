"""Small opt-in BLT/count integration diagnostic, not a quality benchmark."""

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import resource
import statistics
import sys
import time

from scripts.patcher_preflight import file_hash
from phdq_blt_cache.blt_patcher import CountPatcherAdapter
from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, decision_patch_lengths, rollout
from phdq_blt_cache.lmdb_counts import LMDBCountTable


def greedy_generate(input_ids, forward, *, max_new_tokens):
    return _generate(input_ids, forward, max_new_tokens=max_new_tokens)


def sample_generate(input_ids, forward, *, max_new_tokens, seed):
    import torch

    if type(seed) is not int or not 0 <= seed < 2 ** 63:
        raise ValueError("seed must be a nonnegative integer below 2**63")
    generator = torch.Generator(device=input_ids.device).manual_seed(seed)
    result = _generate(input_ids, forward, max_new_tokens=max_new_tokens, generator=generator)
    result["sampling"] = {"do_sample": True, "temperature": 1., "top_p": 1., "top_k": 0, "seed": seed}
    return result


def _generate(input_ids, forward, *, max_new_tokens, generator=None):
    import torch

    if type(max_new_tokens) is not int or max_new_tokens < 1:
        raise ValueError("max_new_tokens must be a positive integer")
    generated = []
    current = input_ids
    for _ in range(max_new_tokens):
        logits, _ = forward(current)
        allowed = logits[0, -1].float().clone()
        allowed[[0, 1, 3]] = -torch.inf
        token_id = int(allowed.argmax().item() if generator is None else
                   torch.multinomial(allowed.softmax(dim=-1), 1, generator=generator).item())
        generated.append(token_id)
        del logits
        if token_id == 2:
            break
        current = torch.cat((current, torch.tensor([[token_id]], device=current.device)), dim=1)
    raw = bytes(token_id - 4 for token_id in generated if token_id >= 4)
    try:
        text = raw.decode("utf-8")
        valid_utf8 = True
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
        valid_utf8 = False
    return {"generated_ids": generated, "eos": generated[-1] == 2,
            "stop_reason": "eos" if generated[-1] == 2 else "max_new_tokens",
            "max_new_tokens": max_new_tokens, "text": text, "valid_utf8": valid_utf8}


def timing_summary(samples):
    import numpy as np

    return {"samples_seconds": samples, "p50_seconds": statistics.median(samples),
            "p95_seconds": float(np.percentile(samples, 95)),
            "minimum_seconds": min(samples), "maximum_seconds": max(samples)}


def validation_prefixes(directory, contract_hash, *, lengths=(512, 1024, 2048)):
    import numpy as np

    candidates = []
    for path in sorted(Path(directory).glob("*-0000.npz"))[:64]:
        with np.load(path, allow_pickle=False) as archive:
            if str(archive["contract_sha256"]) != contract_hash:
                raise ValueError("Validation cache contract mismatch")
            token_ids = archive["input_ids"].astype(np.int64).tolist()
        if len(token_ids) < 2 or token_ids[0] != 1 or any(not 0 <= value < 260 or value == 3 for value in token_ids):
            raise ValueError("Invalid validation byte IDs")
        candidates.append((path, token_ids))
    fixtures = []
    for length in lengths:
        eligible = [(path, token_ids) for path, token_ids in candidates if len(token_ids) >= length][:2]
        if len(eligible) != 2:
            raise ValueError(f"Need two validation first-chunks of at least {length} IDs")
        for path, token_ids in eligible:
            fixtures.append(({"source_name": path.name, "source_sha256": file_hash(path),
                              "input_length": length}, token_ids[:length]))
    return fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blt-project", type=Path, required=True)
    parser.add_argument("--model-checkpoint", type=Path, required=True)
    parser.add_argument("--conversion-report", type=Path, required=True)
    parser.add_argument("--fit-report", type=Path, required=True)
    parser.add_argument("--background", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extended", action="store_true")
    parser.add_argument("--validation-labels", type=Path)
    parser.add_argument("--label-report", type=Path)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-new-tokens", type=int, default=16)
    args = parser.parse_args()
    if args.repeats < 1 or args.max_new_tokens < 1:
        parser.error("Positive repeats and max-new-tokens are required")
    if args.extended and (args.validation_labels is None or args.label_report is None):
        parser.error("Extended validation requires --validation-labels and --label-report")
    if args.output.exists() or args.output.with_suffix(".progress.json").exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import torch

    torch.set_num_threads(8)
    torch.manual_seed(20261027)
    torch.cuda.set_device(0)
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("BF16 CUDA is required")
    sys.path.insert(0, str(args.blt_project.resolve()))
    from blt_hf.model import load_model

    fitted = json.loads(args.fit_report.read_text())
    config = CountConfig(**fitted["count_config"])
    rule = BoundaryRule(**fitted["selected_rule"])
    report = {
        "status": "running", "scope": "Opt-in BLT patcher diagnostic, no cache reuse, batch1 BF16 OSC eager",
        "limitations": "Reused validation and synthetic inputs, not unbiased heldout quality or cold-cache timing. Generation paths may differ; total times are not equal-work speedups. Three repeats give a coarse p95. CPU lookup/transfers included; model loading excluded; original patcher weights remain resident.",
        "protocol": {"repeats": args.repeats, "max_new_tokens": args.max_new_tokens,
                 "mode_order": "Alternates per repeat", "generation_logits_to_keep": 1,
                 "warmup": "One actual-input forward per mode and up to 16 generation IDs before repeats",
                 "eos": "Natural ID2 only; never forced; cap is reported separately"},
        "model_checkpoint": str(args.model_checkpoint),
        "conversion_report_sha256": file_hash(args.conversion_report),
        "fit_report_sha256": file_hash(args.fit_report),
        "rule": asdict(rule), "device": torch.cuda.get_device_name(),
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "code_sha256": {str(path): file_hash(path) for path in (
            Path(__file__), Path(sys.modules[CountPatcherAdapter.__module__].__file__),
            Path(sys.modules[LMDBCountTable.__module__].__file__),
            Path(sys.modules[CountConfig.__module__].__file__),
            args.blt_project / "blt_hf/patched/modeling_blt.py")},
        "cases": [],
        "long_context_cases": [],
    }

    def checkpoint():
        progress = args.output.with_suffix(".progress.json")
        temporary = progress.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(progress)

    try:
        long_inputs = []
        if args.extended:
            if file_hash(args.label_report) != fitted["label_report_sha256"]:
                raise ValueError("Label report differs from the fitted rule")
            label_report = json.loads(args.label_report.read_text())
            long_inputs = validation_prefixes(args.validation_labels, label_report["contract_sha256"])
            report["label_report_sha256"] = file_hash(args.label_report)
            report["validation_contract_sha256"] = label_report["contract_sha256"]
        with LMDBCountTable(args.background) as background:
            if background.config != config:
                raise ValueError("Fitted count config does not match LMDB")
            metadata = background.metadata
            if metadata["source_report_sha256"] != fitted["background_report_sha256"]:
                raise ValueError("Fitted rule and LMDB have different background sources")
            report["background"] = metadata
            model = load_model(args.model_checkpoint, args.conversion_report,
                               attention_mode="osc", backend="eager", device="cuda").eval()
            if model.config.vocab_size != 260 or model.config.eos_token_id != 2 or model.config.pad_token_id != 3:
                raise ValueError("Unexpected BLT byte vocabulary")
            adapter = CountPatcherAdapter(config, rule, background)
            cap = model.config.max_patch_length

            def forward(ids, candidate, logits_to_keep=0):
                lengths = adapter.patch_lengths(ids, max_patch_length=cap) if candidate else None
                output = model(input_ids=ids, patch_lengths=lengths, use_cache=False, logits_to_keep=logits_to_keep)
                if not torch.isfinite(output.logits).all():
                    raise ValueError("Nonfinite BLT logits")
                return output.logits, lengths

            def measure_forward(ids, candidate):
                adapter.reset()
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()
                started = time.perf_counter()
                logits, lengths = forward(ids, candidate)
                loss = torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1, 260), ids[:, 1:].reshape(-1))
                bpb = loss.item() / math.log(2)
                torch.cuda.synchronize()
                elapsed = time.perf_counter() - started
                del logits, loss
                return bpb, elapsed, lengths, torch.cuda.max_memory_allocated()

            def forward_case(metadata, original):
                ids = torch.tensor([original], device="cuda", dtype=torch.long)
                if len(original) > model.config.max_position_embeddings:
                    raise ValueError("Input exceeds model context budget")
                case = dict(metadata, utf8_bytes=len(original) - 1, modes={})
                for candidate in (False, True):
                    measure_forward(ids, candidate)
                for repeat in range(args.repeats):
                    for candidate in ((False, True) if repeat % 2 == 0 else (True, False)):
                        mode = "count_lmdb" if candidate else "original"
                        bpb, elapsed, lengths, peak = measure_forward(ids, candidate)
                        metrics = case["modes"].setdefault(mode, {"bpb_samples": [], "forward_samples_seconds": [],
                                                                 "peak_cuda_allocated_bytes": 0})
                        metrics["bpb_samples"].append(bpb)
                        metrics["forward_samples_seconds"].append(elapsed)
                        metrics["peak_cuda_allocated_bytes"] = max(metrics["peak_cuda_allocated_bytes"], peak)
                        if candidate and repeat == 0:
                            expected = decision_patch_lengths(rollout(original, config=config, rule=rule, background=background))
                            from blt_hf.patched.modeling_blt import process_patch_lengths

                            expected = process_patch_lengths(torch.tensor([expected], device="cuda"), cap)
                            if not torch.equal(lengths, expected):
                                raise AssertionError("Adapter and fresh rollout lengths differ")
                            metrics["patch_count"] = lengths.shape[1]
                            metrics["patch_length_sum"] = int(lengths.sum().item())
                for metrics in case["modes"].values():
                    if len(set(metrics["bpb_samples"])) != 1:
                        raise AssertionError("Repeated same-input BPB differs")
                    metrics["bpb"] = metrics["bpb_samples"][0]
                    metrics["forward_timing"] = timing_summary(metrics["forward_samples_seconds"])
                    metrics["forward_seconds"] = metrics["forward_timing"]["p50_seconds"]
                return case, ids

            with torch.inference_mode():
                for metadata, original in long_inputs:
                    case, _ = forward_case(metadata, original)
                    report["long_context_cases"].append(case)
                    checkpoint()
                    print(json.dumps({"completed_long_context_cases": len(report["long_context_cases"]),
                                      "input_length": len(original)}), flush=True)
                generation_inputs = [(name, [1] + [value + 4 for value in text.encode("utf-8")]) for name, text in (
                    ("plain", "The cat sat on the mat."), ("repeat", "abcXabc abcXabc."),
                    ("multibyte", "English with caf\u00e9."))]
                if args.extended:
                    from transformers import AutoTokenizer
                    from blt_hf.data_adapter import encode_prompt

                    tokenizer = AutoTokenizer.from_pretrained(args.model_checkpoint, local_files_only=True)
                    for name, text in (("gec_short", "She go to school yesterday."),
                                       ("gec_complete", "This is a complete sentence.")):
                        original = encode_prompt(tokenizer, text, max_sequence_bytes=model.config.max_position_embeddings,
                                                 max_new_bytes=args.max_new_tokens, sample_id=name)
                        generation_inputs.append((name, original))
                for name, original in generation_inputs:
                    if len(original) + args.max_new_tokens > model.config.max_position_embeddings:
                        raise ValueError("Prompt plus generation exceeds model context budget")
                    case, ids = forward_case({"name": name, "input_ids": original}, original)
                    for candidate in (False, True):
                        adapter.reset()
                        greedy_generate(ids, lambda current: forward(current, candidate, logits_to_keep=1),
                                        max_new_tokens=min(16, args.max_new_tokens))
                    for repeat in range(args.repeats):
                        for candidate in ((False, True) if repeat % 2 == 0 else (True, False)):
                            mode = "count_lmdb" if candidate else "original"
                            adapter.reset()
                            torch.cuda.reset_peak_memory_stats()
                            torch.cuda.synchronize()
                            started = time.perf_counter()
                            generated = greedy_generate(ids, lambda current: forward(current, candidate, logits_to_keep=1),
                                                        max_new_tokens=args.max_new_tokens)
                            torch.cuda.synchronize()
                            elapsed = time.perf_counter() - started
                            metrics = case["modes"][mode]
                            samples = metrics.setdefault("generation_samples", [])
                            if samples and generated["generated_ids"] != samples[0]["generated_ids"]:
                                raise AssertionError("Repeated same-input generated IDs differ")
                            generated.update(generation_seconds=elapsed, ids_per_second=len(generated["generated_ids"]) / elapsed,
                                             peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated())
                            samples.append(generated)
                            metrics["peak_cuda_allocated_bytes"] = max(metrics["peak_cuda_allocated_bytes"],
                                                                         generated["peak_cuda_allocated_bytes"])
                            print(json.dumps({"case": name, "repeat": repeat, "mode": mode,
                                              "stop_reason": generated["stop_reason"],
                                              "new_ids": len(generated["generated_ids"]), "seconds": elapsed}), flush=True)
                    for metrics in case["modes"].values():
                        metrics.update({key: value for key, value in metrics["generation_samples"][0].items()
                                        if key != "peak_cuda_allocated_bytes"})
                        metrics["generation_timing"] = timing_summary([sample["generation_seconds"]
                                                                      for sample in metrics["generation_samples"]])
                        metrics["generation_seconds"] = metrics["generation_timing"]["p50_seconds"]
                    report["cases"].append(case)
                    checkpoint()
                    print(json.dumps({"completed_cases": len(report["cases"])}), flush=True)
            report["verification"] = {
                "repeatable_bpb_and_generated_ids": True,
                "all_generations_reached_eos": all(metrics["eos"] for case in report["cases"]
                                                    for metrics in case["modes"].values()),
                "generation_cap_cases": [{"name": case["name"], "mode": mode} for case in report["cases"]
                                         for mode, metrics in case["modes"].items() if not metrics["eos"]],
            }
            report["status"] = ("completed_with_generation_limits" if args.extended and
                                not report["verification"]["all_generations_reached_eos"] else "passed")
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()