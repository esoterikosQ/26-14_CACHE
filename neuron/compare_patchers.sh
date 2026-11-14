#!/usr/bin/env bash
#SBATCH --job-name=blt-patcher-compare
#SBATCH --partition=amd_h200nv_8
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --comment="field=nlp;appl=pytorch"
#SBATCH --output=/scratch/r984a02/blt-cache/runtimelog/patcher-compare-%j.out
#SBATCH --error=/scratch/r984a02/blt-cache/runtimelog/patcher-compare-%j.err
set -euo pipefail

ROOT=/scratch/r984a02/blt-cache
BUNDLE="$ROOT/neuron"
: "${RUN_ID:?Set RUN_ID, e.g. ko-patcher-compare-20261114-01}"
[[ "$RUN_ID" =~ ^[a-z0-9-]+$ ]] || { printf '%s\n' 'RUN_ID: lowercase letters, digits and - only' >&2; exit 2; }
[[ "${SLURM_SUBMIT_DIR:-}" = "$ROOT" && -n "${SLURM_JOB_ID:-}" ]] || { printf '%s\n' "Submit with sbatch from $ROOT" >&2; exit 2; }
RUN1="${RUN1:-$ROOT/outputs/korean_entropy/ko-entropy-h200-20261107-01/final-00137500.pt}"
RUN2="${RUN2:-$ROOT/outputs/korean_entropy/ko-entropy-h200-20261110-01/final-00126500.pt}"
OUTPUT="$ROOT/outputs/korean_patcher_compare/$RUN_ID/report.json"
[[ ! -e "$OUTPUT" ]] || { printf '%s\n' "Output exists: $OUTPUT" >&2; exit 2; }
if [[ -z "${CONDA_SH:-}" && -n "${CONDA_EXE:-}" ]]; then
    CONDA_SH="${CONDA_EXE%/bin/conda}/etc/profile.d/conda.sh"
fi
: "${CONDA_SH:?Set CONDA_SH to the existing conda activation script}"
source "$CONDA_SH"
conda activate phdq_blt_hf
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONNOUSERSITE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}" MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BUNDLE/runtime"
cd "$BUNDLE/runtime"
python "$BUNDLE/bundle.py" verify
mkdir -p "$(dirname "$OUTPUT")"
python blt_hf_checks/check_env.py --output "$(dirname "$OUTPUT")/environment.json"
python -c 'import torch; assert torch.cuda.device_count() == 1; assert torch.cuda.get_device_capability() in ((8, 0), (9, 0))'
exec python -u -m blt_hf.patcher_compare --patcher "run1=$RUN1" --patcher "run2=$RUN2" \
    ${TARGETS:+--targets "$TARGETS"} ${DOCUMENTS:+--documents "$DOCUMENTS"} --output "$OUTPUT"
