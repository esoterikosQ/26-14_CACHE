"""Compare native HF stopping with recorded greedy paths and inspect EOS scores."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

from scripts.patcher_preflight import file_hash
from phdq_blt_cache.blt_patcher import CountPatcherAdapter
from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig
from phdq_blt_cache.lmdb_counts import LMDBCountTable


def simple_control_prompts(tokenizer, encode_prompt):
    texts = (
        ("english_greeting", "Hello."),
        ("english_complete", "The weather is nice today."),
        ("korean_greeting", "\uc548\ub155\ud558\uc138\uc694."),
        ("korean_complete", "\uc624\ub298\uc740 \ub0a0\uc528\uac00 \uc88b\ub2e4."),
    )
    prompts = []
    for name, text in texts:
        body = list(tokenizer.encode(text, add_special_tokens=False, truncation=False))
        if body != [byte + 4 for byte in text.encode("utf-8")]:
            raise ValueError("Simple control tokenizer is not raw byte+4")
        for input_format, ids in (
            ("raw", [tokenizer.bos_token_id] + body),
            ("gec", encode_prompt(tokenizer, text, max_new_bytes=128)),
        ):
            if not ids or ids[0] != 1 or 2 in ids or 3 in ids:
                raise ValueError("Simple controls require BOS1 without input EOS or padding")
            prompts.append({"name": name + "_" + input_format, "source_text": text,
                            "input_format": input_format, "input_ids": ids})
    return prompts


def generation_budget(requested, prompt_length, context_length, default):
    budget = default if requested is None else requested
    if type(budget) is not int or budget < 1:
        raise ValueError("max_new_tokens must be a positive integer")
    if prompt_length + budget > context_length:
        raise ValueError("Prompt plus generation exceeds model context budget")
    return budget


def instruction_control_prompts(tokenizer):
    stories = (
        ("story_letter", "Mina found a sealed letter beneath the floorboards of her grandmother's house."),
        ("story_notebook", "At closing time, the librarian found a notebook with no name and a train ticket tucked inside."),
        ("story_clock", "A village clock began running ten minutes fast on the morning of the annual fair."),
    )
    processes = (
        ("process_rain", "rain forms", "the evaporation of water to rainfall"),
        ("process_bread", "bread is made", "mixing the ingredients to cooling the baked loaf"),
        ("process_glass", "glass bottles are recycled", "collecting used bottles to producing new bottles"),
    )
    comparisons = (
        ("compare_travel", "travel options", "a traveler who values reliability more than price",
         "A direct train costing $45, arriving at 10:00.",
         "Two buses costing $25, arriving at 10:30 if the connection is on time."),
        ("compare_laptop", "laptops", "a student who values battery life more than memory capacity",
         "A laptop costing $700, with 8 GB of memory and 12 hours of battery life.",
         "A laptop costing $850, with 16 GB of memory and 8 hours of battery life."),
        ("compare_backup", "backup options", "a person who values automatic backups more than the lowest cost",
         "An external drive costing $80, requiring the user to start each backup manually.",
         "A cloud service costing $5 per month, automatically backing up files over a reliable internet connection."),
    )
    texts = [(name, "story", "Continue the passage into a coherent story. Resolve the situation and bring the story to a natural ending."
              + "\n\nPassage:\n" + passage + "\n\nContinuation:\n") for name, passage in stories]
    texts += [(name, "process", "Explain how " + subject + ", from " + stages
               + ". Describe the stages in order and conclude when the process is complete.\n\nExplanation:\n")
              for name, subject, stages in processes]
    texts += [(name, "comparison", "Compare the two " + subject + " below and recommend one for " + preference
               + ". Explain the trade-off and finish with your recommendation.\n\nOption A: " + option_a
               + "\nOption B: " + option_b + "\n\nComparison:\n")
              for name, subject, preference, option_a, option_b in comparisons]
    controls = []
    for name, category, text in texts:
        body = list(tokenizer.encode(text, add_special_tokens=False, truncation=False))
        if tokenizer.bos_token_id != 1 or body != [byte + 4 for byte in text.encode("utf-8")]:
            raise ValueError("Instruction controls require BOS1 and exact byte+4 encoding")
        controls.append({"name": name, "category": category, "source_text": text,
                         "input_format": "raw", "input_ids": [1] + body})
    return controls


def eos_statistics(last_logits):
    import torch

    if last_logits.ndim != 1 or last_logits.numel() != 260 or not torch.isfinite(last_logits).all():
        raise ValueError("Expected 260 finite next-ID logits")
    raw = last_logits.float()
    allowed = raw.clone()
    allowed[[0, 1, 3]] = -torch.inf
    top = allowed.topk(5)
    return {
        "eos_id": 2, "suppressed_ids": [0, 1, 3],
        "eos_suppressed": not bool(torch.isfinite(allowed[2]).item()),
        "eos_logit": raw[2].item(), "eos_probability_raw": raw.softmax(-1)[2].item(),
        "eos_probability_allowed": allowed.softmax(-1)[2].item(),
        "eos_rank_allowed": int((allowed > allowed[2]).sum().item()) + 1,
        "selected_id": int(allowed.argmax().item()),
        "best_minus_eos_logit": (allowed.max() - allowed[2]).item(),
        "top5_ids": top.indices.tolist(), "top5_logits": top.values.tolist(),
    }


def decoding_plan():
    plan = [{"name": "greedy", "seed": None, "settings": {"do_sample": False}}]
    for name, temperature, top_p in (("full_sampling", 1., 1.), ("nucleus_sampling", .8, .9)):
        for seed in (42, 20261027):
            plan.append({"name": name, "seed": seed, "settings": {
                "do_sample": True, "temperature": temperature, "top_p": top_p, "top_k": 0}})
    return plan


def repetition_metrics(generated):
    if not generated or (2 in generated and (generated[-1] != 2 or generated.count(2) != 1)):
        raise ValueError("Expected a nonempty generation ending at its first EOS")
    body = generated[:-1] if generated[-1] == 2 else generated
    if any(token < 4 or token >= 260 for token in body):
        raise ValueError("Generated body contains non-byte IDs")
    windows = [tuple(body[start:start + 8]) for start in range(max(0, len(body) - 7))]
    repeated = 1 - len(set(windows)) / len(windows) if windows else 0.
    tail = len(body)
    while tail and body[tail - 1] in (13, 14, 17, 36):
        tail -= 1
    longest = current = 0
    previous = None
    for token in body:
        current = current + 1 if token == previous else 1
        longest = max(longest, current)
        previous = token
    return {"body_byte_count": len(body), "repeat8_fraction": repeated,
            "trailing_whitespace_ids": len(body) - tail, "longest_identical_byte_run": longest,
            "repetition_flag": repeated >= .5 or longest >= 32}


def run_decoding_controls(model, tokenizer, args, report, decode_generated):
    import torch

    reference = json.loads(args.greedy_reference.read_text())
    controls = instruction_control_prompts(tokenizer)
    if reference["model_checkpoint"] != report["model_checkpoint"]:
        raise ValueError("Greedy reference checkpoint mismatch")
    prior = {case["name"]: case for case in reference["simple_controls"]}
    if set(prior) != {case["name"] for case in controls}:
        raise ValueError("Greedy reference prompt set mismatch")
    for control in controls:
        if control["input_ids"] != prior[control["name"]]["input_ids"]:
            raise ValueError("Greedy reference prompt IDs differ")
    report.update(prompt_suite="instruction9_v1", decoding_plan=decoding_plan(), decoding_runs=[],
                  greedy_reference_sha256=file_hash(args.greedy_reference),
                  started_at_utc=datetime.now(timezone.utc).isoformat(),
                  repetition_definition="repeat8=1-unique8windows/total8windows excluding EOS; flag repeat8>=0.5 or identical-byte run>=32; descriptive, not quality acceptance",
                  review_rubric={"instruction_following": "met/partial/not_met/unclear",
                                 "task_completion": "complete/incomplete/unclear; core endpoint independent of EOS or tails",
                                 "factuality": "no_obvious_error/has_error/unclear/not_applicable; single non-blinded review, not fact certification",
                                 "limitations": "EOS, repetition, task completion and factuality are separate; no calibrated quality threshold"},
                  runtime={"torch": torch.__version__, "transformers": __import__("transformers").__version__,
                           "gpu": torch.cuda.get_device_name(0), "dtype": str(model.dtype),
                           "attention_mode": "osc", "backend": "eager", "threads": torch.get_num_threads()},
                  common_generation={"num_beams": 1, "use_cache": False, "logits_to_keep": 1,
                                     "bos_token_id": 1, "eos_token_id": 2, "pad_token_id": 3,
                                     "suppress_tokens": [0, 1, 3], "forced_eos_token_id": None,
                                     "repetition_penalty": 1., "min_new_tokens": 0})
    for name in ("attention.py", "patching.py", "generation.py"):
        path = args.blt_project / "blt_hf" / name
        report["code_sha256"][str(path)] = file_hash(path)
    with torch.inference_mode():
        for control in controls:
            prompt = torch.tensor([control["input_ids"]], dtype=torch.long, device="cuda")
            budget = generation_budget(args.max_new_tokens, prompt.shape[1], model.config.max_position_embeddings, 2048)
            for candidate in report["decoding_plan"]:
                torch.manual_seed(42 if candidate["seed"] is None else candidate["seed"])
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()
                started = time.perf_counter()
                sequence = model.generate(
                    input_ids=prompt, attention_mask=torch.ones_like(prompt), max_new_tokens=budget,
                    **report["common_generation"], **candidate["settings"])
                torch.cuda.synchronize()
                elapsed = time.perf_counter() - started
                generated = sequence[0, prompt.shape[1]:].tolist()
                if sequence[0, :prompt.shape[1]].tolist() != control["input_ids"]:
                    raise ValueError("Generation altered the prompt")
                result = decode_generated(generated)
                metrics = repetition_metrics(generated)
                result.update(name=control["name"], category=control["category"],
                              policy=candidate["name"], seed=candidate["seed"], settings=candidate["settings"],
                              input_ids=control["input_ids"], source_text=control["source_text"],
                              generated_ids=generated, max_new_tokens=budget,
                              generation_seconds=elapsed, peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
                              stop_reason="eos" if result["eos_reached"] else "max_new_tokens", **metrics)
                if candidate["name"] == "greedy":
                    result["matches_recorded_greedy"] = generated == prior[control["name"]]["modes"]["original_hf_default"]["generated_ids"]
                    if not result["matches_recorded_greedy"]:
                        raise ValueError("Fresh greedy output differs from recorded baseline")
                report["decoding_runs"].append(result)
                temporary = args.output.with_suffix(".progress.tmp")
                temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
                temporary.replace(args.output.with_suffix(".progress.json"))
                print(json.dumps({"decoding_prompt": control["name"], "policy": candidate["name"],
                                  "seed": candidate["seed"], "eos": result["eos_reached"],
                                  "new_ids": len(generated), "repeat8": metrics["repeat8_fraction"]}), flush=True)
    report["decoding_summary"] = []
    for policy in ("greedy", "full_sampling", "nucleus_sampling"):
        runs = [run for run in report["decoding_runs"] if run["policy"] == policy]
        report["decoding_summary"].append({"policy": policy, "runs": len(runs),
            "eos_count": sum(run["eos_reached"] for run in runs),
            "valid_utf8_count": sum(run["valid_utf8"] for run in runs),
            "repetition_flag_count": sum(run["repetition_flag"] for run in runs),
            "median_new_ids": statistics.median(len(run["generated_ids"]) for run in runs),
            "median_repeat8_fraction": statistics.median(run["repeat8_fraction"] for run in runs),
            "generation_seconds_sum": sum(run["generation_seconds"] for run in runs)})
    report.update(status="diagnostic_complete", finished_at_utc=datetime.now(timezone.utc).isoformat())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blt-project", type=Path, required=True)
    parser.add_argument("--conversion-report", type=Path, required=True)
    parser.add_argument("--background", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--simple-controls", action="store_true")
    parser.add_argument("--instruction-controls", action="store_true")
    parser.add_argument("--decoding-controls", action="store_true")
    parser.add_argument("--greedy-reference", type=Path)
    parser.add_argument("--raw-only", action="store_true")
    parser.add_argument("--max-new-tokens", type=int)
    parser.add_argument("--official-only", action="store_true")
    parser.add_argument("--sample-eos", action="store_true")
    parser.add_argument("--sampling-seed", type=int, default=20261027)
    parser.add_argument("--eos-reference", type=Path)
    parser.add_argument("--eos-reference-mode", choices=("official_hf", "original", "count_lmdb"), default="official_hf")
    args = parser.parse_args()
    if args.decoding_controls and (not args.greedy_reference or args.instruction_controls or args.simple_controls or
                                  args.official_only or args.sample_eos or args.eos_reference or args.raw_only):
        parser.error("--decoding-controls requires --greedy-reference and cannot combine with other suites")
    if args.instruction_controls and (args.simple_controls or args.official_only or args.sample_eos or args.eos_reference):
        parser.error("--instruction-controls cannot be combined with other diagnostic suites")
    if args.max_new_tokens is not None and args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be positive")
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import torch
    from transformers import AutoTokenizer

    torch.set_num_threads(8)
    torch.manual_seed(20261027)
    torch.cuda.set_device(0)
    sys.path.insert(0, str(args.blt_project.resolve()))
    from blt_hf.model import load_model
    from blt_hf.data_adapter import encode_prompt
    from blt_hf.generation import decode_generated
    from scripts.smoke_blt_count_patcher import greedy_generate

    source = json.loads(args.source_report.read_text())
    if file_hash(args.conversion_report) != source["conversion_report_sha256"]:
        raise ValueError("Conversion report identity mismatch")
    config = CountConfig(**source["background"]["config"])
    rule = BoundaryRule(**source["rule"])
    owner_model = args.blt_project / "blt_hf/patched/modeling_blt.py"
    if file_hash(owner_model) != source["code_sha256"][str(owner_model)]:
        raise ValueError("BLT implementation changed since the recorded run")
    conversion = json.loads(args.conversion_report.read_text())
    report = {
        "status": "running", "scope": "Synthetic diagnostics with explicit decoding settings; no forced EOS or weight changes",
        "requested_max_new_tokens": args.max_new_tokens,
        "raw_only": args.raw_only,
        "prompt_suite": "instruction9_v1" if args.instruction_controls else "legacy_controls",
        "source_report_sha256": file_hash(args.source_report),
        "model_checkpoint": source["model_checkpoint"],
        "conversion_source": {key: conversion.get(key) for key in (
            "model_id", "model_revision", "entropy_model_id", "entropy_revision", "created_at")},
        "code_sha256": {str(path): file_hash(path) for path in (
            Path(__file__), args.blt_project / "blt_hf/model.py", owner_model,
            Path(sys.modules[CountPatcherAdapter.__module__].__file__),
            Path(sys.modules[CountConfig.__module__].__file__),
            Path(sys.modules[LMDBCountTable.__module__].__file__))},
        "hf_controls": [], "eos_probes": [], "simple_controls": [],
    }
    try:
        if args.official_only:
            import inspect
            from transformers import BltForCausalLM
            from blt_hf.manifest import verify_file_hashes

            implementation = Path(inspect.getfile(BltForCausalLM))
            report["scope"] = "Official Transformers BLT with identical converted weights; no forced EOS"
            report["code_sha256"][str(implementation)] = file_hash(implementation)
            verify_file_hashes(Path(source["model_checkpoint"]), conversion["output_files"])
            model, loading = BltForCausalLM.from_pretrained(
                source["model_checkpoint"], local_files_only=True, dtype=torch.bfloat16,
                device_map="cuda", attn_implementation="eager", output_loading_info=True,
            )
            if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
                raise ValueError("Official model does not strictly match converted weights")
            model.eval()
            tokenizer = AutoTokenizer.from_pretrained(source["model_checkpoint"], local_files_only=True)
            report["loading_info"] = {key: sorted(loading.get(key, ())) for key in (
                "missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")}
            report["model_specials"] = {key: getattr(model.config, key) for key in (
                "bos_token_id", "eos_token_id", "pad_token_id", "vocab_size")}
            with torch.inference_mode():
                for control in simple_control_prompts(tokenizer, encode_prompt):
                    if (args.sample_eos or args.raw_only) and control["input_format"] != "raw":
                        continue
                    seed = args.sampling_seed + len(report["simple_controls"])
                    torch.manual_seed(seed)
                    budget = generation_budget(args.max_new_tokens, len(control["input_ids"]),
                                               model.config.max_position_embeddings, 1024 if args.sample_eos else 128)
                    sampling = {"top_k": 0, "top_p": 1., "temperature": 1.} if args.sample_eos else {}
                    prompt = torch.tensor([control["input_ids"]], dtype=torch.long, device="cuda")
                    sequence = model.generate(
                        input_ids=prompt, attention_mask=torch.ones_like(prompt),
                        max_new_tokens=budget, do_sample=args.sample_eos, num_beams=1, use_cache=False,
                        bos_token_id=1, eos_token_id=2, pad_token_id=3, suppress_tokens=[0, 1, 3],
                        **sampling,
                    )
                    generated = sequence[0, prompt.shape[1]:].tolist()
                    result = decode_generated(generated)
                    result.update(generated_ids=generated, max_new_tokens=budget,
                                  seed=seed, do_sample=args.sample_eos, sampling=sampling,
                                  stop_reason="eos" if result["eos_reached"] else "max_new_tokens")
                    if result["eos_reached"]:
                        prefix = sequence[:, :prompt.shape[1] + generated.index(2)]
                        logits = model(input_ids=prefix, use_cache=False, logits_to_keep=1).logits
                        result["eos_selection_statistics"] = eos_statistics(logits[0, -1])
                    control["modes"] = {"official_hf": result}
                    report["simple_controls"].append(control)
                    print(json.dumps({"official_control": control["name"],
                                      "eos": result["eos_reached"], "new_ids": len(generated)}), flush=True)
                    if args.sample_eos and result["eos_reached"]:
                        break
            report["natural_eos_count"] = sum(
                control["modes"]["official_hf"]["eos_reached"] for control in report["simple_controls"])
            report["status"] = "eos_observed" if report["natural_eos_count"] else "no_eos_observed"
            return
        model = load_model(Path(source["model_checkpoint"]), args.conversion_report,
                           attention_mode="osc", backend="eager", device="cuda").eval()
        tokenizer = AutoTokenizer.from_pretrained(source["model_checkpoint"], local_files_only=True)
        report["tokenizer_specials"] = {key: getattr(tokenizer, key) for key in (
            "bos_token_id", "eos_token_id", "pad_token_id", "eos_token")}
        report["model_specials"] = {key: getattr(model.config, key) for key in (
            "bos_token_id", "eos_token_id", "pad_token_id", "vocab_size")}
        report["generation_defaults"] = {key: getattr(model.generation_config, key, None) for key in (
            "bos_token_id", "eos_token_id", "pad_token_id", "forced_eos_token_id",
            "min_length", "min_new_tokens", "suppress_tokens", "begin_suppress_tokens",
            "do_sample", "num_beams", "repetition_penalty")}
        if (tokenizer.bos_token_id, tokenizer.eos_token_id, tokenizer.pad_token_id) != (1, 2, 3):
            raise ValueError("Tokenizer special IDs differ from recorded generation")
        if args.decoding_controls:
            run_decoding_controls(model, tokenizer, args, report, decode_generated)
            return
        with LMDBCountTable(args.background) as background:
            for key in ("config", "source_report_sha256", "source_manifest_sha256", "status"):
                if background.metadata[key] != source["background"][key]:
                    raise ValueError(f"Background identity mismatch: {key}")
            adapter = CountPatcherAdapter(config, rule, background)
            with torch.inference_mode():
                if args.sample_eos or args.eos_reference:
                    control = simple_control_prompts(tokenizer, encode_prompt)[0]
                    if args.eos_reference:
                        reference = json.loads(args.eos_reference.read_text())
                        recorded = reference["simple_controls"][0]
                        reference_ids = recorded["modes"][args.eos_reference_mode]["generated_ids"]
                        if (reference["model_checkpoint"] != source["model_checkpoint"] or
                            recorded["input_ids"][:len(control["input_ids"])] != control["input_ids"] or
                            not reference_ids or reference_ids[-1] != 2 or 2 in reference_ids[:-1] or
                            any(token < 4 or token >= 260 for token in recorded["input_ids"][1:] + reference_ids[:-1])):
                            raise ValueError("Invalid natural EOS reference")
                        report["eos_reference_sha256"] = file_hash(args.eos_reference)
                        report["eos_reference_mode"] = args.eos_reference_mode
                        control["input_ids"] = recorded["input_ids"] + reference_ids[:-1]
                        control["source_text"] = bytes(token - 4 for token in control["input_ids"][1:]).decode("utf-8", errors="replace")
                        control["name"] += "_completed_reference"
                    control["modes"] = {}
                    prompt = torch.tensor([control["input_ids"]], dtype=torch.long, device="cuda")

                    def count_input_hook(module, positional, keyword):
                        ids = keyword.get("input_ids")
                        if ids is None:
                            raise ValueError("Count generation hook requires full input_ids")
                        keyword["patch_lengths"] = adapter.patch_lengths(
                            ids, max_patch_length=model.config.max_patch_length)
                        return positional, keyword

                    for mode in ("original", "count_lmdb"):
                        adapter.reset()
                        handle = model.register_forward_pre_hook(count_input_hook, with_kwargs=True) if mode == "count_lmdb" else None
                        try:
                            torch.manual_seed(args.sampling_seed)
                            initial_logits = model(input_ids=prompt, use_cache=False, logits_to_keep=1).logits
                            initial_statistics = eos_statistics(initial_logits[0, -1])
                            sampling = {"top_k": 0, "top_p": 1., "temperature": 1.} if args.sample_eos else {}
                            budget = generation_budget(args.max_new_tokens, prompt.shape[1],
                                                       model.config.max_position_embeddings, 1024 if args.sample_eos else 128)
                            sequence = model.generate(
                                input_ids=prompt, attention_mask=torch.ones_like(prompt),
                                max_new_tokens=budget, do_sample=args.sample_eos,
                                num_beams=1, use_cache=False, bos_token_id=1, eos_token_id=2,
                                pad_token_id=3, suppress_tokens=[0, 1, 3], logits_to_keep=1,
                                **sampling,
                            )
                            generated = sequence[0, prompt.shape[1]:].tolist()
                            result = decode_generated(generated)
                            result.update(generated_ids=generated, max_new_tokens=budget, seed=args.sampling_seed,
                                          do_sample=args.sample_eos, sampling=sampling,
                                          initial_eos_statistics=initial_statistics,
                                          stop_reason="eos" if result["eos_reached"] else "max_new_tokens")
                            if result["eos_reached"]:
                                prefix = sequence[:, :prompt.shape[1] + generated.index(2)]
                                logits = model(input_ids=prefix, use_cache=False, logits_to_keep=1).logits
                                result["eos_selection_statistics"] = eos_statistics(logits[0, -1])
                            if not args.sample_eos:
                                adapter.reset()

                                def manual_forward(input_ids):
                                    return model(input_ids=input_ids, use_cache=False, logits_to_keep=1).logits, None

                                manual = greedy_generate(prompt, manual_forward, max_new_tokens=budget)
                                result["manual_generated_ids"] = manual["generated_ids"]
                                result["manual_matches_hf"] = manual["generated_ids"] == generated
                                if not result["manual_matches_hf"]:
                                    raise ValueError("Manual greedy termination differs from HF")
                            control["modes"][mode] = result
                            print(json.dumps({"sampled_mode": mode, "eos": result["eos_reached"],
                                              "new_ids": len(generated)}), flush=True)
                        finally:
                            if handle is not None:
                                handle.remove()
                    report["simple_controls"].append(control)
                    report["natural_eos_count"] = sum(result["eos_reached"] for result in control["modes"].values())
                    report["status"] = "eos_observed" if report["natural_eos_count"] == 2 else "eos_incomplete"
                    return
                if args.simple_controls or args.instruction_controls:
                    def count_forward(input_ids):
                        lengths = adapter.patch_lengths(input_ids, max_patch_length=model.config.max_patch_length)
                        output = model(input_ids=input_ids, patch_lengths=lengths,
                                       use_cache=False, logits_to_keep=1)
                        return output.logits, None

                    controls = (instruction_control_prompts(tokenizer) if args.instruction_controls
                                else simple_control_prompts(tokenizer, encode_prompt))
                    for control in controls:
                        if args.raw_only and control["input_format"] != "raw":
                            continue
                        prompt = torch.tensor([control["input_ids"]], dtype=torch.long, device="cuda")
                        budget = generation_budget(args.max_new_tokens, prompt.shape[1],
                                                   model.config.max_position_embeddings, 2048 if args.instruction_controls else 128)
                        torch.cuda.synchronize()
                        started = time.perf_counter()
                        sequence = model.generate(
                            input_ids=prompt, attention_mask=torch.ones_like(prompt),
                            max_new_tokens=budget, do_sample=False, num_beams=1, use_cache=False,
                            length_penalty=1., bos_token_id=1, eos_token_id=2, pad_token_id=3,
                            suppress_tokens=[0, 1, 3], return_dict_in_generate=False,
                        )
                        torch.cuda.synchronize()
                        native_seconds = time.perf_counter() - started
                        generated = sequence[0, prompt.shape[1]:].tolist()
                        native = decode_generated(generated)
                        native.update(generated_ids=generated, max_new_tokens=budget, generation_seconds=native_seconds,
                                      stop_reason="eos" if native["eos_reached"] else "max_new_tokens")
                        adapter.reset()
                        torch.cuda.synchronize()
                        started = time.perf_counter()
                        count = greedy_generate(prompt, count_forward, max_new_tokens=budget)
                        torch.cuda.synchronize()
                        count["generation_seconds"] = time.perf_counter() - started
                        control["modes"] = {"original_hf_default": native, "count_lmdb": count}
                        report["simple_controls"].append(control)
                        print(json.dumps({"simple_control": control["name"],
                                          "original_eos": native["eos_reached"], "count_eos": count["eos"]}), flush=True)
                        temporary = args.output.with_suffix(".progress.tmp")
                        temporary.write_text(json.dumps(report, indent=2) + "\n")
                        temporary.replace(args.output.with_suffix(".progress.json"))
                        del sequence
                for case in source["cases"]:
                    prompt = torch.tensor([case["input_ids"]], dtype=torch.long, device="cuda")
                    sequence = model.generate(
                        input_ids=prompt, attention_mask=torch.ones_like(prompt),
                        max_new_tokens=128, do_sample=False, num_beams=1, use_cache=False,
                        bos_token_id=1, eos_token_id=2, pad_token_id=3,
                        suppress_tokens=[0, 1, 3], logits_to_keep=1,
                    )
                    generated = sequence[0, prompt.shape[1]:].tolist()
                    reference = case["modes"]["original"]["generated_ids"][:len(generated)]
                    report["hf_controls"].append({
                        "name": case["name"], "new_ids": len(generated),
                        "eos": 2 in generated, "matches_manual_prefix": generated == reference,
                        "generated_ids": generated,
                    })
                    del sequence
                    for mode in ("original", "count_lmdb"):
                        adapter.reset()
                        recorded = case["modes"][mode]["generated_ids"]
                        for position in (0, 16, 128, 512, 1024):
                            if position > len(recorded):
                                continue
                            ids = torch.tensor([case["input_ids"] + recorded[:position]], device="cuda")
                            lengths = (adapter.patch_lengths(ids, max_patch_length=model.config.max_patch_length)
                                       if mode == "count_lmdb" else None)
                            logits = model(input_ids=ids, patch_lengths=lengths,
                                           use_cache=False, logits_to_keep=1).logits
                            result = eos_statistics(logits[0, -1])
                            result.update(name=case["name"], mode=mode, generated_position=position,
                                          matches_recorded_next=(result["selected_id"] == recorded[position]
                                                                 if position < len(recorded) else None))
                            report["eos_probes"].append(result)
                            del logits
                    print(json.dumps({"completed_cases": len(report["hf_controls"]),
                                      "hf_matches_manual": generated == reference}), flush=True)
        report["hf_all_match_manual"] = all(control["matches_manual_prefix"] for control in report["hf_controls"])
        report["recorded_next_all_match"] = all(probe["matches_recorded_next"] is not False for probe in report["eos_probes"])
        report["status"] = ("diagnostic_complete" if report["hf_all_match_manual"] and
                            report["recorded_next_all_match"] else "control_mismatch")
        if args.simple_controls or args.instruction_controls:
            results = [result for control in report["simple_controls"] for result in control["modes"].values()]
            report["simple_control_generation_count"] = len(results)
            report["simple_control_eos_count"] = sum(result.get("eos_reached", result.get("eos", False)) for result in results)
            if report["status"] == "diagnostic_complete" and report["simple_control_eos_count"] < len(results):
                report["status"] = "completed_with_generation_limits"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()