#!/usr/bin/env bash
#SBATCH --job-name=blt-count-sample
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --comment="field=nlp;appl=pytorch"
#SBATCH --output=/scratch/r984a02/blt-cache/runtimelog/count-sample-%j.out
#SBATCH --error=/scratch/r984a02/blt-cache/runtimelog/count-sample-%j.err
set -euo pipefail

ROOT=/scratch/r984a02/blt-cache
BUNDLE="$ROOT/neuron"
: "${RUN_ID:?Set RUN_ID, e.g. ko-count-sample-20261127-01}"
[[ "$RUN_ID" =~ ^[a-z0-9-]+$ ]] || { printf '%s\n' 'RUN_ID: lowercase letters, digits and - only' >&2; exit 2; }
[[ "${SLURM_SUBMIT_DIR:-}" = "$ROOT" && -n "${SLURM_JOB_ID:-}" ]] || { printf '%s\n' "Submit with sbatch from $ROOT" >&2; exit 2; }
CONTRACT="$ROOT/outputs/korean_entropy/ko-entropy-h200-20261107-01/contract.json"
OUTPUT="$ROOT/data/korean_cpt/count_samples/$RUN_ID"
[[ ! -e "$OUTPUT" ]] || { printf '%s\n' "Output exists: $OUTPUT" >&2; exit 2; }
if [[ -z "${CONDA_SH:-}" && -n "${CONDA_EXE:-}" ]]; then
    CONDA_SH="${CONDA_EXE%/bin/conda}/etc/profile.d/conda.sh"
fi
: "${CONDA_SH:?Set CONDA_SH to the existing conda activation script}"
source "$CONDA_SH"
conda activate phdq_blt_hf
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$BUNDLE/runtime"
cd "$BUNDLE/runtime"
python "$BUNDLE/bundle.py" verify
MANIFEST="${MANIFEST:-$(python -c 'import json, sys; print(json.load(open(sys.argv[1]))["config"]["dataset_manifest"])' "$CONTRACT")}"
printf 'Source manifest: %s\n' "$MANIFEST"
mkdir -p "$ROOT/data/korean_cpt/count_samples"
exec python -u -m blt_hf.count_sample --manifest "$MANIFEST" --output "$OUTPUT" ${SEED:+--seed "$SEED"}
