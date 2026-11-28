"""Profile the stages of disk background preparation without changing its outputs."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import time
import zlib

import numpy as np
from datasketch.hashfunc import sha1_hash32

from scripts.disk_dedup import DiskDeduplicator
from scripts.native_minhash import build_native
from scripts.prepare_english_data import length_band


def profile_add(index, document, timings):
    clock = time.perf_counter
    started = clock()
    normalized = " ".join(document["text"].casefold().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    url = document.get("url") or None
    marked = clock()
    timings["normalize_sha256"] += marked - started
    exists = index.connection.execute("SELECT 1 FROM documents WHERE digest=? OR url=? LIMIT 1", (digest, url)).fetchone()
    timings["sqlite_exact_lookup"] += clock() - marked
    if exists:
        return False
    marked = clock()
    words = normalized.split()
    shingles = {" ".join(words[offset:offset + 5]).encode("utf-8") for offset in range(max(1, len(words) - 4))}
    hashes = [sha1_hash32(value) for value in sorted(shingles)]
    shingled = clock()
    timings["python_shingle_sha1"] += shingled - marked
    values = index.native.values(hashes, *index.template.permutations, scheme=getattr(index.template, "scheme", "legacy"))
    hashvalues = np.asarray(values, dtype=index.template.hashvalues.dtype)
    hashed = clock()
    timings["native_minhash_call"] += hashed - shingled
    keys = [(band, index.layout._H(hashvalues[start:end])) for band, (start, end) in enumerate(index.layout.hashranges)]
    timings["band_keys"] += clock() - hashed
    marked = clock()
    for band, value in keys:
        for (stored,) in index.connection.execute(
                "SELECT documents.signature FROM buckets JOIN documents USING(identifier) WHERE buckets.band=? AND buckets.value=?",
                (band, value)):
            if np.count_nonzero(hashvalues == np.frombuffer(stored, dtype=index.template.hashvalues.dtype)) / 128 >= 0.8:
                timings["sqlite_band_lookup"] += clock() - marked
                return False
    timings["sqlite_band_lookup"] += clock() - marked
    marked = clock()
    payload = zlib.compress(json.dumps(document, ensure_ascii=False).encode("utf-8"), level=1)
    serialized = clock()
    timings["json_zlib"] += serialized - marked
    cursor = index.connection.execute(
        "INSERT INTO documents(digest,url,signature,payload,band,protected) VALUES(?,?,?,?,?,?)",
        (digest, url, hashvalues.tobytes(), payload, length_band(document), 1))
    index.connection.executemany("INSERT INTO buckets VALUES(?,?,?)", [(band, value, cursor.lastrowid) for band, value in keys])
    index.accepted += 1
    if index.accepted % 1000 == 0:
        index.connection.commit()
    timings["sqlite_insert_commit"] += clock() - serialized
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", type=Path, required=True)
    parser.add_argument("--documents", type=int, required=True)
    parser.add_argument("--repository")
    parser.add_argument("--revision")
    parser.add_argument("--shard")
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    args.output_directory.mkdir(exist_ok=False)
    result = {"documents_requested": args.documents}
    index = DiskDeduplicator(args.output_directory / "profile.sqlite", 20261019, build_native(args.output_directory / "native"),
                             compress_payload=True)
    timings, utf8_bytes, accepted = Counter(), 0, 0
    read_started = time.perf_counter()
    read_seconds = 0.0
    total_started = time.perf_counter()
    with args.background.open() as stream:
        for position, line in enumerate(stream):
            if position == args.documents:
                break
            read_started = time.perf_counter()
            document = json.loads(line)
            read_seconds += time.perf_counter() - read_started
            utf8_bytes += len(document["text"].encode("utf-8"))
            accepted += profile_add(index, document, timings)
    index.connection.commit()
    total = time.perf_counter() - total_started
    index.close()
    result.update(documents=position, accepted=accepted, utf8_bytes=utf8_bytes, total_seconds=total,
                  json_read_seconds=read_seconds, stage_seconds=dict(timings),
                  stage_fraction={key: value / total for key, value in timings.items()},
                  milliseconds_per_document=1000 * total / max(1, position),
                  megabytes_per_second=utf8_bytes / total / 1e6)
    if args.shard:
        from huggingface_hub import HfFileSystem
        target = args.output_directory / "shard.parquet"
        started = time.perf_counter()
        HfFileSystem(token=False).get_file(f"datasets/{args.repository}@{args.revision}/{args.shard}", str(target))
        elapsed = time.perf_counter() - started
        result["shard_download"] = {"shard": args.shard, "bytes": target.stat().st_size, "seconds": elapsed,
                                    "megabytes_per_second": target.stat().st_size / elapsed / 1e6}
        started = time.perf_counter()
        import pyarrow.parquet as parquet
        reader = parquet.ParquetFile(target)
        rows = text_bytes = 0
        for group in range(reader.num_row_groups):
            table = reader.read_row_group(group, columns=["text", "id", "url"]).to_pylist()
            rows += len(table)
            text_bytes += sum(len(row["text"].encode("utf-8")) for row in table)
        result["shard_local_read"] = {"seconds": time.perf_counter() - started, "row_groups": reader.num_row_groups,
                                      "rows": rows, "text_utf8_bytes": text_bytes}
        target.unlink()
    result["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    (args.output_directory / "profile.sqlite").unlink()
    with (args.output_directory / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
