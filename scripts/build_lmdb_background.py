"""Convert existing document count blocks without rebuilding corpus counts."""

import argparse
import json
from pathlib import Path
import resource
import signal

from phdq_blt_cache.lmdb_counts import build_lmdb_background


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--map-size-gib", type=int, default=32)
    parser.add_argument("--memory-limit-gib", type=int, default=48)
    parser.add_argument("--rss-limit-gib", type=int, default=48)
    parser.add_argument("--min-free-gib", type=int, default=100)
    parser.add_argument("--max-output-gib", type=int, default=100)
    parser.add_argument("--block-limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--parent-background", type=Path)
    parser.add_argument("--parent-report", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.map_size_gib <= 0 or arguments.memory_limit_gib <= arguments.map_size_gib or arguments.rss_limit_gib <= 0:
        parser.error("Require 0 < map size < address-space memory limit")
    limit = arguments.memory_limit_gib * 1024 ** 3
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    if hard != resource.RLIM_INFINITY and hard < limit:
        parser.error("Requested address-space limit exceeds the inherited hard limit")
    resource.setrlimit(resource.RLIMIT_AS, (min(limit, hard) if hard != resource.RLIM_INFINITY else limit, hard))
    output = Path(arguments.output)
    if output.with_suffix(".report.json").exists() or (output.exists() and not arguments.resume):
        raise FileExistsError("LMDB output or report already exists")

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        result = build_lmdb_background(
            arguments.report, output, map_size_bytes=arguments.map_size_gib * 1024 ** 3,
            min_free_bytes=arguments.min_free_gib * 1024 ** 3,
            max_output_bytes=arguments.max_output_gib * 1024 ** 3, block_limit=arguments.block_limit,
            progress=lambda value: print(json.dumps(value), flush=True), resume=arguments.resume,
            max_rss_bytes=arguments.rss_limit_gib * 1024 ** 3,
            parent_background=arguments.parent_background, parent_report=arguments.parent_report,
        )
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "output": str(output),
                          "next": "Resume from the last committed checkpoint with --resume"}), flush=True)
        raise SystemExit(130)
    result["address_space_limit_bytes"] = limit
    result["peak_host_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    with output.with_suffix(".report.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()