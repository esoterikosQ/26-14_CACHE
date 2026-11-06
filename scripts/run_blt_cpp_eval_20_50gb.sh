#!/usr/bin/env bash
# Package C++ count backend on the frozen 20GB and 50GB BLT comparisons (neural / Python count / C++ count).
set -euo pipefail
ROOT=/home/itcmaster/projects/blt-cache
RUNS=$ROOT/runs
SOURCE=$RUNS/en-blt-cpp-eval-runtime-20261105-01/source
PYTHON=/home/itcmaster/miniconda3/envs/phdq_blt_hf/bin/python
cd "$SOURCE"
export PYTHONPATH="$SOURCE/src" OPENBLAS_NUM_THREADS=8 PYTHONDONTWRITEBYTECODE=1
"$PYTHON" -c 'import sys, os; assert sys.executable == "/home/itcmaster/miniconda3/envs/phdq_blt_hf/bin/python", sys.executable; print(sys.executable)'
run() {
    local tag=$1 compare=$2 total=$3
    echo "$(date -u +%FT%TZ) $tag started"
    "$PYTHON" -m scripts.evaluate_cpp_blt_patcher \
        --quality-reference "$RUNS/$compare/quality.json" \
        --total-reference "$RUNS/$total/total.json" \
        --generation-reference "$RUNS/$compare/generation.json" \
        --native-reference "$RUNS/en-count-cpp-compare-20261029-02/result.json" \
        --dataset-directory "$ROOT/datasets/en-patcher-20261019-01" \
        --background "$RUNS/$compare/counts.lmdb" \
        --blt-project /home/itcmaster/projects/phdq3 \
        --conversion-report /home/itcmaster/projects/phdq3/blt_hf_checks/manifests/conversion_B_20260915.json \
        --output-directory "$RUNS/en-blt${tag}-cpp-eval-20261105-01"
    echo "$(date -u +%FT%TZ) $tag finished"
}
run 20gb en-blt20gb-compare-20261101-01 en-blt20gb-total-20261104-01
run 50gb en-blt50gb-compare-20261105-01 en-blt50gb-compare-20261105-01
echo "C++ BLT evaluation completed"
