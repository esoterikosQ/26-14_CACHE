#!/usr/bin/env bash
#SBATCH --job-name=blt-entropy
#SBATCH --partition=amd_h200nv_8
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --signal=B:USR1@300
#SBATCH --comment="field=nlp;appl=pytorch"
#SBATCH --output=entropy-%j.out
#SBATCH --error=entropy-%j.err
set -euo pipefail

ROOT=/scratch/r984a02/phdq3
: "${BUNDLE:?Set BUNDLE to the absolute neuron directory from the pinned Git checkout}"
: "${CONFIG:?Set CONFIG to an absolute reviewed JSON config path}"
[[ "$BUNDLE" = /* && "$CONFIG" = /* ]] || { printf '%s\n' 'Absolute BUNDLE and CONFIG required' >&2; exit 2; }
[[ "${SLURM_SUBMIT_DIR:-}" = "$ROOT" && -n "${SLURM_JOB_ID:-}" ]] || { printf '%s\n' 'Submit with sbatch from the owner root' >&2; exit 2; }
if [[ -z "${CONDA_SH:-}" && -n "${CONDA_EXE:-}" ]]; then
    CONDA_SH="${CONDA_EXE%/bin/conda}/etc/profile.d/conda.sh"
fi
: "${CONDA_SH:?Set CONDA_SH to the existing conda activation script}"
[[ -f "$CONDA_SH" ]] || { printf '%s\n' 'Existing conda activation script missing' >&2; exit 2; }
source "$CONDA_SH"
conda activate phdq_blt_hf
export MODE="${MODE:-preflight}" PILOT_STEPS="${PILOT_STEPS:-2}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}" OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}" PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BUNDLE/runtime"
cd "$BUNDLE/runtime"
python "$BUNDLE/bundle.py" validate-job --config "$CONFIG"
REPORT_DIR="$ROOT/artifacts/korean_entropy/neuron-${SLURM_JOB_ID}-${SLURM_RESTART_COUNT:-0}"
mkdir -p "$ROOT/artifacts/korean_entropy" "$ROOT/outputs/korean_entropy"
mkdir "$REPORT_DIR"
cp "$CONFIG" "$REPORT_DIR/config.json"
cp "$BUNDLE/runtime-manifest.json" "$REPORT_DIR/runtime-manifest.json"
CONFIG="$REPORT_DIR/config.json"
python blt_hf_checks/check_env.py --output "$REPORT_DIR/environment.json"
python -c 'import torch; assert torch.cuda.device_count() == 1; assert torch.cuda.get_device_capability() in ((8, 0), (9, 0))'
python -m blt_hf.entropy_train --config "$CONFIG" --report "$REPORT_DIR/preflight.json"
if [[ "$MODE" = preflight ]]; then
    exit 0
fi
python -c 'import json,sys; report=json.load(open(sys.argv[1])); assert report["training_ready"], report["blockers"]' "$REPORT_DIR/preflight.json"
args=(--config "$CONFIG" --execute)
if [[ "$MODE" = pilot ]]; then
    args+=(--stop-after-steps "$PILOT_STEPS")
fi
if [[ -n "${RESUME:-}" ]]; then
    [[ "$RESUME" = /* ]] || { printf '%s\n' 'RESUME must be an absolute trusted checkpoint path' >&2; exit 2; }
    args+=(--resume "$RESUME")
fi
exec python -u -m blt_hf.entropy_train "${args[@]}"