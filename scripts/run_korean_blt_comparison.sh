#!/usr/bin/env bash
# T14 BLT comparison on itcerdo: the exported Korean body with its run1 patcher versus the T14 count patcher.
# Run from a source snapshot at <run>/source with EXPORT set; existing conda only. Timing needs an idle host.
set -euo pipefail

ROOT=/home/itcmaster/projects/blt-cache
T14="$ROOT/runs/ko-patcher-t14-20261127-01"
: "${EXPORT:?Set EXPORT to the transferred body export directory}"
STAGES="${STAGES:-quality timing}"
PYTHON="/home/itcmaster/miniconda3/bin/conda run --no-capture-output -n phdq_blt_hf python -u"
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$(dirname "$SOURCE")"
[[ "$(basename "$SOURCE")" = source ]] || { printf 'Run from <run>/source\n' >&2; exit 2; }
cd "$SOURCE"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8

common=(--blt-project "$SOURCE/neuron/runtime" --model-path /home/itcmaster/projects/phdq3/artifacts/converted/blt-1b-hf-own
        --fit-report "$T14/fit/report.json" --label-report "$T14/label_generation.json" --background "$T14/counts.lmdb"
        --dataset-directory "$ROOT/datasets/ko-count-sample-20261127-01" --output-directory "$RUN"
        --body-export "$EXPORT"
        --patcher-checkpoint "$ROOT/artifacts/korean_entropy/ko-entropy-h200-20261107-01/final-00137500.pt")
for stage in $STAGES; do
    [[ -e "$RUN/$stage.json" ]] && continue
    printf '%s %s\n' "$(date -u +%FT%TZ)" "$stage"
    $PYTHON -m scripts.compare_korean_blt --stage "$stage" "${common[@]}"
done
printf '%s done\n' "$(date -u +%FT%TZ)"
