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

### 2026-10-30 수신 구조 확인

사용자가 아래 디렉터리별 JSON 개수와 대표1파일의 구조를 전달했다.
후속 확인에서 DIALOGUE_v1.2는 SPOKEN_v1.2를 중복 배치한 것이라고 확정했다.
그 사본은 사용자가 제거하며,아래10출처 카탈로그는 폴더가 남아 있어도 그 사본을 읽지 않는다.
모두 `data/korean_cpt/incoming/nikl` 바로 아래에 이미 풀려 있으므로 재해제하거나
아래 예시의 `extracted/CORPUS`로 옮길 필요가 없다. 원본 ZIP/JSON은 그대로 보존한다.
**제공된 train/validation/test 분할은 없다.** 아래 개수는 문서 수나 고유 문서 수가 아닌 JSON 파일 수다.

| 디렉터리 | JSON 파일 수 | 대표 파일 형식 |
| --- | ---: | --- |
| NIKL_DIALOGUE_2020_v1.4 | 2232 | nikl_utterance |
| NIKL_DIALOGUE_2021_v1.1 | 4143 | nikl_utterance |
| NIKL_DIALOGUE_2022_v1.0 | 2654 | nikl_utterance |
| NIKL_DIALOGUE_2023_v1.1 | 1973 | nikl_utterance |
| NIKL_DIALOGUE_2024_v1.0 | 3227 | nikl_utterance |
| NIKL_DIALOGUE_2025_v1.0 | 2927 | nikl_utterance |
| NIKL_OM_2021_v1.1 | 47421 | nikl_utterance |
| NIKL_SPOKEN_v1.2 | 25696 | nikl_utterance |
| NIKL_WRITTEN 2025_v1.0 | 10293 | nikl_paragraph |
| NIKL_WRITTEN(v1.2) | 10045 | nikl_paragraph |

중복 사본 제외 후 합계110611파일이며 각 폴더의 대표1파일만 확인한 결과다.
전체 파일은 아래 audit에서 확인하며 카탈로그의 예상 파일 수와 다르면 중단한다.
대표 JSON들은 `document[].id`와 `utterance[].form` 또는 `paragraph[].form`을 갖는다.
기존 변환기는 `form`을 LF로 연결하고 `original_form`/화자/시간/metadata 값은 학습 본문에 넣지 않는다.
OM 대표 JSON은 `document`4개를 담으며 나머지 대표 JSON은1개다. 분할 단위는 JSON 파일이나
발화/문단이 아니라 `document[]`의 문서다. 동일 문서의 발화/문단을 다른 split으로 나누지 않는다.

별도 `entropy_corpus`의 audit/split으로 전체 문서를 읽어 확인한다. 범위는 이번 NIKL10출처이며
FineWeb2 혼합이나 기존 평가 자료의 재분할은 하지 않는다. 수동 파일 배정 예시는 미분할 입력에
맞지 않아 제거했다. 자료 준비는 학습 실행이나 검토 승인과 다르다.

### 추가 ZIP이 있을 때만 해제

원본 ZIP은 `data/korean_cpt/incoming/nikl`에 그대로 둔다. 먼저 파일 목록과 디스크 여유를 확인한다.
아래 `CORPUS.zip`은 실제 받은 ZIP 파일명으로 바꾼다. unzip -l은 압축 해제 전 파일 목록과
비압축 크기를 보여준다. 목록에 절대경로나 `../`가 있으면 풀지 말고 확인한다.

```bash
find data/korean_cpt/incoming/nikl -type f -iname '*.zip' -print
df -h .
unzip -l data/korean_cpt/incoming/nikl/CORPUS.zip
```

추가 ZIP을 풀 때는 현재 셸의 blt-cache에서 다음을 실행한다. 별도 자원 할당은 필요 없다.
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

### 입력 형식과 보존 규칙

모든 `document[]`를 읽고 form을 LF로 연결한다. JSONL은 한 행에 문서1개와 `id`, `source`, `text`를 쓴다.
문서 내부의 빈 문자열 form은 삭제하지 않고 LF 구분자까지 보존하며 출처별 `empty_form_parts`로 집계한다.
UTF-8 본문은 정규화하거나 자르지 않는다. 단일 JSON512MiB 초과/JSONL 한 행16MiB 초과,
누락·비문자열 form/잘못된 schema/같은 source·ID의 다른 본문/심볼릭 링크는 중단한다.
문서 전체가 비거나 공백뿐인 경우도 기본은 중단한다. 아래 audit의 명시적
`--empty-document-policy quarantine`에서만 해당 문서의 LF 연결 본문·출처·ID·파일 위치·사유를
private SQLite의 `quarantine` 원장에 보존하고 학습 파생 JSONL에서 제외한다. 원본은 변경하지 않는다.
구조 오류는 원문 값 대신 발화·문단 위치와 자료형을 표시한다. original_form으로 자동 대체하지 않는다.
실패한 부분 산출물도 보존하며 새 버전 디렉터리로 다시 실행한다.

## 6. 현재 셸에서 자료 준비

스캔·분할·ZIP 해제는 현재 셸에서 직접 실행한다. Slurm/GPU/별도 CPU 할당은 필요 없다.
blt-cache에서 시작한다. 아직 nikl 위치라면 `cd ../../../..`로 먼저 돌아온다.
같은 출력 디렉터리는 재사용하지 않으며 실패한 부분 산출물도 보존한다.
이미 phdq_blt_hf 환경이면 conda activate도 생략한다.

```bash
conda activate phdq_blt_hf
python neuron/bundle.py verify
df -h .
```

### 6-1. 문서 및 중복 관계 audit

2026-10-30 사용자 실행의 nikl-v001은 첫 출처의 form 검사에서 실패했다. 실패 디렉터리는
삭제하거나 재사용하지 않는다. 후속 nikl-v002는 마지막 heartbeat87000파일/114244문서 이후
SPOKEN 문서의 발화4개가 모두 빈 문자열인 경우에 중단됐다. 코드 갱신 후 아래처럼 새 nikl-v003에서
내용 없는 문서의 명시적 격리 정책으로 처음부터 읽는다. 기존 부분 DB에 검증 가능한 재개
체크포인트가 없어 자동 재개하지 않는다. v001/v002와 원본은 보존한다.
아래 split과 보고서 복사도 같은 v003 audit를 가리킨다.

이미 풀린10폴더를 카탈로그대로 읽어 문서/본문 hash/출처/파일 hash를 SQLite에 기록한다.
전체 본문을 RAM에 모으지 않고 JSON1파일씩 읽으며 문서 연결 정보만 RAM에 둔다.
기본으로100GiB 여유 공간을 남기고,입력 파일 크기의2배를 추가 여유로 확인한다.
SQLite와 파생 JSONL이 모두 본문을 저장하므로 디스크 여유도 필요하다.100GiB는 최대 사용량이 아닌
최소 여유다. 처리 시간은 미측정이며 중단되면 새 audit 버전으로 다시 시작한다.

```bash
PYTHONPATH=neuron/runtime python -u -m blt_hf.entropy_corpus audit \
    --input-root data/korean_cpt/incoming/nikl \
    --sources neuron/runtime/plan/nikl_sources.json \
    --output data/korean_cpt/audits/nikl-v003 \
    --empty-document-policy quarantine
python -m json.tool data/korean_cpt/audits/nikl-v003/audit.json
```

500파일마다 진행 개수를 출력한다. 성공 보고서의 `status=complete`,출처별 files/documents/utf8_bytes,
`empty_form_parts`와 `empty_document_policy=quarantine`을 확인한다. 일부 form만 빈 문서는 LF까지 그대로 쓴다.
`input_documents`에는 격리 문서도 포함하고 `usable_documents`에는 격리되지 않은 문서만 센다.
전체 및 출처별 `quarantined_documents`, `quarantined_utf8_bytes`를 검토한다.
빈 form4개의 LF 연결 본문도3bytes이므로 격리 바이트가 반드시0인 것은 아니다.
격리 문서는 본문/ID 중복 연결과 대표 선택에 포함하지 않는다. 원문과 격리 원장은 보존한다.
`exact_duplicate_documents`, `groups`, `largest_group_unique_documents`를 확인한다.
중복·그룹 수는 격리되지 않은 문서 기준이며 같은 source/ID의 다른 본문 검사는 격리 원장에도 적용한다.
예상은10출처110611JSON이지110611문서가 아니다. 큰 그룹이나 source/ID 충돌은 원인을 확인한다.
실패한 audit에는 성공 표식인 audit.json이 없고 split은 진행하지 않는다.

그룹 연결은 다음 두 기준의 전이적 연결 성분이다.

- 출처가 달라도 동일한 문서 ID.
- 본문을 비교할 때만 NFC·공백 접기를 적용한 결과가 동일함.

원문 byte hash가 같은 중복은 정렬된 source/파일/문서 순서의 대표1개만 JSONL에 쓰며,
다른 출처/위치의 별칭은 SQLite에 보존한다. NFC/공백 비교만 같은 서로 다른 원문은 삭제하지 않고
같은 그룹에 둔다. 같은 ID의 다른 본문도 출처가 다르면 보수적으로 묶는다.
**퍼지·부분중복을 모두 찾는 검사는 아니다.** 따라서 근접 중복 검토 승인은 자동 설정하지 않는다.

### 6-2. 그룹 단위 split과 JSONL 생성

audit 결과 검토 후에만 실행한다. 아래는 train/validation/test 약98/1/1과 seed42를 선택하는 예시다.
사용자가 이 비율을 채택할 때 실행하며,다른 비율은 명시적으로 바꾼다. 학습 실행 승인은 아니다.
그룹 대표 hash와 seed로 split을 정하므로 같은 그룹은 분리되지 않고 재현된다.
이는 그룹 해시의 기대 비율이지 정확한 문서/바이트 할당량이나 출처별 층화 비율은 아니다.

```bash
PYTHONPATH=neuron/runtime python -u -m blt_hf.entropy_corpus split \
    --audit data/korean_cpt/audits/nikl-v003 \
    --output data/korean_cpt/prepared/korean-entropy-v001 \
    --validation-percent 1 --test-percent 1 --seed 42
python -m json.tool data/korean_cpt/prepared/korean-entropy-v001/report.json
```

split은 hash로 고정한 SQLite 스냅샷만 읽는다. 입력을 변경했다면 새 audit를 만들어야 한다.
실행 코드/SQLite hash가 바뀌면 기존 audit 재사용을 거부한다. 같은 출력 디렉터리는 재사용하지 않고
빈 split이면 중단한다. 결과는 `train.jsonl`, `validation.jsonl`, `test.jsonl`, `manifest.json`, `report.json`이다.
출처별 문서 수와 실제 바이트 수를 검토한다. manifest의 `splits`에는 train/validation만 있고
test는 `held_out_test`로 별도 보관해 학습에 넘기지 않는다. test는 교사·threshold·후보 선택에 쓰지 않는다.
manifest와 report에도 `empty_document_policy`, `quarantined_documents`가 고정된다.

### 6-3. 작은 보고서 전달

본문이나 ID/화자 실제 값을 포함하지 않는 audit.json/report.json만 검토 후 전달한다.
`index.sqlite`,JSONL,원본 JSON/ZIP은 Git에 추가하지 않는다. 먼저 audit만 돌렸다면 report 복사는 나중에 한다.

```bash
mkdir -p runtimelog
mkdir runtimelog/nikl-prep-v001 &&
cp -n data/korean_cpt/audits/nikl-v003/audit.json runtimelog/nikl-prep-v001/
```

split 완료 후 같은 로그 디렉터리에 다음 보고서만 추가한다. 선별 commit/push는11절을 따르되
대상 경로는 `runtimelog/nikl-prep-v001`을 직접 적는다.

```bash
cp -n data/korean_cpt/prepared/korean-entropy-v001/report.json runtimelog/nikl-prep-v001/
```

위 자료 준비는 근접 중복·PII 검토를 대신하지 않는다. 다음2개 값은 검토 완료 후에만 수정한다.
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