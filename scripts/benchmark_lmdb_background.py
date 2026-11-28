"""Measure exact LMDB lookups on existing development prefixes, not GPU inference."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import resource
import time

import numpy as np

from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountModel, contexts, rollout
from phdq_blt_cache.lmdb_counts import LMDBCountTable
from scripts.benchmark_count_patcher import file_hash, measure, samples
from scripts.fit_count_patcher import block_manifest_hash, load_background, query_contexts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background-report", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--documents", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-partial", action="store_true")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    if output.exists():
        raise FileExistsError(output)
    resource.setrlimit(resource.RLIMIT_AS, (48 * 1024 ** 3, 48 * 1024 ** 3))
    report = json.loads(Path(arguments.background_report).read_text())
    with LMDBCountTable(arguments.database, allow_partial=arguments.allow_partial) as disk:
        metadata = disk.metadata
        if file_hash(arguments.background_report) != metadata["source_report_sha256"]:
            raise ValueError("LMDB source report mismatch")
    report["blocks"] = report["blocks"][:metadata["selected_blocks"]]
    report["table_sha256"] = block_manifest_hash(report["blocks"])
    config = replace(CountConfig(**report["count_config"]), window=None)
    documents = samples(Path(arguments.documents), 4, 512)
    chunks = [{"input_ids": document["input_ids"]} for document in documents]
    required = query_contexts(chunks, config)
    started = time.perf_counter()
    memory = load_background(report, required)
    load_seconds = time.perf_counter() - started
    keys = []
    for document in documents:
        history = b""
        keys.append(b"")
        for token_id in document["input_ids"]:
            history = (history + token_id.to_bytes(2, "little"))[-2 * config.max_context:] if config.max_context else b""
            if token_id == config.eos_id:
                history = b""
            keys.extend(contexts(history, config.max_context))
    rule = BoundaryRule((-4, 0.1, 0, 1, 0.1), 4, 0.375)
    references = [rollout(document["input_ids"], config=config, rule=rule, background=memory) for document in documents]

    def lookup_pass(table):
        for context in keys:
            table.lookup(context)

    def patch_pass(table):
        for document in documents:
            rollout(document["input_ids"], config=config, rule=rule, background=table)

    cases = {"memory_projected": {
        "lookup": measure(lambda: lookup_pass(memory), 1, 5),
        "patcher": measure(lambda: patch_pass(memory), 1, 5),
    }}
    for cache_size in (0, 4096):
        with LMDBCountTable(arguments.database, cache_size=cache_size, allow_partial=arguments.allow_partial) as disk:
            for context in required:
                if disk.lookup(context) != memory.lookup(context):
                    raise ValueError("LMDB integer count mismatch")
            for document, reference in zip(documents, references):
                if rollout(document["input_ids"], config=config, rule=rule, background=disk) != reference:
                    raise ValueError("LMDB boundary mismatch")
                memory_model, disk_model = CountModel(config, memory), CountModel(config, disk)
                for token_id in document["input_ids"]:
                    np.testing.assert_array_equal(memory_model.probabilities(), disk_model.probabilities())
                    memory_model.observe(token_id)
                    disk_model.observe(token_id)
            cases[f"lmdb_cache_{cache_size}"] = {
                "lookup": measure(lambda: lookup_pass(disk), 1, 5),
                "patcher": measure(lambda: patch_pass(disk), 1, 5),
                "cache_info": disk.cache_info()._asdict(),
            }
    result = {
        "status": "exact_counts_probabilities_boundaries", "source": metadata,
        "background_report_sha256": file_hash(arguments.background_report),
        "benchmark_code_sha256": file_hash(__file__),
        "backend_code_sha256": file_hash(Path(__file__).resolve().parents[1] / "src/phdq_blt_cache/lmdb_counts.py"),
        "documents": [{key: value for key, value in document.items() if key != "input_ids"} for document in documents],
        "input_ids": sum(len(document["input_ids"]) for document in documents),
        "lookup_calls_per_pass": len(keys), "unique_contexts": len(required),
        "reference_load_seconds": load_seconds, "cases": cases,
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "limitations": "Small known development prefixes; page/cache warmed by correctness checks. No cold-cache, full-database, fitted-rule, GPU or BLT end-to-end speed claim.",
    }
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()