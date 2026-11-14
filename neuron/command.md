# Neuron 작업별 명령

모든 명령은 **사용자가 Neuron에서 직접 실행**한다. 셸은 bash 기준이다.
phdq3는 파일/정책을 참고하는 읽기 전용 프로젝트다. 이번 코드·설정·로그는 blt-cache에서만 관리한다.
현재 제공하는 실행기는 T12 한국어 entropy 교사용이며 본체 ENCODER/HASH/BODY_FULL 학습용이 아니다.
영어20GB 작업은 itcerdo에서 별도로 실행하므로 여기서 다시 시작하지 않는다.
NIKL audit/split은 사용자 보고서로 완료를 확인했다. FineWeb2 전체 train 확보/통합은 아래6-4절을 따른다.
통합 자료 검토, 학습 예산 확정, GPU 학습 파일럿은 아직 완료되지 않았다.

## 1. 저장 경로

프로젝트 루트이자 sbatch 제출 cwd는 `/scratch/r984a02/blt-cache`다.
처음 clone할 때를 제외한 모든 Neuron 명령과 sbatch 제출은 이 디렉터리에서 한다. 디렉터리를 옮기지 않는다.
실행기가 요구하는 경로·모드는 sbatch 인자에 직접 적는다. 사전 변수 설정은 필요 없다.
job 내부 작업 cwd는 `neuron/runtime`이며 제출 cwd와 독립적이다. 아래 경로는 모두 Neuron 경로다.

| 용도 | 절대 경로 |
| --- | --- |
| sbatch 제출 cwd | `/scratch/r984a02/blt-cache` |
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
| SLURM stdout/stderr | `/scratch/r984a02/blt-cache/runtimelog/entropy-<JOB_ID>.out` 및 `.err` |

**원문과 가중치를 Git에 추가하지 않는다.** 프로젝트 내 `data/`, `artifacts/`, `outputs/`는
Git 제외 경로다. 로그 전달도 아래의 검토한 `runtimelog`만 stage한다. 기존 `data/Preprocessed`, `data/Raw`,
GEC checkpoint와 원본 말뭉치를 덮어쓰거나 재분할하지 않는다. NIKL 원본 ZIP은 보존하고,
해제본은 별도 하위 디렉터리에 둔다. NIKL 변환기는 ZIP을 직접 읽지 않는다.
FineWeb2 수집/Parquet 변환/통합은 opt-in `blt_hf.entropy_fineweb`을 사용한다.

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
아래 merge --ff-only는 현재 커밋을 보존한 채 갱신할 수 있다. 인자 없는 git pull --ff-only는
detached HEAD에서 upstream을 결정하지 못하므로 사용하지 않는다. 로그 push는 현재 HEAD를
지정하므로 오래된 로컬 main을 올리지 않는다. fast-forward 불가/로컬 변경 충돌이면 중단하고
현재 이력을 보존한다. 강제 reset/checkout이나 임의 merge commit을 만들지 않는다.
예전 a0cfa52는 새 실행에 사용하지 않는다.

```bash
git status --short
git sparse-checkout add neuron runtimelog
git fetch origin
git merge --ff-only origin/main
git rev-parse HEAD
python neuron/bundle.py verify
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
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/neuron/entropy.template.json,MODE=preflight,RESUME= \
    neuron/train_entropy.sh
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

### 6-4. FineWeb2 한국어 전체 train 확보 및 NIKL 통합

2026-11-01 사용자 선택은 **한국어 train 전체**, 새 산출물 상한은 **10TB
(10000000000000bytes)**다. 고정 revision `af9c13333eb981300149d5ca60a8e9d659b276b9`의
`kor_Hang/train`25개 Parquet 메타데이터 합계는105767105257압축bytes다.
공식 `kor_Hang/test`는 catalog에서 보류하고 내려받지 않는다. 전체 원문 선택은 학습
노출량이나75/15/10 replay 혼합 비율 승인과 다르다. 임의로 자료를 잘라 예산을 맞추지 않는다.

기존 conda `phdq_blt_hf`에서 자료 준비/다운로드/통합을 모두 실행한다. 이미 활성화돼
있으면 activate는 생략한다. interpreter 경로와 PyArrow 설치 상태/버전을 먼저 확인한다
(합성 Parquet 검사에 사용한 버전은26.0.0). venv나 별도 준비 환경을 만들지 않고
패키지를 자동 설치/업그레이드하지 않는다. 의존성이 없거나 호환되지 않으면 중단하고
기존 환경의 고정 버전 및 실행 중 작업 영향을 확인한 뒤 사용자 승인을 받는다.
이번 변경이 반영된 코드에서 bundle verify를 실행한다.
NIKL audit nikl-v003와 prepared korean-entropy-v001은 그대로 보존한다.

```bash
conda activate phdq_blt_hf &&
command -v python &&
python -c 'import sys, pyarrow; print(sys.executable); print("pyarrow", pyarrow.__version__)' &&
python neuron/bundle.py verify &&
PYTHONPATH=neuron/runtime python -u -m blt_hf.entropy_fineweb catalog \
    --output data/korean_cpt/manifests/fineweb2-kor-full-v001.json
```

catalog는 공개 API의 고정 경로/크기/LFS SHA256을 검증해 새 파일에 기록한다.
이미 있는 catalog를 덮어쓰지 않는다. 실제 다운로드는 다음 명령이다.

```bash
OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 \
PYTHONPATH=neuron/runtime python -u -m blt_hf.entropy_fineweb download \
    --catalog data/korean_cpt/manifests/fineweb2-kor-full-v001.json \
    --output data/korean_cpt/incoming/fineweb2/full-v001 \
    --max-output-bytes 10000000000000 --min-free-gib 100 --memory-limit-gib 48
```

모든 원본 Parquet는 보존하고 SHA/크기를 확인한다.32행 batch로 id/source/text JSONL을
gzip 변환하며 본문을 trim/NFC 변환하거나 빈 본문을 버리지 않는다. 빈 본문은 통합
quarantine 입력으로 보존한다. 일부 web 문서의 최대16MiB 기록 한도 초과/잘못된 schema는
원본을 보존하고 중단한다. 이는 자동 품질 필터나 개인정보 정제 완료를 뜻하지 않는다.

download의 `report.json`에서 `status=complete`와25shard를 확인한다. 중단 후 재개는
같은 코드/catalog/예산에서 다음처럼 명시한다. 완성 파일을 다시 받아 덮어쓰지 않고,
검증된 부분 다운로드는 Range로 재개한다. 미완료 변환본은 별도 이름으로 보존하고 다시 변환한다.

```bash
OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 \
PYTHONPATH=neuron/runtime python -u -m blt_hf.entropy_fineweb download \
    --catalog data/korean_cpt/manifests/fineweb2-kor-full-v001.json \
    --output data/korean_cpt/incoming/fineweb2/full-v001 \
    --max-output-bytes 10000000000000 --min-free-gib 100 --memory-limit-gib 48 --resume
```

전체 다운로드 완료 후 통합한다. 새로운 보호 역할 충돌을 임의로 해소하거나 기존 NIKL
train/validation/test를 재배정하지 않는다. 이 단계는 새 디렉터리에서만 실행하며,
통합 중단의 임의 재개는 지원하지 않는다. 실패 산출물을 보존하고 원인을 검토한다.

```bash
OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 \
PYTHONPATH=neuron/runtime python -u -m blt_hf.entropy_fineweb combine \
    --nikl-audit data/korean_cpt/audits/nikl-v003 \
    --nikl-manifest data/korean_cpt/prepared/korean-entropy-v001/manifest.json \
    --fineweb-report data/korean_cpt/incoming/fineweb2/full-v001/report.json \
    --output data/korean_cpt/prepared/korean-entropy-nikl-fineweb-v001 \
    --max-output-bytes 10000000000000 --min-free-gib 100 --memory-limit-gib 48 &&
python -m json.tool data/korean_cpt/prepared/korean-entropy-nikl-fineweb-v001/report.json
```

NIKL 원장을 read-only backup한 새 private SQLite에서 문서 ID/NFC·공백 본문 연결을
통합한다. 연결된 FineWeb 그룹은 기존 NIKL 역할을 따르고,새 그룹만 기존seed42/1%/1%
정책을 사용한다. 두 NIKL 보호 역할을 잇는 문서는 오류로 중단한다. 정확 중복은 기존
NIKL 대표를 우선하며 빈 본문은 private 격리 원장에 남긴다. 퍼지/부분중복 검토는 별도다.

통합 다운로드 원본/gzip JSONL과 새 SQLite/파생 JSONL을 합쳐10TB 상한을 검사하고,
실제 디스크 최소 가용100GiB·주소공간48GiB를 유지한다.10TB가 실제 가용 용량이라고
가정하거나 파일을 삭제해 자동으로 여유를 만들지 않는다. 진행은 각 output의
`progress.json`, 성공은 `report.json`의 complete로 구분한다. traceback 후 progress의
running 표시는 성공이 아니다. Neuron 접속/실행은 사용자 담당이며 별도 Slurm CPU 할당을 요구하지 않는다.

학습은 검토 후 **통합** `korean-entropy-nikl-fineweb-v001/manifest.json`을 사용한다.
manifest의 splits에는 train/validation만 있고 test는 held_out_test다. PII/근접 중복 검토
플래그는 false를 유지한다. 두 출처의 실제 문서/바이트 비중은 보고서로 확인하며
학습 sampling/replay 비율·노출 예산을 자동 확정하지 않는다. Git에 원문/SQLite/JSONL을
추가하지 않는다. 로그용 작은 보고서도 공개 경로·합계·hash만 검토 후 전달한다.

### 6-5. 빠른 통합(native, 2026-11-05)

위 SQLite 통합은 문서마다 본문을 DB에 넣어 수 일이 걸리고 재개가 없다. 2026-11-05 사용자
결정으로 같은 분할 결과를 만드는 `blt_hf.entropy_combine`으로 다시 실행한다. 입력 검증,
그룹 규칙(ID/NFC·공백 정규화 본문 연결), NIKL 역할 보존, 새 그룹 seed 해시, 대표 문서
선택, 출력 순서는 그대로다. train/validation/test JSONL과 manifest.json이 기존 구현과
바이트 단위로 같음을 합성·실제 FineWeb2 표본으로 확인했다. 본문은 DB에 넣지 않고
문서별 SHA-256만 메모리에 두며, shard를 병렬로 해시하고 해시 첫 바이트 버킷 정렬로 쓴다.
FineWeb 빈 본문 격리 원장은 `quarantine.jsonl`이다(private, Git 금지).

C++11 컴파일러가 필요하다. 먼저 확인하고, 없으면 사용 가능한 gcc 모듈을 load한 뒤 다시 확인한다.
진행 중인 SQLite 통합을 중단할지와 그 산출물 정리는 사용자가 결정한다(이 명령은 지우지 않는다).
새 출력 디렉터리를 사용한다. `--workers`는 이 셸에서 쓸 수 있는 CPU 수 이하로 정한다.

```bash
conda activate phdq_blt_hf &&
c++ --version | head -n 1 &&
python neuron/bundle.py verify &&
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONPATH=neuron/runtime python -u -m blt_hf.entropy_combine \
    --nikl-audit data/korean_cpt/audits/nikl-v003 \
    --nikl-manifest data/korean_cpt/prepared/korean-entropy-v001/manifest.json \
    --fineweb-report data/korean_cpt/incoming/fineweb2/full-v001/report.json \
    --output data/korean_cpt/prepared/korean-entropy-nikl-fineweb-native-v001 \
    --max-output-bytes 10000000000000 --min-free-gib 100 --memory-limit-gib 48 \
    --workers 8 2>&1 | tee data/korean_cpt/prepared/combine-native-v001.log
```

진행은 표준 출력의 stage(scan → group → buckets → merge)와 출력의 `progress.json`으로 본다.
시작 직후 출력 크기·여유 공간을 미리 검사하며(입력 본문의 약 2배), 부족하면 작업 전에 실패한다.
성공하면 `report.json` status=complete다. 재개는 지원하지 않으며 실패 시 새 디렉터리로 다시 실행한다.
학습에는 `korean-entropy-nikl-fineweb-native-v001/manifest.json`을 사용한다.

## 7. 실행 설정 생성과 승인

새 설정은 승인 false/예산 null로 만든다. 아래 실행명은 예시이며 기존 실행과 겹치지 않아야 한다.
새 run 디렉터리는 만들지 않는다. 실행기가 생성한다.

```bash
python - <<'PY'
import json
from pathlib import Path
config = json.loads(Path('neuron/entropy.template.json').read_text())
config['dataset_manifest'] = str(Path('data/korean_cpt/prepared/korean-entropy-nikl-fineweb-v001/manifest.json').resolve())
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
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=preflight,RESUME= \
    neuron/train_entropy.sh
```

## 8. 최초 2step 파일럿

승인·preflight 확인 후 실행한다. `MODE=pilot`도 실제 pretrained optimizer를 실행한다.
기본2시간 할당이 부족하면 site 정책과 승인 예산 안에서 `--time`을 지정한다. 자동 확대하지 않는다.

```bash
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=pilot,PILOT_STEPS=2,RESUME= \
    neuron/train_entropy.sh
```

sbatch가 출력한 번호로4절처럼 squeue/sacct를 확인한다. 아래 `JOB_NUMBER`는 그 실제 번호로 바꾼다.
job이 끝난 뒤 확인하며 `validation-*.json`이 없으면 검증 완료를 주장하지 않는다.

```bash
sacct -j JOB_NUMBER --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 40 runtimelog/entropy-JOB_NUMBER.out
tail -n 40 runtimelog/entropy-JOB_NUMBER.err
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
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=pilot,PILOT_STEPS=2,RESUME=/scratch/r984a02/blt-cache/outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000002.pt \
    neuron/train_entropy.sh
```

재개 파일럿이 총4step까지 완료했으며 실제 GPU 재개 검토와 본 학습 승인이 끝난 경우에만,
원래 승인된 총 예산 안에서 같은 실행을 이어간다.

```bash
test -r outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000004.pt &&
test -r outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000004.sha256 &&
test ! -e outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/.active &&
sbatch --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-pilot-20261029-01.json,MODE=train,RESUME=/scratch/r984a02/blt-cache/outputs/korean_entropy/ko-entropy-h200-pilot-20261029-01/step-00000004.pt \
    neuron/train_entropy.sh
```

외부 checkpoint는 torch pickle 위험 때문에 사용하지 않는다. `.active`가 남으면 실행 중
프로세스가 없는지 먼저 확인하고 별도 복구 판단을 한다. 자동 삭제는 하지 않는다.

### 다음 작업 미리 걸기

`RESUME=latest`는 config의 `run_dir`에서 `.sha256`까지 기록된 가장 최근 `step-*.pt`를 고른다.
`.active`가 남아 있거나 완성된 checkpoint가 없으면 그 job은 시작 직후 실패한다.
각 job은 종료10분 전 신호로 저장하고 exit75로 끝나므로(Slurm에는 FAILED) 의존성은 `afterany`를 쓴다.
학습이 먼저 끝나면 이후 job은 `already_finished`를 출력하고 바로 종료한다. 남은 job은 `scancel`로 지워도 된다.

```bash
CONFIG=/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/ko-entropy-h200-20261107-01.json
sbatch --dependency=afterany:이전_JOB_번호 --time=24:00:00 --export=ALL,BUNDLE=/scratch/r984a02/blt-cache/neuron,CONFIG=$CONFIG,MODE=train,RESUME=latest neuron/train_entropy.sh
squeue -u r984a02
```

대기 사유가 `(Dependency)`로 보여야 이전 job 뒤에 실행된다.

## 10. 상태 확인과 저장 후 중단

```bash
squeue -u r984a02
scontrol show job JOB_NUMBER
sacct -j JOB_NUMBER --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 40 runtimelog/entropy-JOB_NUMBER.out
tail -n 40 runtimelog/entropy-JOB_NUMBER.err
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
Slurm job의 `.out`/`.err`는 처음부터 `runtimelog/entropy-<JOB_ID>.out`/`.err`로 기록된다.
preflight 보고서, 학습 step(처음 20개와 100 step마다), 검증 결과, 종료 상태가 모두 `.out`에 있다.
따로 복사할 파일은 없다. 가중치/checkpoint/원문/토큰은 Git에 올리지 않는다.

`blt-cache`에서 실행한다. `git add .`는 쓰지 않는다. 충돌이나 거부가 나면 강제 push하지 않는다.

```bash
git add runtimelog
git commit -m "Neuron logs"
git fetch origin && git merge --no-edit origin/main && git push origin HEAD:main
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
본체 ENCODER/HASH/BODY_FULL 학습 명령은 아직 구현되지 않았다.

## 12. 패처 비교(BLT 기준·threshold 보정·PATCHER)

공개 본체를 고정하고 패처(공개, run1 final, run2 final)와 threshold만 바꿔 한국어 본체 BPB를 잰다.
한 job이 세 단계를 모두 한다. 영어 평가는 하지 않는다.

1. threshold 보정: 두 run이 읽지 않은 train 뒷부분에서 무작위 문서 약 20MB를 뽑아, 패처마다
   평균 패치 길이 4 / 4.5 / 6 / 8 bytes가 되는 threshold를 찾는다.
2. BLT 기준: 공개 패처 + 공개 threshold(설정값 1.3354).
3. PATCHER: 3개 패처 × 4개 길이. validation 앞 5000문서(패처 학습 때 쓴 검증 표본)로 평가한다.

입력 경로(manifest·공개 모델)는 두 run의 `contract.json`에서 읽고 해시를 검사한다.
H200 1GPU, 예상 3~4시간(최대 12시간 할당). 코드 갱신(2절) 뒤 `blt-cache`에서 제출한다.
`RUN_ID`는 매번 새 이름을 쓴다.

```bash
sbatch --export=ALL,RUN_ID=ko-patcher-compare-20261114-01 neuron/compare_patchers.sh
```

로그는 `runtimelog/patcher-compare-<JOB_ID>.out`/`.err`에 바로 기록된다. 100문서마다 진행 BPB,
끝에 요약 JSON(threshold, 설정별 BPB·패치 통계, 비교 구간, 경계 일치도)이 찍힌다.
문서별 상세는 `outputs/korean_patcher_compare/<RUN_ID>/report.json`에 남으며 Git에 올리지 않는다.
끝나면 11절처럼 `runtimelog`만 push한다.