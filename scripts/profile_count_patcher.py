"""Measure frozen count-patcher costs without changing its calculations."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import platform
import statistics
import time

from phdq_blt_cache.blt_patcher import CountPatcherAdapter
from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig
from phdq_blt_cache.lmdb_counts import LMDBCountTable


class CostMeter:
    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.seconds = {}
        self.calls = {}

    def call(self, category, function, *args, **kwargs):
        started = self.clock()
        result = function(*args, **kwargs)
        elapsed = self.clock() - started
        self.seconds[category] = self.seconds.get(category, 0.0) + elapsed
        self.calls[category] = self.calls.get(category, 0) + 1
        return result

    def finish(self, total):
        measured = dict(self.seconds)
        measured["compute_and_other"] = total - sum(measured.values())
        if measured["compute_and_other"] < 0:
            raise ValueError("Overlapping timing categories")
        return {"total_seconds": total, "seconds": measured, "calls": dict(self.calls)}


class MeasuredInput:
    def __init__(self, tensor, meter):
        self.tensor = tensor
        self.meter = meter

    def __getattr__(self, name):
        return getattr(self.tensor, name)

    def __getitem__(self, index):
        return MeasuredInput(self.tensor[index], self.meter)

    def tolist(self):
        return self.meter.call("input_to_cpu", self.tensor.tolist)


@contextmanager
def instrument(adapter, meter, torch):
    background = adapter.background
    online = adapter._patcher.model.online
    original_background = background.lookup
    original_online = online.lookup
    original_tensor = torch.tensor

    def output_tensor(*args, **kwargs):
        def create():
            result = original_tensor(*args, **kwargs)
            torch.cuda.synchronize()
            return result
        return meter.call("output_to_gpu", create)

    background.lookup = lambda context: meter.call("background_lookup", original_background, context)
    online.lookup = lambda context: meter.call("online_lookup", original_online, context)
    torch.tensor = output_tensor
    try:
        yield
    finally:
        background.lookup = original_background
        online.lookup = original_online
        torch.tensor = original_tensor


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(samples):
    totals = [sample["total_seconds"] for sample in samples]
    result = {"samples": samples, "total_p50_seconds": statistics.median(totals)}
    if samples[0].get("seconds"):
        categories = samples[0]["seconds"]
        denominator = sum(totals)
        result["time_weighted_percent"] = {
            category: 100 * sum(sample["seconds"][category] for sample in samples) / denominator
            for category in categories
        }
        result["category_p50_seconds"] = {
            category: statistics.median(sample["seconds"][category] for sample in samples)
            for category in categories
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--background", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    reference = json.loads(args.reference.read_text())
    if reference["status"] != "completed" or reference["stage"] != "total":
        raise ValueError("Expected completed total replay reference")
    import torch

    torch.set_num_threads(8)
    torch.cuda.set_device(0)
    for symbol in (CountPatcherAdapter, CountConfig, LMDBCountTable):
        source = Path(inspect.getfile(symbol)).resolve()
        matches = [digest for name, digest in reference["code_sha256"].items()
                   if name.endswith("/" + source.name)]
        if matches != [sha256(source)]:
            raise ValueError(f"Executed source differs from reference: {source}")
    if torch.__version__ != reference["runtime"]["torch"] or torch.cuda.get_device_name(0) != reference["runtime"]["gpu"]:
        raise ValueError("Torch or GPU differs from reference")
    report = {
        "status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_sha256": sha256(args.reference), "rule": reference["rule"],
        "count_config": reference["count_config"], "runtime": {
            "python": platform.python_version(), "torch": torch.__version__,
            "gpu": torch.cuda.get_device_name(0), "threads": torch.get_num_threads()},
        "code_sha256": {str(Path(inspect.getfile(symbol)).resolve()): sha256(inspect.getfile(symbol))
                        for symbol in (CountPatcherAdapter, CountConfig, LMDBCountTable)},
        "profiler_sha256": sha256(__file__),
        "protocol": {
            "scope": "Count patcher only, no full model, loading/reset/priming excluded",
            "inputs": "Exact total-reference IDs; initial prefix ends 32 IDs before final length",
            "warmups": 3, "repeats": 10, "order": "Alternate baseline/instrumented per repeat",
            "lookup": "Background LRU/LMDB read/row decoding plus online dictionary lookup; not disk I/O alone",
            "transfer": "Input GPU Tensor.tolist and output torch.tensor creation plus CUDA completion",
            "compute_and_other": "Residual: probability/entropy/boundary/state work, Python, validation, allocations and timer/wrapper overhead",
            "percent": "Sum of category durations / sum of instrumented elapsed durations, not sum of medians",
            "cache": "Existing 4096-row LRU retained; warmups; no OS cache flush; count state reset each repetition",
            "limitations": "Single process, patcher isolated without resident BLT weights; instrumented shares are not uninstrumented full-model shares; no optimization or refitting",
        }, "cases": [],
    }
    with LMDBCountTable(args.background) as background, torch.inference_mode():
        if background.metadata != reference["background"]:
            raise ValueError("Background metadata differs from reference")
        report["background"] = background.metadata
        adapter = CountPatcherAdapter(CountConfig(**reference["count_config"]), BoundaryRule(**reference["rule"]), background)
        cases = reference["timing_cases"]
        if len(cases) != 8:
            raise ValueError("Expected eight frozen inputs")
        for case in cases:
            ids = torch.tensor([case["input_ids"]], dtype=torch.long, device="cuda")
            priming = ids[:, :-32]
            extensions = tuple(ids[:, :length] for length in range(ids.shape[1] - 31, ids.shape[1] + 1))
            record = {key: value for key, value in case.items() if key != "measurements"}
            record["initial_length"] = priming.shape[1]
            record["phases"] = {}
            for phase, inputs in (("initial", (priming,)), ("incremental32", extensions)):
                samples = {mode: [] for mode in ("baseline", "instrumented")}
                for repetition in range(-3, 10):
                    outputs = {}
                    order = ("baseline", "instrumented") if repetition % 2 == 0 else ("instrumented", "baseline")
                    for mode in order:
                        adapter.reset()
                        if phase == "incremental32":
                            adapter.patch_lengths(priming)
                        meter = CostMeter()
                        cache_before = background.cache_info()
                        torch.cuda.synchronize()
                        started = time.perf_counter()
                        if mode == "instrumented":
                            with instrument(adapter, meter, torch):
                                results = [adapter.patch_lengths(MeasuredInput(current, meter)) for current in inputs]
                        else:
                            results = [adapter.patch_lengths(current) for current in inputs]
                        torch.cuda.synchronize()
                        total = time.perf_counter() - started
                        cache_after = background.cache_info()
                        outputs[mode] = [result.tolist() for result in results]
                        if repetition >= 0:
                            sample = meter.finish(total) if mode == "instrumented" else {"total_seconds": total}
                            sample["repetition"] = repetition
                            sample["cache_hits"] = cache_after.hits - cache_before.hits
                            sample["cache_misses"] = cache_after.misses - cache_before.misses
                            samples[mode].append(sample)
                    if outputs["baseline"] != outputs["instrumented"]:
                        raise ValueError("Instrumentation changed patch lengths")
                record["phases"][phase] = {mode: summarize(values) for mode, values in samples.items()}
                record["phases"][phase]["instrumentation_ratio"] = (
                    statistics.median(sample["total_seconds"] for sample in samples["instrumented"])
                    / statistics.median(sample["total_seconds"] for sample in samples["baseline"]))
                print(case["input_length"], phase, record["phases"][phase]["instrumentation_ratio"], flush=True)
            record["boundary_controls"] = "Exact baseline/instrumented match in all 26 blocks per phase"
            report["cases"].append(record)
    report["status"] = "completed"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()