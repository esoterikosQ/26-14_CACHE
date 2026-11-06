"""Opt-in immutable LMDB background counts; online counts remain in memory."""

from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import resource
import shutil
import struct
import sys
import time
from types import MappingProxyType

import lmdb

from .count_patcher import CountConfig, checked_id


_FORMAT = "phdq_count_lmdb_v1"
_METADATA = b"\x00metadata"
_ENTRY = struct.Struct("<HQ")


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode(value):
    if value is None:
        return {}, 0
    if len(value) % _ENTRY.size:
        raise ValueError("Invalid LMDB count row")
    row = dict(_ENTRY.iter_unpack(value))
    if len(row) * _ENTRY.size != len(value) or any(count == 0 for count in row.values()):
        raise ValueError("Invalid LMDB count entries")
    return row, sum(row.values())


class LMDBCountTable:
    def __init__(self, path, *, cache_size=4096, allow_partial=False):
        if type(cache_size) is not int or cache_size < 0:
            raise ValueError("cache_size must be a nonnegative integer")
        self.path = Path(path).resolve()
        self._environment = lmdb.open(str(self.path), readonly=True, create=False, readahead=False)
        self._transaction = self._environment.begin()
        try:
            payload = self._transaction.get(_METADATA)
            self.metadata = json.loads(payload) if payload is not None else {}
            if self.metadata.get("format") != _FORMAT or self.metadata.get("status") != "complete":
                raise ValueError("LMDB background is incomplete or has an unknown format")
            if not self.metadata.get("complete_source") and not allow_partial:
                raise ValueError("Partial LMDB backgrounds require explicit allow_partial=True")
            self.config = CountConfig(**self.metadata["config"])
            self._frozen = True
            self._cached_lookup = lru_cache(maxsize=cache_size)(self._read)
        except BaseException:
            self._transaction.abort()
            self._environment.close()
            raise

    def _read(self, context):
        row, total = _decode(self._transaction.get(b"\x01" + context))
        return MappingProxyType(row), total

    def lookup(self, context):
        if self._transaction is None:
            raise ValueError("LMDB background is closed")
        return self._cached_lookup(context)

    def cache_info(self):
        return self._cached_lookup.cache_info()

    def to_dict(self):
        raise TypeError("LMDB backgrounds cannot be embedded in state_dict; reopen the immutable database instead")

    def close(self):
        if self._transaction is not None:
            self._cached_lookup.cache_clear()
            self._transaction.abort()
            self._transaction = None
            self._environment.close()

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()


def _resume_position(saved, expected, selected):
    identity = ("format", "config", "source_report_sha256", "source_manifest_sha256",
                "source_blocks", "selected_blocks", "complete_source")
    if saved.get("status") != "building" or any(saved.get(key) != expected[key] for key in identity):
        raise ValueError("Resume source, selection, format or status mismatch")
    completed, rows = saved.get("completed_blocks"), saved.get("input_rows")
    if type(completed) is not int or not 0 <= completed <= len(selected) or type(rows) is not int or rows < 0:
        raise ValueError("Invalid resume checkpoint")
    if saved.get("source_utf8_bytes") != sum(block.get("utf8_bytes", 0) for block in selected[:completed]):
        raise ValueError("Resume completed-byte total mismatch")
    declared = [block.get("contexts") for block in selected[:completed]]
    known_rows = all(type(value) is int and value >= 0 for value in declared)
    if "completed_input_rows" in saved:
        completed_rows = saved["completed_input_rows"]
        current_rows = saved.get("current_block_rows")
        if type(completed_rows) is not int or completed_rows < 0 or type(current_rows) is not int or current_rows < 0:
            raise ValueError("Invalid resume row position")
        if completed_rows + current_rows != rows or (known_rows and sum(declared) != completed_rows):
            raise ValueError("Resume row totals mismatch")
    else:
        if not known_rows:
            raise ValueError("Legacy resume requires source block context counts")
        completed_rows = sum(declared)
        current_rows = rows - completed_rows
    if current_rows < 0 or (completed == len(selected) and current_rows != 0):
        raise ValueError("Invalid resume block position")
    if completed < len(selected) and "contexts" in selected[completed]:
        if current_rows > selected[completed]["contexts"]:
            raise ValueError("Resume position exceeds source block")
    return completed_rows, current_rows


def _copy_parent_background(parent_background, parent_report, selected, config, output,
                            min_free_bytes, max_output_bytes):
    parent_report = Path(parent_report).resolve()
    parent_hash = _file_hash(parent_report)
    report = json.loads(parent_report.read_text())
    blocks = report.get("blocks", [])
    if (report.get("storage") != "document_blocks_v1" or not blocks
            or selected[:len(blocks)] != blocks or report.get("count_config") != asdict(config)):
        raise ValueError("Parent background must be the exact selected block prefix")
    with LMDBCountTable(parent_background) as parent:
        saved = parent.metadata
        if (output.is_relative_to(parent.path) or parent.config != config
                or saved.get("source_report_sha256") != parent_hash
                or saved.get("source_manifest_sha256") != report.get("table_sha256")
                or saved.get("completed_blocks") != len(blocks)
                or saved.get("selected_blocks") != len(blocks)
                or saved.get("source_blocks") != len(blocks)
                or saved.get("current_block_rows", 0) != 0
                or saved.get("completed_input_rows", saved["input_rows"]) != saved["input_rows"]
                or saved.get("source_utf8_bytes") != sum(block.get("utf8_bytes", 0) for block in blocks)):
            raise ValueError("Parent LMDB identity or completion changed")
        if all("contexts" in block for block in blocks) and saved["input_rows"] != sum(block["contexts"] for block in blocks):
            raise ValueError("Parent LMDB row totals changed")
        data = parent.path / "data.mdb"
        before = data.stat()
        if max_output_bytes is not None and before.st_size > max_output_bytes:
            raise RuntimeError("Parent copy exceeds LMDB output guard")
        if shutil.disk_usage(output).free < min_free_bytes + before.st_size:
            raise RuntimeError("Insufficient disk headroom for parent copy")
        parent._environment.copy(str(output), compact=True)
        after = data.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or _file_hash(parent_report) != parent_hash:
            raise ValueError("Parent changed during LMDB copy")
        return {"completed_blocks": len(blocks), "input_rows": saved["input_rows"],
                "completed_input_rows": saved["input_rows"], "source_utf8_bytes": saved["source_utf8_bytes"],
                "parent_reuse": {"database": str(parent.path), "source_report_sha256": parent_hash,
                                 "completed_blocks": len(blocks), "input_rows": saved["input_rows"]}}


def build_lmdb_background(report_path, output, *, map_size_bytes, batch_rows=10000,
                          min_free_bytes=0, max_output_bytes=None, block_limit=None, progress=None,
                          resume=False, max_rss_bytes=None, parent_background=None, parent_report=None):
    if (parent_background is None) != (parent_report is None) or (resume and parent_background is not None):
        raise ValueError("Parent database and report must be paired on a fresh conversion")
    if type(map_size_bytes) is not int or map_size_bytes <= 0 or type(batch_rows) is not int or batch_rows <= 0:
        raise ValueError("Map size and batch_rows must be positive integers")
    if min_free_bytes < 0 or (max_output_bytes is not None and max_output_bytes <= 0) or (max_rss_bytes is not None and max_rss_bytes <= 0):
        raise ValueError("Invalid storage guard")
    report_path, output = Path(report_path).resolve(), Path(output).resolve()
    source_hash = _file_hash(report_path)
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
    metadata = {
        "format": _FORMAT, "status": "building", "config": asdict(config),
        "source_report_sha256": source_hash, "source_manifest_sha256": report["table_sha256"],
        "source_manifest_encoding": next(name for name, digest in manifests.items() if digest == report["table_sha256"]),
        "source_blocks": len(blocks), "selected_blocks": len(selected),
        "complete_source": len(selected) == len(blocks), "completed_blocks": 0,
        "input_rows": 0, "source_utf8_bytes": 0, "lmdb_version": lmdb.__version__,
        "completed_input_rows": 0, "current_block_rows": 0,
    }
    if resume:
        if not (output / "data.mdb").is_file():
            raise FileNotFoundError("Resume requires an existing LMDB database")
        if (output / "data.mdb").stat().st_size > map_size_bytes:
            raise ValueError("Requested map is smaller than the existing database")
    else:
        output.mkdir()
        if parent_background is not None:
            metadata.update(_copy_parent_background(parent_background, parent_report, selected, config, output,
                                                    min_free_bytes, max_output_bytes))
    environment = None
    transaction = None
    started = time.perf_counter()

    def check_storage():
        used = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
        if shutil.disk_usage(output).free < min_free_bytes:
            raise RuntimeError("LMDB minimum free disk guard reached")
        if max_output_bytes is not None and used > max_output_bytes:
            raise RuntimeError("LMDB maximum output guard reached")
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        if max_rss_bytes is not None and peak_rss > max_rss_bytes:
            raise RuntimeError("LMDB peak RSS guard reached")
        return used

    def checkpoint():
        nonlocal transaction
        metadata["session_elapsed_seconds"] = time.perf_counter() - started
        transaction.put(_METADATA, json.dumps(metadata, sort_keys=True).encode())
        transaction.commit()
        transaction = None
        used = check_storage()
        if progress is not None:
            progress({**metadata, "output_bytes": used, "elapsed_seconds": time.perf_counter() - started})
        transaction = environment.begin(write=True)

    try:
        check_storage()
        environment = lmdb.open(str(output), map_size=map_size_bytes, readahead=False, create=not resume)
        if 1 + 2 * config.max_context > environment.max_key_size():
            raise ValueError("Context exceeds LMDB maximum key size")
        transaction = environment.begin(write=True)
        if resume:
            payload = transaction.get(_METADATA)
            saved = json.loads(payload) if payload is not None else {}
            completed_rows, current_rows = _resume_position(saved, metadata, selected)
            metadata = saved
            metadata["completed_input_rows"] = completed_rows
            metadata["current_block_rows"] = current_rows
            history = list(metadata.get("resume_history", []))
            history.append({
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "completed_blocks": metadata["completed_blocks"], "input_rows": metadata["input_rows"],
                "current_block_rows": current_rows, "previous_map_size_bytes": metadata.get("map_size_bytes"),
                "map_size_bytes": environment.info()["map_size"],
                "previous_session_elapsed_seconds": metadata.get("session_elapsed_seconds"),
                "backend_code_sha256": _file_hash(__file__),
            })
            metadata["resume_history"] = history
        metadata["map_size_bytes"] = environment.info()["map_size"]
        metadata["backend_code_sha256"] = _file_hash(__file__)
        metadata["limits"] = {"min_free_bytes": min_free_bytes, "max_output_bytes": max_output_bytes,
                              "max_rss_bytes": max_rss_bytes}
        first_block = metadata["completed_blocks"]
        skip_rows = metadata["current_block_rows"]
        transaction.put(_METADATA, json.dumps(metadata, sort_keys=True).encode())
        transaction.commit()
        transaction = environment.begin(write=True)
        if progress is not None:
            progress({**metadata, "stage": "resumed" if resume else "started",
                      "output_bytes": check_storage(), "elapsed_seconds": time.perf_counter() - started})
        for block_index, block in enumerate(selected):
            path = Path(block["table_path"])
            if _file_hash(path) != block["table_sha256"]:
                raise ValueError("Background block hash mismatch")
            if block_index < first_block:
                continue
            compression = block.get("compression", "none")
            if compression not in ("none", "gzip"):
                raise ValueError("Unsupported background compression")
            opener = gzip.open if compression == "gzip" else open
            with opener(path, "rt") as stream:
                if json.loads(next(stream)) != {"version": 1, "config": asdict(config)}:
                    raise ValueError("Background block configuration mismatch")
                row_index = 0
                for row_index, line in enumerate(stream, 1):
                    if block_index == first_block and row_index <= skip_rows:
                        continue
                    encoded, entries = json.loads(line)
                    context = bytes.fromhex(encoded)
                    if len(context) % 2 or len(context) > 2 * config.max_context:
                        raise ValueError("Invalid background context")
                    for offset in range(0, len(context), 2):
                        if checked_id(int.from_bytes(context[offset:offset + 2], "little"), config) == config.eos_id:
                            raise ValueError("Context cannot cross EOS")
                    key = b"\x01" + context
                    row, _ = _decode(transaction.get(key))
                    seen = set()
                    for token_id, count in entries:
                        token_id = checked_id(token_id, config)
                        if type(count) is not int or count <= 0 or token_id in seen:
                            raise ValueError("Invalid serialized count")
                        seen.add(token_id)
                        row[token_id] = row.get(token_id, 0) + count
                    packed = b"".join(_ENTRY.pack(token_id, count) for token_id, count in row.items())
                    transaction.put(key, packed)
                    metadata["input_rows"] += 1
                    metadata["current_block_rows"] = row_index
                    if metadata["input_rows"] % batch_rows == 0:
                        checkpoint()
                if (block_index == first_block and row_index < skip_rows) or ("contexts" in block and row_index != block["contexts"]):
                    raise ValueError("Source block row count mismatch")
            metadata["completed_input_rows"] += row_index
            metadata["current_block_rows"] = 0
            metadata["completed_blocks"] += 1
            metadata["source_utf8_bytes"] += block.get("utf8_bytes", 0)
            checkpoint()
        if _file_hash(report_path) != source_hash:
            raise ValueError("Source report changed during conversion")
        transaction.abort()
        transaction = None
        environment.sync()
        check_storage()
        transaction = environment.begin(write=True)
        metadata["contexts"] = transaction.stat()["entries"] - 1
        metadata["elapsed_seconds"] = time.perf_counter() - started
        metadata["status"] = "complete"
        transaction.put(_METADATA, json.dumps(metadata, sort_keys=True).encode())
        transaction.commit()
        transaction = None
        environment.sync()
        used = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
        return {**metadata, "output": str(output), "output_bytes": used}
    finally:
        if transaction is not None:
            transaction.abort()
        if environment is not None:
            environment.close()