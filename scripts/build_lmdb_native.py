"""Native (C++) builder of phdq_count_lmdb_v1 backgrounds from document count blocks.

Produces the same keys and per-context counts as phdq_blt_cache.lmdb_counts.build_lmdb_background; token
entries inside a row are stored in ascending token order (lookups are order-insensitive).
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

import lmdb

from phdq_blt_cache.count_patcher import CountConfig

SOURCE = Path(__file__).resolve().parent / "native" / "lmdb_build.cpp"
FORMAT = "phdq_count_lmdb_v1"
METADATA = b"\x00metadata"
# Shard key, slot, head and entry storage per unique context, with vector growth slack.
BYTES_PER_KEY = 17 + 16 + 4
BYTES_PER_ENTRY = 16
GROWTH = 1.6


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_library(directory):
    directory.mkdir(parents=True, exist_ok=False)
    library = directory / "lmdb_build.so"
    subprocess.run(["c++", "-std=c++17", "-O3", "-shared", "-fPIC", "-pthread", str(SOURCE), "-o", str(library),
                    "-lz", "-l:liblmdb.so.0"], check=True)
    native = ctypes.CDLL(str(library))
    u64, ptr, text = ctypes.c_uint64, ctypes.c_void_p, ctypes.c_char_p
    out = ctypes.POINTER(ctypes.c_uint64)
    native.bl_new.restype = ptr
    native.bl_new.argtypes = [text, u64, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, text, u64]
    native.bl_free.argtypes = [ptr]
    native.bl_sample.argtypes = [ptr, ctypes.c_uint32, ptr, out, out, ptr, u64]
    native.bl_plan.argtypes = [ptr, ctypes.c_uint32, ptr, u64]
    native.bl_write.argtypes = [ptr, text, u64, u64, u64, u64, text, u64, out, out, ptr, u64]
    return native, library


def check(status, error):
    if status:
        raise ValueError(error.value.decode("utf-8", "replace"))


def build(report_path, output, *, map_size_bytes, threads, memory_budget_bytes, max_rss_bytes, min_free_bytes,
          max_output_bytes, block_limit=None, passes=None, sample_modulus=1024, progress=print):
    started = time.perf_counter()
    report_path, output = Path(report_path).resolve(), Path(output).resolve()
    if output.exists() or output.with_suffix(".report.json").exists():
        raise FileExistsError("LMDB output or report already exists")
    source_hash = file_hash(report_path)
    report = json.loads(report_path.read_text())
    if report.get("storage") != "document_blocks_v1":
        raise ValueError("Expected a document_blocks_v1 background report")
    blocks = report["blocks"]
    manifests = {
        "json_compact": hashlib.sha256(json.dumps(blocks, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "json_default": hashlib.sha256(json.dumps(blocks, sort_keys=True).encode()).hexdigest(),
    }
    if report["table_sha256"] not in manifests.values():
        raise ValueError("Background block manifest hash mismatch")
    config = CountConfig(**report["count_config"])
    if block_limit is not None and (type(block_limit) is not int or not 1 <= block_limit <= len(blocks)):
        raise ValueError("Invalid block_limit")
    selected = blocks if block_limit is None else blocks[:block_limit]
    if any(block.get("compression", "none") != "gzip" for block in selected):
        raise ValueError("Native builder reads gzip blocks only")
    with ThreadPoolExecutor(threads) as pool:
        hashes = list(pool.map(lambda block: file_hash(block["table_path"]), selected))
    if any(digest != block["table_sha256"] for digest, block in zip(hashes, selected)):
        raise ValueError("Background block hash mismatch")
    progress({"stage": "verified", "blocks": len(selected), "elapsed_seconds": time.perf_counter() - started})

    output.mkdir(parents=True)
    native, library = build_library(output.parent / (output.name + ".native"))
    header = json.dumps({"version": 1, "config": asdict(config)}).encode()
    paths = "\n".join(block["table_path"] for block in selected).encode()
    handle = native.bl_new(header, len(header), config.vocab_size, config.pad_id, config.eos_id, config.max_context,
                           threads, paths, len(selected))
    error = ctypes.create_string_buffer(1024)
    try:
        rows = (ctypes.c_uint64 * len(selected))()
        sample_keys, sample_entries = ctypes.c_uint64(), ctypes.c_uint64()
        check(native.bl_sample(handle, sample_modulus, rows, ctypes.byref(sample_keys), ctypes.byref(sample_entries),
                               error, len(error)), error)
        for count, block in zip(rows, selected):
            if "contexts" in block and count != block["contexts"]:
                raise ValueError("Source block row count mismatch")
        estimated_keys = sample_keys.value * sample_modulus
        entries_per_key = sample_entries.value / max(1, sample_keys.value)
        estimated_bytes = estimated_keys * (BYTES_PER_KEY + BYTES_PER_ENTRY * entries_per_key) * GROWTH
        planned = passes or max(1, math.ceil(estimated_bytes / memory_budget_bytes))
        progress({"stage": "sampled", "input_rows": sum(rows), "estimated_contexts": estimated_keys,
                  "entries_per_context": entries_per_key, "estimated_aggregate_bytes": int(estimated_bytes),
                  "passes": planned, "elapsed_seconds": time.perf_counter() - started})
        check(native.bl_plan(handle, planned, error, len(error)), error)
        metadata = {
            "format": FORMAT, "status": "building", "config": asdict(config),
            "source_report_sha256": source_hash, "source_manifest_sha256": report["table_sha256"],
            "source_manifest_encoding": next(name for name, digest in manifests.items() if digest == report["table_sha256"]),
            "source_blocks": len(blocks), "selected_blocks": len(selected), "complete_source": len(selected) == len(blocks),
            "completed_blocks": 0, "input_rows": 0, "source_utf8_bytes": 0, "lmdb_version": lmdb.__version__,
            "completed_input_rows": 0, "current_block_rows": 0,
        }
        payload = json.dumps(metadata, sort_keys=True).encode()
        contexts, input_rows = ctypes.c_uint64(), ctypes.c_uint64()
        check(native.bl_write(handle, str(output).encode(), map_size_bytes, min_free_bytes, max_output_bytes, max_rss_bytes,
                              payload, len(payload), ctypes.byref(contexts), ctypes.byref(input_rows), error, len(error)), error)
    finally:
        native.bl_free(handle)
    if input_rows.value != sum(rows):
        raise ValueError("Native passes did not cover every input row exactly once")
    if file_hash(report_path) != source_hash:
        raise ValueError("Source report changed during conversion")
    code = {"python": file_hash(Path(__file__)), "cpp": file_hash(SOURCE), "library": file_hash(library)}
    environment = lmdb.open(str(output), map_size=map_size_bytes, readahead=False)
    try:
        with environment.begin(write=True) as transaction:
            entries = transaction.stat()["entries"] - 1
            if entries != contexts.value:
                raise ValueError("Written context count differs from LMDB entries")
            metadata.update(
                status="complete", completed_blocks=len(selected), input_rows=input_rows.value,
                completed_input_rows=input_rows.value, source_utf8_bytes=sum(block.get("utf8_bytes", 0) for block in selected),
                contexts=entries, map_size_bytes=environment.info()["map_size"],
                backend_code_sha256=code["python"], elapsed_seconds=time.perf_counter() - started,
                session_elapsed_seconds=time.perf_counter() - started,
                limits={"min_free_bytes": min_free_bytes, "max_output_bytes": max_output_bytes, "max_rss_bytes": max_rss_bytes},
                builder={"name": "native_range_passes_v1", "code_sha256": code, "threads": threads, "passes": planned,
                         "sample_modulus": sample_modulus, "row_entry_order": "ascending token id"})
            transaction.put(METADATA, json.dumps(metadata, sort_keys=True).encode())
        environment.sync(True)
    finally:
        environment.close()
    shutil.rmtree(library.parent)
    result = {**metadata, "data_bytes": (output / "data.mdb").stat().st_size}
    with output.with_suffix(".report.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--map-size-gib", type=int, required=True)
    parser.add_argument("--threads", type=int, default=os.cpu_count())
    parser.add_argument("--memory-budget-gib", type=int, default=24)
    parser.add_argument("--rss-limit-gib", type=int, default=48)
    parser.add_argument("--min-free-gib", type=int, default=100)
    parser.add_argument("--max-output-gib", type=int, default=100)
    parser.add_argument("--passes", type=int)
    parser.add_argument("--sample-modulus", type=int, default=1024)
    parser.add_argument("--block-limit", type=int)
    arguments = parser.parse_args(argv)
    gib = 1024 ** 3
    result = build(arguments.report, arguments.output, map_size_bytes=arguments.map_size_gib * gib,
                   threads=arguments.threads, memory_budget_bytes=arguments.memory_budget_gib * gib,
                   max_rss_bytes=arguments.rss_limit_gib * gib, min_free_bytes=arguments.min_free_gib * gib,
                   max_output_bytes=arguments.max_output_gib * gib, block_limit=arguments.block_limit,
                   passes=arguments.passes, sample_modulus=arguments.sample_modulus,
                   progress=lambda value: print(json.dumps(value), flush=True))
    print(json.dumps({key: result[key] for key in ("status", "contexts", "input_rows", "data_bytes", "elapsed_seconds")}), flush=True)


if __name__ == "__main__":
    main()
