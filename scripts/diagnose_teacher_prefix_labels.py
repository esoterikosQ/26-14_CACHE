"""Explicit heldout teacher-prefix diagnostic; never fit or change a patcher."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np

from phdq_blt_cache import patch_starts
from scripts.compare_blt_patchers import evaluation_documents
from scripts.patcher_preflight import file_hash


def compare_teacher_prefixes(token_ids, evaluate):
    if len(token_ids) < 2:
        raise ValueError("At least BOS and one byte are required")
    full_entropy, full_labels = evaluate(token_ids)
    size = len(token_ids)
    if full_entropy.shape != (size + 1,) or full_labels.shape != (size + 1,):
        raise ValueError("Invalid full-input alignment")
    entropy_rows = np.full((size - 1, size + 1), np.nan, dtype=np.float32)
    label_rows = np.zeros((size - 1, (size + 8) // 8), dtype=np.uint8)
    summary = {"input_ids": size, "prefixes": size - 1,
               "endpoint_positions": size - 1, "endpoint_mismatches": 0,
               "past_positions": 0, "past_mismatches": 0,
               "prefixes_with_any_mismatch": 0, "max_abs_entropy_difference": 0.,
               "endpoint_disagreements": [], "same_input_replay_exact": False}
    for row_index, length in enumerate(range(2, size + 1)):
        entropy, labels = evaluate(token_ids[:length])
        if entropy.shape != (length + 1,) or labels.shape != entropy.shape:
            raise ValueError("Invalid prefix alignment")
        if not np.isfinite(entropy).all() or not labels[:2].all():
            raise ValueError("Invalid teacher prefix labels")
        entropy_rows[row_index, :length + 1] = entropy
        packed = np.packbits(labels, bitorder="little")
        label_rows[row_index, :len(packed)] = packed
        differences = labels[2:] != full_labels[2:length + 1]
        summary["endpoint_mismatches"] += int(differences[-1])
        summary["past_positions"] += length - 2
        summary["past_mismatches"] += int(differences[:-1].sum())
        summary["prefixes_with_any_mismatch"] += int(differences.any())
        summary["max_abs_entropy_difference"] = max(
            summary["max_abs_entropy_difference"],
            float(np.max(np.abs(entropy[2:] - full_entropy[2:length + 1]))))
        if differences[-1]:
            summary["endpoint_disagreements"].append({
                "prefix_input_ids": length, "full_entropy": float(full_entropy[length]),
                "prefix_entropy": float(entropy[-1]), "full_label": bool(full_labels[length]),
                "prefix_label": bool(labels[-1])})
        if length == size:
            if not np.array_equal(entropy, full_entropy) or not np.array_equal(labels, full_labels):
                raise ValueError("Same-input teacher replay changed")
            summary["same_input_replay_exact"] = True
    summary["endpoint_mismatch_rate"] = summary["endpoint_mismatches"] / summary["endpoint_positions"]
    summary["past_mismatch_rate"] = (summary["past_mismatches"] / summary["past_positions"]
                                     if summary["past_positions"] else None)
    summary["all_visible_positions"] = summary["past_positions"] + summary["endpoint_positions"]
    summary["all_visible_mismatches"] = summary["past_mismatches"] + summary["endpoint_mismatches"]
    summary["all_visible_mismatch_rate"] = summary["all_visible_mismatches"] / summary["all_visible_positions"]
    return summary, {"full_entropy": full_entropy, "full_labels": full_labels,
                     "prefix_entropy": entropy_rows, "prefix_labels_packed_little": label_rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pilot-config", "quality-reference", "dataset-directory", "blt-project", "output-directory"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--documents-per-split", type=int, default=3)
    args = parser.parse_args()
    if args.documents_per_split <= 0:
        parser.error("Expected a positive subset size")
    pilot = json.loads(args.pilot_config.read_text())
    reference = json.loads(args.quality_reference.read_text())
    baseline, budgets = pilot["baseline"], pilot["budgets"]
    if reference["status"] != "completed" or reference["stage"] != "quality":
        raise ValueError("Expected completed frozen quality evidence")
    checkpoint = Path(baseline["model_checkpoint"])
    conversion = Path(baseline["conversion_report"])
    if str(checkpoint) != reference["model_checkpoint"]:
        raise ValueError("Checkpoint differs from frozen quality evidence")
    if reference["sources"][str(conversion)] != file_hash(conversion):
        raise ValueError("Conversion report changed")
    for source, digest in reference["code_sha256"].items():
        if Path(source).is_relative_to(args.blt_project) and file_hash(Path(source)) != digest:
            raise ValueError(f"Owner model source changed: {source}")
    selected = []
    for split in ("test", "wikipedia_test"):
        if file_hash(args.dataset_directory / f"{split}.jsonl") != reference["split_sha256"][split]:
            raise ValueError(f"Evaluation split changed: {split}")
        documents = evaluation_documents(args.dataset_directory, split)
        for document_index in range(args.documents_per_split):
            metadata, chunks = next(documents)
            selected.append((dict(metadata, document_index=document_index, chunk_index=0,
                                  byte_offset=0), np.asarray(chunks[0], dtype=np.uint16)))
    args.output_directory.mkdir(parents=True, exist_ok=False)
    report_path = args.output_directory / "result.json"
    report = {"status": "running", "stage": "T06-evaluation-teacher-prefixes",
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "sources": {str(path): file_hash(path) for path in
                          (args.pilot_config, args.quality_reference, conversion, Path(__file__))},
              "model_checkpoint": str(checkpoint),
              "model_safetensors_sha256": file_hash(checkpoint / "model.safetensors"),
              "owner_source_sha256": {source: digest for source, digest in reference["code_sha256"].items()
                                      if Path(source).is_relative_to(args.blt_project)},
              "split_sha256": {split: reference["split_sha256"][split] for split in ("test", "wikipedia_test")},
              "protocol": {"subset": f"First {args.documents_per_split} documents per split, first chunk only, fixed before inference",
                           "chunk": "At most 2047 original bytes plus BOS, no appended EOS or padding",
                           "prefixes": "All input lengths 2..n, complete independent teacher calls, use_cache=False",
                           "endpoint": "Label at virtual next-byte position length versus full-input label at that position",
                           "past": "All visible positions 2..length-1; repeated positions are not independent observations",
                           "forced_positions": "0/1 excluded from all mismatch rates",
                           "sampling": "None: fixed document bytes revealed one at a time; no refitting or threshold selection"},
              "limitations": "Small deterministic previously opened evaluation subset; not full-split parity, causal-error diagnosis, free-generation quality or new independent evaluation. Raw labels stay outside the package.",
              "cases": []}
    started = time.perf_counter()

    def save():
        temporary = report_path.with_suffix(".partial.json")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(report_path)

    save()
    try:
        import torch
        import transformers

        torch.set_num_threads(budgets["cpu_threads"])
        torch.cuda.set_device(budgets["gpu_index"])
        sys.path.insert(0, str(args.blt_project.resolve()))
        from blt_hf.model import load_model

        model = load_model(checkpoint, conversion, attention_mode="osc", backend="eager", device="cpu")
        model.eval().requires_grad_(False)
        model.model.patcher.to("cuda")
        torch.cuda.reset_peak_memory_stats()
        threshold = torch.tensor(model.config.patching_threshold, dtype=torch.bfloat16).item()
        if model.config.vocab_size != 260 or model.config.max_patch_length is not None:
            raise ValueError("Teacher vocabulary or patch cap changed")
        report["effective_threshold"] = threshold
        report["runtime"] = {"torch": torch.__version__, "transformers": transformers.__version__,
                             "gpu": torch.cuda.get_device_name(), "dtype": "bfloat16", "batch": 1,
                             "threads": torch.get_num_threads(), "attention": "osc", "backend": "eager", "cache": False}

        def evaluate(token_ids):
            inputs = torch.as_tensor(token_ids.astype(np.int64), device="cuda").unsqueeze(0)
            entropy, lengths, _ = model.model.patcher(
                inputs, patch_size=model.config.patch_size, threshold=model.config.patching_threshold,
                max_patch_length=model.config.max_patch_length, use_cache=False)
            if entropy.dtype != torch.bfloat16:
                raise ValueError("Teacher entropy dtype changed")
            aligned = np.concatenate(([0.], entropy[0].float().cpu().numpy())).astype(np.float32)
            labels = np.zeros(len(token_ids) + 1, dtype=bool)
            labels[patch_starts(lengths[0].cpu().tolist(), input_length=len(token_ids))] = True
            if not np.array_equal(labels[2:], aligned[2:] > threshold):
                raise ValueError("Teacher entropy/boundary alignment changed")
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > budgets["peak_host_ram_gib"] * 2**30:
                raise RuntimeError("Host RAM budget exceeded")
            if torch.cuda.max_memory_reserved() > budgets["peak_gpu_memory_gib"] * 2**30:
                raise RuntimeError("GPU memory budget exceeded")
            return aligned, labels

        with torch.inference_mode():
            for case_index, (metadata, token_ids) in enumerate(selected):
                result, arrays = compare_teacher_prefixes(token_ids, evaluate)
                archive = args.output_directory / f"case-{case_index:02}.npz"
                with archive.open("xb") as output:
                    np.savez_compressed(output, **arrays)
                del arrays
                report["cases"].append(dict(metadata, **result, archive=str(archive),
                                            archive_sha256=file_hash(archive)))
                save()
                print(json.dumps({"case": case_index, "split": metadata["split"], **result}), flush=True)
        for scope in ("test", "wikipedia_test", "combined"):
            cases = [case for case in report["cases"] if scope == "combined" or case["split"] == scope]
            totals = {key: sum(case[key] for case in cases) for key in (
                "endpoint_positions", "endpoint_mismatches", "past_positions", "past_mismatches",
                "all_visible_positions", "all_visible_mismatches", "prefixes_with_any_mismatch")}
            for kind in ("endpoint", "past", "all_visible"):
                totals[f"{kind}_mismatch_rate"] = (totals[f"{kind}_mismatches"] / totals[f"{kind}_positions"]
                                                     if totals[f"{kind}_positions"] else None)
            report.setdefault("summary", {})[scope] = dict(totals, documents=len(cases))
        report["status"] = "completed"
        report["peak_gpu_reserved_bytes"] = torch.cuda.max_memory_reserved()
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = time.perf_counter() - started
        report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        save()
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    main()