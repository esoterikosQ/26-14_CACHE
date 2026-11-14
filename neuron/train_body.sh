#!/usr/bin/env bash
#SBATCH --job-name=blt-body
#SBATCH --partition=amd_h200nv_8
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --comment="field=nlp;appl=pytorch"
#SBATCH --output=/scratch/r984a02/blt-cache/runtimelog/body-%j.out
#SBATCH --error=/scratch/r984a02/blt-cache/runtimelog/body-%j.err
set -euo pipefail

ROOT=/scratch/r984a02/blt-cache
BUNDLE="$ROOT/neuron"
: "${CONFIG:?Set CONFIG to an absolute reviewed JSON config path}"
[[ "$CONFIG" = /* ]] || { printf '%s\n' 'Absolute CONFIG required' >&2; exit 2; }
[[ "${SLURM_SUBMIT_DIR:-}" = "$ROOT" && -n "${SLURM_JOB_ID:-}" ]] || { printf '%s\n' "Submit with sbatch from $ROOT" >&2; exit 2; }
if [[ -z "${CONDA_SH:-}" && -n "${CONDA_EXE:-}" ]]; then
    CONDA_SH="${CONDA_EXE%/bin/conda}/etc/profile.d/conda.sh"
fi
: "${CONDA_SH:?Set CONDA_SH to the existing conda activation script}"
source "$CONDA_SH"
conda activate phdq_blt_hf
export MODE="${MODE:-preflight}" PILOT_STEPS="${PILOT_STEPS:-2}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONNOUSERSITE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}" MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BUNDLE/runtime" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd "$BUNDLE/runtime"
python "$BUNDLE/bundle.py" validate-job --config "$CONFIG" --run-base outputs/korean_body
REPORT_DIR="$ROOT/artifacts/korean_body/neuron-${SLURM_JOB_ID}-${SLURM_RESTART_COUNT:-0}"
mkdir -p "$ROOT/artifacts/korean_body" "$ROOT/outputs/korean_body"
mkdir "$REPORT_DIR"
cp "$CONFIG" "$REPORT_DIR/config.json"
cp "$BUNDLE/runtime-manifest.json" "$REPORT_DIR/runtime-manifest.json"
CONFIG="$REPORT_DIR/config.json"
python blt_hf_checks/check_env.py --output "$REPORT_DIR/environment.json"
python -c 'import torch; assert torch.cuda.device_count() == 1; assert torch.cuda.get_device_capability() in ((8, 0), (9, 0))'
python -m blt_hf.body_train --config "$CONFIG" --report "$REPORT_DIR/preflight.json"
if [[ "$MODE" = preflight ]]; then
    exit 0
fi
python -c 'import json,sys; report=json.load(open(sys.argv[1])); assert report["training_ready"], report["blockers"]' "$REPORT_DIR/preflight.json"
args=(--config "$CONFIG" --execute)
# The site job wrapper does not forward --signal=B:USR1 to python, so stop on the job end time itself.
END_TIME="$(scontrol show job "$SLURM_JOB_ID" -o | grep -o 'EndTime=[^ ]*' | cut -d= -f2)"
args+=(--deadline-unix "$(( $(date -d "$END_TIME" +%s) - 1200 ))")
printf 'Job end %s; save-and-stop deadline 20 minutes earlier\n' "$END_TIME"
if [[ "$MODE" = pilot ]]; then
    args+=(--stop-after-steps "$PILOT_STEPS")
fi
if [[ "${RESUME:-}" = latest ]]; then
    RESUME="$(python "$BUNDLE/bundle.py" latest --config "$CONFIG")"
    printf 'RESUME=latest -> %s\n' "$RESUME"
fi
if [[ -n "${RESUME:-}" ]]; then
    [[ "$RESUME" = /* ]] || { printf '%s\n' 'RESUME must be an absolute trusted checkpoint path' >&2; exit 2; }
    args+=(--resume "$RESUME")
fi
exec python -u -m blt_hf.body_train "${args[@]}"
