"""Create resumable train/validation teacher labels; never open heldout splits."""

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np

from phdq_blt_cache import patch_starts
from scripts.benchmark_count_patcher import file_hash


PROTOCOL = {
    "version": 1, "maximum_input_ids": 2048, "bos_id": 1, "eos_id": 2, "pad_id": 3,
    "input": "Original UTF-8 bytes plus 4, with BOS per chunk; no appended EOS or padding",
    "chunking": "Consecutive nonoverlapping chunks of at most 2047 bytes; byte offsets, not character offsets",
    "state": "Teacher and candidate context/online counts reset per chunk; no state carried between chunks",
    "alignment": "H[i] from logit i-1; starts 0 and 1 forced; include virtual next-ID position n; H[0]=0 sentinel",
    "evaluation": "Only positions 2..n inclusive; empty text rejected; no final-test access",
    "prefix_diagnostic": "First three validation documents, first chunk only, distinct prefix lengths 64/128/256/n",
}


def chunk_inputs(text):
    raw = text.encode("utf-8")
    if not raw:
        raise ValueError("Empty documents cannot be labeled")
    for offset in range(0, len(raw), PROTOCOL["maximum_input_ids"] - 1):
        payload = raw[offset:offset + PROTOCOL["maximum_input_ids"] - 1]
        yield offset, np.asarray([1] + [value + 4 for value in payload], dtype=np.uint16)


def verify_cached(path, token_ids, contract_hash):
    with np.load(path, allow_pickle=False) as cached:
        if str(cached["contract_sha256"]) != contract_hash or not np.array_equal(cached["input_ids"], token_ids):
            raise ValueError("Existing label cache does not match input/protocol")
        entropy = cached["entropy"].copy()
        labels = cached["labels"].copy()
        if entropy.shape != (len(token_ids) + 1,) or labels.shape != entropy.shape:
            raise ValueError("Invalid cached alignment")
        if not np.isfinite(entropy).all() or not labels[:2].all():
            raise ValueError("Invalid cached labels")
        return entropy, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--blt-project", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    root = Path(config["work_root"])
    run = root / config["run_directory"]
    dataset = root / config["dataset_directory"] / config["run_id"]
    manifest = json.loads((dataset / "manifest.json").read_text())
    background = json.loads((run / "background_build.json").read_text())
    if background["status"] != "built":
        raise ValueError("A successful bounded background build is required")
    budgets = config["budgets"]
    baseline = config["baseline"]
    contract = {
        "protocol": PROTOCOL, "config_sha256": file_hash(args.config),
        "conversion_sha256": file_hash(baseline["conversion_report"]),
        "owner_source_sha256": {str(path.relative_to(args.blt_project)): file_hash(path) for path in sorted((args.blt_project / "blt_hf").rglob("*.py"))},
    }
    contract_hash = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    labels_root = run / "labels"
    labels_root.mkdir(exist_ok=True)
    report_path = run / "label_generation.json"
    if args.resume:
        report_path = run / f"label_generation_resume_{time.time_ns()}.json"
    report = {"stage": "T06-labels", "run_id": config["run_id"], "status": "running", "contract": contract, "contract_sha256": contract_hash, "splits": {}, "prefix_diagnostics": []}
    started = time.perf_counter()
    with report_path.open("x") as output:
        try:
            import torch
            from transformers import AutoTokenizer

            sys.path.insert(0, str(args.blt_project.resolve()))
            from blt_hf.model import load_model

            torch.set_num_threads(budgets["cpu_threads"])
            torch.cuda.set_device(budgets["gpu_index"])
            model = load_model(Path(baseline["model_checkpoint"]), Path(baseline["conversion_report"]), attention_mode="osc", backend="eager", device="cpu")
            model.eval().requires_grad_(False)
            model.model.patcher.to("cuda")
            tokenizer = AutoTokenizer.from_pretrained(baseline["model_checkpoint"], local_files_only=True)
            if (model.config.vocab_size, tokenizer.bos_token_id, tokenizer.eos_token_id, tokenizer.pad_token_id) != (260, 1, 2, 3):
                raise ValueError("Byte protocol differs from the actual model")
            torch.cuda.reset_peak_memory_stats()
            effective_threshold = torch.tensor(model.config.patching_threshold, dtype=torch.bfloat16).item()

            def evaluate(token_ids):
                inputs = torch.as_tensor(token_ids.astype(np.int64), device="cuda").unsqueeze(0)
                entropy, lengths, _ = model.model.patcher(
                    inputs, patch_size=model.config.patch_size, threshold=model.config.patching_threshold,
                    max_patch_length=model.config.max_patch_length, use_cache=False,
                )
                if entropy.dtype != torch.bfloat16:
                    raise ValueError("Teacher entropy dtype changed")
                aligned_entropy = np.concatenate(([0.0], entropy[0].float().cpu().numpy())).astype(np.float32)
                labels = np.zeros(len(token_ids) + 1, dtype=bool)
                labels[patch_starts(lengths[0].cpu().tolist(), input_length=len(token_ids))] = True
                if not np.isfinite(aligned_entropy).all() or not np.array_equal(labels[2:], aligned_entropy[2:] > effective_threshold):
                    raise ValueError("Teacher entropy/boundary alignment changed")
                return aligned_entropy, labels

            with torch.inference_mode():
                for split in ("train", "validation"):
                    source = dataset / f"{split}.jsonl"
                    if file_hash(source) != manifest["splits"][split]["file_sha256"]:
                        raise ValueError("Source split hash mismatch")
                    destination = labels_root / split
                    destination.mkdir(exist_ok=True)
                    stats = {"documents": 0, "chunks": 0, "input_ids": 0, "positions": 0, "boundaries": 0, "patches": 0, "patch_slots": 0, "reused_chunks": 0, "same_shape_replays": 0}
                    report["splits"][split] = stats
                    records = []
                    with source.open() as stream:
                        for document_index, line in enumerate(stream):
                            document = json.loads(line)
                            stats["documents"] += 1
                            for chunk_index, (offset, token_ids) in enumerate(chunk_inputs(document["text"])):
                                path = destination / f"{document_index:06d}-{chunk_index:04d}.npz"
                                if path.exists():
                                    entropy, labels = verify_cached(path, token_ids, contract_hash)
                                    stats["reused_chunks"] += 1
                                else:
                                    entropy, labels = evaluate(token_ids)
                                    temporary = path.with_suffix(".partial.npz")
                                    with temporary.open("xb") as archive:
                                        np.savez_compressed(archive, input_ids=token_ids, entropy=entropy, labels=labels, contract_sha256=contract_hash)
                                    temporary.rename(path)
                                if not np.array_equal(labels[2:], entropy[2:] > effective_threshold):
                                    raise ValueError("Cached labels no longer match entropy/threshold")
                                if document_index == 0 and chunk_index == 0:
                                    repeated_entropy, repeated_labels = evaluate(token_ids)
                                    if not np.array_equal(entropy, repeated_entropy) or not np.array_equal(labels, repeated_labels):
                                        raise ValueError("Same-input label replay mismatch")
                                    verify_cached(path, token_ids, contract_hash)
                                    stats["same_shape_replays"] += 1
                                if split == "validation" and document_index < 3 and chunk_index == 0:
                                    for length in sorted({64, 128, 256, len(token_ids)}):
                                        if length > len(token_ids):
                                            continue
                                        prefix_entropy, prefix_labels = evaluate(token_ids[:length])
                                        report["prefix_diagnostics"].append({
                                            "document_id": document["document_id"], "prefix_input_ids": length,
                                            "full_entropy": float(entropy[length]), "prefix_entropy": float(prefix_entropy[-1]),
                                            "full_label": bool(labels[length]), "prefix_label": bool(prefix_labels[-1]),
                                        })
                                records.append({"file": str(path.relative_to(labels_root)), "file_sha256": file_hash(path), "document_id": document["document_id"], "text_sha256": document["text_sha256"], "byte_offset": offset, "byte_length": len(token_ids) - 1})
                                stats["chunks"] += 1
                                stats["input_ids"] += len(token_ids)
                                stats["positions"] += len(token_ids) - 1
                                stats["boundaries"] += int(labels[2:].sum())
                                stats["patches"] += int(labels.sum())
                                stats["patch_slots"] += len(labels)
                                if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > budgets["peak_host_ram_gib"] * 2**30:
                                    raise RuntimeError("Host memory budget exceeded")
                                if torch.cuda.max_memory_reserved() > budgets["peak_gpu_memory_gib"] * 2**30:
                                    raise RuntimeError("GPU memory budget exceeded")
                                if time.perf_counter() - started + background["elapsed_seconds"] > budgets["maximum_initial_build_and_label_seconds"]:
                                    raise RuntimeError("Combined build and label budget exceeded")
                            if stats["documents"] % 100 == 0:
                                print(json.dumps({"split": split, **stats}), flush=True)
                    manifest_path = labels_root / f"{split}_manifest.json"
                    manifest_payload = {"contract_sha256": contract_hash, "source_sha256": file_hash(source), "chunks": records}
                    if manifest_path.exists():
                        if json.loads(manifest_path.read_text()) != manifest_payload:
                            raise ValueError("Existing manifest differs from regenerated records")
                    else:
                        with manifest_path.open("x") as stream:
                            json.dump(manifest_payload, stream)
                    stats["manifest_sha256"] = file_hash(manifest_path)
                    stats["teacher_mean_patch_length"] = stats["patch_slots"] / stats["patches"]
            report.update(status="generated", effective_threshold=effective_threshold, peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved())
        except Exception as error:
            report.update(status="failed", error_type=type(error).__name__, error=str(error))
        finally:
            report["elapsed_seconds"] = time.perf_counter() - started
            report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            json.dump(report, output, indent=2)
            output.write("\n")
    print(json.dumps({"status": report["status"], "splits": report["splits"], "error": report.get("error")}), flush=True)
    return int(report["status"] != "generated")


if __name__ == "__main__":
    raise SystemExit(main())