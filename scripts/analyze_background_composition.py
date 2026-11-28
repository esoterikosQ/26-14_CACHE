"""Read-only composition diagnosis of a nested background file, split into its sampling increments."""

import argparse
from array import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import resource
import time
from urllib.parse import urlsplit

import numpy as np

BANDS = ("short", "medium", "long")
QUANTILES = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)


def band(size):
    return "short" if size <= 1024 else "medium" if size <= 8192 else "long"


def host_of(url):
    try:
        host = (urlsplit(url or "").hostname or "").lower()
    except ValueError:
        host = ""
    return host[4:] if host.startswith("www.") else host


def nested_chain(run):
    chain = []
    while True:
        report = json.loads((run / "data_preparation.json").read_text())
        chain.append({"run": str(run), "documents": report["documents"], "utf8_bytes": report["utf8_bytes"],
                      "file_sha256": report.get("file_sha256"), "parent_documents": report["original_background_documents_retained"]})
        parent = (report.get("parent_background") or {}).get("run")
        if not parent:
            break
        run = Path(parent)
    chain.reverse()
    for previous, current in zip(chain, chain[1:]):
        if current["parent_documents"] != previous["documents"]:
            raise ValueError(f"Nested chain document counts disagree at {current['run']}")
    return [{"run": "original_background", "documents": chain[0]["parent_documents"], "utf8_bytes": None, "file_sha256": None}] + chain


class Accumulator:
    def __init__(self):
        self.lengths = array("I")
        self.scores = array("d")
        self.tokens = array("q")
        self.band_documents = Counter()
        self.band_bytes = Counter()
        self.hosts = Counter()
        self.tlds = Counter()
        self.shards = Counter()
        self.unscored = 0

    def add(self, size, url, shard, quality):
        self.lengths.append(size)
        self.band_documents[band(size)] += 1
        self.band_bytes[band(size)] += size
        host = host_of(url)
        self.hosts[host] += 1
        self.tlds[host.rsplit(".", 1)[-1] if host else ""] += 1
        self.shards[shard] += 1
        if quality is None:
            self.unscored += 1
        else:
            self.scores.append(quality[0])
            self.tokens.append(quality[1])

    def merge(self, other):
        merged = Accumulator()
        for item in (self, other):
            merged.lengths.extend(item.lengths)
            merged.scores.extend(item.scores)
            merged.tokens.extend(item.tokens)
            for name in ("band_documents", "band_bytes", "hosts", "tlds", "shards"):
                getattr(merged, name).update(getattr(item, name))
            merged.unscored += item.unscored
        return merged


def shares(counter, keys=None):
    total = sum(counter.values())
    return {key: counter[key] / total if total else 0.0 for key in (keys or counter)}


def jensen_shannon(left, right):
    left_total, right_total = sum(left.values()), sum(right.values())
    if not left_total or not right_total:
        return None
    value = 0.0
    for key in left.keys() | right.keys():
        p, q = left[key] / left_total, right[key] / right_total
        m = (p + q) / 2
        value += (p * math.log2(p / m) if p else 0.0) + (q * math.log2(q / m) if q else 0.0)
    return value / 2


def kolmogorov_smirnov(left, right):
    from scipy.stats import ks_2samp

    if len(left) < 1000 or len(right) < 1000:
        return None
    return float(ks_2samp(np.frombuffer(left, dtype=left.typecode), np.frombuffer(right, dtype=right.typecode),
                          method="asymp").statistic)


def summary(item):
    lengths = np.frombuffer(item.lengths, dtype=np.uint32)
    result = {"documents": len(lengths), "utf8_bytes": int(lengths.sum(dtype=np.int64)),
              "length_mean": float(lengths.mean()) if len(lengths) else None,
              "length_quantiles": dict(zip(map(str, QUANTILES), np.quantile(lengths, QUANTILES).tolist())) if len(lengths) else None,
              "band_document_shares": shares(item.band_documents, BANDS), "band_byte_shares": shares(item.band_bytes, BANDS),
              "distinct_hosts": len(item.hosts), "top_hosts": item.hosts.most_common(10),
              "top_100_host_document_share": sum(count for _, count in item.hosts.most_common(100)) / max(1, len(lengths)),
              "top_tlds": [(tld, count / max(1, len(lengths))) for tld, count in item.tlds.most_common(10)],
              "distinct_shards": len(item.shards), "unscored_documents": item.unscored}
    if item.scores:
        scores = np.frombuffer(item.scores, dtype=np.float64)
        result.update(language_score_mean=float(scores.mean()),
                      language_score_quantiles=dict(zip(map(str, QUANTILES), np.quantile(scores, QUANTILES).tolist())),
                      token_count_mean=float(np.frombuffer(item.tokens, dtype=np.int64).mean()))
    return result


def compare(left, right):
    return {"ks_utf8_length": kolmogorov_smirnov(left.lengths, right.lengths),
            "ks_language_score": kolmogorov_smirnov(left.scores, right.scores),
            "js_band_bytes": jensen_shannon(left.band_bytes, right.band_bytes),
            "js_band_documents": jensen_shannon(left.band_documents, right.band_documents),
            "js_tld": jensen_shannon(left.tlds, right.tlds), "js_host": jensen_shannon(left.hosts, right.hosts),
            "byte_share_difference": {key: shares(left.band_bytes, BANDS)[key] - shares(right.band_bytes, BANDS)[key] for key in BANDS}}


def load_quality(directory, revision):
    import pyarrow.parquet as parquet

    tables = {}
    for path in sorted(directory.glob("data/**/*.parquet")):
        reader = parquet.ParquetFile(path)
        offsets = np.cumsum([0] + [reader.metadata.row_group(group).num_rows for group in range(reader.num_row_groups)])
        table = reader.read(columns=["id", "language_score", "token_count"])
        tables[str(path.relative_to(directory))] = (offsets, table.column("id").combine_chunks(),
                                                    table.column("language_score").to_numpy(), table.column("token_count").to_numpy())
    return {"revision": revision, "tables": tables}


def natural_reference(directory):
    """All local-shard rows passing the same 256..65536 UTF-8 byte filter (before blank-text and deduplication checks)."""
    import pyarrow.compute as compute
    import pyarrow.parquet as parquet

    item = Accumulator()
    for path in sorted(directory.glob("data/**/*.parquet")):
        reader = parquet.ParquetFile(path)
        shard = str(path.relative_to(directory))
        for group in range(reader.num_row_groups):
            table = reader.read_row_group(group, columns=["text", "url", "language_score", "token_count"])
            sizes = compute.binary_length(table.column("text")).to_numpy(zero_copy_only=False)
            keep = (sizes >= 256) & (sizes <= 65536)
            urls = table.column("url").to_pylist()
            scores = table.column("language_score").to_numpy()
            tokens = table.column("token_count").to_numpy()
            for position in np.flatnonzero(keep):
                item.add(int(sizes[position]), urls[position], shard, (float(scores[position]), int(tokens[position])))
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--local-shard-directory", type=Path)
    parser.add_argument("--natural-reference", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    started = time.perf_counter()
    chain = nested_chain(args.run_directory.resolve())
    quality = load_quality(args.local_shard_directory, args.local_shard_directory.name) if args.local_shard_directory else None
    print(json.dumps({"stage": "quality tables loaded", "shards": len(quality["tables"]) if quality else 0,
                      "seconds": time.perf_counter() - started}), flush=True)
    segments = [[Accumulator(), Accumulator()] for _ in chain]
    verification = []
    hasher = hashlib.sha256()
    segment = index = cumulative = 0
    scored = mismatched = 0
    # Line parity would align with the band round-robin period, so halves are drawn at random.
    halves = random.Random(20261105)
    with (args.run_directory / "background.jsonl").open("rb") as stream:
        for line in stream:
            hasher.update(line)
            document = json.loads(line)
            size = len(document["text"].encode("utf-8"))
            record = None
            if (quality and document.get("revision") == quality["revision"] and document.get("shard") in quality["tables"]
                    and document.get("row_group") is not None):
                offsets, identifiers, scores, tokens = quality["tables"][document["shard"]]
                row = int(offsets[document["row_group"]]) + document["row_in_group"]
                if identifiers[row].as_py() != document["document_id"]:
                    mismatched += 1
                else:
                    record = (float(scores[row]), int(tokens[row]))
                    scored += 1
            segments[segment][halves.random() < 0.5].add(size, document.get("url"), document.get("shard", "original"), record)
            index += 1
            cumulative += size
            if index == chain[segment]["documents"]:
                expected = chain[segment]
                # Older runs may serialize JSON differently, so only text bytes are a hard check.
                checks = {"run": expected["run"], "documents": index, "utf8_bytes": cumulative,
                          "bytes_match": expected["utf8_bytes"] in (None, cumulative),
                          "prefix_sha256_match": None if expected["file_sha256"] is None else expected["file_sha256"] == hasher.copy().hexdigest()}
                if not checks["bytes_match"]:
                    raise ValueError(f"Nested prefix verification failed: {checks}")
                verification.append(checks)
                segment += 1
            if index % 1000000 == 0:
                print(json.dumps({"stage": "streaming", "documents": index, "seconds": time.perf_counter() - started}), flush=True)
    if segment != len(chain) or mismatched:
        raise ValueError(f"Incomplete stream or provenance mismatch: segments {segment}/{len(chain)}, mismatched ids {mismatched}")
    names = [Path(item["run"]).name for item in chain]
    merged = [halves[0].merge(halves[1]) for halves in segments]
    report = {"format": "background_composition_v1", "run_directory": str(args.run_directory.resolve()),
              "verification": verification, "scored_documents": scored,
              "segments": [{"name": names[position] if position == 0 else f"{names[position - 1]} -> {names[position]}",
                            **summary(item)} for position, item in enumerate(merged)],
              "split_half_noise_floor": [{"segment": position, **compare(*segments[position])}
                                         for position in range(len(chain)) if len(merged[position].lengths) >= 2000],
              "increment_versus_parent": [], "increment_versus_previous_increment": []}
    parent = merged[0]
    for position in range(1, len(chain)):
        report["increment_versus_parent"].append({"segment": position, **compare(merged[position], parent)})
        if position > 1:
            report["increment_versus_previous_increment"].append({"segment": position, **compare(merged[position], merged[position - 1])})
        parent = parent.merge(merged[position])
    if args.natural_reference:
        natural = natural_reference(args.local_shard_directory)
        report["natural_reference"] = {"definition": natural_reference.__doc__, **summary(natural)}
        report["segment_versus_natural"] = [{"segment": position, **compare(item, natural)} for position, item in enumerate(merged)]
    report["elapsed_seconds"] = time.perf_counter() - started
    report["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    report["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"stage": "completed", "output": str(args.output), "seconds": report["elapsed_seconds"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
