# Neuron 작업별 명령

모든 명령은 **사용자가 Neuron에서 직접 실행**한다. 셸은 bash 기준이다.
phdq3는 파일/정책을 참고하는 읽기 전용 프로젝트다. 이번 코드·설정·로그는 blt-cache에서만 관리한다.
현재 제공하는 실행기는 T12 한국어 entropy 교사용이며 본체 ENCODER/GLOBAL/BODY_FULL 학습용이 아니다.
영어20GB 작업은 itcerdo에서 별도로 실행하므로 여기서 다시 시작하지 않는다.
실제 말뭉치/권리 검토/학습 예산/GPU 파일럿은 아직 완료되지 않았다.

## 1. 저장 경로

제출 cwd는 `/scratch/r984a02`, 프로젝트 루트는 `/scratch/r984a02/blt-cache`다.
스크립트는 하위 프로젝트에 있어도 부모 디렉터리에서 절대경로로 sbatch에 전달한다.
job 내부 작업 cwd는 `$BUNDLE/runtime`이며 제출 cwd와 독립적이다. 아래 경로는 모두 Neuron 경로다.

| 용도 | 절대 경로 |
| --- | --- |
| sbatch 제출 cwd | `/scratch/r984a02` |
| GitHub 코드 사본 | `/scratch/r984a02/blt-cache` |
| 실행 bundle | `/scratch/r984a02/blt-cache/neuron` |
| NIKL 수령 원본 ZIP/JSON | `/scratch/r984a02/blt-cache/data/korean_cpt/incoming/nikl` |
| FineWeb2 수령 원본 | `/scratch/r984a02/blt-cache/data/korean_cpt/incoming/fineweb2` |
| 약정/라이선스/출처 설명 | `/scratch/r984a02/blt-cache/data/korean_cpt/licenses` |
| 명시적 입력 파일/분할 계획 | `/scratch/r984a02/blt-cache/data/korean_cpt/manifests` |
| 변환된 train/validation JSONL와 manifest | `/scratch/r984a02/blt-cache/data/korean_cpt/prepared/<DATA_ID>` |
| 기존 BF16 변환 가중치 | `/scratch/r984a02/blt-cache/artifacts/converted/blt-1b-hf-own` |
| 실행별 학습 설정 | `/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/<RUN_ID>.json` |
| job 환경/preflight/설정 사본 | `/scratch/r984a02/blt-cache/artifacts/korean_entropy/neuron-<JOB_ID>-<RESTART>` |
| 학습 checkpoint/metrics/validation | `/scratch/r984a02/blt-cache/outputs/korean_entropy/<RUN_ID>` |
| SLURM stdout/stderr | `/scratch/r984a02/blt-cache/entropy-<JOB_ID>.out` 및 `.err` |

**원문과 가중치를 Git에 추가하지 않는다.** 프로젝트 내 `data/`, `artifacts/`, `outputs/`는
Git 제외 경로다. 로그 전달도 아래의 검토한 `runtimelog`만 stage한다. 기존 `data/Preprocessed`, `data/Raw`,
GEC checkpoint와 원본 말뭉치를 덮어쓰거나 재분할하지 않는다. NIKL 원본 ZIP은 보존하고,
해제본은 별도 하위 디렉터리에 둔다. 변환기는 ZIP/Parquet을 직접 읽지 않는다.
FineWeb2 Parquet 수집/정제 코드는 이 bundle에 없으며, 검토된 JSONL 변환본이 있어야 한다.

## 2. 코드 다운로드

처음 한 번만 실행한다. 기존 clone이 있으면 다음의 갱신 절차를 사용한다.
목적지가 이미 있고 clone이 아니라면 덮어쓰거나 삭제하지 말고 경로 상태를 먼저 확인한다.
이전 안내의 홈 디렉터리 clone이나 그곳을 쓰는 실행 중 job은 자동 이동/변경하지 않는다.

```bash
cd /scratch/r984a02
git clone --filter=blob:none --sparse https://github.com/esoterikosQ/26-14_CACHE.git "/scratch/r984a02/blt-cache"
cd "/scratch/r984a02/blt-cache"
git sparse-checkout set neuron
git checkout --detach origin/main
git rev-parse HEAD
```

기존 clone을 지정된 검증 버전으로 맞추는 경우, 해당 사본을 사용하는 job이 없고
`git status --short`에 보존해야 할 변경이 없는지 먼저 확인한다. 강제 checkout은 하지 않는다.
fetch한 origin/main을 detached HEAD로 고정한 뒤 `git rev-parse HEAD`를 기록한다.
인계받은 수정 commit인지 확인하고 실행 중에는 갱신하지 않는다. 예전 a0cfa52는 잘못된 phdq3 쓰기 경로가 있으므로 새 실행에 사용하지 않는다.

```bash
cd "/scratch/r984a02/blt-cache"
git status --short
git fetch origin
git sparse-checkout set neuron
git checkout --detach origin/main
```

## 3. 매 로그인 시 환경과 디렉터리

이미 설치된 conda를 사용한다. `conda`가 초기화되지 않았다면 본인 설치 경로의
`etc/profile.d/conda.sh`를 먼저 source한다. 설치/업그레이드나 `module load cuda`는 하지 않는다.

```bash
export SUBMIT_ROOT=/scratch/r984a02
export ROOT=/scratch/r984a02/blt-cache
export BUNDLE="/scratch/r984a02/blt-cache/neuron"
conda activate phdq_blt_hf
export CONDA_SH="$(conda info --base)/etc/profile.d/conda.sh"
export PYTHONPATH="$BUNDLE/runtime"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
unset RESUME
mkdir -p "$ROOT"
cd "$ROOT"
mkdir -p data/korean_cpt/{incoming/nikl,incoming/fineweb2,licenses,manifests,prepared}
mkdir -p artifacts/korean_entropy/configs outputs/korean_entropy
python "$BUNDLE/bundle.py" verify
python -m unittest discover -s "$BUNDLE" -p test_bundle.py -v
test -r "$ROOT/artifacts/converted/blt-1b-hf-own/config.json"
test -r "$ROOT/artifacts/converted/blt-1b-hf-own/model.safetensors"
df -h "$ROOT"
showque
showappl
```

가중치 검사가 실패하면 변환본의 위치와 출처/hash를 확인한 뒤 사용자가 이 프로젝트 경로에 준비한다.
새 blt-cache 경로에 기존 자료나 가중치가 자동으로 생기는 것은 아니다. 참조 프로젝트 파일을 자동 이동하지 않는다.
임의의 다른 HF 모델을 대신 내려받거나 기존 가중치를 덮어쓰지 않는다.
최소 디스크 여유는 현재 template 기준100GiB다. 큰 원문 변환/hash 검사는 로그인 노드에서 실행하지 않는다.

## 4. 데이터 없이 GPU 환경 검사

이 명령은 optimizer를 실행하지 않는다. H2001GPU/CPU8/RAM48G/2시간이 기본이다.
3절에서 프로젝트 디렉터리를 먼저 준비해야 Slurm이 절대경로 stdout/stderr를 열 수 있다.
이후 모든 sbatch도 같은 제출 cwd를 사용한다.

```bash
cd "$SUBMIT_ROOT"
export CONFIG="$BUNDLE/entropy.template.json"
unset RESUME
JOB_ID=$(sbatch --parsable --export=ALL,MODE=preflight "$BUNDLE/train_entropy.sh")
export JOB_ID="${JOB_ID%%;*}"
squeue -j "$JOB_ID"
```

job 완료 후 확인한다. 정상 새 job의 restart 번호는0이다. 재queue된 job은 실제 보고서 경로를 확인한다.

```bash
sacct -j "$JOB_ID" --format=JobID,State,ExitCode,Elapsed,MaxRSS
cat "$ROOT/artifacts/korean_entropy/neuron-${JOB_ID}-0/environment.json"
cat "$ROOT/artifacts/korean_entropy/neuron-${JOB_ID}-0/preflight.json"
```

환경 `status=pass`와 `training_ready=true`는 다른 조건이다. 미승인 template은
`training_ready=false`가 정상이다. A100 검사만 필요하면 제출 시 `-p amd_a100nv_8`을 추가한다.
장치를 바꾼 결과를 같은 조건의 비교나 checkpoint 재개로 취급하지 않는다.

## 5. 입력 목록과 분할 계획

먼저 수령 파일을 확인한다. 아래 명령은 원문 내용을 출력하지 않는다.

```bash
find "$ROOT/data/korean_cpt/incoming" -type f -print
find "$ROOT/data/korean_cpt/licenses" -type f -print
export DATA_ID=korean-entropy-v001
export PLAN="$ROOT/data/korean_cpt/manifests/${DATA_ID}.json"
export PREPARED="$ROOT/data/korean_cpt/prepared/$DATA_ID"
python - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ['ROOT'])
plan = {'files': [
    {'path': str(root / 'data/korean_cpt/incoming/nikl/REPLACE_TRAIN.json'),
     'source': 'REPLACE_NIKL_CORPUS_VERSION', 'split': 'train', 'format': 'nikl_paragraph'},
    {'path': str(root / 'data/korean_cpt/incoming/nikl/REPLACE_VALIDATION.json'),
     'source': 'REPLACE_NIKL_CORPUS_VERSION', 'split': 'validation', 'format': 'nikl_paragraph'}
]}
with Path(os.environ['PLAN']).open('x') as handle:
    json.dump(plan, handle, ensure_ascii=False, indent=2)
    handle.write('\n')
PY
vi "$PLAN"
python -m json.tool "$PLAN"
```

`REPLACE_...`를 실제 파일/출처 버전으로 수정한 뒤 진행한다. 위 이름은 실제 수령 파일명이 아니다.
원문 전체를 자동 분할하는 명령이 아니다. **각 입력 파일 전체를 지정한 split에 넣으므로**
이미 검토한 문서 단위 train/validation 파일 목록만 지정한다. 혼합 split 파일은 먼저 별도 준비가 필요하다.
원본의 제공 validation/test를 임의 재분할하거나 최종평가 파일을 여기에 넣지 않는다.

지원 형식은 다음과 같다.

- `nikl_paragraph`: `document[].id`, `document[].paragraph[].form`.
- `nikl_utterance`: `document[].id`, `document[].utterance[].form`.
- `jsonl`: 각 행에 비어 있지 않은 문자열 `id`, `source`, `text`. 행의 source는 계획의 source와 같아야 한다.

NIKL form은 LF로 연결하며 Unicode 정규화는 하지 않는다. 단일 NIKL JSON512MiB 초과 또는
JSONL 한 행16MiB 초과는 거부한다. 실제 schema가 다르면 변환기를 먼저 보완해야 한다.
FineWeb2 JSONL을 추가할 때도 동일 계획의 files 배열에 실제 경로/source/split을 명시한다.

## 6. 할당 노드에서 자료 준비

아래는 기존 H2001GPU 할당 방식이다. 변환 자체는 CPU 작업이며 GPU를 이용하지 않는다.
첨부 자료의 CPU partition을 사용하는 제출 방식은 이번 cwd 수정에서 변경하지 않았다.
로그인 셸의 ROOT/BUNDLE/PLAN/PREPARED/CONDA_SH가 설정된 상태에서 실행한다.

```bash
cd "$SUBMIT_ROOT"
srun --partition=amd_h200nv_8 --nodes=1 --ntasks=1 --gres=gpu:1 \
  --cpus-per-task=8 --mem=48G --time=02:00:00 \
  --comment='field=nlp;appl=pytorch' --pty bash
```

할당된 셸 안에서 실행한다. 같은 출력 디렉터리는 재사용하지 않으며 실패한 부분 산출물도 보존한다.

```bash
source "$CONDA_SH"
conda activate phdq_blt_hf
export PYTHONPATH="$BUNDLE/runtime"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8
cd "$BUNDLE/runtime"
python blt_hf_checks/check_env.py
python -m blt_hf.entropy_data --plan "$PLAN" --output "$PREPARED"
python -m json.tool "$PREPARED/manifest.json"
exit
```

출력은 `train.jsonl`, `validation.jsonl`, `manifest.json`이다. exact 중복/hash 검사는 수행하지만
근접 중복·권리·PII 검토를 대신하지 않는다. manifest의 다음3개 값은 검토 완료 후에만 수정한다.
자료 파일을 바꾸면 기존 hash를 임의로 맞추지 말고 새 DATA_ID로 다시 준비한다.

```bash
vi "$PREPARED/manifest.json"
```

승인 필드: `license_approved`, `pii_review_approved`, `near_duplicate_split_review_approved`.
학습이 시작된 뒤에는 manifest나 원문을 변경하지 않는다.

## 7. 실행 설정 생성과 승인

새 설정은 승인 false/예산 null로 만든다. 아래 RUN_ID는 예시이며 기존 실행과 겹치지 않아야 한다.
`RUN_DIR` 자체는 만들지 않는다. 새 run 디렉터리는 실행기가 생성한다.

```bash
export RUN_ID=ko-entropy-h200-pilot-20261029-01
export CONFIG="$ROOT/artifacts/korean_entropy/configs/${RUN_ID}.json"
export RUN_DIR="$ROOT/outputs/korean_entropy/$RUN_ID"
python - <<'PY'
import json, os
from pathlib import Path
config = json.loads((Path(os.environ['BUNDLE']) / 'entropy.template.json').read_text())
config['dataset_manifest'] = str(Path(os.environ['PREPARED']) / 'manifest.json')
config['run_dir'] = os.environ['RUN_DIR']
with Path(os.environ['CONFIG']).open('x') as handle:
    json.dump(config, handle, indent=2)
    handle.write('\n')
PY
vi "$CONFIG"
python -m json.tool "$CONFIG"
```

합의된 양의 정수 예산5개 `max_steps`, `max_train_bytes`, `max_seconds`, `max_run_bytes`,
`max_gpu_memory_bytes`를 정하고, 검토 후 `training_authorized=true`로 바꾼다.
바이트 예산의 단위는 bytes, 시간은 seconds다. `max_train_bytes`는 반복 노출을 포함하는 누적 학습 바이트다.
2step 후 재개 검사를 하려면 최초부터 총 step/byte 예산이 그 이후까지 남도록 승인해야 한다.
GPU 예산은 실제 VRAM보다 작게, threads는 할당 CPU 이하로 지정한다.
`max_seconds`는 job의 남은 시간보다 최소900초 짧아야 한다. 모델 로드·해시·저장 시간 여유도 필요하다.

승인된 설정으로 다시 preflight를 제출하고 완료 후 `training_ready=true`를 확인한다.
실제 전체 자료 hash/중복 검사가 포함되므로 로그인 노드에서 직접 실행하지 않는다.

```bash
cd "$SUBMIT_ROOT"
unset RESUME
JOB_ID=$(sbatch --parsable --export=ALL,MODE=preflight "$BUNDLE/train_entropy.sh")
export JOB_ID="${JOB_ID%%;*}"
```

## 8. 최초 2step 파일럿

승인·preflight 확인 후 실행한다. `MODE=pilot`도 실제 pretrained optimizer를 실행한다.
기본2시간 할당이 부족하면 site 정책과 승인 예산 안에서 `--time`을 지정한다. 자동 확대하지 않는다.

```bash
cd "$SUBMIT_ROOT"
unset RESUME
JOB_ID=$(sbatch --parsable --export=ALL,MODE=pilot,PILOT_STEPS=2 "$BUNDLE/train_entropy.sh")
export JOB_ID="${JOB_ID%%;*}"
squeue -j "$JOB_ID"
```

job이 끝난 뒤 결과를 확인한다. `validation-*.json`이 없으면 검증 완료를 주장하지 않는다.

```bash
sacct -j "$JOB_ID" --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 40 "$ROOT/entropy-${JOB_ID}.out"
tail -n 40 "$ROOT/entropy-${JOB_ID}.err"
find "$RUN_DIR" -maxdepth 1 -type f -print
cat "$RUN_DIR/metrics.jsonl"
cat "$RUN_DIR/validation-00000002.json"
```

실제 step, 유한 손실/gradient, VRAM, bytes/s, checkpoint/sidecar와 validation을 검토한다.
2step 수치는 대규모 CPT 품질이나 충분한 처리량 측정을 뜻하지 않는다.

## 9. 동일 실행 재개와 본 학습

동일 CONFIG/자료/hash/런타임/장치를 유지한다. 파일럿 뒤 예산을 수정하면 resume identity가
달라져 거부된다. 다른 예산의 독립 본 학습은 별도 RUN_ID/CONFIG와 원본 공개 가중치로 시작한다.
checkpoint 파일명은 실제 완료 step에 맞춘다. 아래는2step 완료한 경우다.

```bash
export RESUME="$RUN_DIR/step-00000002.pt"
test -r "$RESUME"
test -r "${RESUME%.pt}.sha256"
test ! -e "$RUN_DIR/.active"
cd "$SUBMIT_ROOT"
JOB_ID=$(sbatch --parsable --export=ALL,MODE=pilot,PILOT_STEPS=2,RESUME "$BUNDLE/train_entropy.sh")
export JOB_ID="${JOB_ID%%;*}"
```

재개 파일럿이 총4step까지 완료했으며 실제 GPU 재개 검토와 본 학습 승인이 끝난 경우에만,
원래 승인된 총 예산 안에서 같은 실행을 이어간다.

```bash
export RESUME="$RUN_DIR/step-00000004.pt"
test -r "$RESUME"
test -r "${RESUME%.pt}.sha256"
test ! -e "$RUN_DIR/.active"
cd "$SUBMIT_ROOT"
JOB_ID=$(sbatch --parsable --export=ALL,MODE=train,RESUME "$BUNDLE/train_entropy.sh")
export JOB_ID="${JOB_ID%%;*}"
```

외부 checkpoint는 torch pickle 위험 때문에 사용하지 않는다. `.active`가 남으면 실행 중
프로세스가 없는지 먼저 확인하고 별도 복구 판단을 한다. 자동 삭제·최신 checkpoint 자동 선택은 하지 않는다.

## 10. 상태 확인과 저장 후 중단

```bash
squeue -u "$USER"
scontrol show job "$JOB_ID"
sacct -j "$JOB_ID" --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 40 "$ROOT/entropy-${JOB_ID}.out"
tail -n 40 "$ROOT/entropy-${JOB_ID}.err"
```

학습 실행기가 시작되어 metrics가 기록되는 상태에서 저장 후 중단을 요청한다.
preflight/모델 로드 단계에는 아직 학습 checkpoint가 없을 수 있다.

```bash
scancel --signal=USR1 --batch "$JOB_ID"
```

현재 step을 마친 뒤 저장하고 exit75로 끝난다. Slurm에는 FAILED로 보일 수 있으므로
로그의 `paused_signal`,완성된 `.pt`와 `.sha256`를 확인한다. SIGKILL/OOM/노드 장애에는
마지막 완성 checkpoint만 사용한다. 같은 job을 무조건 재제출하지 않는다.

## 11. GitHub를 통한 결과 전달

전달 경로는 **Neuron의 runtimelog → GitHub push → 로컬 pull → 결과 분석**이다.
Neuron의 실행과 업로드는 모두 사용자가 직접 수행한다. 실패 로그도 보존하며,
비밀정보·개인정보·원문이 출력된 부분은 제거한 사본만 올린다.
가중치/checkpoint/토큰은 Git에 올리지 않는다. 기존 Neuron 출력 경로는 변경하지 않는다.

### Neuron: 로그용 clone 준비

실행용 `/scratch/r984a02/blt-cache`는 고정 commit/detached HEAD를 유지한다.
실행 중 코드 변경과 detached HEAD에서의 push 혼동을 피하려고 **로그용 clone을 따로 둔다.**
처음 한 번만 다음을 실행한다. 기존 로그용 clone이 있으면 clone 명령은 생략한다.

```bash
git clone --filter=blob:none --sparse --branch main \
  https://github.com/esoterikosQ/26-14_CACHE.git "/scratch/r984a02/blt-cache-logs"
git -C "/scratch/r984a02/blt-cache-logs" sparse-checkout set runtimelog neuron
```

최신 명령 문서는 로그용 clone의 `neuron/command.md`에서 볼 수 있지만,
학습에 쓰는 BUNDLE은 계속 실행용 clone을 가리켜야 한다.
push 권한이 있는 기존 Git 인증을 사용한다. 토큰을 명령/URL/로그에 넣지 않는다.

### Neuron: 실행 결과 모으기

완료한 작업의 JOB_ID, 필요하면 RUN_DIR을 앞 절과 같이 지정한다.
아래는 새 preflight 결과 수집 예시다. 파일럿/학습이면 LOG_ID 접두부를 바꾸고
실제 RUN_DIR을 지정한다. 재queue된 job은 실제 RESTART 번호를 사용한다.
새 로그 디렉터리 이름을 사용하며 기존 결과를 덮어쓰지 않는다.

```bash
export LOG_REPO="/scratch/r984a02/blt-cache-logs"
git -C "$LOG_REPO" status --short
git -C "$LOG_REPO" pull --ff-only
: "${ROOT:?Set ROOT}" "${JOB_ID:?Set the completed JOB_ID}"
export RESTART=0
export LOG_ID="preflight-${JOB_ID}-${RESTART}"
export DEST="$LOG_REPO/runtimelog/$LOG_ID"
mkdir "$DEST"
```

mkdir가 실패하면 기존 디렉터리에 계속 복사하지 말고 새 LOG_ID를 지정한다.
작업에 따라 존재하는 작은 파일만 복사한다. 원본은 그대로 보존한다.

```bash
for path in "$ROOT/entropy-${JOB_ID}.out" "$ROOT/entropy-${JOB_ID}.err"; do
    if [[ -f "$path" ]]; then cp -n "$path" "$DEST/"; fi
done
REPORT_DIR="$ROOT/artifacts/korean_entropy/neuron-${JOB_ID}-${RESTART}"
for name in environment.json preflight.json config.json runtime-manifest.json; do
    if [[ -f "$REPORT_DIR/$name" ]]; then cp -n "$REPORT_DIR/$name" "$DEST/"; fi
done
if [[ -n "${RUN_DIR:-}" && -d "$RUN_DIR" ]]; then
    for name in contract.json metrics.jsonl; do
        if [[ -f "$RUN_DIR/$name" ]]; then cp -n "$RUN_DIR/$name" "$DEST/"; fi
    done
    find "$RUN_DIR" -maxdepth 1 -type f -name 'validation-*.json' -exec cp -n {} "$DEST/" \;
fi
sacct -j "$JOB_ID" --format=JobID,State,ExitCode,Elapsed,MaxRSS > "$DEST/slurm-status.txt"
git -C "/scratch/r984a02/blt-cache" rev-parse HEAD > "$DEST/runtime-commit.txt"
find "$DEST" -maxdepth 1 -type f -print
du -sh "$DEST"
```

**파일 내용을 직접 확인하고 민감정보를 제거한 뒤에만** 다음 단계로 진행한다.
공유 크기가 크면 필요한 로그 구간/요약을 남기고 원본은 Neuron에 보존한다.
다른 작업의 RUN_DIR을 실수로 묶지 않도록 config.json/contract.json의 run_dir도 대조한다.

### Neuron: 검토한 결과만 commit/push

기존 staged 변경이 있으면 먼저 그 작업을 정리한다. `git add .`는 사용하지 않는다.

```bash
git -C "$LOG_REPO" diff --cached --name-only
git -C "$LOG_REPO" add -- "runtimelog/$LOG_ID"
git -C "$LOG_REPO" diff --cached --stat
git -C "$LOG_REPO" diff --cached -- "runtimelog/$LOG_ID"
```

staged 목록이 해당 결과만 포함하는 것을 확인한 뒤 실행한다.

```bash
git -C "$LOG_REPO" commit -m "Record Neuron results: $LOG_ID"
git -C "$LOG_REPO" push origin main
git -C "$LOG_REPO" rev-parse HEAD
```

push가 원격 갱신으로 거부되면 강제 push하지 않는다. 로그용 clone에 미커밋 변경이 없는지
확인하고 `git pull --rebase origin main` 후 충돌이 없을 때만 다시 push한다.
충돌이 있으면 양쪽 로그를 보존하고 해결한다. 실행용 clone을 갱신하지 않는다.

### 로컬: GitHub에서 결과 받기

아래는 **Mac의 이 저장소 루트**에서 실행한다. Neuron 명령이 아니다.
기존 코드 변경을 보존하며, 충돌/덮어쓰기 경고가 나면 중단하고 별도로 확인한다.
`reset --hard`,강제 checkout,원본 로그 삭제를 하지 않는다.

```bash
git status --short
git pull --ff-only origin main
git log -1 --oneline -- runtimelog
find runtimelog -maxdepth 2 -type f -print
```

받은 결과의 디렉터리명/commit을 알려주면 해당 로그를 기준으로 분석한다.
한국어 본체5개 arm/교사 threshold 보정/최종 품질 비교/독립 평가 명령은 아직 구현되지 않았다.
이 명령표를 그 단계들의 실행 승인이나 완료 증거로 사용하지 않는다.