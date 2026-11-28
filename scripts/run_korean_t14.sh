#!/usr/bin/env bash
# T14 Korean count patcher on itcerdo: prepare, blocks, run1 teacher labels, fit and LMDB; existing conda only.
# Run from a source snapshot at <run>/source; finished stages are skipped, failed ones stop the script.
set -euo pipefail

CONFIG="${CONFIG:-experiments/korean_patcher_t14.json}"
PLAN="${PLAN:-experiments/korean_background_50gb.json}"
PYTHON="/home/itcmaster/miniconda3/bin/conda run --no-capture-output -n phdq_blt_hf python -u"
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SOURCE"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8

read -r RUN DATA < <($PYTHON -c 'import json, sys; c = json.load(open(sys.argv[1])); print(c["work_root"] + "/" + c["run_directory"], c["work_root"] + "/" + c["dataset_directory"] + "/" + c["dataset_id"])' "$CONFIG")
[[ "$SOURCE" = "$RUN/source" ]] || { printf 'Run from the snapshot %s/source\n' "$RUN" >&2; exit 2; }

stage() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
completed() { [[ -e "$1" ]] && $PYTHON -c 'import json, sys; sys.exit(json.load(open(sys.argv[1]))["status"] not in sys.argv[2:])' "$@"; }

if [[ ! -e "$DATA/background.jsonl" ]]; then
    stage "verify transferred background"
    SHA="$($PYTHON -c 'import json, sys; print(json.load(open(sys.argv[1]))["splits"]["background"]["compressed"]["sha256"])' "$DATA/manifest.json")"
    printf '%s  %s\n' "$SHA" "$DATA/background.jsonl.gz" | sha256sum -c --quiet
    stage "decompress background"
    pigz -dc "$DATA/background.jsonl.gz" > "$DATA/background.jsonl.partial"
    mv "$DATA/background.jsonl.partial" "$DATA/background.jsonl"
fi
if ! completed "$RUN/data_preparation.json" prepared; then
    stage prepare
    $PYTHON -m scripts.run_background_expansion --plan "$PLAN" --stage prepare
fi
if ! completed "$RUN/background_build.json" built; then
    stage build
    $PYTHON -m scripts.run_background_expansion --plan "$PLAN" --stage build
fi
if ! completed "$RUN/label_generation.json" generated; then
    stage labels
    $PYTHON -m scripts.prepare_patcher_labels --config "$CONFIG" --blt-project "$SOURCE/neuron/runtime"
fi
if ! completed "$RUN/fit/report.json" fitted; then
    stage fit
    $PYTHON -m scripts.fit_count_patcher --config "$CONFIG" --window unlimited \
        --background-report "$RUN/background_build.json" --output-directory "$RUN/fit" \
        --progress-log "$RUN/progress.md" --no-time-limit --count-backend cpp_v1 \
        --native-count-library "$RUN/native_counts/count_blocks.so" --load-workers 8 --save-projection
fi
if ! completed "$RUN/counts.report.json" complete; then
    stage lmdb
    $PYTHON -m scripts.build_lmdb_native --report "$RUN/background_build.json" --output "$RUN/counts.lmdb" \
        --map-size-gib 192 --threads 22 --memory-budget-gib 28 --rss-limit-gib 48 --min-free-gib 30 --max-output-gib 160
fi
stage done
