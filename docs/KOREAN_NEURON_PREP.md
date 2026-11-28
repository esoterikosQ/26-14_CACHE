# 한국어 CPT 및 Neuron T12~T14 준비

## 현재 기록 위치

2026-10-29 사용자 정정: **phdq3는 읽기 전용 참조**다. 이번 작업의 구현·테스트·설정은
blt-cache/neuron/runtime,명령은 [루트 안내](../command.md)와 [Neuron 명령표](../neuron/command.md),
진행 기록은 blt-cache/log.md,실행 로그 전달은 runtimelog를 사용한다.
Neuron의 새 데이터·설정·출력 루트는 `/scratch/r984a02/blt-cache`다.
아래 itcerdo/phdq3에 준비했다는 내용은 이전 실행 이력이며 새 쓰기 경로가 아니다.

2026-10-29 현재 **준비 단계**다. 영어10GB T08·T09는 완료했고20GB 배경 빈도
파이프라인의 첫 실행은 prepare 단계 실패로 종료됐다. 후속 진단·추가12shard 고정 후
새 run en-patcher-bg20gb-nested-20261029-02가 prepare 진행 중이며 기존 실패 산출물은 보존한다. 한국어 원문 다운로드·교사/본체 학습·Neuron
접속/전송/Slurm 제출은 하지 않았다. 접속·전송·제출은 사용자 담당이다.
기계 판독용 상태는 [준비 계약](../experiments/korean_neuron_readiness.json)에 있다.
[Neuron 실행 bundle](../neuron/README.md)에 사용자 다운로드·환경 검사·파일럿·재개 명령을 모았다.
기본은 H2001GPU/preflight이며 실제 자료·예산 승인 전에는 학습하지 않는다. 독립 배포 사본의
CPU guard/entropy/실제 패처 strict load는 통과했고 Neuron GPU 검증은 사용자 실행 대기다.

## 외부 계획 병합 기준

2026-10-29 사용자 제공 [T13.plan.md](../T13.plan.md)의 연구 설계를 아래에 병합했다.
원본의 작성일과 내용은 보존하고,현재 프로젝트의 실행 계약은 이 문서·준비 JSON·
[task.md](../task.md)를 따른다. 문서 병합은 학습 실행이나 예산 승인과 다르다.

- 채택한 설계: 공개 가중치 기반 계속 사전학습(CPT),BLT/PATCHER 대조,로컬 모듈 ENCODER 후 조건부 HASH/BODY_FULL 비교,동일 노출량 통제,한국어 품질·실측 비용의 분리. 2026-11-14 사용자 결정으로 영어 성능(망각 감시·영어 replay)은 평가·학습 범위에서 제외한다.
- 제안으로 병합: 바이트 혼합75/15/10,누적1GB→5GB 점검,필요시30/100/300GB,평균4/6/8 bytes/patch 후보,5090 PATCHER·ENCODER 우선 파일럿. 승인된 상한·모델 설정은 아직 아니다.
- 자동 승계하지 않음: 원본의 외부 프로젝트 PDF/환경 파일 경로,노드명·파티션·walltime/MaxRun 정책,모델 크기·메모리 추정·기간 시나리오·선행 연구의 그래프 수치. 실제 체크포인트/공식 출처/현재 할당으로 확인 전 실행 근거로 쓰지 않는다. 비밀 환경 파일은 읽거나 복사하지 않았다.
- 기존 규약 유지: 수용한 원문의 UTF-8 바이트를 그대로 사용한다. NFC 변환이나 문자 경계로 패치를 이동하는 규칙은 별도 승인·실험 없이는 추가하지 않는다.

기존 H200 목표는 유지한다. 5090 우선안은 승인할 수 있는 대안으로 병합하되 현재
학습 배치를 변경하지 않는다. 승인된 경우 itcerdo에서 작은 PATCHER/ENCODER 파일럿을 먼저
측정하고 필요시 Neuron으로 확장할 수 있다. Neuron 계정 준비는 승인된 로컬 파일럿의
필수 조건이 아니지만,진행 중 영어20GB 작업의 CPU/RAM/I/O 예산과 별도 공존 검사가 필요하다.

## 데이터 후보

### 2026-11-01 현재 데이터 준비

사용자 NIKL nikl-v003 audit와 korean-entropy-v001 split은 완료 보고서/산술로 확인했다.
이8.32GB 파생 본문은 **NIKL만**이며 약속한 통합 학습 자료 전체가 아니다.
사용자는 FineWeb2 한국어 train 전체와 새 산출물 상한10TB를 선택했다.
고정 revision의25개 Parquet 메타데이터는105767105257압축bytes이며 원문은 아직 받지 않았다.
standalone runtime의 `blt_hf.entropy_fineweb`에 catalog/download/combine을 구현했고,
실제 합성 Parquet를 포함한4검사를 기존 서버 환경에서 통과했다. Neuron 실행은 사용자가 한다.

[직접 명령](../neuron/command.md#6-4-fineweb2-한국어-전체-train-확보-및-nikl-통합)은
NIKL의 원장/3분할을 보존하고 FineWeb2 공식 test를 받지 않는다. 기존 NIKL에 연결된
FineWeb 그룹은 보호 역할을 따르며 역할 충돌은 재배정 없이 실패한다. 전체 원문/파생 데이터
상한10TB와 최소 가용100GiB·AS48GiB를 유지하고 원본 Parquet/실패 산출물은 삭제하지 않는다.
통합 성공 후 korean-entropy-nikl-fineweb-v001/manifest.json을 검토해 학습에 연결한다.
권리/PII/퍼지 중복·학습 노출량/혼합·GPU 예산 승인은 자동 변경하지 않는다.
아래 미선택/미다운로드 문구와 과거 외부 프로젝트 경로는 이전 준비 이력이다.

사용자 결정에 따라 **모두의 말뭉치와 FineWeb2를 기본 자료로 하고 세종 확보는 필수
조건에서 제외**한다. 아래 세종 도구 검토는 참고 이력이며 실행 선행 조건이 아니다.

2026-10-29 사용자 보고: 모두의 말뭉치의 필요한 자료는 신청 완료했으며,사용자가
직접 다운로드해 itcerdo로 전송할 예정이다. 승인·다운로드·전송 완료를 확인한 것은
아니며,도착 후 실제 경로·파일 목록·설명서/약정·SHA를 확인한다.

세종 후보 [coolengineer/sejong-corpus](https://github.com/coolengineer/sejong-corpus)는
자료 자체가 아니라 과거 `ithub.korean.go.kr` 게시판용 다운로드/변환 스크립트다.
현재 다운로드 성공 여부는 미검증이며,공식 웹 배포 종료 안내와 구분해야 한다.
첨부 약정은 비상업적 연구 용도와 출처 표시를 요구하므로 현재 취득·모델 공개 조건을
별도 확인한다. 기본 실행의 UTF-16→UTF-8 변환·수작업 패치 및 형태소/자모 가공을
원문 CPT 전처리로 자동 채택하지 않는다. 원본과 변환본·적용 패치 이력을 구분한다.

공식 [FineWeb2 카드](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2)와 API에서
`kor_Hang`,revision `af9c13333eb981300149d5ca60a8e9d659b276b9`,train25개·test1개
파일 메타데이터를 확인했다. 아직 선택/다운로드 manifest는 없다. 배포 라이선스는
[ODC-By1.0](https://opendatacommons.org/licenses/by/1-0/)이며
[CommonCrawl 이용 조건](https://commoncrawl.org/terms-of-use)도 검토해야 한다.
이는 개별 웹 문서의 모든 권리나 개인정보 안전성을 보장하는 판단이 아니다.
상류 이메일/IP 익명화만으로 충분하다고 보지 않고 한국어 전화번호 등 별도 검토를 남긴다.

공식 test는 최초부터 보류한다. 문서/중복 군집 단위로 역할을 나누고 train 내부의
교사 학습·본체 학습·카운트 배경 사이에 허용할 중첩도 명시한다. 경계 계수 학습/
검증과 최종 미열람 평가는 구분한다. UTF-8 바이트를 그대로 보존하고 정규화는 중복
탐지에만 사용한다. 바이트 예산·시드·최종 shard SHA·개인정보/품질 필터가 확정되기
전에는 자료를 구축하지 않는다. 영어20GB는 한국어 원문이나 신경망 학습량이 아니다.

## 교사와 본체

이번 연구 계획의 경로는 공개 `facebook/blt-entropy`와 `facebook/blt-1b` 기반 CPT다.
Scratch/LoRA/양자화 학습은 주 비교에서 제외한다. 실제 모듈별 모수·문맥/마스크·
checkpoint/code revision·변환 SHA·학습 진입점은 실행 전에 확인한다. 모델 이름의1B나
선행 사례의 학습 비율로 총 모수·VRAM·시간을 추정 확정하지 않는다.

교사는 다음 바이트 cross-entropy로 추가 학습하되 패칭에는 실제 다음 바이트의
surprisal이 아닌 예측 분포 entropy를 사용한다. BOS/가상 다음 위치/로그 밑/엄격한
임계값 비교의 기존 인덱싱을 검증한다. 기존 영어 임계값이나 count 계수를 옮기지 않는다.
한국어 교사를 선행 적응하고 PATCHER 영향 확인 뒤 본체 비교 전에 교사·threshold를 고정한다.
본체 학습 뒤 교사를 새로 학습하는 것을 필수 단계로 두지 않는다. 교사를 바꾸면
패처 변경 자체의 품질 통제가 필요하며 동일 후보 교체 비교와 구분한다.

실제 학습 코드·설정·Slurm 작업은 소유 프로젝트 `phdq3`에서 관리한다. 이 패키지는
재현 계약과 후보 평가를 담당하며 학습 엔진·가중치·자료를 복사하지 않는다.

## Itcerdo PATCHER 준비 상태

2026-10-29 사용자 요청으로 수신 디렉터리와 학습 코드를 준비했다. 소유 프로젝트
`/home/itcmaster/projects/phdq3` 아래 `data/korean_cpt/incoming/nikl`에 원본을,
`data/korean_cpt/licenses`에 설명서·약정을 전송하면 된다. FineWeb2 수신은
`data/korean_cpt/incoming/fineweb2`,manifest/prepared와 `outputs/korean_entropy`는
각각 별도 경로다. 원본 압축파일을 보존하고 기존 제공 데이터/작업/환경은 변경하지 않는다.

소유 코드 `blt_hf/entropy_data.py`는 명시적 문서 분할 계획의 NIKL paragraph/utterance
또는 id/source/text JSONL을 변환하며,실제 도착 자료의 schema 검토는 남았다.
`blt_hf/entropy_train.py`는 다음 바이트 CE·실제 본문 byte BPB·패처만의 CPT·모수/Adam/RNG/
cursor 저장·해시 재개를 제공한다. `blt_hf/KOREAN_ENTROPY.md`에 절차와 한계가 있다.
기존 환경 `miniconda3/envs/phdq_blt_hf/bin/python`을 재사용하고 패키지는 설치하지 않았다.

CPU 준비7검사·기존 스케줄3검사와 실제 패처99,512,064모수 BF16 strict load/합성 forward·backward를
통과했다. 129모수 텐서 기울기는 유한했고 실제 패처 optimizer 업데이트는0회다.
GPU Adam 상태/VRAM/처리량·실제 데이터/영어 망각·threshold 보정은 아직 미검증이다.
소유 설정 `plan/korean_entropy_preparation.json`의 학습 승인은 false,5개 실행 예산은
null이며 기본 명령은 preflight뿐이다. 자료 수신·약정/PII/근접 중복 분할 검토와 파일럿
예산 승인 전 실제 학습은 차단한다. CPU 검사를 GPU 학습 준비 완료로 해석하지 않는다.

## 통제 비교 설계

| ID | 본체 업데이트 | 패처 | 해석 |
| --- | --- | --- | --- |
| BLT | 없음 | 공개 교사 | 한국어 출발 기준 |
| PATCHER | 없음 | 한국어 CPT 후 고정 교사 | 패처 가중치와 threshold의 결합 교체 효과 |
| ENCODER | 글로벌·해시 n-gram 임베딩 고정,나머지 본체 | PATCHER에서 고정 | 로컬 모듈 적응 효과 |
| HASH | 글로벌만 고정,해시 n-gram 임베딩 포함 나머지 본체 | 동일 | ENCODER 대비 해시 업데이트 효과,조건부 |
| BODY_FULL | 글로벌 포함 본체 전체 | 동일 | HASH 대비 글로벌 업데이트 효과,조건부 |

2026-11-12 사용자 결정으로 순서를 ENCODER → HASH → BODY_FULL로 바꿨다(이전 GLOBAL은 해시 고정·글로벌 학습).
2026-11-14 사용자 결정으로 **BODY_FULL을 먼저** 수행한다. ENCODER/HASH는 그 뒤 학습 범위를 줄여 가며
어디까지 학습해야 성능이 안정되는지 확인하는 부차적 축소 실험이다.
2026-11-27 사용자 결정으로 ENCODER/HASH 축소 실험은 T14 뒤 맨 마지막으로 미룬다.
해시(30.72억 모수)는 조회 연산이라 추가 계산이 작고, 글로벌(12.85억)은 가중치 기울기 행렬곱이 더해져 더 비싸다.
해시는 FP32 원본·Adam·기울기로 약49GB를 더 쓴다. 임베딩이므로 weight decay에서 제외한다.

문서와 기계 계약은 표의 대문자 ID를 동일하게 사용한다. 경계 평가 지표 F1은 그대로다.
ENCODER/HASH/BODY_FULL은 **동일 공개 본체에서 각각 독립 출발**한다.
예비 ENCODER나 앞 단계 가중치를 물려받는 운영 실험은 별도 run으로 분리한다. 공통 데이터
manifest·문서 순서·패처·byte/patch context·패킹·유효 global batch·노출량·공통
optimizer/schedule을 고정한다. ENCODER와 BODY_FULL 차이를 해시 단독 효과로 해석하지 않는다.

ENCODER는 encoder만 학습한다는 뜻이 아니다. 학습 목록은 로컬 encoder/decoder,해시 제외 byte 임베딩,cross-attention과
입출력 projection을 실제 파라미터 이름으로 확정한다. 공유 파라미터와 optimizer
등록 목록을 검사하고 각 비교 쌍의 차이가 의도한 모듈뿐인지 검증한다. 글로벌을
고정해도 encoder로 gradient를 전달해야 하므로 해당 경로에 `no_grad`/`detach`를
적용하지 않는다. 작은 step에서 학습 모듈의 gradient/갱신과 고정 가중치 불변을 확인한다.
학습 모수 비율을 속도 절감률로 환산하지 않는다. FSDP는 필요가 측정된 경우에만
혼합 frozen/trainable wrapping·상태 복원을 검증하고 도입한다. 초기 CPU offload는 제외한다.

## 단계별 데이터와 예산 제안

초기 혼합 제안은 유효 학습 바이트 기준 FineWeb2 한국어75%,기타 한국어15%,영어
replay10%였다. 2026-11-14 사용자 결정으로 영어 replay는 제외하고 한국어 자료만 쓴다. 기타 후보는 MADLAD-400 clean 한국어,CulturaX,한국어 Wikipedia,
허가된 국내 말뭉치다. 이들의 revision/라이선스/접근/오염은 아직 확인하지 않았으며
확보한 데이터로 취급하지 않는다. 작은 자료를 반복해 비율을 억지로 맞추지 않는다.
혼합 변경은 주 비교 전 승인·고정하며 한 비교군에만 다른 혼합을 적용하지 않는다.

단위는 정제한 본문 UTF-8 바이트이며 압축·메타데이터·padding을 제외한다. 고유
바이트와 반복 포함 누적 노출을 따로 기록한다. 제안 순서는 수십 step 저장/복원 →
PATCHER 누적1GB 점검/필요시5GB → 패처 고정 → BODY_FULL 누적1GB/5GB다(2026-11-14 순서 변경). ENCODER/HASH는 각각
진입 승인 뒤 같은 노출량부터 비교한다. 초기100~300GB 다운로드/패치 캐시는 요구하지 않는다.
5GB 뒤25GB를 더 읽으면 누적30GB다. 현재 방식의 학습량 부족과 학습 범위 부족을
분리하며 필요한 상대군만 노출량을 맞춘다.30/100/300GB 확대·seed 반복은 별도 승인이다.

교사 train과 본체 train의 중첩은 manifest에서 명시할 수 있지만 본체 validation/test를
교사 학습이나 threshold 보정에 사용하지 않는다. train 내부 보정 표본으로 평균
4/6/8 bytes/patch 후보를 검토하고,공개/적응 교사를 유사한 평균 길이로 맞춘 대조도
포함한다. 본체 BPB·패치 길이 상위 분위·패치 수·유효 context/truncation을 함께 본다.
Entropy BPB가 낮다는 이유만으로 패처를 채택하지 않는다.

## 패치 캐시와 평가

동일 교사로 필요한 shard만 사전 패칭하고 GPU 패칭과 학습은 순차 배치하는 안을
사용할 수 있다. 데이터 manifest/전처리/교사 가중치/threshold/문맥·chunk·문서 reset/
특수 ID/정밀도·커널 버전을 캐시 식별자에 포함하고 변경 시 재생성한다.
T06에서 전체 입력과 접두부의 경계 차이를 실측했으므로 인과적 모델이라는 이유만으로
캐시의 접두부 동등성을 가정하지 않는다. 동일 학습/평가 문맥과 chunk에서 온라인/
오프라인 경계 일치 및 미래 바이트 누출·문서 간 누출을 검사하고,가변 길이 추론의
차이는 별도 기록한다. 기존 가드 캐시의 출력 보존과 학습용 패치 사전 계산은 별개다.

주 지표는 한국어 validation BPB이며(영어 heldout은 2026-11-14 사용자 결정으로 제외) 출처별 수치와
paired 불확실성을 보고한다. Belebele 한국어/KoBEST/KMMLU는 라이선스·오염·동일
prompt/scoring 어댑터를 검증한 뒤 선택할 후보다. test-only 과제를 반복 튜닝에 쓰지 않는다.
생성 UTF-8·반복·문장/한국어 품질을 보완하되 과거 EOS 원인 진단을 선행 조건으로 재개하지 않는다.
최소 BPB 개선·GPU-hours 상한은 비교 전 수치로 승인해야 한다.
이 신경망 CPT 기준은 count 경계 F1/F0.5 모사 기준과 별개이며 기존0.005 등을 전용하지 않는다.

BODY_FULL을 먼저 기준으로 만든 뒤 ENCODER/HASH 축소 실험을 같은 노출량에서 비교한다(2026-11-14 사용자 결정).
축소 실험 결과로 BODY_FULL 이전 단계의 충분성을 판단하며, 상위 단계 미수행이 열등성을 입증하지 않는다는 원칙은 유지한다.
최종 본체·교사를 잠근 뒤 T14에서 count 후보를
새로 적합·비교하며,후보만을 위한 추가 본체 학습은 대칭적인 교체 실험에서 제외한다.

## 비용과 복원 계약

실행 전체의 padding 제외 학습 bytes/s,장치 종류/수량별 GPU-hours,peak VRAM/RAM,
I/O·저장 비용을 측정한다.5090과 H200 GPU-hours는 동등한 계산량이 아니며 hardware를
옮기면 필요한 비교만 같은 장치에서 재측정한다. 큐 대기는 별도이고,달력 기간의 확보율은
GPU utilization과 구분한다. 저장/평가 비용이 포함된 처리량에는 같은 비용을 다시 더하지 않는다.
공유 entropy/패칭 비용은 한 번만,비교군·탐색·seed 비용은 각각 합산한다.

체크포인트는 모델/optimizer/scheduler/RNG/iterator/누적 바이트/학습·고정 이름 목록과
코드·패처·데이터 버전을 보존한다. 모든 rank의 무결성 확인 후 정상본으로 표시하고
이전 정상본을 덮어쓰지 않는다. 장치/GPU 수 변경 시 optimizer 재분할과 iterator 복원을
확인한다. 원문·정제·패치·scratch·여러 checkpoint 세대·백업의 quota/inode/RAM까지
산정한다. 원본 계획의 Slurm 수치나 저장 주기는 현재 정책/실측 없이 확정하지 않는다.

## 사용자 환경 확인

새 환경 설치나 제출 없이,사용자가 기존 할당과 작업 경로에서 아래 수집기를 실행한다.
`NEURON_WORK_ROOT`와 `PYTHON`은 사용자의 실제 경로로 지정한다. 출력은 stdout이며
원문/가중치·환경 변수 전체·인증 정보를 수집하지 않는다. 이 명령은 작업을 제출하지 않는다.

```bash
PYTHON=/actual/existing/environment/bin/python \
  bash scripts/collect_neuron_readiness.sh "$NEURON_WORK_ROOT" \
  > "$NEURON_WORK_ROOT/korean-neuron-inventory.txt"
```

필요한 추가 정보는 GPU 실제 할당 수/VRAM,파티션·계정·시간 한도,호스트 RAM·디스크/
작업 경로,소유 프로젝트 학습 entrypoint와 모델 설정이다. 수집기는 일부만 확인하며
누락된 Slurm 정책을 추정하지 않는다. 할당 밖에서는 Torch CUDA context 검사를 생략한다.

## 파일럿 통과 조건

1. 별도 GPU/RAM/디스크/시간 상한과 데이터·모델·교사 선택을 승인하고 코드/설정/입력 SHA를 고정한다.
2. 실제 모델로 forward/backward/optimizer step을 수행하고 Adam 상태 생성 후 여러 step을 측정한다. 가중치·기울기·옵티마이저·activation 메모리를 구분한다.
3. 예열 후 동기화한 optimizer step의 학습 bytes/s와 검증·저장 비용을 측정한다. gradient accumulation은 activation 부담을 줄일 수 있지만 모수·옵티마이저 상태 자체를 줄이지 않는다.
4. 체크포인트를 저장·재개해 optimizer/scheduler/RNG/dataloader 상태와 다음 loss/update를 중단 없는 통제와 비교한다.
5. 전체 학습 바이트/실측 bytes/s에 검증·체크포인트 비용을 더해 기간을 산정한다.5090 접두부 재생이나 이론 TOPS를 H200 학습 속도로 환산하지 않는다.

현재 학습량·모델·할당·학습 진입점·기간 예산이 미확정이므로 실행 가능한 Slurm
학습 스크립트나 완료 기간을 만들어 제출하지 않는다. 위 입력과 파일럿 측정이 갖춰지면
소유 프로젝트에 실제 제출 설정을 준비하고 T13/T14로 이동한다.