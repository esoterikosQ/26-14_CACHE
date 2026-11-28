"""Disk-backed, order-preserving equivalent of the pilot deduplication policy."""

from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import zlib

import numpy as np
from datasketch import MinHash, MinHashLSH
from datasketch.hashfunc import sha1_hash32

from scripts.native_minhash import NativeMinHash
from scripts.prepare_english_data import length_band

BANDS = ("short", "medium", "long")


class SignedDocument(dict):
    """Document dict carrying a precomputed normalization and MinHash; serializes as the plain dict."""

    __slots__ = ("prepared", "hashvalues")


def prepare_text(document):
    normalized = " ".join(document["text"].casefold().split())
    return normalized, hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Signer:
    """Native batch MinHash equal to DiskDeduplicator.signature for the same seed."""

    def __init__(self, seed, library):
        self.template = MinHash(num_perm=128, seed=seed)
        self.native = library if isinstance(library, NativeMinHash) else NativeMinHash(library)

    def sign(self, documents, threads):
        signed = [SignedDocument(document) for document in documents]
        for document in signed:
            document.prepared = prepare_text(document)
        values = self.native.signatures([document.prepared[0].encode("utf-8") for document in signed],
                                        *self.template.permutations, scheme=getattr(self.template, "scheme", "legacy"),
                                        threads=threads)
        for document, row in zip(signed, values):
            document.hashvalues = row.astype(self.template.hashvalues.dtype, copy=False)
        return signed


class DiskDeduplicator:
    def __init__(self, path, seed, library, *, compress_payload=False, base=None, fast=False):
        if type(compress_payload) is not bool or type(fast) is not bool:
            raise ValueError("compress_payload and fast must be explicit booleans")
        if Path(path).exists():
            raise FileExistsError(path)
        self.compress_payload = compress_payload
        self.connection = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=rwc", uri=True)
        self.connection.execute("PRAGMA cache_size=-32768")
        self.connection.execute("PRAGMA temp_store=FILE")
        if fast:
            # Disposable scratch: durability is unnecessary; logical contents are unchanged.
            self.connection.execute("PRAGMA journal_mode=OFF").fetchall()
            self.connection.execute("PRAGMA synchronous=OFF")
        self.schemas = ("main",)
        if base is not None:
            self.connection.execute("ATTACH DATABASE ? AS base", (f"{Path(base).resolve().as_uri()}?mode=ro",))
            self.schemas = ("base", "main")
        self.connection.executescript("""
            CREATE TABLE documents (
                identifier INTEGER PRIMARY KEY, digest TEXT UNIQUE,
                url TEXT UNIQUE, signature BLOB NOT NULL, payload TEXT NOT NULL,
                band TEXT NOT NULL, protected INTEGER NOT NULL);
            CREATE TABLE buckets (
                band INTEGER NOT NULL, value BLOB NOT NULL, identifier INTEGER NOT NULL);
            CREATE INDEX bucket_lookup ON buckets(band, value);
        """)
        self.seed = seed
        self.template = MinHash(num_perm=128, seed=seed)
        self.layout = MinHashLSH(threshold=0.8, num_perm=128)
        self.native = NativeMinHash(library)
        self.rejected = Counter()
        self.accepted = 0

    def close(self):
        self.connection.close()

    def payload_text(self, payload):
        return zlib.decompress(payload).decode("utf-8") if self.compress_payload else payload

    def signature(self, normalized):
        words = normalized.split()
        shingles = {" ".join(words[offset:offset + 5]).encode("utf-8")
                    for offset in range(max(1, len(words) - 4))}
        hashes = [sha1_hash32(value) for value in sorted(shingles)]
        scheme = getattr(self.template, "scheme", "legacy")
        values = self.native.values(hashes, *self.template.permutations, scheme=scheme)
        options = {"scheme": scheme} if hasattr(self.template, "scheme") else {}
        return MinHash(num_perm=128, seed=self.seed, hashvalues=np.asarray(values, dtype=self.template.hashvalues.dtype),
                   permutations=self.template.permutations, **options)

    def add(self, document, protected=False):
        normalized, digest = (getattr(document, "prepared", None) or prepare_text(document))
        url = document.get("url") or None
        if any(self.connection.execute(f"SELECT 1 FROM {schema}.documents WHERE digest=? OR url=? LIMIT 1", (digest, url)).fetchone()
               for schema in self.schemas):
            self.rejected["exact_text_or_url"] += 1
            return False
        hashvalues = getattr(document, "hashvalues", None)
        if hashvalues is None:
            hashvalues = self.signature(normalized).hashvalues
        keys = [(band, self.layout._H(hashvalues[start:end]))
                for band, (start, end) in enumerate(self.layout.hashranges)]
        for band, value in keys:
            for schema in self.schemas:
                rows = self.connection.execute(
                    f"SELECT {schema}.documents.signature FROM {schema}.buckets JOIN {schema}.documents USING(identifier) "
                    f"WHERE {schema}.buckets.band=? AND {schema}.buckets.value=?", (band, value))
                for (stored,) in rows:
                    if np.count_nonzero(hashvalues == np.frombuffer(stored, dtype=self.template.hashvalues.dtype)) / 128 >= 0.8:
                        self.rejected["near_duplicate"] += 1
                        return False
        payload = json.dumps(document, ensure_ascii=False)
        if self.compress_payload:
            payload = zlib.compress(payload.encode("utf-8"), level=1)
        cursor = self.connection.execute(
            "INSERT INTO main.documents(digest,url,signature,payload,band,protected) VALUES(?,?,?,?,?,?)",
            (digest, url, hashvalues.tobytes(), payload, length_band(document), int(protected)))
        self.connection.executemany("INSERT INTO main.buckets VALUES(?,?,?)",
                                    [(band, value, cursor.lastrowid) for band, value in keys])
        self.accepted += 1
        if self.accepted % 1000 == 0:
            self.connection.commit()
        return cursor.lastrowid

    def sign(self, documents, threads):
        return Signer.sign(self, documents, threads)


def _batched(documents, size):
    batch = []
    for document in documents:
        batch.append(document)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _add_protected(index, existing, check, threads):
    size = protected_background = 0
    bands = Counter()
    for split, documents in existing.items():
        position = 0
        batches = _batched(documents, 4096) if threads else ([document] for document in documents)
        for batch in batches:
            for document in (index.sign(batch, threads) if threads else batch):
                if not index.add(document, protected=True):
                    raise ValueError("Existing splits are not disjoint under the declared deduplication policy")
                if split == "background":
                    size += len(document["text"].encode("utf-8"))
                    protected_background += 1
                    bands[length_band(document)] += 1
                if position % 1000 == 0:
                    check()
                position += 1
    return size, protected_background, bands


def build_protected_index(existing, seed, database, library, check=lambda: None, *, compress_payload=False, threads=1):
    """Build the reusable protected-split index exactly as expand_to_disk's first phase would."""
    if next(iter(existing), None) != "background":
        raise ValueError("Protected background must precede other splits")
    if type(threads) is not int or threads < 1:
        raise ValueError("threads must be a positive integer")
    index = DiskDeduplicator(database, seed, library, compress_payload=compress_payload, fast=True)
    try:
        size, protected_background, bands = _add_protected(index, existing, check, threads)
        index.connection.commit()
        documents = index.connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    finally:
        index.close()
    return {"background_utf8_bytes": size, "protected_background": protected_background, "length_bands": dict(bands),
            "protected_documents": documents, "compress_payload": compress_payload, "seed": seed}


def expand_to_disk(existing, candidates, target, seed, database, library, output, check=lambda: None, *, compress_payload=False,
                   on_candidate_retained=None, protected_index=None, threads=0, shards=None):
    if protected_index is None and next(iter(existing), None) != "background":
        raise ValueError("Protected background must precede other splits")
    if shards is not None and (not isinstance(shards, list) or not shards or len(set(shards)) != len(shards)
                               or not all(isinstance(shard, str) for shard in shards)):
        raise ValueError("shards must be a nonempty list of unique shard names")
    if on_candidate_retained is not None and not callable(on_candidate_retained):
        raise ValueError("on_candidate_retained must be callable")
    if type(threads) is not int or threads < 0:
        raise ValueError("threads must be a nonnegative integer")
    base = None
    if protected_index is not None:
        base, summary = protected_index
        if summary["compress_payload"] != compress_payload or summary["seed"] != seed:
            raise ValueError("Protected index payload compression or seed differs")
    index = DiskDeduplicator(database, seed, library, compress_payload=compress_payload, base=base, fast=bool(threads))
    size = 0
    protected_background = 0
    bands = Counter()
    candidates_seen = 0
    members = {shard: [] for shard in shards} if shards is not None else None
    try:
        if base is None:
            size, protected_background, bands = _add_protected(index, existing, check, threads)
        else:
            size, protected_background = summary["background_utf8_bytes"], summary["protected_background"]
            bands = Counter(summary["length_bands"])
        if target <= size:
            raise ValueError("Expanded background must exceed the original size")
        for candidates_seen, document in enumerate(candidates, start=1):
            identifier = index.add(document)
            if identifier and members is not None:
                if document.get("shard") not in members:
                    raise ValueError(f"Candidate from an unpinned shard: {document.get('shard')}")
                members[document["shard"]].append(identifier)
            if identifier and on_candidate_retained is not None:
                on_candidate_retained(len(document["text"].encode("utf-8")))
            if candidates_seen % 1000 == 0:
                check()
        index.connection.commit()
        generator = random.Random(seed)
        buckets = []
        for group in (members.values() if members is not None else ()):
            generator.shuffle(group)
            buckets.append(deque(group))
        for band in (BANDS if members is None else ()):
            identifiers = [row[0] for row in index.connection.execute(
                "SELECT identifier FROM main.documents WHERE protected=0 AND band=? ORDER BY identifier", (band,))]
            generator.shuffle(identifiers)
            buckets.append(deque(identifiers))
        documents_written = protected_background
        protected_schema = "base" if base is not None else "main"
        with Path(output).open("x") as stream:
            for (payload,) in index.connection.execute(
                    f"SELECT payload FROM {protected_schema}.documents ORDER BY identifier LIMIT ?", (protected_background,)):
                stream.write(index.payload_text(payload) + "\n")
            added = [0] * len(buckets)
            while members is not None and size < target:
                # Equal bytes per shard: the shard with the fewest added bytes supplies its next random document.
                position = min(range(len(buckets)), key=lambda position: (added[position], position))
                if not buckets[position]:
                    raise ValueError(f"Shard exhausted before target: {shards[position]}; increase candidate_oversample")
                payload, band = index.connection.execute("SELECT payload,band FROM main.documents WHERE identifier=?",
                                                         (buckets[position].popleft(),)).fetchone()
                payload = index.payload_text(payload)
                length = len(json.loads(payload)["text"].encode("utf-8"))
                stream.write(payload + "\n")
                size += length
                added[position] += length
                bands[band] += 1
                documents_written += 1
                if documents_written % 1000 == 0:
                    check()
            while members is None and size < target and any(buckets):
                for group in buckets:
                    if not group:
                        continue
                    identifier = group.popleft()
                    payload, band = index.connection.execute("SELECT payload,band FROM main.documents WHERE identifier=?", (identifier,)).fetchone()
                    payload = index.payload_text(payload)
                    document = json.loads(payload)
                    stream.write(payload + "\n")
                    size += len(document["text"].encode("utf-8"))
                    bands[band] += 1
                    documents_written += 1
                    if documents_written % 1000 == 0:
                        check()
                    if size >= target:
                        break
        if size < target:
            raise ValueError(f"Not enough deduplicated text: {size} bytes, need {target}")
        check()
        result = {"documents": documents_written, "utf8_bytes": size, "length_bands": dict(bands),
            "payload_storage": "zlib_json_utf8_v1" if compress_payload else "json_utf8_v1",
                "candidate_documents": candidates_seen, "duplicates_removed": dict(index.rejected),
                "original_background_documents_retained": protected_background}
        if members is not None:
            result["shard_selection"] = {
                "policy": "shard_uniform_v1", "added_utf8_bytes": dict(zip(shards, added)),
                "max_minus_min_added_bytes": max(added) - min(added),
                "remaining_candidates": {shard: len(group) for shard, group in zip(shards, buckets)}}
        return result
    finally:
        index.close()