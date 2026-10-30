# Neuron 작업별 명령

모든 명령은 **사용자가 Neuron에서 직접 실행**한다. 셸은 bash 기준이다.
phdq3는 파일/정책을 참고하는 읽기 전용 프로젝트다. 이번 코드·설정·로그는 blt-cache에서만 관리한다.
현재 제공하는 실행기는 T12 한국어 entropy 교사용이며 본체 ENCODER/GLOBAL/BODY_FULL 학습용이 아니다.
영어20GB 작업은 itcerdo에서 별도로 실행하므로 여기서 다시 시작하지 않는다.
학습 자료의 형식·분할 확인, 학습 예산 확정, GPU 학습 파일럿은 아직 완료되지 않았다.

## 1. 저장 경로

제출 cwd는 `/scratch/r984a02`, 프로젝트 루트는 `/scratch/r984a02/blt-cache`다.
처음 clone할 때를 제외한 Neuron 명령은 `blt-cache`에서 시작한다.
제출할 때만 `cd ..`로 부모에 이동하고 제출 후 `cd blt-cache`로 돌아온다.
실행기가 요구하는 경로·모드는 sbatch 인자에 직접 적는다. 사전 변수 설정은 필요 없다.
job 내부 작업 cwd는 `neuron/runtime`이며 제출 cwd와 독립적이다. 아래 경로는 모두 Neuron 경로다.

| 용도 | 절대 경로 |
| --- | --- |
| sbatch 제출 cwd | `/scratch/r984a02` |
| GitHub 코드 사본 | `/scratch/r984a02/blt-cache` |
| 실행 bundle | `/scratch/r984a02/blt-cache/neuron` |
| NIKL 수령 원본 ZIP/JSON | `/scratch/r984a02/blt-cache/data/korean_cpt/incoming/nikl` |
| FineWeb2 수령 원본 | `/scratch/r984a02/blt-cache/data/korean_cpt/incoming/fineweb2` |
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

처음 한 번만 `/scratch/r984a02`에서 실행한다. 이미 `blt-cache` 안에 있으면
clone 블록을 건너뛰고 다음의 갱신 절차를 사용한다.
목적지가 이미 있고 clone이 아니라면 덮어쓰거나 삭제하지 말고 경로 상태를 먼저 확인한다.
이전 안내의 홈 디렉터리 clone이나 그곳을 쓰는 실행 중 job은 자동 이동/변경하지 않는다.

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/esoterikosQ/26-14_CACHE.git blt-cache
cd blt-cache
git sparse-checkout set neuron runtimelog
git rev-parse HEAD
```

기존 clone은 사용하는 job이 모두 끝난 뒤 갱신한다. `git status --short`에 변경이 있으면
먼저 보존하며 강제 checkout은 하지 않는다. 이전 안내로 detached HEAD라면 그 상태에서도
아래 merge는 현재 커밋을 보존한다. 로그 push는 현재 HEAD를 지정하므로 오래된 로컬 main을 올리지 않는다.
충돌이 나면 중단하고 충돌 내용을 확인한다. 예전 a0cfa52는 새 실행에 사용하지 않는다.

```bash
git status --short
git sparse-checkout add neuron runtimelog
git fetch origin
git merge --no-edit origin/main
git rev-parse HEAD
```

## 3. 매 로그인 시 환경과 디렉터리

이미 설치된 conda를 사용한다. `conda`가 초기화되지 않았다면 본인 설치 경로의
`etc/profile.d/conda.sh`를 먼저 source한다. 설치/업그레이드나 `module load cuda`는 하지 않는다.

```bash
conda activate phdq_blt_hf
mkdir -p data/korean_cpt/{incoming/nikl,incoming/fineweb2,manifests,prepared}
mkdir -p artifacts/korean_entropy/configs outputs/korean_entropy
python neuron/bundle.py verify
python -m unittest discover -s neuron -p test_bundle.py -v
df -h .
showque
showappl
```

최초 준비에서 아직 가중치를 복사하지 않았다면 아래를 한 번만 실행한다.
원본 경로는 사용자가 전달한 Neuron 파일 목록에서 확인했다. `outputs/.../step-*` 학습 checkpoint는 사용하지 않는다.
목적지가 이미 있으면 mkdir에서 중단한다. 원본과 실패한 복사본은 삭제하거나 덮어쓰지 않는다.

```bash
test -r ../phdq3/artifacts/converted/blt-1b-hf-own/config.json &&
test -r ../phdq3/artifacts/converted/blt-1b-hf-own/model.safetensors &&
mkdir -p artifacts/converted &&
mkdir artifacts/converted/blt-1b-hf-own &&
cp -L ../phdq3/artifacts/converted/blt-1b-hf-own/{config.json,model.safetensors} \
    artifacts/converted/blt-1b-hf-own/
```

준비된 파일을 확인한다. `READY`가 없으면 제출하지 않는다.
이 검사는 읽기 가능 여부만 확인하며 출처/hash·모델 로딩·호환성 검증 완료를 뜻하지 않는다.

```bash
test -r artifacts/converted/blt-1b-hf-own/config.json &&
test -r artifacts/converted/blt-1b-hf-own/model.safetensors &&
printf '%s\n' READY
```

새 blt-cache 경로에 기존 자료나 가중치가 자동으로 생기는 것은 아니다.
임의의 다른 HF 모델을 대신 내려받거나 기존 가중치를 덮어쓰지 않는다.
최소 디스크 여유는 현재 template 기준100GiB다. 큰 원문 변환/hash 검사는 로그인 노드에서 실행하지 않는다.

## 4. 데이터 없이 GPU 환경 검사

이 명령은 optimizer를 실행하지 않는다. H2001GPU/CPU8/RAM48G/2시간이 기본이다.
3절에서 프로젝트 디렉터리를 먼저 준비해야 Slurm이 절대경로 stdout/stderr를 열 수 있다.
이후 모든 sbatch도 같은 제출 cwd를 사용한다.

```bash
cd ..
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/neuron/entropy.template.json,MODE=preflight,RESUME= \
    blt-cache/neuron/train_entropy.sh
cd blt-cache
```

sbatch가 출력한 job 번호를 다음 명령에 직접 적는다. 아래 `953179`는 이미 수신한 환경 검사
job의 실제 번호이며 새 제출은 새 번호로 바꾼다. 정상 새 job의 restart 번호는0이다.
재queue된 job은 실제 보고서 경로를 확인한다.

```bash
squeue -j 953179
sacct -j 953179 --format=JobID,State,ExitCode,Elapsed,MaxRSS
cat artifacts/korean_entropy/neuron-953179-0/environment.json
cat artifacts/korean_entropy/neuron-953179-0/preflight.json
```

환경 `status=pass`와 `training_ready=true`는 다른 조건이다. 미승인 template은
`training_ready=false`가 정상이다. A100 검사만 필요하면 제출 시 `-p amd_a100nv_8`을 추가한다.
장치를 바꾼 결과를 같은 조건의 비교나 checkpoint 재개로 취급하지 않는다.

## 5. ZIP 해제와 입력 계획

원본 ZIP은 `data/korean_cpt/incoming/nikl`에 그대로 둔다. 먼저 파일 목록과 디스크 여유를 확인한다.
아래 `CORPUS.zip`은 실제 받은 ZIP 파일명으로 바꾼다. unzip -l은 압축 해제 전 파일 목록과
비압축 크기를 보여준다. 목록에 절대경로나 `../`가 있으면 풀지 말고 확인한다.

```bash
find data/korean_cpt/incoming/nikl -type f -iname '*.zip' -print
df -h .
unzip -l data/korean_cpt/incoming/nikl/CORPUS.zip
```

큰 압축 해제는 로그인 노드 대신6절의 할당 셸에서 한다. 할당 셸에서 blt-cache로 들어온 뒤
다음을 실행하고, 완료 후 `exit`로 로그인 셸에 돌아온다. 변환 명령은 아직 실행하지 않는다.
ZIP마다 다른 새 디렉터리를 사용한다. 이미 있는 목적지는 mkdir에서 중단하며 unzip -n은 덮어쓰지 않는다.

```bash
mkdir -p data/korean_cpt/incoming/nikl/extracted &&
mkdir data/korean_cpt/incoming/nikl/extracted/CORPUS &&
unzip -n data/korean_cpt/incoming/nikl/CORPUS.zip \
    -d data/korean_cpt/incoming/nikl/extracted/CORPUS
```

여러 ZIP이면 파일명과 목적지 `CORPUS`를 각각 바꿔 같은 명령을 반복한다. 암호를 요구하면
터미널에 직접 입력하고 채팅이나 명령 인자에 넣지 않는다. 원본 ZIP은 삭제하지 않는다.
압축 해제 실패나 파일명 깨짐이 있으면 변환을 진행하지 말고 오류를 확인한다.

로그인 셸의 blt-cache에서 JSON 파일 목록을 확인하고 입력 계획을 만든다.

```bash
find data/korean_cpt/incoming/nikl/extracted -type f -iname '*.json' -print
python - <<'PY'
import json
from pathlib import Path
root = Path.cwd()
plan = {'files': [
    {'path': str(root / 'data/korean_cpt/incoming/nikl/extracted/CORPUS/REPLACE_TRAIN.json'),
     'source': 'REPLACE_NIKL_CORPUS_VERSION', 'split': 'train', 'format': 'nikl_paragraph'},
    {'path': str(root / 'data/korean_cpt/incoming/nikl/extracted/CORPUS/REPLACE_VALIDATION.json'),
     'source': 'REPLACE_NIKL_CORPUS_VERSION', 'split': 'validation', 'format': 'nikl_paragraph'}
]}
with Path('data/korean_cpt/manifests/korean-entropy-v001.json').open('x') as handle:
    json.dump(plan, handle, ensure_ascii=False, indent=2)
    handle.write('\n')
PY
vi data/korean_cpt/manifests/korean-entropy-v001.json
python -m json.tool data/korean_cpt/manifests/korean-entropy-v001.json
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
ZIP 해제도 이 할당 셸에서 한다. CPU partition 전환은 이번 명령표 수정에 포함하지 않았다.

```bash
cd ..
srun --partition=amd_h200nv_8 --nodes=1 --ntasks=1 --gres=gpu:1 \
  --cpus-per-task=8 --mem=48G --time=02:00:00 \
  --comment='field=nlp;appl=pytorch' --pty bash
```

할당된 셸은 부모 디렉터리에서 시작한다. 아래처럼 blt-cache로 들어가 실행한다.
같은 출력 디렉터리는 재사용하지 않으며 실패한 부분 산출물도 보존한다.

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate phdq_blt_hf
cd blt-cache
python neuron/runtime/blt_hf_checks/check_env.py
```

최초 ZIP 해제가 목적이면 여기서5절의 unzip 명령만 실행한다.
해제와 입력 계획 수정까지 끝났으면 아래 변환 명령을 실행한다.

```bash
OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8 PYTHONPATH=neuron/runtime \
    python -m blt_hf.entropy_data \
    --plan data/korean_cpt/manifests/korean-entropy-v001.json \
    --output data/korean_cpt/prepared/korean-entropy-v001
python -m json.tool data/korean_cpt/prepared/korean-entropy-v001/manifest.json
```

작업을 마치면 할당 셸을 종료하고 로그인 셸에서 프로젝트로 돌아온다.

```bash
exit
```

다음 명령은 할당 셸 종료 후 로그인 셸에서 실행한다.

```bash
cd blt-cache
```

출력은 `train.jsonl`, `validation.jsonl`, `manifest.json`이다. exact 중복/hash 검사는 수행하지만
근접 중복·PII 검토를 대신하지 않는다. 다음2개 값은 검토 완료 후에만 수정한다.
자료 파일을 바꾸면 기존 hash를 임의로 맞추지 말고 새 데이터 이름으로 다시 준비한다.

```bash
vi data/korean_cpt/prepared/korean-entropy-v001/manifest.json
```

검토 필드: `pii_review_approved`, `near_duplicate_split_review_approved`.
학습이 시작된 뒤에는 manifest나 원문을 변경하지 않는다.

## 7. 실행 설정 생성과 승인

새 설정은 승인 false/예산 null로 만든다. 아래 실행명은 예시이며 기존 실행과 겹치지 않아야 한다.
새 run 디렉터리는 만들지 않는다. 실행기가 생성한다.

```bash
python - <<'PY'
import json
from pathlib import Path
config = json.loads(Path('neuron/entropy.template.json').read_text())
config['dataset_manifest'] = str(Path('data/korean_cpt/prepared/korean-entropy-v001/manifest.json').resolve())
config['run_dir'] = str(Path('outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01').resolve())
with Path('artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json').open('x') as handle:
    json.dump(config, handle, indent=2)
    handle.write('\n')
PY
vi artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json
python -m json.tool artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json
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
cd ..
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=preflight,RESUME= \
    blt-cache/neuron/train_entropy.sh
cd blt-cache
```

## 8. 최초 2step 파일럿

승인·preflight 확인 후 실행한다. `MODE=pilot`도 실제 pretrained optimizer를 실행한다.
기본2시간 할당이 부족하면 site 정책과 승인 예산 안에서 `--time`을 지정한다. 자동 확대하지 않는다.

```bash
cd ..
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=pilot,PILOT_STEPS=2,RESUME= \
    blt-cache/neuron/train_entropy.sh
cd blt-cache
```

sbatch가 출력한 번호로4절처럼 squeue/sacct를 확인한다. 아래 `JOB_NUMBER`는 그 실제 번호로 바꾼다.
job이 끝난 뒤 확인하며 `validation-*.json`이 없으면 검증 완료를 주장하지 않는다.

```bash
sacct -j JOB_NUMBER --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 40 entropy-JOB_NUMBER.out
tail -n 40 entropy-JOB_NUMBER.err
find outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01 -maxdepth 1 -type f -print
cat outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/metrics.jsonl
cat outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/validation-00000002.json
```

실제 step, 유한 손실/gradient, VRAM, bytes/s, checkpoint/sidecar와 validation을 검토한다.
2step 수치는 대규모 CPT 품질이나 충분한 처리량 측정을 뜻하지 않는다.

## 9. 동일 실행 재개와 본 학습

동일 설정/자료/hash/런타임/장치를 유지한다. 파일럿 뒤 예산을 수정하면 resume identity가
달라져 거부된다. 다른 예산의 독립 본 학습은 별도 실행명/설정과 원본 공개 가중치로 시작한다.
checkpoint 파일명은 실제 완료 step에 맞춘다. 아래는2step 완료한 경우다.

```bash
test -r outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000002.pt &&
test -r outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000002.sha256 &&
test ! -e outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/.active &&
cd .. &&
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=pilot,PILOT_STEPS=2,RESUME=/scratch/r984a02/blt-cache/outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000002.pt \
    blt-cache/neuron/train_entropy.sh
```

제출 단계까지 갔다면 `cd blt-cache`로 돌아온다. 사전 검사에서 중단됐으면 이동하지 않는다.

```bash
cd blt-cache
```

재개 파일럿이 총4step까지 완료했으며 실제 GPU 재개 검토와 본 학습 승인이 끝난 경우에만,
원래 승인된 총 예산 안에서 같은 실행을 이어간다.

```bash
test -r outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000004.pt &&
test -r outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000004.sha256 &&
test ! -e outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/.active &&
cd .. &&
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=train,RESUME=/scratch/r984a02/blt-cache/outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000004.pt \
    blt-cache/neuron/train_entropy.sh
```

제출 단계까지 갔다면 `cd blt-cache`로 돌아온다. 사전 검사에서 중단됐으면 이동하지 않는다.

외부 checkpoint는 torch pickle 위험 때문에 사용하지 않는다. `.active`가 남으면 실행 중
프로세스가 없는지 먼저 확인하고 별도 복구 판단을 한다. 자동 삭제·최신 checkpoint 자동 선택은 하지 않는다.

## 10. 상태 확인과 저장 후 중단

```bash
squeue -u r984a02
scontrol show job JOB_NUMBER
sacct -j JOB_NUMBER --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 40 entropy-JOB_NUMBER.out
tail -n 40 entropy-JOB_NUMBER.err
```

학습 실행기가 시작되어 metrics가 기록되는 상태에서 저장 후 중단을 요청한다.
preflight/모델 로드 단계에는 아직 학습 checkpoint가 없을 수 있다.

```bash
scancel --signal=USR1 --batch JOB_NUMBER
```

현재 step을 마친 뒤 저장하고 exit75로 끝난다. Slurm에는 FAILED로 보일 수 있으므로
로그의 `paused_signal`,완성된 `.pt`와 `.sha256`를 확인한다. SIGKILL/OOM/노드 장애에는
마지막 완성 checkpoint만 사용한다. 같은 job을 무조건 재제출하지 않는다.

## 11. GitHub를 통한 결과 전달

전달 경로는 **Neuron의 runtimelog → GitHub push → 로컬 pull → 결과 분석**이다.
Neuron의 실행과 업로드는 모두 사용자가 직접 수행한다. 실패 로그도 보존하며,
비밀정보·개인정보·원문이 출력된 부분은 제거한 사본만 올린다.
가중치/checkpoint/토큰은 Git에 올리지 않는다. 기존 Neuron 출력 경로는 변경하지 않는다.

### Neuron: 실행 결과 모으기

별도 clone 없이 현재 blt-cache의 `runtimelog`에 검토한 로그를 넣는다.
아래는 완료한 환경 검사953179의 예시다. 새 job은 번호와 디렉터리 이름을 직접 바꾼다.
재queue된 job은 보고서 경로의 restart 번호도 실제 값으로 바꾼다.

```bash
git sparse-checkout add runtimelog
mkdir -p runtimelog
mkdir runtimelog/preflight-953179-0
```

마지막 mkdir가 실패하면 기존 결과를 덮어쓰지 말고 새 이름을 정한다.
아래 파일이 실제로 있는지 확인한 뒤 복사한다. 원본은 그대로 보존한다.

```bash
cp -n entropy-953179.out entropy-953179.err runtimelog/preflight-953179-0/
cp -n artifacts/korean_entropy/neuron-953179-0/{environment.json,preflight.json,config.json,runtime-manifest.json} \
  runtimelog/preflight-953179-0/
sacct -j 953179 --format=JobID,State,ExitCode,Elapsed,MaxRSS \
  > runtimelog/preflight-953179-0/slurm-status.txt
find runtimelog/preflight-953179-0 -maxdepth 1 -type f -print
du -sh runtimelog/preflight-953179-0
```

파일럿/학습 결과라면 별도 새 로그 디렉터리에 해당 실행의 `contract.json`, `metrics.jsonl`,
`validation-*.json`도 복사한다. `.pt`, `.safetensors`,원문은 복사하지 않는다.
이미 원본 .out/.err를 runtimelog 최상위에 올린 기존 결과는 그대로 보존한다.

**파일 내용을 직접 확인하고 민감정보를 제거한 뒤에만** 다음 단계로 진행한다.
공유 크기가 크면 필요한 로그 구간/요약을 남기고 원본은 Neuron에 보존한다.
다른 실행을 묶지 않도록 config.json/contract.json의 run_dir도 대조한다.

### Neuron: 검토한 결과만 commit/push

기존 staged 변경이 있으면 먼저 그 작업을 정리한다. `git add .`는 사용하지 않는다.

```bash
git status --short --branch
git diff --cached --name-only
git add -- runtimelog/preflight-953179-0
git diff --cached --stat
git diff --cached -- runtimelog/preflight-953179-0
```

staged 목록이 해당 결과만 포함하는 것을 확인한 뒤 commit한다.

```bash
git commit -m "Record Neuron preflight 953179"
```

이 clone을 사용하는 job이 모두 끝난 뒤 원격 변경을 합치고 현재 커밋을 올린다.
`HEAD:main`은 detached HEAD에서도 방금 만든 로그 커밋을 올린다. 오래된 로컬 main을 지정하지 않는다.
토큰은 명령/URL/로그에 넣지 않는다. 충돌이나 거부가 나면 강제 push하지 않는다.

```bash
git fetch origin &&
git merge --no-edit origin/main &&
git push origin HEAD:main
git rev-parse HEAD
```

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