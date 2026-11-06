"""Explicit, experimental C++ count-patcher comparison; not a package backend."""

from dataclasses import asdict
import argparse
import copy
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sysconfig
import time


def build_native(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    library = directory / ("_count_patcher_probe" + sysconfig.get_config_var("EXT_SUFFIX"))
    if library.exists():
        raise FileExistsError(library)
    source = Path(__file__).parent / "native" / "count_patcher.cpp"
    command = ["c++", "-std=c++17", "-O3", "-ffp-contract=off", "-shared", "-fPIC",
               "-I" + sysconfig.get_path("include"), str(source), "-o", str(library)]
    subprocess.run(command, check=True)
    spec = importlib.util.spec_from_file_location("_count_patcher_probe", library)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, command, library


class NativeAdapter:
    def __init__(self, module, config, rule, background):
        if config.window is not None or (config.vocab_size, config.eos_id, config.pad_id) != (260, 2, 3):
            raise ValueError("Probe supports only the frozen unlimited-window BLT vocabulary")
        self.module, self.config, self.rule, self.background = module, config, rule, background
        self.reset()

    def reset(self):
        self.state = self.module.create(asdict(self.config), asdict(self.rule), self.background.lookup)

    def patch_lengths(self, input_ids):
        import torch

        if torch.is_grad_enabled() or input_ids.dtype != torch.long or input_ids.ndim != 2 or input_ids.shape[0] != 1:
            raise ValueError("Expected inference-only batch-one long input")
        lengths = self.module.run(self.state, input_ids[0].tolist())
        return torch.tensor([lengths], dtype=torch.long, device=input_ids.device)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paired_summary(samples):
    import numpy as np

    python = np.array([sample["python"] for sample in samples])
    cpp = np.array([sample["cpp"] for sample in samples])
    indices = np.random.default_rng(20261019).integers(0, len(samples), size=(2000, len(samples)))
    ratios = np.median(python[indices], axis=1) / np.median(cpp[indices], axis=1)
    ratio = float(np.median(python) / np.median(cpp))
    return {"samples": samples,
            "p50_seconds": {"python": float(np.median(python)), "cpp": float(np.median(cpp))},
            "p95_seconds": {"python": float(np.percentile(python, 95)), "cpp": float(np.percentile(cpp, 95))},
            "speedup": ratio, "reduction_percent": 100 * (1 - 1 / ratio),
            "paired_bootstrap95_speedup": np.percentile(ratios, [2.5, 97.5]).tolist()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--cost-reference", required=True, type=Path)
    parser.add_argument("--background", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.parent.exists():
        raise FileExistsError("Use a completely new output directory")
    reference = json.loads(args.reference.read_text())
    cost_reference = json.loads(args.cost_reference.read_text())
    if (reference["status"], reference["stage"], cost_reference["status"]) != ("completed", "total", "completed"):
        raise ValueError("Expected completed frozen references")
    if cost_reference["reference_sha256"] != sha256(args.reference):
        raise ValueError("Cost reference belongs to different inputs")
    import numpy as np
    import torch
    from phdq_blt_cache.blt_patcher import CountPatcherAdapter
    from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig
    from phdq_blt_cache.lmdb_counts import LMDBCountTable

    torch.set_num_threads(8)
    torch.cuda.set_device(0)
    if torch.__version__ != cost_reference["runtime"]["torch"] or torch.cuda.get_device_name(0) != cost_reference["runtime"]["gpu"]:
        raise ValueError("Runtime differs from cost reference")
    for symbol in (CountPatcherAdapter, CountConfig, LMDBCountTable):
        source = Path(inspect.getfile(symbol)).resolve()
        expected = [digest for name, digest in cost_reference["code_sha256"].items() if name.endswith("/" + source.name)]
        if expected != [sha256(source)]:
            raise ValueError(f"Reference source changed: {source}")
    module, command, library = build_native(args.output.parent / "native")
    source = Path(__file__).parent / "native" / "count_patcher.cpp"
    report = {
        "status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_sha256": sha256(args.reference), "cost_reference_sha256": sha256(args.cost_reference),
        "rule": reference["rule"], "count_config": reference["count_config"],
        "code_sha256": cost_reference["code_sha256"], "runner_sha256": sha256(__file__),
        "cpp_sha256": sha256(source), "library_sha256": sha256(library),
        "build_command": command,
        "compiler": subprocess.run(["c++", "--version"], capture_output=True, text=True, check=True).stdout,
        "runtime": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__,
                    "gpu": torch.cuda.get_device_name(0), "threads": torch.get_num_threads()},
        "protocol": {
            "scope": "Isolated count patcher; unchanged Python LMDB/LRU callback and GPU input/output; no model weights loaded",
            "changed": "C++ token loop, probability/entropy/score, online counts and boundary/length state; no rule tuning",
            "not_changed": "Same Python LMDB background, 4096-row LRU, GPU.tolist input and torch.tensor output",
            "cache_control": "Separate identical LRU caches over one shared read-only LMDB transaction; clear both before each phase, then identical warmups",
            "warmups": 3, "repeats": 10, "order": "Alternate python/cpp per repetition",
            "initial": "One prefix forward ending 32 IDs before final length",
            "incremental32": "Identical 32 full-prefix calls after untimed priming; count state reused",
            "excluded": "Build/loading, adapter reset, priming, diagnostics, output copying for validation",
            "numerical_atol": 2e-13, "numerical_rtol": 0,
            "bootstrap": "Paired execution blocks, 2000 resamples, seed20261019; ratio of medians",
            "limitations": "Not pure interpreter overhead or theoretical maximum removal; C++ changes storage/layout and numeric reductions. Not full-model or generation speedup, no adoption claim.",
        }, "cases": [],
    }
    with LMDBCountTable(args.background) as background, torch.inference_mode():
        if background.metadata != reference["background"]:
            raise ValueError("Background metadata differs")
        report["background"] = background.metadata
        config, rule = CountConfig(**reference["count_config"]), BoundaryRule(**reference["rule"])
        backgrounds = {mode: copy.copy(background) for mode in ("python", "cpp")}
        for candidate in backgrounds.values():
            candidate._cached_lookup = lru_cache(maxsize=4096)(candidate._read)
        adapters = {"python": CountPatcherAdapter(config, rule, backgrounds["python"]),
                    "cpp": NativeAdapter(module, config, rule, backgrounds["cpp"])}
        if len(reference["timing_cases"]) != 8:
            raise ValueError("Expected eight frozen inputs")
        for case in reference["timing_cases"]:
            ids = torch.tensor([case["input_ids"]], dtype=torch.long, device="cuda")
            priming = ids[:, :-32]
            extensions = tuple(ids[:, :length] for length in range(ids.shape[1] - 31, ids.shape[1] + 1))
            record = {key: value for key, value in case.items() if key != "measurements"}
            record["initial_length"] = priming.shape[1]
            for adapter in adapters.values():
                adapter.reset()
            max_entropy = max_score = 0.0
            minimum_margin = float("inf")
            checked_positions = 0
            for current in (priming, *extensions):
                python_lengths = adapters["python"].patch_lengths(current)
                cpp_lengths = adapters["cpp"].patch_lengths(current)
                if not torch.equal(python_lengths, cpp_lengths):
                    raise ValueError("C++ boundaries differ")
                _, diagnostics = module.run(adapters["cpp"].state, current[0].tolist(), True)
                expected = adapters["python"]._decisions + [adapters["python"]._patcher.predict_boundary()]
                expected_values = np.array([(item.entropy, item.score) for item in expected])
                actual_values = np.array(diagnostics)[:, :2]
                np.testing.assert_allclose(actual_values, expected_values, rtol=0, atol=2e-13)
                if [tuple(row[2:]) for row in diagnostics] != [(item.repeated_length, item.distance, int(item.boundary)) for item in expected]:
                    raise ValueError("C++ discrete diagnostics differ")
                difference = np.max(np.abs(actual_values - expected_values), axis=0)
                max_entropy, max_score = max(max_entropy, float(difference[0])), max(max_score, float(difference[1]))
                minimum_margin = min(minimum_margin, min(abs(item.score - rule.threshold) for item in expected[2:]))
                checked_positions += len(expected)
                fresh = NativeAdapter(module, config, rule, backgrounds["cpp"])
                if not torch.equal(fresh.patch_lengths(current), cpp_lengths):
                    raise ValueError("C++ warm/fresh boundaries differ")
            record["control"] = {"prefixes": 33, "positions_including_rechecks": checked_positions,
                                 "max_entropy_abs_error": max_entropy, "max_score_abs_error": max_score,
                                 "minimum_python_threshold_margin": minimum_margin,
                                 "boundaries_and_discrete_diagnostics_exact": True, "cpp_warm_fresh_exact": True}
            record["phases"] = {}
            for phase, inputs in (("initial", (priming,)), ("incremental32", extensions)):
                for candidate in backgrounds.values():
                    candidate._cached_lookup.cache_clear()
                samples = []
                for repetition in range(-3, 10):
                    sample = {"repetition": repetition}
                    results = {}
                    order = ("python", "cpp") if repetition % 2 == 0 else ("cpp", "python")
                    for mode in order:
                        adapter = adapters[mode]
                        adapter.reset()
                        if phase == "incremental32":
                            adapter.patch_lengths(priming)
                        cache_before = backgrounds[mode].cache_info()
                        torch.cuda.synchronize()
                        started = time.perf_counter()
                        lengths = [adapter.patch_lengths(current) for current in inputs]
                        torch.cuda.synchronize()
                        sample[mode] = time.perf_counter() - started
                        cache_after = backgrounds[mode].cache_info()
                        sample[mode + "_cache"] = {"hits": cache_after.hits - cache_before.hits,
                                                    "misses": cache_after.misses - cache_before.misses}
                        results[mode] = [value.tolist() for value in lengths]
                    if results["python"] != results["cpp"]:
                        raise ValueError("Timed boundaries differ")
                    if sample["python_cache"] != sample["cpp_cache"]:
                        raise ValueError("Timed background cache workload differs")
                    if repetition >= 0:
                        samples.append(sample)
                record["phases"][phase] = paired_summary(samples)
                print(case["split"], case["input_length"], phase,
                      record["phases"][phase]["speedup"], flush=True)
            report["cases"].append(record)
    report["status"] = "completed"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()