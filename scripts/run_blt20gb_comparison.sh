#!/usr/bin/env bash
set -euo pipefail

cd /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/source
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=8
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8

python3 - <<'PY'
import hashlib
import json
from pathlib import Path
from scripts.patcher_preflight import file_hash

root = Path('/home/itcmaster/projects/blt-cache')
for path, expected in (
    (root / 'runs/en-patcher-bg20gb-nested-20261029-02/fit/report.json', 'd3e6da68eb5ae667b287c176cd6e77ea30487de96fc68060f9b2314a51e2b48d'),
    (root / 'runs/en-patcher-bg20gb-nested-20261029-02/background_build.json', 'f4098e2f2c098a9d5fdabed1172ecfe011b107c1230f2131fcadc9f0b9171e06'),
    (Path('experiments/english_patcher_pilot.json'), '6043b4e375cabca5744d91a948add168cf4a90bd4365d6df3129c98c6c4eba64'),
    (Path('/home/itcmaster/projects/phdq3/artifacts/converted/blt-1b-hf-own/model.safetensors'), '4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061'),
):
    if file_hash(path) != expected:
        raise ValueError('Frozen experiment input changed: ' + str(path))
print('Frozen20GB inputs and model weights verified', flush=True)
PY

date -u '+%Y-%m-%dT%H:%M:%SZ index started'
/home/itcmaster/projects/blt-cache/.venv/bin/python -u -m scripts.build_lmdb_background \
    --report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/background_build.json \
    --output /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/counts.lmdb \
    --parent-background /home/itcmaster/projects/blt-cache/runs/en-count-lmdb-full-20261025-01/counts.lmdb \
    --parent-report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg10gb-diskcpp-20261024-02/background_build.json \
    --map-size-gib 128 --memory-limit-gib 160 --rss-limit-gib 48 \
    --min-free-gib 100 --max-output-gib 100

date -u '+%Y-%m-%dT%H:%M:%SZ quality started'
/home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/model-venv/bin/python -u -m scripts.compare_blt_patchers \
    --stage quality \
    --blt-project /home/itcmaster/projects/phdq3 \
    --model-checkpoint /home/itcmaster/projects/phdq3/artifacts/converted/blt-1b-hf-own \
    --conversion-report /home/itcmaster/projects/phdq3/blt_hf_checks/manifests/conversion_B_20260915.json \
    --fit-report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/fit/report.json \
    --background /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/counts.lmdb \
    --dataset-directory /home/itcmaster/projects/blt-cache/datasets/en-patcher-20261019-01 \
    --preparation-report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/data_preparation.json \
    --label-report /home/itcmaster/projects/blt-cache/runs/en-patcher-20261019-01/label_generation.json \
    --pilot-config experiments/english_patcher_pilot.json \
    --output /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/quality.json

date -u '+%Y-%m-%dT%H:%M:%SZ generation started'
/home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/model-venv/bin/python -u -m scripts.compare_blt_patchers \
    --stage generation \
    --blt-project /home/itcmaster/projects/phdq3 \
    --model-checkpoint /home/itcmaster/projects/phdq3/artifacts/converted/blt-1b-hf-own \
    --conversion-report /home/itcmaster/projects/phdq3/blt_hf_checks/manifests/conversion_B_20260915.json \
    --fit-report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/fit/report.json \
    --background /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/counts.lmdb \
    --dataset-directory /home/itcmaster/projects/blt-cache/datasets/en-patcher-20261019-01 \
    --preparation-report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/data_preparation.json \
    --label-report /home/itcmaster/projects/blt-cache/runs/en-patcher-20261019-01/label_generation.json \
    --pilot-config experiments/english_patcher_pilot.json \
    --prompt-report /home/itcmaster/projects/blt-cache/runs/en-blt-instruction9-20261028-01/report.json \
    --sampling-reference /home/itcmaster/projects/blt-cache/runs/en-blt-decoding9-20261028-01/report.json \
    --output /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/generation.json

date -u '+%Y-%m-%dT%H:%M:%SZ timing started'
/home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/model-venv/bin/python -u -m scripts.compare_blt_patchers \
    --stage timing \
    --blt-project /home/itcmaster/projects/phdq3 \
    --model-checkpoint /home/itcmaster/projects/phdq3/artifacts/converted/blt-1b-hf-own \
    --conversion-report /home/itcmaster/projects/phdq3/blt_hf_checks/manifests/conversion_B_20260915.json \
    --fit-report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/fit/report.json \
    --background /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/counts.lmdb \
    --dataset-directory /home/itcmaster/projects/blt-cache/datasets/en-patcher-20261019-01 \
    --preparation-report /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/data_preparation.json \
    --label-report /home/itcmaster/projects/blt-cache/runs/en-patcher-20261019-01/label_generation.json \
    --pilot-config experiments/english_patcher_pilot.json \
    --output /home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01/timing.json

python3 - <<'PY'
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path('/home/itcmaster/projects/blt-cache/runs/en-blt20gb-compare-20261101-01')
stages = []
for stage in ('quality', 'generation', 'timing'):
    path = root / (stage + '.json')
    if json.loads(path.read_text())['status'] != 'completed':
        raise ValueError('Incomplete stage: ' + stage)
    stages.append({'stage': stage, 'artifact': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
with (root / 'run_report.json').open('x') as handle:
    json.dump({'run_id': root.name, 'status': 'completed', 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
               'stages': stages, 'scope': 'Frozen20GB count versus OSC neural; compare to frozen10GB evidence separately'}, handle, indent=2)
    handle.write('\n')
print('20GB BLT comparison completed', flush=True)
PY