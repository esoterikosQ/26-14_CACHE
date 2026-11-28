"""Compare EOS scores on identical recorded contexts across implementations and dtypes."""

import argparse
import gc
import inspect
import json
from pathlib import Path
import sys

from scripts.diagnose_blt_termination import eos_statistics
from scripts.patcher_preflight import file_hash
from phdq_blt_cache.blt_patcher import CountPatcherAdapter
from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig
from phdq_blt_cache.lmdb_counts import LMDBCountTable


def probe_positions(generated_ids):
    body = generated_ids[:-1] if generated_ids[-1] == 2 else generated_ids
    tail_start = len(body)
    while tail_start and body[tail_start - 1] in (13, 14, 17, 36):
        tail_start -= 1
    last_position = len(generated_ids) - 1
    positions = {0, min(128, last_position), min(512, last_position), last_position}
    if tail_start < len(body):
        positions.update((tail_start, min(tail_start + 16, len(generated_ids) - 1)))
    return sorted(positions), len(body) - tail_start


def stage_contexts(source):
    requested = (
        ("story_letter", "original_hf_default", 0),
        ("compare_travel", "original_hf_default", 412),
        ("compare_travel", "original_hf_default", 428),
        ("compare_travel", "original_hf_default", 2047),
        ("compare_backup", "original_hf_default", 655),
        ("story_clock", "original_hf_default", 1338),
        ("compare_laptop", "count_lmdb", 867),
    )
    cases = {case["name"]: case for case in source["simple_controls"]}
    contexts = []
    for name, mode, position in requested:
        case = cases[name]
        generated = case["modes"][mode]["generated_ids"]
        if not 0 <= position < len(generated):
            raise ValueError("Stage position outside recording")
        prefix = case["input_ids"] + generated[:position]
        if prefix[0] != 1 or any(token < 4 or token >= 260 for token in prefix[1:]):
            raise ValueError("Stage prefix contains special IDs")
        contexts.append({"name": name, "source_mode": mode, "position": position,
                         "input_ids": prefix, "recorded_next": generated[position]})
    return contexts


def tensor_comparison(reference, observed):
    import torch

    result = {"reference_shape": list(reference.shape), "observed_shape": list(observed.shape)}
    if reference.shape != observed.shape:
        return {**result, "same_shape": False, "equal": False}
    delta = (reference.float() - observed.float()).abs()
    return {**result, "same_shape": True, "equal": torch.equal(reference, observed),
            "max_abs_difference": delta.max().item(), "mean_abs_difference": delta.mean().item()}


def capture_stages(model, ids, patch_lengths=None, full_local=()):
    import torch

    captured = {}
    handles = []

    def save(name):
        def hook(module, inputs, output):
            if name == "patcher":
                names = ("entropy", "patch_lengths", "entropy_logits")
                for key, tensor in zip(names, output, strict=True):
                    captured[key] = tensor.detach().cpu().clone()
            elif name == "encoder":
                captured["encoder_bytes"] = output[0].detach().cpu().clone()
                captured["encoder_patches"] = output[1].detach().cpu().clone()
            else:
                captured[name] = output.detach().cpu().clone()
        return hook

    def full_causal(module, inputs, kwargs):
        length = ids.shape[1]
        blocked = torch.ones((length, length), dtype=torch.bool, device=ids.device).triu(1)
        mask = torch.zeros((length, length), dtype=model.dtype, device=ids.device)
        kwargs["attention_mask"] = mask.masked_fill(blocked, torch.finfo(model.dtype).min)[None, None]
        return inputs, kwargs

    try:
        for name, module in (("patcher", model.model.patcher), ("encoder", model.model.local_encoder),
                             ("global", model.model.global_transformer), ("decoder", model.model.local_decoder)):
            handles.append(module.register_forward_hook(save(name)))
        for name in full_local:
            handles.append(getattr(model.model, name).register_forward_pre_hook(full_causal, with_kwargs=True))
        kwargs = {} if patch_lengths is None else {"patch_lengths": patch_lengths.to(ids.device)}
        logits = model(input_ids=ids, use_cache=False, logits_to_keep=1, **kwargs).logits[0, -1]
        captured["logits"] = logits.detach().cpu().clone()
        if patch_lengths is not None:
            captured["patch_lengths"] = patch_lengths.cpu().clone()
        stats = eos_statistics(logits)
        allowed = logits.float().clone()
        allowed[[0, 1, 3]] = -torch.inf
        stats["newline_probability"] = allowed.softmax(-1)[14].item()
        return captured, stats
    finally:
        for handle in handles:
            handle.remove()


def compare_stages(args, source, report):
    import torch
    from blt_hf.model import load_model
    from transformers import BltForCausalLM

    contexts = stage_contexts(source)
    report.update(scope="HF implementation interventions on seven selected fixed contexts; not upstream parity or quality",
                  contexts=contexts, stage_runs=[], comparisons=[], controls=[])
    references = {}
    official_fixed = {}
    official_auto = {}
    for implementation in ("osc", "official", "lre"):
        if implementation == "official":
            model, loading = BltForCausalLM.from_pretrained(
                source["model_checkpoint"], local_files_only=True, dtype=torch.bfloat16,
                device_map="cuda", attn_implementation="eager", output_loading_info=True)
            if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
                raise ValueError("Official weights did not strictly load")
        else:
            model = load_model(Path(source["model_checkpoint"]), args.conversion_report,
                               attention_mode=implementation, backend="eager", device="cuda")
        model.eval()
        with torch.inference_mode():
            for index, context in enumerate(contexts):
                ids = torch.tensor([context["input_ids"]], dtype=torch.long, device="cuda")
                variants = ("auto", "osc_lengths")
                if implementation == "osc":
                    variants += ("full_encoder", "full_decoder", "full_both")
                for variant in variants:
                    lengths = None if variant == "auto" else references[index]["auto"]["patch_lengths"]
                    full = {"full_encoder": ("local_encoder",), "full_decoder": ("local_decoder",),
                            "full_both": ("local_encoder", "local_decoder")}.get(variant, ())
                    tensors, stats = capture_stages(model, ids, lengths, full)
                    label = f"{implementation}_{variant}"
                    run = {"context_index": index, "implementation": label, "scores": stats,
                           "patch_lengths": tensors["patch_lengths"].tolist(),
                           "patch_length_sum": tensors["patch_lengths"].sum().item(),
                           "stage_shapes": {key: list(value.shape) for key, value in tensors.items()}}
                    report["stage_runs"].append(run)
                    if implementation == "osc":
                        references.setdefault(index, {})[variant] = tensors
                        if variant == "auto" and context["source_mode"] == "original_hf_default":
                            report["controls"].append({"name": "recorded_osc_next", "context_index": index,
                                                       "passed": stats["selected_id"] == context["recorded_next"]})
                    elif implementation == "official":
                        (official_auto if variant == "auto" else official_fixed)[index] = tensors
                    for target, reference in (("osc_auto", references[index]["auto"]),):
                        report["comparisons"].append({"context_index": index, "observed": label, "reference": target,
                            "stages": {key: tensor_comparison(reference[key], value) for key, value in tensors.items()
                                       if key in reference}})
                    if implementation == "osc" and variant == "osc_lengths":
                        report["controls"].append({"name": "osc_external_lengths_replay", "context_index": index,
                            "passed": all(torch.equal(value, references[index]["auto"][key]) for key, value in tensors.items())})
                    if implementation == "official" and variant == "osc_lengths":
                        report["controls"].append({"name": "both_local_masks_explain_fixed_body", "context_index": index,
                            "passed": all(torch.equal(value, references[index]["full_both"][key]) for key, value in tensors.items())})
                    if implementation == "lre":
                        reference = (official_auto if variant == "auto" else official_fixed)[index]
                        report["controls"].append({"name": f"lre_matches_official_{variant}", "context_index": index,
                            "passed": set(reference) == set(tensors) and all(torch.equal(value, reference[key]) for key, value in tensors.items())})
                del ids
        del model
        gc.collect()
        torch.cuda.empty_cache()
        print(json.dumps({"completed_stage_implementation": implementation, "runs": len(report["stage_runs"])}), flush=True)
    report["status"] = "diagnostic_complete" if all(control["passed"] for control in report["controls"]) else "control_mismatch"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blt-project", type=Path, required=True)
    parser.add_argument("--conversion-report", type=Path, required=True)
    parser.add_argument("--background", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--instruction-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage-comparison", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import torch
    import transformers

    torch.set_num_threads(8)
    torch.cuda.set_device(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    sys.path.insert(0, str(args.blt_project.resolve()))
    from blt_hf.model import load_model
    from blt_hf.manifest import verify_file_hashes
    from transformers import BltForCausalLM

    baseline = json.loads(args.baseline_report.read_text())
    source = json.loads(args.instruction_report.read_text())
    if file_hash(args.conversion_report) != baseline["conversion_report_sha256"]:
        raise ValueError("Conversion identity mismatch")
    if source["model_checkpoint"] != baseline["model_checkpoint"]:
        raise ValueError("Recorded models differ")
    if source["source_report_sha256"] != file_hash(args.baseline_report):
        raise ValueError("Instruction report baseline identity mismatch")
    owner = args.blt_project / "blt_hf/patched/modeling_blt.py"
    if file_hash(owner) != source["code_sha256"][str(owner)]:
        raise ValueError("Recorded OSC implementation changed")
    config = CountConfig(**baseline["background"]["config"])
    rule = BoundaryRule(**baseline["rule"])
    conversion = json.loads(args.conversion_report.read_text())
    verify_file_hashes(Path(source["model_checkpoint"]), conversion["output_files"])
    report = {
        "status": "running", "scope": "Paired fixed-context score diagnostics, not upstream weight parity or output quality",
        "instruction_report_sha256": file_hash(args.instruction_report),
        "baseline_report_sha256": file_hash(args.baseline_report),
        "conversion_report_sha256": file_hash(args.conversion_report),
        "model_checkpoint": source["model_checkpoint"],
        "weight_sha256": conversion["output_files"]["model.safetensors"],
        "runtime": {"torch": torch.__version__, "transformers": transformers.__version__,
                    "gpu": torch.cuda.get_device_name(0), "tf32": False, "threads": 8},
        "code_sha256": {str(path): file_hash(path) for path in (
            Path(__file__), owner, Path(inspect.getfile(BltForCausalLM)),
            Path(inspect.getfile(eos_statistics)), Path(inspect.getfile(CountPatcherAdapter)),
            Path(inspect.getfile(LMDBCountTable)), Path(inspect.getfile(CountConfig)))},
        "paths": [], "probes": [],
    }
    if args.stage_comparison:
        try:
            compare_stages(args, source, report)
        except Exception as error:
            report.update(status="failed", error_type=type(error).__name__, error=str(error))
            raise
        finally:
            with args.output.open("x") as stream:
                json.dump(report, stream, indent=2)
                stream.write("\n")
        return
    for case in source["simple_controls"]:
        for mode, result in case["modes"].items():
            positions, whitespace_tail = probe_positions(result["generated_ids"])
            report["paths"].append({"name": case["name"], "source_mode": mode,
                                    "positions": positions, "trailing_whitespace_ids": whitespace_tail,
                                    "stop_reason": result["stop_reason"]})
    try:
        with LMDBCountTable(args.background) as background:
            for key in ("config", "source_report_sha256", "source_manifest_sha256", "status"):
                if background.metadata[key] != baseline["background"][key]:
                    raise ValueError(f"Background identity mismatch: {key}")
            adapter = CountPatcherAdapter(config, rule, background)
            for implementation in ("official_bf16", "osc_bf16", "count_bf16", "osc_fp32"):
                if implementation == "official_bf16":
                    model, loading = BltForCausalLM.from_pretrained(
                        source["model_checkpoint"], local_files_only=True, dtype=torch.bfloat16,
                        device_map="cuda", attn_implementation="eager", output_loading_info=True)
                    if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
                        raise ValueError("Official weights did not strictly load")
                else:
                    model = load_model(Path(source["model_checkpoint"]), args.conversion_report,
                                       attention_mode="osc", backend="eager", device="cuda")
                    if implementation == "osc_fp32":
                        model.float()
                model.eval()
                with torch.inference_mode():
                    for case in source["simple_controls"]:
                        for source_mode, result in case["modes"].items():
                            generated = result["generated_ids"]
                            positions, _ = probe_positions(generated)
                            for position in positions:
                                prefix = case["input_ids"] + generated[:position]
                                if prefix[0] != 1 or any(token < 4 or token >= 260 for token in prefix[1:]):
                                    raise ValueError("Probe prefix contains special IDs")
                                ids = torch.tensor([prefix], dtype=torch.long, device="cuda")
                                kwargs = {}
                                if implementation == "count_bf16":
                                    adapter.reset()
                                    kwargs["patch_lengths"] = adapter.patch_lengths(ids, max_patch_length=model.config.max_patch_length)
                                logits = model(input_ids=ids, use_cache=False, logits_to_keep=1, **kwargs).logits[0, -1]
                                stats = eos_statistics(logits)
                                allowed = logits.float().clone()
                                allowed[[0, 1, 3]] = -torch.inf
                                probabilities = allowed.softmax(-1)
                                positive = probabilities > 0
                                stats.update(name=case["name"], source_mode=source_mode,
                                             implementation=implementation, generated_position=position,
                                             newline_probability=probabilities[14].item(),
                                             entropy_bits=(-(probabilities[positive] * probabilities[positive].log2()).sum()).item(),
                                             recorded_next=generated[position],
                                             matches_recorded_next=stats["selected_id"] == generated[position])
                                report["probes"].append(stats)
                                del logits, ids
                    print(json.dumps({"completed_implementation": implementation,
                                      "probes": len(report["probes"])}), flush=True)
                del model
                gc.collect()
                torch.cuda.empty_cache()
                temporary = args.output.with_suffix(".progress.tmp")
                temporary.write_text(json.dumps(report, indent=2) + "\n")
                temporary.replace(args.output.with_suffix(".progress.json"))
        matching = {"original_hf_default": "osc_bf16", "count_lmdb": "count_bf16"}
        own = [probe for probe in report["probes"] if matching[probe["source_mode"]] == probe["implementation"]]
        report["own_path_checks"] = {"count": len(own), "mismatches": sum(not probe["matches_recorded_next"] for probe in own)}
        report["status"] = "diagnostic_complete" if not report["own_path_checks"]["mismatches"] else "control_mismatch"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()