"""Explicit opt-in C++ count block builder and required-context projector."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
import ctypes
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from phdq_blt_cache.count_patcher import CountTable
from scripts.benchmark_count_patcher import file_hash

BOS_ID = 1
BYTE_OFFSET = 4
ERRORS = {
    -1: "invalid argument", -2: "invalid token or count", -3: "open failed or output exists",
    -4: "write failed", -5: "out of memory", -6: "count overflow", -7: "read failed",
    -8: "block header mismatch", -9: "block parse failed", -10: "invalid projector state",
}


def build_native_counts(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    library = directory / ("count_blocks.dylib" if sys.platform == "darwin" else "count_blocks.so")
    if library.exists():
        raise FileExistsError(library)
    source = Path(__file__).parent / "native" / "count_blocks.cpp"
    subprocess.run(["c++", "-std=c++17", "-O3", "-shared", "-fPIC", str(source), "-o", str(library), "-lz"], check=True)
    return library


def table_header(config):
    return json.dumps({"version": 1, "config": asdict(config)})


def _check(status, subject):
    if status != 0:
        raise ValueError(f"Native count kernel failed for {subject}: {ERRORS.get(status, status)}")


@dataclass
class Projection:
    contexts: list
    row_lengths: np.ndarray
    tokens: np.ndarray
    counts: np.ndarray

    def to_table(self, config):
        table = CountTable(config)
        tokens = self.tokens.tolist()
        counts = self.counts.tolist()
        offset = 0
        for context, length in zip(self.contexts, self.row_lengths.tolist()):
            stop = offset + length
            row_counts = counts[offset:stop]
            table._rows[context] = dict(zip(tokens[offset:stop], row_counts))
            table._totals[context] = sum(row_counts)
            offset = stop
        return table.freeze()


def _packed(contexts):
    lengths = np.fromiter((len(context) for context in contexts), dtype=np.uint32, count=len(contexts))
    return b"".join(contexts), lengths


class NativeCounts:
    def __init__(self, library):
        self.library_path = Path(library)
        self.library = ctypes.CDLL(str(library))
        library = self.library
        pointer = ctypes.c_void_p
        library.blt_count_block.argtypes = [
            ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint64,
            ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]
        library.blt_count_block.restype = ctypes.c_int
        library.blt_projector_new.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint64,
                                              ctypes.c_int, ctypes.c_char_p, ctypes.c_uint64]
        library.blt_projector_new.restype = pointer
        library.blt_projector_free.argtypes = [pointer]
        library.blt_projector_free.restype = None
        library.blt_projector_parse.argtypes = [pointer, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        library.blt_projector_parse.restype = pointer
        library.blt_partial_free.argtypes = [pointer]
        library.blt_partial_free.restype = None
        library.blt_projector_merge.argtypes = [pointer, pointer]
        library.blt_projector_merge.restype = ctypes.c_int
        library.blt_projector_seed.argtypes = [
            pointer, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint64,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64)]
        library.blt_projector_seed.restype = ctypes.c_int
        library.blt_projector_sizes.argtypes = [pointer, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)]
        library.blt_projector_sizes.restype = None
        library.blt_projector_export.argtypes = [pointer, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
                                                 ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint64)]
        library.blt_projector_export.restype = None

    def build_block(self, texts, config, path, compress_level):
        lengths = np.fromiter((len(text) for text in texts), dtype=np.uint64, count=len(texts))
        header = (table_header(config) + "\n").encode()
        stats = (ctypes.c_uint64 * 3)()
        status = self.library.blt_count_block(
            b"".join(texts), lengths.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), len(texts),
            config.max_context, config.vocab_size, config.eos_id, config.pad_id, BOS_ID, BYTE_OFFSET,
            header, len(header), str(path).encode(), compress_level, stats)
        _check(status, path)
        return {"contexts": int(stats[0]), "edges": int(stats[1]), "uncompressed_table_bytes": int(stats[2])}

    def project(self, paths, required, config, *, workers, seed=None, verify=None, progress=None):
        if type(workers) is not int or workers < 1:
            raise ValueError("workers must be a positive integer")
        if config.max_context > 8:
            raise ValueError("Native projection supports max_context <= 8")
        # Longer or odd-length contexts cannot occur in K<=8 blocks, matching Python's no-match result.
        required = sorted(context for context in required if len(context) <= 16 and len(context) % 2 == 0)
        data, lengths = _packed(required)
        header = table_header(config).encode()
        handle = self.library.blt_projector_new(data, lengths.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                                                len(required), config.vocab_size, header, len(header))
        if not handle:
            raise ValueError("Invalid or duplicate required contexts for native projection")
        pending = deque()

        def parse(path):
            if verify is not None:
                verify(path)
            status = ctypes.c_int()
            partial = self.library.blt_projector_parse(handle, str(path).encode(), ctypes.byref(status))
            _check(status.value, path)
            return partial

        def merge():
            path, future = pending.popleft()
            partial = future.result()
            try:
                _check(self.library.blt_projector_merge(handle, partial), path)
            finally:
                self.library.blt_partial_free(partial)
            if progress is not None:
                contexts, edges = ctypes.c_uint64(), ctypes.c_uint64()
                self.library.blt_projector_sizes(handle, ctypes.byref(contexts), ctypes.byref(edges))
                progress("Background block merged", {"path": str(path), "loaded_contexts": contexts.value})

        try:
            skipped = 0
            if seed is not None:
                seed_data, seed_lengths = _packed(seed.contexts)
                skipped_value = ctypes.c_uint64()
                row_lengths = np.ascontiguousarray(seed.row_lengths, dtype=np.uint32)
                tokens = np.ascontiguousarray(seed.tokens, dtype=np.uint16)
                counts = np.ascontiguousarray(seed.counts, dtype=np.uint64)
                _check(self.library.blt_projector_seed(
                    handle, seed_data, seed_lengths.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)), len(seed.contexts),
                    row_lengths.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                    tokens.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),
                    counts.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), ctypes.byref(skipped_value)), "seed projection")
                skipped = skipped_value.value
            with ThreadPoolExecutor(workers) as pool:
                try:
                    for path in paths:
                        pending.append((path, pool.submit(parse, path)))
                        while len(pending) > workers:
                            merge()
                    while pending:
                        merge()
                finally:
                    while pending:
                        _, future = pending.popleft()
                        if future.exception() is None:
                            self.library.blt_partial_free(future.result())
            contexts, edges = ctypes.c_uint64(), ctypes.c_uint64()
            self.library.blt_projector_sizes(handle, ctypes.byref(contexts), ctypes.byref(edges))
            order = np.empty(contexts.value, dtype=np.uint32)
            row_lengths = np.empty(contexts.value, dtype=np.uint32)
            tokens = np.empty(edges.value, dtype=np.uint16)
            counts = np.empty(edges.value, dtype=np.uint64)
            self.library.blt_projector_export(
                handle, order.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                row_lengths.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                tokens.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),
                counts.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)))
        finally:
            self.library.blt_projector_free(handle)
        return Projection([required[index] for index in order.tolist()], row_lengths, tokens, counts), skipped


def required_sha256(required):
    data, lengths = _packed(sorted(required))
    return hashlib.sha256(lengths.tobytes() + data).hexdigest()


def save_projection(path, projection, required, metadata):
    path = Path(path)
    required = sorted(required)
    data, lengths = _packed(projection.contexts)
    required_data, required_lengths = _packed(required)
    with path.open("xb") as stream:
        np.savez(stream, context_bytes=np.frombuffer(data, dtype=np.uint8), context_lengths=lengths,
                 row_lengths=projection.row_lengths, tokens=projection.tokens, counts=projection.counts,
                 required_bytes=np.frombuffer(required_data, dtype=np.uint8), required_lengths=required_lengths)
    report = {
        **metadata, "format": "count_projection_v1", "arrays_path": path.name, "arrays_sha256": file_hash(path),
        "required_contexts": len(required), "required_sha256": required_sha256(required),
        "contexts": len(projection.contexts), "edges": int(projection.tokens.size),
    }
    report_path = path.with_suffix(".json")
    with report_path.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report_path, report


def _unpack(data, lengths):
    contexts, offset = [], 0
    data = data.tobytes()
    for length in lengths.tolist():
        contexts.append(data[offset:offset + length])
        offset += length
    if offset != len(data):
        raise ValueError("Projection context bytes are inconsistent")
    return contexts


def load_projection(report_path, expected_sha256):
    report_path = Path(report_path)
    if file_hash(report_path) != expected_sha256:
        raise ValueError("Pinned projection report changed")
    report = json.loads(report_path.read_text())
    arrays_path = report_path.parent / report["arrays_path"]
    if report.get("format") != "count_projection_v1" or file_hash(arrays_path) != report["arrays_sha256"]:
        raise ValueError("Projection arrays changed")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        projection = Projection(_unpack(arrays["context_bytes"], arrays["context_lengths"]), arrays["row_lengths"],
                                arrays["tokens"], arrays["counts"])
        required = _unpack(arrays["required_bytes"], arrays["required_lengths"])
    if (len(projection.contexts) != report["contexts"] or int(projection.tokens.size) != report["edges"]
            or int(projection.row_lengths.sum()) != report["edges"] or required_sha256(required) != report["required_sha256"]):
        raise ValueError("Projection contents do not match their report")
    return projection, set(required), report
