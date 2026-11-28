#!/usr/bin/env bash
# Frozen 50GB count patcher versus the neural (OSC) patcher on the converted BLT model; existing conda only.
set -euo pipefail

ROOT=/home/itcmaster/projects/blt-cache
RUN=$ROOT/runs/en-blt50gb-compare-20261105-01
BG=$ROOT/runs/en-patcher-bg50gb-nested-20261105-01
PHDQ3=/home/itcmaster/projects/phdq3
PYTHON="/home/itcmaster/miniconda3/bin/conda run --no-capture-output -n phdq_blt_hf python -u"

cd "$RUN/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8

# conda run does not forward stdin, so inline checks are passed with -c.
CHECK=$(cat <<'PY'
import sys
from pathlib import Path
from scripts.patcher_preflight import file_hash

root = Path('/home/itcmaster/projects/blt-cache')
print(sys.executable, flush=True)
for path, expected in (
    (root / 'runs/en-patcher-bg50gb-nested-20261105-01/fit/report.json', '9b23ba62f752c2c55b2e91163b11870c3648e193ab7611512b41ffbb864750b1'),
    (root / 'runs/en-patcher-bg50gb-nested-20261105-01/background_build.json', 'd0a835d849f9b2ecdc4f23dd8a54d74567d706e4126948c8320ebeec13e9363c'),
    (root / 'runs/en-patcher-bg50gb-nested-20261105-01/data_preparation.json', '540ffc45ce61f16433ce175d7d904772657c81adaec82eac314507b14b35b6f2'),
    (Path('experiments/english_patcher_pilot.json'), '6043b4e375cabca5744d91a948add168cf4a90bd4365d6df3129c98c6c4eba64'),
    (Path('/home/itcmaster/projects/phdq3/artifacts/converted/blt-1b-hf-own/model.safetensors'), '4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061'),
):
    if file_hash(path) != expected:
        raise ValueError('Frozen experiment input changed: ' + str(path))
print('Frozen 50GB inputs and model weights verified', flush=True)
PY
)
$PYTHON -c "$CHECK"

date -u '+%Y-%m-%dT%H:%M:%SZ index started'
$PYTHON -m scripts.build_lmdb_native --report "$BG/background_build.json" --output "$RUN/counts.lmdb" \
    --map-size-gib 192 --threads 22 --memory-budget-gib 28 --rss-limit-gib 48 \
    --min-free-gib 30 --max-output-gib 160

common=(--blt-project "$PHDQ3" --model-checkpoint "$PHDQ3/artifacts/converted/blt-1b-hf-own"
        --conversion-report "$PHDQ3/blt_hf_checks/manifests/conversion_B_20260915.json"
        --fit-report "$BG/fit/report.json" --background "$RUN/counts.lmdb"
        --dataset-directory "$ROOT/datasets/en-patcher-20261019-01"
        --preparation-report "$BG/data_preparation.json"
        --label-report "$ROOT/runs/en-patcher-20261019-01/label_generation.json"
        --pilot-config experiments/english_patcher_pilot.json)

date -u '+%Y-%m-%dT%H:%M:%SZ quality started'
$PYTHON -m scripts.compare_blt_patchers --stage quality "${common[@]}" --output "$RUN/quality.json"

date -u '+%Y-%m-%dT%H:%M:%SZ generation started'
$PYTHON -m scripts.compare_blt_patchers --stage generation "${common[@]}" \
    --prompt-report "$ROOT/runs/en-blt-instruction9-20261028-01/report.json" \
    --sampling-reference "$ROOT/runs/en-blt-decoding9-20261028-01/report.json" \
    --output "$RUN/generation.json"

date -u '+%Y-%m-%dT%H:%M:%SZ timing started'
$PYTHON -m scripts.compare_blt_patchers --stage timing "${common[@]}" --output "$RUN/timing.json"

date -u '+%Y-%m-%dT%H:%M:%SZ total started'
$PYTHON -m scripts.compare_blt_patchers --stage total "${common[@]}" --timing-reference "$RUN/timing.json" \
    --output "$RUN/total.json"

FINISH=$(cat <<'PY'
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path('/home/itcmaster/projects/blt-cache/runs/en-blt50gb-compare-20261105-01')
stages = []
for stage in ('quality', 'generation', 'timing', 'total'):
    path = root / (stage + '.json')
    if json.loads(path.read_text())['status'] != 'completed':
        raise ValueError('Incomplete stage: ' + stage)
    stages.append({'stage': stage, 'artifact': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
lmdb = json.loads((root / 'counts.report.json').read_text())
with (root / 'run_report.json').open('x') as handle:
    json.dump({'run_id': root.name, 'status': 'completed', 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
               'stages': stages, 'lmdb': {key: lmdb[key] for key in ('contexts', 'input_rows', 'data_bytes', 'elapsed_seconds', 'builder')},
               'scope': 'Frozen 50GB count versus OSC neural; compare to frozen 20GB evidence separately'}, handle, indent=2)
    handle.write('\n')
print('50GB BLT comparison completed', flush=True)
PY
)
$PYTHON -c "$FINISH"
