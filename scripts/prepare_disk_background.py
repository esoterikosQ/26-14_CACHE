"""Opt-in streaming preparation for nested background experiments."""

from datetime import datetime
from contextlib import closing
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import resource
import shutil
import sqlite3
import time

def read_documents(path):
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def sample_shards(shards, read_shard, quota, policy, on_shard, *, retained_bytes=None):
    if policy not in ('equal_v1', 'redistribute_remaining_v2', 'retained_unique_v3'):
        raise ValueError(f'Unknown candidate quota policy: {policy}')
    if not shards or type(quota) is not int or quota < 1:
        raise ValueError('Pinned shards and positive byte quota required')
    unique_quota = policy == 'retained_unique_v3'
    if unique_quota and not callable(retained_bytes):
        raise ValueError('retained_unique_v3 requires retained_bytes feedback')
    total = 0
    total_retained = 0
    budget = quota * len(shards)
    for index, shard in enumerate(shards):
        credited_total = total_retained if unique_quota else total
        requested = (quota if policy == 'equal_v1' else
                     max(0, math.ceil((budget - credited_total) / (len(shards) - index))))
        selected = 0
        retained = 0
        initial_retained = retained_bytes() if unique_quota else 0
        if requested:
            with closing(read_shard(shard)) as documents:
                for document in documents:
                    selected += len(document['text'].encode('utf-8'))
                    yield document
                    retained = retained_bytes() - initial_retained if unique_quota else selected
                    if retained >= requested:
                        break
        total += selected
        total_retained += retained
        details = {'shard': shard, 'candidate_bytes': selected, 'requested_bytes': requested,
                   'shortfall_bytes': max(0, requested - retained), 'total_candidate_bytes': total,
                   'candidate_quota_policy': policy}
        if unique_quota:
            details.update(retained_unique_bytes=retained, total_retained_unique_bytes=total_retained)
        on_shard(details)
        if policy == 'equal_v1' and selected < requested:
            raise ValueError(f'Insufficient candidate bytes in pinned shard {shard}: {selected}, need {requested}')
    if unique_quota and total_retained < budget:
        raise ValueError(f'Insufficient retained unique bytes across all pinned shards: {total_retained}, need {budget}')
    if not unique_quota and total < budget:
        raise ValueError(f'Insufficient candidate bytes across all pinned shards: {total}, need {budget}')


def prepare_disk(plan, config, run, baseline, source):
    from datasketch import MinHash
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as parquet
    from scripts.disk_dedup import Signer, expand_to_disk
    from scripts.native_minhash import build_native
    from scripts.run_background_expansion import file_hash, record_progress, write_json

    started = time.perf_counter()
    root = Path(config["work_root"])
    dataset = root / config["dataset_directory"] / config["run_id"]
    manifest = json.loads((dataset / "manifest.json").read_text())
    paths = {}
    for split in ("background", "train", "validation", "test", "wikipedia_test"):
        paths[split] = dataset / f"{split}.jsonl"
        if file_hash(paths[split]) != manifest["splits"][split]["file_sha256"]:
            raise ValueError("Existing split hash changed")
    original_hashes = {item["text_sha256"] for item in read_documents(paths["background"])}
    parent_identity = None
    if plan.get("parent_background_run_directory"):
        parent = root / plan["parent_background_run_directory"]
        parent_report = json.loads((parent / "data_preparation.json").read_text())
        paths["background"] = parent / "background.jsonl"
        if file_hash(paths["background"]) != parent_report["file_sha256"]:
            raise ValueError("Parent background hash changed")
        parent_identity = {"run": str(parent), "report_sha256": file_hash(parent / "data_preparation.json"),
                           "file_sha256": parent_report["file_sha256"]}
    parent_size = 0
    for document in read_documents(paths["background"]):
        original_hashes.discard(document["text_sha256"])
        parent_size += len(document["text"].encode("utf-8"))
    if original_hashes:
        raise ValueError("Parent background does not contain the original background")
    sources = json.loads((source / plan["sources"]).read_text())
    if sources["config_sha256"] != file_hash(source / plan["baseline_config"]):
        raise ValueError("Source/config identity changed")
    selected = next(item for item in sources["sources"] if item["repository"] == config["data"]["fineweb_repository"])
    remaining = plan["background_utf8_bytes"] - parent_size
    if remaining <= 0:
        raise ValueError("Expanded target must exceed parent background")
    policy = plan.get('candidate_quota_policy', 'equal_v1')
    selection = plan.get("selection_policy")
    if selection not in (None, "shard_uniform_v1") or (selection and policy != "retained_unique_v3"):
        raise ValueError("selection_policy must be shard_uniform_v1 with retained_unique_v3")
    oversample = plan.get("candidate_oversample", 1)
    if type(oversample) not in (int, float) or oversample < 1 or (oversample != 1 and policy != "retained_unique_v3"):
        raise ValueError("candidate_oversample must be >= 1 and requires retained_unique_v3")
    quota = math.ceil((oversample if policy == 'retained_unique_v3' else 2) * remaining / len(selected["selected_shards"]))
    generator = random.Random(plan["sampling_seed"])
    filesystem = HfFileSystem(token=False)
    row_groups_read = []
    checked = 0
    signature_workers = plan.get("signature_workers", 0)
    if type(signature_workers) is not int or signature_workers < 0:
        raise ValueError("signature_workers must be a nonnegative integer")
    library = build_native(run / "native")
    signer = Signer(config["seed"], library) if signature_workers else None
    local_shards = None
    if plan.get("local_shard_directory"):
        local_shards = {}
        pinned = plan["local_shard_sha256"]
        for shard in selected["selected_shards"]:
            path = root / plan["local_shard_directory"] / shard
            if file_hash(path) != pinned[shard]:
                raise ValueError(f"Pinned local shard changed: {shard}")
            local_shards[shard] = path
    protected_index = None
    if plan.get("protected_index_report"):
        index_report_path = root / plan["protected_index_report"]
        if file_hash(index_report_path) != plan["protected_index_report_sha256"]:
            raise ValueError("Pinned protected index report changed")
        index_report = json.loads(index_report_path.read_text())
        index_path = index_report_path.parent / index_report["database"]
        expected = {split: file_hash(path) for split, path in paths.items()}
        if (index_report["split_sha256"] != expected or file_hash(index_path) != index_report["database_sha256"]
                or index_report["seed"] != config["seed"]):
            raise ValueError("Protected index does not match the protected splits")
        protected_index = (index_path, index_report)

    def check():
        nonlocal checked
        budgets = config["budgets"]
        if shutil.disk_usage(root).free < budgets["minimum_free_disk_gib"] * 2**30:
            raise RuntimeError("Disk headroom budget exhausted")
        storage = sum(path.stat().st_size for path in run.rglob("*") if path.is_file())
        if storage > budgets["maximum_new_artifact_storage_gib"] * 2**30:
            raise RuntimeError("Preparation storage budget exceeded")
        checked += 1
        if checked % 10 == 0:
            record_progress(plan, run, source, "Disk preparation heartbeat", {
                "checks": checked, "scratch_bytes": storage,
                "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}, started)

    def read_shard(shard):
            remote = f"datasets/{selected['repository']}@{selected['resolved_revision']}/{shard}"
            opened = local_shards[shard].open("rb") if local_shards else filesystem.open(remote, "rb", block_size=2**20)
            with opened as stream:
                reader = parquet.ParquetFile(stream)
                groups = list(range(reader.num_row_groups))
                generator.shuffle(groups)
                for group in groups:
                    rows = reader.read_row_group(group, columns=["text", "id", "url"]).to_pylist()
                    positions = list(range(len(rows)))
                    generator.shuffle(positions)
                    row_groups_read.append({"shard": shard, "row_group": group})
                    documents = []
                    for position in positions:
                        row = rows[position]
                        text = row["text"]
                        if not isinstance(text, str) or not text.strip():
                            continue
                        raw = text.encode("utf-8")
                        if not 256 <= len(raw) <= 65536:
                            continue
                        documents.append({"source": selected["repository"], "revision": selected["resolved_revision"],
                               "shard": shard, "row_group": group, "row_in_group": position,
                               "document_id": row["id"], "url": row["url"], "text": text,
                               "text_sha256": hashlib.sha256(raw).hexdigest()})
                    yield from (signer.sign(documents, signature_workers) if signer else documents)
                    check()

    shard_sampling = []
    retained_size = 0

    def sampled(details):
        shard_sampling.append(details)
        record_progress(plan, run, source, 'Shard sampled', details, started)

    def candidate_retained(size):
        nonlocal retained_size
        retained_size += size

    candidates = sample_shards(selected['selected_shards'], read_shard, quota, policy, sampled,
                               retained_bytes=lambda: retained_size)

    check()
    database = run / "dedup.sqlite"
    output = run / "background.jsonl"
    result = expand_to_disk({split: read_documents(path) for split, path in paths.items()}, candidates,
                            plan["background_utf8_bytes"], config["seed"], database, library, output, check,
                            compress_payload=plan.get("compress_dedup_payload", False),
                            on_candidate_retained=candidate_retained if policy == 'retained_unique_v3' else None,
                            protected_index=protected_index, threads=signature_workers,
                            shards=list(selected["selected_shards"]) if selection else None)
    scratch_bytes = database.stat().st_size
    report = {
        **result, "status": "prepared", "run_id": plan["run_id"], "source": selected,
        "row_groups_read": row_groups_read, "parent_background": parent_identity,
        "candidate_quota_policy": policy, "shard_sampling": shard_sampling,
        "original_split_hashes": {split: details["file_sha256"] for split, details in manifest["splits"].items()},
        "deduplication": "Same normalized-text/URL and 5-word MinHash128 LSH .8 policy; existing five splits protected; approximate, not exhaustive",
        "preparation_backend": "sqlite_cpp_v1", "minhash_scheme": getattr(MinHash(), "scheme", "legacy"),
        "native_library_sha256": file_hash(library), "native_source_sha256": file_hash(source / "scripts/native/minhash.cpp"),
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "datasketch", "pyarrow")},
        "sqlite_version": sqlite3.sqlite_version, "scratch_bytes_at_completion": scratch_bytes,
        "scratch_policy": "Delete only this run's disposable dedup.sqlite after successful output; retain native binary and report; preserve scratch on failure",
        "file_sha256": file_hash(output), "elapsed_seconds": time.perf_counter() - started,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "peak_host_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    if signature_workers or local_shards or protected_index:
        report["acceleration"] = {
            "signature_workers": signature_workers, "local_shards": bool(local_shards),
            "protected_index_report_sha256": plan.get("protected_index_report_sha256")}
    if oversample != 1:
        report["candidate_oversample"] = oversample
    write_json(run / "data_preparation.json", report)
    database.unlink()
    if protected_index is not None and plan.get("delete_protected_index_after_prepare") is True:
        protected_index[0].unlink()
        record_progress(plan, run, source, "Protected index database removed", {
            "path": str(protected_index[0]), "sha256": protected_index[1]["database_sha256"],
            "reason": "Explicit plan opt-in after successful preparation"}, started)
    return report