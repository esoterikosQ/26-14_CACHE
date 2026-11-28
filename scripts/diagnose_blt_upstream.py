"""Record whether the original BLT implementation can execute in this environment."""

import argparse
import importlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys


def preflight():
    report = {"python": sys.version, "executable": sys.executable, "modules": {}}
    for name in ("torch", "bytelatent", "xformers", "pydantic", "omegaconf", "tiktoken", "einops"):
        spec = importlib.util.find_spec(name)
        item = {"available": spec is not None, "origin": spec.origin if spec else None}
        if spec:
            try:
                item["version"] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                item["version"] = None
        report["modules"][name] = item
    try:
        model = importlib.import_module("bytelatent.model.blt")
        report.update(status="import_ready", model_source=model.__file__)
    except Exception as error:
        report.update(status="blocked", error_type=type(error).__name__, error=str(error))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = preflight()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()