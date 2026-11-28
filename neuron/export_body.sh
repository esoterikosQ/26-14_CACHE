#!/usr/bin/env bash
#SBATCH --job-name=blt-body-export
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --comment="field=nlp;appl=pytorch"
#SBATCH --output=/scratch/r984a02/blt-cache/runtimelog/body-export-%j.out
#SBATCH --error=/scratch/r984a02/blt-cache/runtimelog/body-export-%j.err
set -euo pipefail

ROOT=/scratch/r984a02/blt-cache
BUNDLE="$ROOT/neuron"
: "${RUN_ID:?Set RUN_ID, e.g. ko-body-full-run1-45-20261117-01}"
[[ "$RUN_ID" =~ ^[a-z0-9-]+$ ]] || { printf '%s\n' 'RUN_ID: lowercase letters, digits and - only' >&2; exit 2; }
[[ "${SLURM_SUBMIT_DIR:-}" = "$ROOT" && -n "${SLURM_JOB_ID:-}" ]] || { printf '%s\n' "Submit with sbatch from $ROOT" >&2; exit 2; }
RUN_DIR="$ROOT/outputs/korean_body/$RUN_ID"
[[ -d "$RUN_DIR" && ! -e "$RUN_DIR/.active" ]] || { printf '%s\n' "Missing or active run: $RUN_DIR" >&2; exit 2; }
if [[ -z "${CONDA_SH:-}" && -n "${CONDA_EXE:-}" ]]; then
    CONDA_SH="${CONDA_EXE%/bin/conda}/etc/profile.d/conda.sh"
fi
: "${CONDA_SH:?Set CONDA_SH to the existing conda activation script}"
source "$CONDA_SH"
conda activate phdq_blt_hf
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$BUNDLE/runtime"
cd "$BUNDLE/runtime"
python "$BUNDLE/bundle.py" verify
# Default: the final checkpoint recorded by the finished run.
CHECKPOINT="${CHECKPOINT:-$(python -c 'import json, sys; print(json.load(open(sys.argv[1]))["checkpoint"])' "$RUN_DIR/validation-final.json")}"
OUTPUT="$ROOT/outputs/korean_body_export/$RUN_ID/$(basename "$CHECKPOINT" .pt)"
[[ ! -e "$OUTPUT" ]] || { printf '%s\n' "Output exists: $OUTPUT" >&2; exit 2; }
mkdir -p "$(dirname "$OUTPUT")"
printf 'Checkpoint: %s\nOutput: %s\n' "$CHECKPOINT" "$OUTPUT"
exec python -u -m blt_hf.body_export --run-dir "$RUN_DIR" --checkpoint "$CHECKPOINT" --output "$OUTPUT"
