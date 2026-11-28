#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! -d "$1" ]]; then
    printf 'Usage: bash %s EXISTING_WORK_DIRECTORY\n' "$0" >&2
    exit 2
fi

printf 'UTC: '
date -u '+%Y-%m-%dT%H:%M:%SZ'
printf 'Host: '
hostname
uname -sm
for variable in SLURM_JOB_ID SLURM_JOB_PARTITION SLURM_CPUS_PER_TASK SLURM_MEM_PER_NODE CUDA_VISIBLE_DEVICES; do
    printf '%s=%s\n' "$variable" "${!variable:-unset}"
done
df -h "$1"
if command -v free >/dev/null 2>&1; then
    free -h
fi
if command -v lscpu >/dev/null 2>&1; then
    lscpu
fi
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
else
    printf 'nvidia-smi unavailable\n'
fi

python_bin=${PYTHON:-python3}
if ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Selected Python unavailable: %s\n' "$python_bin" >&2
    exit 3
fi
"$python_bin" - <<'PY'
import importlib.metadata
import json
import os
import platform
import sys

report = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(), "packages": {}}
for package_name in ("torch", "transformers", "numpy", "safetensors", "datasets", "huggingface-hub"):
    try:
        report["packages"][package_name] = importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        report["packages"][package_name] = None
if report["packages"]["torch"]:
    import torch

    report["torch_compiled_cuda"] = torch.version.cuda
    if os.environ.get("SLURM_JOB_ID"):
        report["cuda_available"] = torch.cuda.is_available()
        report["cuda_devices"] = [{"name": torch.cuda.get_device_name(index),
                                   "vram_bytes": torch.cuda.get_device_properties(index).total_memory}
                                  for index in range(torch.cuda.device_count())]
    else:
        report["cuda_probe"] = "Skipped without a Slurm allocation; no GPU context requested"
print(json.dumps(report, indent=2))
PY