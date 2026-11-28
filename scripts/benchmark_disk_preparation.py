"""Compare isolated Python and disk/C++ preparation on a fixed real-text prefix."""

import argparse
from itertools import islice
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

from scripts.prepare_disk_background import read_documents
from scripts.run_background_expansion import expanded_background, file_hash, write_json


def worker(args):
    started = time.perf_counter()
    count = total = 0
    for item in islice(read_documents(args.input), args.documents):
        count += 1
        total += len(item["text"].encode())
    if count != args.documents or count < 2:
        raise ValueError("Insufficient sample documents")
    target = total // 2
    if args.backend == "python":
        documents = list(islice(read_documents(args.input), args.documents))
        protected, candidates = documents[:1], documents[1:]
        selected, rejected = expanded_background({"background": protected}, candidates, target, 42)
        output = args.output / "background.jsonl"
        with output.open("x") as stream:
            for item in selected:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        result = {"documents": len(selected), "duplicates_removed": rejected,
                  "utf8_bytes": sum(len(item["text"].encode()) for item in selected)}
    else:
        from scripts.disk_dedup import expand_to_disk
        from scripts.native_minhash import build_native
        library = build_native(args.output / "native")
        iterator = read_documents(args.input)
        protected = [next(iterator)]
        result = expand_to_disk({"background": protected}, islice(iterator, args.documents - 1), target, 42,
                                args.output / "dedup.sqlite", library, args.output / "background.jsonl")
        result["database_bytes"] = (args.output / "dedup.sqlite").stat().st_size
    result.update(backend=args.backend, elapsed_seconds=time.perf_counter() - started,
                  peak_host_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                  output_sha256=file_hash(args.output / "background.jsonl"))
    write_json(args.output / "report.json", result)


def kernel_benchmark(path, library):
    from datasketch import MinHash
    from scripts.disk_dedup import DiskDeduplicator

    documents = list(islice(read_documents(path), 500))
    normalized = [" ".join(item["text"].casefold().split()) for item in documents]
    index = DiskDeduplicator(library.parent / "kernel.sqlite", 42, library)
    try:
        started = time.perf_counter()
        reference = []
        for text in normalized:
            words = text.split()
            shingles = {" ".join(words[offset:offset + 5]).encode() for offset in range(max(1, len(words) - 4))}
            signature = MinHash(num_perm=128, seed=42)
            signature.update_batch(sorted(shingles))
            reference.append(signature.hashvalues)
        python_seconds = time.perf_counter() - started
        started = time.perf_counter()
        for text, expected in zip(normalized, reference):
            actual = index.signature(text).hashvalues
            if not (actual == expected).all():
                raise AssertionError("Native signature mismatch on real text")
        cpp_seconds = time.perf_counter() - started
        return {"documents": len(documents), "all_signatures_equal": True, "python_seconds": python_seconds,
                "cpp_seconds": cpp_seconds, "python_over_cpp": python_seconds / cpp_seconds,
                "scope": "5-word shingle creation, SHA1, permutation and reduction; excludes LSH/SQLite"}
    finally:
        index.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--documents", type=int, default=20000)
    parser.add_argument("--backend", choices=("python", "disk_cpp"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.backend:
        worker(args)
        return
    for backend in ("python", "disk_cpp"):
        subprocess.run([sys.executable, "-m", "scripts.benchmark_disk_preparation", "--input", str(args.input),
                        "--output", str(args.output / backend), "--documents", str(args.documents), "--backend", backend], check=True)
    reports = {backend: json.loads((args.output / backend / "report.json").read_text()) for backend in ("python", "disk_cpp")}
    for name in ("documents", "utf8_bytes", "duplicates_removed", "output_sha256"):
        if reports["python"][name] != reports["disk_cpp"][name]:
            raise AssertionError(f"Preparation differs: {name}")
    result = {"status": "verified", "input": str(args.input), "input_sha256": file_hash(args.input),
              "sample_documents": args.documents, "reports": reports, "outputs_equal": True,
              "kernel": kernel_benchmark(args.input, next((args.output / "disk_cpp/native").glob("minhash.*"))),
              "limitations": "Fixed prefix only; worker RSS includes its imports/sample scan; not a 10GB peak bound or downstream inference benchmark"}
    source = Path(__file__).resolve().parents[1]
    result["code_sha256"] = {name: file_hash(source / name) for name in (
        "scripts/benchmark_disk_preparation.py", "scripts/disk_dedup.py", "scripts/native_minhash.py", "scripts/native/minhash.cpp")}
    write_json(args.output / "report.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()