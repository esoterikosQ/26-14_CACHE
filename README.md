# PHDQ BLT cache

`phdq3`가 사용하는 변환 BLT 모델용 실험적 캐시이며, 명시적으로 선택해야 동작한다.
이 저장소는 학습 저장소와 독립되어 있으며 캐시 구현, 테스트, 설계 이력, 실험 계획,
작은 JSON 근거 자료를 담는다. 모델 가중치, 데이터셋, 토크나이저 파일,
신경망 모델 학습 코드, Slurm 작업은 포함하지 않는다.

현재 guarded 경로는 생성되는 모든 바이트마다 엔트로피 패칭과 로컬 인코더를
다시 계산한다. 패치 시작점이 바뀌지 않으면 전역 트랜스포머 결과를 재사용하고,
허용된 상위 두 바이트 logit의 차이가 설정한 guard margin 이내이면 전체 forward로
갱신한다. 검증된 guarded 경로에서는 디코더 KV 재사용을 끈다. 공개
`GlobalPrefixReuse` 클래스는 `phdq3`의 OSC BLT 모듈 구조를 전제로 하며,
범용 Transformers 캐시가 아니다.

```bash
python -m pip install --no-deps "phdq-blt-cache @ git+https://github.com/esoterikosQ/blt-cache.git@<COMMIT_SHA>"
```

위 GitHub URL은 **향후 저장소의 예시**이며 아직 배포된 의존성이 아니다.
새 저장소를 만들고 테스트한 뒤 실제 commit을 고정한다. 실행 환경에는 BF16을
지원하는 PyTorch와 대응하는 변환 BLT 모델이 필요하다. Python 사용 예:

```python
import torch
from phdq_blt_cache import GlobalPrefixReuse

model.eval()
with torch.inference_mode():
    cache = GlobalPrefixReuse(model, reuse_decoder=False)
    output, _, _, _ = cache.run(input_ids, logits_to_keep=1, guard_margin=1.0)
```

이 저수준 호출은 토큰 선택, 종료 판단, 텍스트 디코딩을 대신하지 않는다.
이 단계들은 `phdq3` 생성 어댑터가 계속 담당한다. 이 API를 바꾸거나 학습
저장소를 외부 패키지로 옮기기 전에 [docs/HANDOFF.md](docs/HANDOFF.md)를 읽는다.
GitHub 저장소 생성과 Python 설치 절차는
[docs/PUBLISH_GITHUB.md](docs/PUBLISH_GITHUB.md)를 따른다.

## 명시적 선택: count 패처 연구

별도의 [패처 계획](BLT-PATCHER.md)과 [실행 현황](task.md)은 신경망 엔트로피 패처를
대체하는 실험적 count 기반 패처를 다룬다. 수치 의존성은
`python -m pip install -e '.[patcher]'`로 설치하고 `phdq_blt_cache.count_patcher`를
명시적으로 import한다. 기존 캐시 API와 기본값은 바뀌지 않으며, BLT 패처 교체는
자동으로 켜지지 않는다.

이 모듈은 인과적 count, 유한 window 만료, 모든 짧은 문맥의 혼합, 직렬화 가능한
증분 상태, 제약 조건이 있는 고정 특징 적합을 제공한다. 연구 스크립트는 데이터셋,
테이블, 라벨, 적합 산출물을 이 소스 트리 밖에 둔다. 초기 K=8 설정 두 개의
validation F1은 약 0.626으로 사전 등록한 0.90 기준에 못 미쳤으며, 어느 쪽도 통합이
승인되지 않았다. 한국어 후속 학습과 비교는 Neuron H200에서 수행하며, 접속·전송·
작업 제출은 사용자가 맡는다.

### 디스크 기반 데이터 준비

확장 실행기는 기본적으로 기존 Python 준비 경로를 유지한다. 계획에
`preparation_backend: "sqlite_cpp_v1"`을 명시하면 원문 문서, MinHash 서명, LSH 버킷을
SQLite에 저장하고, 길이 층화 셔플에는 정수 문서 ID만 유지하며, 호스트의 `c++`
컴파일러로 C++17 MinHash 커널을 빌드한다. Python 표준 SQLite 모듈로 충분하며 SQLite 개발
헤더나 네이티브 패키지 설치는 필요 없다. 패키지 캐시 API와 적합은 Python으로 남는다.
추론 기본값도 Python이며, 아래의 C++ count 패처 백엔드는 명시적으로 선택해야 한다.

네이티브 커널은 datasketch의 `legacy`와 `affine32` 방식을 지원하고, 설치된 라이브러리의
순열과 LSH 버킷 배치를 그대로 사용한다. 합성 Parquet 테스트로 기존 경로와 디스크 경로의
전체 출력 해시를 비교했다. 다만 이것이 앞으로의 임의 라이브러리 버전에 대한 동등성을
보장하지는 않는다. 새 경로는 후보 할당량, seed, 원래 분할, 문서 단위 바이트 예산,
근사 중복 탐지를 그대로 유지하며, 중복 제거를 전수 검사로 만들지는 않는다.
Parquet row group 하나와 문서 ID 목록을 메모리에 두므로 고정 메모리 구현이 아니고,
10GB 메모리 상한도 입증되지 않았다.

승인된 서버 실험은 분리된 tmux 세션에서 실행한다:

```bash
OPENBLAS_NUM_THREADS=8 python -m scripts.run_background_expansion --plan experiments/english_background_10gb_disk_cpp_repro.json
```

이 계획은 시간 제한 없이 48GiB 주소 공간 제한과 디스크 안전장치를 유지한다.
준비가 성공하면 새 run의 일회용 SQLite 데이터베이스만 지우고, 실패하면 진단을 위해
작업 파일을 남긴다. 보고서는 소스와 네이티브 바이너리 해시를 기록한다. 이전 출력은
보존하고 재시도마다 새 run ID를 쓴다. 재현성 계획은 Python 시작 시 OpenBLAS 스레드
8개를 요구하며, 설정이 없으면 즉시 실패한다. 같은 저장 replay 배열에서 기본값(24스레드)
AP 축약은 저장된 결과와 1 ULP 차이가 났고, 8스레드는 확인한 다섯 지표를 모두
정확히 재현했다. 부모 실행과의 정확 일치 검증은 그대로 켜 두었고 수치 허용 오차는
완화하지 않았다.
[사전 점검 측정](evidence/english_disk_cpp_preflight_20261024.json)은 실제 문서 20,000개를
비교했다. 출력은 같았고, 최대 RSS는 약 472MiB 대 191MiB, 전체 시간은 12.48초 대
14.18초였다. SQLite는 메모리를 줄였지만 전체 시간은 늘었다. 이 측정은 하류 추론
속도의 근거가 아니다.

### LMDB 배경 count (명시적 선택)

`phdq_blt_cache.lmdb_counts.LMDBCountTable`을 쓰려면
`python -m pip install -e '.[patcher,lmdb]'`로 설치한다. 바뀌지 않는 배경 행을 필요할 때
읽고, 디코딩한 행은 크기 제한이 있는 캐시에 둔다. 문서 내 온라인 count는
메모리에 남는다. 없는 키는 실제로 배경에 없는 것이며, 평가 문맥만 미리 골라 둔
부분집합이 아니다. 기본 패키지 import와 메모리 백엔드는 바뀌지 않는다. LMDB 배경은
`state_dict`에 넣을 수 없으므로 context manager로 닫고 데이터베이스를 명시적으로
다시 연다.

기존 count block 보고서는 연구 서버에서 변환하며, 오래 걸리는 작업은 분리된 tmux에서
실행한다:

```bash
OPENBLAS_NUM_THREADS=8 python -m scripts.build_lmdb_background \
    --report /path/to/background_build.json --output /path/to/new-counts.lmdb
```

출력 경로는 존재하지 않아야 한다. 변환은 소스 해시를 검증하고, 토큰 순서나 평활화를
바꾸지 않고 모든 블록의 정수 count를 합산한다. 기본값은 LMDB map 32GiB, 주소 공간
제한 48GiB, 최소 여유 디스크 100GiB, 출력 상한 100GiB다. `MapFullError`가 나면
안전장치를 올리거나 자동 재시도하지 않고 변환을 멈춘다. LMDB 매핑은 대부분의
페이지가 RAM에 올라와 있지 않아도 주소 공간 제한에 포함된다. 실패 시 작업 파일은
보존한다. 이전 writer를 멈춘 뒤 같은 데이터베이스를 명시적으로 재개한다:

```bash
OPENBLAS_NUM_THREADS=8 python -m scripts.build_lmdb_background \
    --report /path/to/background_build.json --output /path/to/existing-counts.lmdb \
    --resume --map-size-gib 128 --memory-limit-gib 160 --rss-limit-gib 48
```

이 더 큰 제한값은 실험 승인을 따로 받아야 한다. 주소 공간 제한은 매핑을
수용하기 위한 것이고, RSS 제한은 배치 단위로 확인하는 최대 상주 메모리
안전장치일 뿐 커널이 강제하는 물리 메모리 상한이 아니다. 디스크 안전장치는 별도로
유지된다. 재개 시 원래 보고서·설정·블록 선택을 검증하고 블록 해시를 다시 확인하며,
commit된 입력 행을 정확히 건너뛴다. 예전 checkpoint는 위치를 복원하려면 블록별 문맥
수가 선언되어 있어야 한다. 완료된 데이터베이스와 맞지 않는 checkpoint는 거부한다.
새 CLI에서 SIGTERM을 받으면 commit되지 않은 트랜잭션을 버리고 종료 코드 130으로 끝나며,
마지막 commit부터 재개할 수 있다. 이전 stdout은 보존하고 재개용 stdout을 새로 쓴다.
메타데이터에는 재개 위치, map 크기, 코드 해시, 제한값이 기록된다. 세션 시간 기록으로
예전 checkpoint에 없던 경과 시간을 복원하지는 않는다.

`--block-limit 1`은 사전 점검 전용이다. 부분 데이터베이스는 `allow_partial=True`로 명시적으로
열지 않으면 reader가 거부한다.

작은 개발용 접두부의 count·확률·경계 확인과 조회·패처 시간 측정에는
`python -m scripts.benchmark_lmdb_background --background-report ...
--database ... --documents ... --output ...`를 쓴다. `--allow-partial`은 접두부 사전
점검에만 넘긴다. warm cache 시간은 BLT 생성 속도 측정이 아니며, 전체 소스 변환과
하류 품질·속도 검증은 별도의 관문으로 남는다.

### C++ 패처 백엔드 (명시적 선택)

`CountPatcherAdapter`는 기본적으로 기존 Python 계산을 사용한다. C++를 사용하려면
동일 Python ABI용으로 빌드한 신뢰할 수 있는 확장 파일을 명시적으로 전달한다.
자동 빌드나 실패 시 암묵적 백엔드 전환은 하지 않는다. 검증 환경은 itcerdo의
Linux/CPython3.11/GCC13.3이다. 다른 Python ABI·플랫폼에서는 다시 빌드해야 한다.
배경은 frozen 카운트여야 하며 현재 C++ 경로는 window=None,260-ID 바이트
어휘·기본 특수 ID를 지원한다. LMDB 조회·GPU 입출력은 기존 구현을 유지한다.

소스 체크아웃에서 사용하지 않은 새 빌드 디렉터리를 지정한다.

```python
from scripts.benchmark_cpp_count_patcher import build_native

_, _, library = build_native("/path/to/new-native-build")
print(library)
```

설치한 패키지에서는 모델·스크립트 소스 경로 없이 빌드된 라이브러리를 로드할 수 있다.
아래 config/rule/background는 기존 검증된 후보의 설정·규칙·카운트 객체다.

```python
from phdq_blt_cache.blt_patcher import CountPatcherAdapter

adapter = CountPatcherAdapter(
    config, rule, background, backend="cpp", native_library=library
)
```

호출은 기존처럼 inference_mode/no_grad 안에서 `adapter.patch_lengths(input_ids)`를
사용한다. `max_patch_length`와 `reset()`도 지원한다. 빌드 결과는 wheel에 포함되지
않으며 해당 ABI의 외부 산출물로 관리한다. 기존 guarded cache와는 별개의 대체 패처다.

실제 전체 평가333문서에서 Python/C++ 경계·모델 로짓·BPB가 같았고 생성18개도
기존 Python 출력과 같았다. 초기+동일32바이트 전체 모델 시간은 이 조건에서
Python count 대비1.05-1.12배, 신경망 대비1.10-1.46배 빨랐다. 일반적인 출력
동일성·생성 품질 향상이나 모든 채택 기준 통과를 뜻하지 않는다.
[세부 조건과 결과](docs/INTEGRATION.md)를 확인한다.
