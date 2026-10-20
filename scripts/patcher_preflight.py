"""Measure the existing BLT checkpoint without changing its owning project."""

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import time


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def command_output(*arguments):
    return subprocess.check_output(arguments, text=True).strip()


def module_size(module):
    parameters = list(module.parameters())
    buffers = list(module.buffers())
    return {
        "parameters": sum(parameter.numel() for parameter in parameters),
        "parameter_bytes": sum(parameter.numel() * parameter.element_size() for parameter in parameters),
        "buffer_bytes": sum(buffer.numel() * buffer.element_size() for buffer in buffers),
        "parameter_dtypes": sorted({str(parameter.dtype) for parameter in parameters}),
    }


def teacher_contract(model, tokenizer, torch):
    from phdq_blt_cache import patch_starts
    from blt_hf.patching import entropy_patch_lengths

    def patch(token_ids):
        return model.model.patcher(
            torch.tensor([token_ids], device="cuda", dtype=torch.long),
            patch_size=model.config.patch_size,
            threshold=model.config.patching_threshold,
            max_patch_length=model.config.max_patch_length,
            use_cache=False,
        )

    texts = {
        "short": "A",
        "repeat": "abcXabc",
        "list": "One sentence.\n1. Item 42.\n2. Item 43.",
        "multibyte": "English with caf\u00e9 and \ud55c\uae00.",
        "length_511": ("The context repeats. " * 30)[:510],
        "length_512": ("The context repeats. " * 30)[:511],
        "length_513": ("The context repeats. " * 30)[:512],
    }
    cases = []
    checks = {
        "empty_text_encodes_empty": tokenizer.encode("", add_special_tokens=False) == [],
        "vocab_and_specials": model.config.vocab_size == 260 and (tokenizer.bos_token_id, tokenizer.eos_token_id, tokenizer.pad_token_id) == (1, 2, 3),
    }
    fixtures = {}
    for name, text in texts.items():
        encoded = tokenizer.encode(text, add_special_tokens=False, truncation=False)
        checks[f"byte_mapping_{name}"] = encoded == [value + 4 for value in text.encode("utf-8")]
        fixtures[name] = [tokenizer.bos_token_id] + encoded
    fixtures["eos_segments"] = fixtures["list"] + [tokenizer.eos_token_id] + fixtures["repeat"][1:]
    with torch.inference_mode():
        threshold = torch.tensor(model.config.patching_threshold, dtype=torch.bfloat16, device="cuda")
        below = torch.nextafter(threshold, torch.full_like(threshold, -math.inf))
        above = torch.nextafter(threshold, torch.full_like(threshold, math.inf))
        synthetic = torch.stack([threshold, below, threshold, above]).unsqueeze(0)
        starts = patch_starts(entropy_patch_lengths(synthetic, model.config.patching_threshold)[0].tolist(), input_length=4)
        checks["strict_threshold_and_virtual_slot"] = starts == [0, 1, 4]
        unsupported_inputs = []
        for name, token_ids in (("empty_ids", []), ("bos_only", [tokenizer.bos_token_id])):
            try:
                patch(token_ids)
            except (ValueError, RuntimeError, IndexError) as error:
                unsupported_inputs.append({"case": name, "error_type": type(error).__name__})
            else:
                checks[f"reject_{name}"] = False
        for name, token_ids in fixtures.items():
            entropy, lengths, logits = patch(token_ids)
            log_probabilities = logits.log_softmax(dim=-1)
            reconstructed = -(log_probabilities.exp() * log_probabilities).sum(dim=-1)
            checks[f"entropy_from_same_logits_{name}"] = torch.equal(entropy, reconstructed)
            expected = [0, 1] + [index + 1 for index in range(1, len(token_ids)) if entropy[0, index].item() > threshold.item()]
            full_starts = patch_starts(lengths[0].tolist(), input_length=len(token_ids))
            checks[f"boundary_alignment_{name}"] = full_starts == expected
            repeated_entropy, repeated_lengths, _ = patch(token_ids)
            checks[f"same_shape_repeat_{name}"] = torch.equal(entropy, repeated_entropy) and torch.equal(lengths, repeated_lengths)
            cut = max(1, len(token_ids) // 2)
            changed = token_ids[:cut] + [tokenizer.eos_token_id if value == tokenizer.eos_token_id else ord("Z") + 4 for value in token_ids[cut:]]
            changed_entropy, _, _ = patch(changed)
            checks[f"same_shape_future_causality_{name}"] = torch.equal(entropy[:, :cut], changed_entropy[:, :cut])
            if name == "eos_segments":
                eos_position = token_ids.index(tokenizer.eos_token_id)
                changed = [tokenizer.bos_token_id] + [ord("X") + 4] * (eos_position - 1) + token_ids[eos_position:]
                changed_entropy, _, _ = patch(changed)
                checks["eos_segment_isolation"] = torch.equal(entropy[:, eos_position + 1:], changed_entropy[:, eos_position + 1:])
            prefixes = []
            for prefix_length in sorted({length for length in (2, 3, 4, 8, 16, 31, 63, 128, 255, 511, 512, 513, len(token_ids)) if length <= len(token_ids)}):
                prefix_entropy, prefix_lengths, _ = patch(token_ids[:prefix_length])
                prefix_starts = patch_starts(prefix_lengths[0].tolist(), input_length=prefix_length)
                reference = [position for position in full_starts if position <= prefix_length]
                prefixes.append({
                    "input_ids": prefix_length,
                    "max_abs_entropy_difference": (entropy[:, :prefix_length].float() - prefix_entropy.float()).abs().max().item(),
                    "changed_boundary_positions": sorted(set(prefix_starts) ^ set(reference)),
                })
            cases.append({"name": name, "input_ids": len(token_ids), "full_starts": full_starts, "prefixes": prefixes})
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "unsupported_inputs": unsupported_inputs,
        "tokenizer_entries_outside_model_vocab": {
            token: token_id for token, token_id in tokenizer.get_vocab().items()
            if token_id >= model.config.vocab_size
        },
        "label_protocol": "No padding; skip empty/BOS-only inputs; entropy at input index j determines boundary j+1 for j>=1; starts 0 and 1 are forced; last boundary can be virtual",
        "entropy_unit": "nats",
        "prefix_differences_are_diagnostic_not_failure": True,
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--blt-project", type=Path, required=True)
    parser.add_argument("--teacher-contract", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    work_root = Path(config["work_root"]).resolve()
    run_directory = (work_root / config["run_directory"]).resolve()
    if not run_directory.is_relative_to(work_root):
        raise ValueError("Output directory must stay inside work_root")
    run_directory.mkdir(parents=True, exist_ok=True)
    output_path = run_directory / ("teacher_contract.json" if args.teacher_contract else "preflight.json")
    report = {
        "run_id": config["run_id"],
        "status": "running",
        "scope": "Synthetic English BF16 inference preflight, not a quality or candidate-speed result",
        "config_sha256": file_hash(args.config),
        "script_sha256": file_hash(__file__),
        "samples": [],
    }
    with output_path.open("x") as output:
        started = time.perf_counter()
        try:
            import torch
            from packaging.specifiers import SpecifierSet
            from transformers import AutoTokenizer

            project = args.blt_project.resolve()
            sys.path.insert(0, str(project))
            from blt_hf.model import load_model

            baseline = config["baseline"]
            budgets = config["budgets"]
            torch.set_num_threads(budgets["cpu_threads"])
            torch.manual_seed(config["seed"])
            torch.cuda.set_device(budgets["gpu_index"])
            if not torch.cuda.is_bf16_supported():
                raise RuntimeError("BF16 CUDA support is required")
            if importlib.metadata.version("torch") not in SpecifierSet(">=2.11,<3"):
                raise RuntimeError("Runtime does not meet the standalone package requirement")
            free_disk = shutil.disk_usage(work_root).free
            if free_disk < budgets["minimum_free_disk_gib"] * 2**30:
                raise RuntimeError("Insufficient free disk for the declared budget")
            report["environment"] = {
                "python": sys.version,
                "executable": sys.executable,
                "platform": platform.platform(),
                "packages": {package.metadata["Name"]: package.version for package in importlib.metadata.distributions()},
                "cuda_runtime": torch.version.cuda,
                "gpu": torch.cuda.get_device_name(),
                "capability": list(torch.cuda.get_device_capability()),
                "gpu_state": command_output("nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version", "--format=csv"),
                "cpu": command_output("lscpu"),
                "memory": command_output("free", "-b"),
                "free_disk_bytes": free_disk,
            }
            model_path = Path(baseline["model_checkpoint"])
            conversion = Path(baseline["conversion_report"])
            report["checkpoint"] = {
                "path": str(model_path),
                "conversion_report_sha256": file_hash(conversion),
                "files": json.loads(conversion.read_text())["output_files"],
                "config": json.loads((model_path / "config.json").read_text()),
                "owner_commit": command_output("git", "-C", str(project), "rev-parse", "HEAD"),
                "owner_sources_sha256": {
                    str(path.relative_to(project)): file_hash(path)
                    for path in sorted((project / "blt_hf").rglob("*.py"))
                },
            }
            load_started = time.perf_counter()
            model = load_model(model_path, conversion, attention_mode="osc", backend="eager", device="cpu")
            model.eval().requires_grad_(False)
            report["checkpoint"]["hashes_verified_and_strict_load_passed"] = True
            report["load_seconds"] = time.perf_counter() - load_started
            report["model_size"] = module_size(model)
            report["components"] = {
                name: module_size(getattr(model.model, name))
                for name in ("patcher", "local_encoder", "global_transformer", "local_decoder")
            }
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            report["tokenizer"] = {
                "vocab_size": len(tokenizer),
                "bos": tokenizer.bos_token_id,
                "eos": tokenizer.eos_token_id,
                "pad": tokenizer.pad_token_id,
            }
            lengths = baseline["probe_lengths_input_ids"]
            if min(lengths) < 2 or max(lengths) > model.config.max_position_embeddings:
                raise ValueError("Probe length outside the model's configured range")
            fixture = "The quick brown fox crosses the road. A repeatable English example.\n"
            text = (fixture * math.ceil(max(lengths) / len(fixture)))[:max(lengths) - 1]
            payload = tokenizer.encode(text, add_special_tokens=False, truncation=False)
            model.model.patcher.to("cuda")
            if args.teacher_contract:
                report["teacher_contract"] = teacher_contract(model, tokenizer, torch)
                if report["teacher_contract"]["status"] != "passed":
                    raise RuntimeError("Teacher contract checks failed; inspect per-check results")
            with torch.inference_mode():
                for stage in (() if args.teacher_contract else ("teacher_only", "full_model")):
                    if stage == "full_model":
                        model.to("cuda")
                    for length in lengths:
                        input_ids = torch.tensor([[tokenizer.bos_token_id] + payload[:length - 1]], device="cuda")
                        gc.collect()
                        torch.cuda.empty_cache()
                        torch.cuda.reset_peak_memory_stats()
                        durations = []
                        details = {}
                        for repetition in range(baseline["warmup_repetitions"] + baseline["timed_repetitions"]):
                            if time.perf_counter() - started > budgets["maximum_preflight_seconds"]:
                                raise RuntimeError("Preflight time budget exceeded")
                            torch.cuda.synchronize()
                            before = time.perf_counter()
                            if stage == "teacher_only":
                                result = model.model.patcher(
                                    input_ids, patch_size=model.config.patch_size,
                                    threshold=model.config.patching_threshold,
                                    max_patch_length=model.config.max_patch_length, use_cache=False,
                                )
                                values = result[0]
                            else:
                                result = model(input_ids=input_ids, use_cache=False)
                                values = result.logits
                            torch.cuda.synchronize()
                            elapsed_ms = (time.perf_counter() - before) * 1000
                            if not torch.isfinite(values).all().item():
                                raise RuntimeError("Nonfinite model output")
                            details = {"output_shape": list(values.shape), "dtype": str(values.dtype)}
                            if stage == "teacher_only":
                                details["patch_count"] = int(result[1].ne(0).sum().item())
                                details["effective_threshold"] = torch.tensor(model.config.patching_threshold, dtype=values.dtype).item()
                            if repetition >= baseline["warmup_repetitions"]:
                                durations.append(elapsed_ms)
                            del result, values
                        item = {
                            "stage": stage,
                            "input_ids": length,
                            "median_ms": statistics.median(durations),
                            "mean_ms": statistics.mean(durations),
                            "stdev_ms": statistics.pstdev(durations),
                            "p95_ms": sorted(durations)[math.ceil(0.95 * len(durations)) - 1],
                            "runs_ms": durations,
                            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                            **details,
                        }
                        report["samples"].append(item)
                        print(json.dumps(item), flush=True)
                        if item["peak_reserved_bytes"] > budgets["peak_gpu_memory_gib"] * 2**30:
                            raise RuntimeError("GPU memory budget exceeded")
                        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > budgets["peak_host_ram_gib"] * 2**30:
                            raise RuntimeError("Host RAM budget exceeded")
                        del input_ids
            report["status"] = "passed"
        except Exception as error:
            report.update(status="failed", error_type=type(error).__name__, error=str(error))
        finally:
            report["elapsed_seconds"] = time.perf_counter() - started
            report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            json.dump(report, output, indent=2)
            output.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output_path), "error": report.get("error")}), flush=True)
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())