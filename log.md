# 작업 로그

단계별 작업과 결과를 오래된 순서부터 누적한다. 계획과 상태표는
[task.md](task.md), 수학적 모형은 [BLT-PATCHER.md](BLT-PATCHER.md)를 따른다.
각 단계 전환 시 수행 내용, 설정·산출물, 검증 결과, 한계와 다음 작업을 기록한다.
완료·실패·보류·미실행 제안을 구분하고, 정정은 새 항목으로 추가한다.
원문·가중치·대용량 실행 출력·비밀 정보는 이 파일에 저장하지 않는다.

## 2026-10-19 / T00 / 실행 범위 확정 [사후 정리]

- 기존 대화와 저장된 증거에서 복원한 기록이다. 아래 사후 정리 항목은 실행 당시 작성된 로그가 아니며 정확한 시각을 추정하지 않는다.
- 영어 파일럿은 itcerdo의 `/home/itcmaster/projects/blt-cache`, 실행 ID `en-patcher-20261019-01`로 고정했다. 소스·독립 환경·원문·산출물을 분리했다.
- FineWeb 개발 자료와 별도 Wikipedia 평가 자료를 선택했다. 신규 작성 문서 조건은 사용자 선택으로 완화했으며 교사가 보지 않은 자료라고 주장하지 않는다.
- 검증 경계 F1 0.90, 증분 패처 속도 1.2배 등 선별 기준과 RAM 48GiB·VRAM 28GiB·최대 24개 설정의 예산을 고정했다.
- 근거: [실행 설정](experiments/english_patcher_pilot.json). 다음 단계: 환경과 모델 실행 확인.

## 2026-10-19 / T01 / 환경·교사·본체 확인 [사후 정리]

- itcerdo RTX 5090, Python 3.11.16, PyTorch 2.11.0+cu128의 독립 환경에서 변환 체크포인트 해시와 엄격 로딩을 확인했다. 기존 환경과 가중치는 변경하지 않았다.
- 실제 전체 파라미터는 4,633,391,872개, 교사 패처는 99,512,064개였다. 모델 이름의 1B를 전체 파라미터 수로 사용하지 않았다.
- 합성 입력 256/512/1024/2048 ID의 BF16 추론이 통과했다. 본체 2048 ID 중앙값 52.84ms, 최대 예약 VRAM 약 9.83GiB였다.
- 근거: [환경·모델 보고서](evidence/english_patcher_preflight_20261019.json). 합성 추론 결과이며 학습 가능성이나 실제 문서 처리량을 보장하지 않는다.
- 다음 단계: 교사 라벨 위치와 상태 규약 확인.

## 2026-10-19 / T02 교사 / 위치·수치 규약 확인 [사후 정리]

- 모델 어휘 260, BOS 1, EOS 2, PAD 3과 바이트 ID 매핑을 검증했다. 토크나이저 등록 항목 261개와 모델 어휘를 구분했다.
- 자연로그 엔트로피, BF16 유효 임계값 1.3359375, 강제 시작점 0·1, 가상 다음 ID 위치와 EOS 구간 격리를 확인했다.
- 빈 입력·BOS 전용 입력의 기존 교사 거부 동작과 합성 인과성·접두부 검사를 실행했다. 선택한 표본의 경계 일치는 다른 입력의 BF16 안정성을 보장하지 않는다.
- 근거: [교사 규약 보고서](evidence/english_teacher_contract_20261019.json). 후보 상태 검사는 T04까지 미완료로 남겼다.

## 2026-10-19 / T03 / 영어 자료 확보·분할 [사후 정리]

- 고정한 FineWeb 4개 shard와 Wikipedia 2개 shard에서 표집하고, 정확 해시·URL·MinHash 근사 중복을 검사했다. 길이 구간을 고려해 문서 단위로 분리했다.
- 배경 2,241문서·10,001,309바이트, 학습 898문서·4,041,644바이트, 검증 111문서·463,770바이트를 확보했다.
- 잠근 평가 자료는 FineWeb 113문서·495,516바이트와 Wikipedia 220문서·1,002,062바이트다. 원문 무결성은 검사했지만 평가 라벨·성능은 확인하지 않았다.
- 원문은 원격에만 보관했다. 근사 중복 후보가 없다는 결과가 모든 유사 문서의 부재를 증명하지는 않는다.
- 근거: [소스](evidence/english_dataset_sources_20261019.json), [분할](evidence/english_data_manifest_20261019.json), [무결성](evidence/english_data_validation_20261019.json).
- 다음 단계: 후보 기준 구현과 소규모 비용 측정.

## 2026-10-19 / 후속 장치 / Neuron H200 지정 [사후 정리]

- 사용자 지시에 따라 영어 T04~T11은 itcerdo, 한국어 사전학습·교사 확정·비교 T12~T14는 Neuron H200으로 지정했다.
- Neuron 접속·전송·작업 제출은 사용자가 담당한다. 실제 할당 자원과 optimizer step 메모리·처리량은 아직 확인하지 않았다.
- 반영: [단계별 계획](task.md). Neuron에 접속하거나 작업을 제출한 것은 아니다.

## 2026-10-19 / T04·T02 후보 / 기준 구현·검증 [사후 정리]

- [count_patcher.py](src/phdq_blt_cache/count_patcher.py)에 opt-in 카운트 모형을 구현했다. 기존 캐시 API와 기본 동작은 변경하지 않았다.
- 유한 W에서 전체 문맥+outcome의 만료, 무한 W, 모든 짧은 suffix의 혼합, eta 가중치, 반복 길이 R, 판정 후 관측, 문서 초기화를 구현했다.
- EOS는 구간의 마지막 outcome으로 세고 이후 문맥에서 제외한다. 이전 구간의 완결 관측은 W 안에서 보존한다.
- 교사 이력 특징과 후보 순차 판정을 분리하고, 미래 변경 불변성·중복 접두부 입력 거부·엄격 임계값·가상 슬롯·상태 복원을 검사했다.
- 전수 카운트/혼합 oracle과 비교했다. NumPy/SciPy는 `patcher` optional extra로 분리했다.
- 검증: itcerdo 독립 환경의 `python -m unittest discover -s tests -v`. 해당 단계의 후보 테스트가 통과했으며 이후 추가 검사를 포함한 최종 결과는 아래 정리 항목에 기록한다.
- 근거: [합성 테스트](tests/test_count_patcher.py). 다음 단계: 실제 개발 자료의 비용 파일럿.

## 2026-10-19 / T05 / 소규모 자원·속도 측정 [사후 정리]

- [벤치마크](scripts/benchmark_count_patcher.py)로 K=8/32/128/512와 W=1024/무제한을 측정했다. 배경·학습 자료에서 각각 첫 4문서를 사용했다.
- 문서 일괄 처리와 접두부 64~128 재생을 분리하고 초기화·조회·갱신·교사 전송 비용을 포함했다.
- K=8은 작은 표본의 증분 처리에서 약 32배 빨랐으나 일괄 처리에서는 교사보다 약 5배 느렸다. 미학습 경계 계수와 작은 배경의 결과이며 전체 배경·BLT 전체 속도 근거가 아니다.
- 큰 K의 소표본 측정은 완료했지만 전체 크기의 선형 RAM 추정이 예산을 넘었다. 보수적으로 K=8 두 설정만 초기 학습 대상으로 선정했다. 큰 K의 실제 전체 구축 불가능성을 입증한 것은 아니다.
- 근거: [T05 보고서](evidence/english_count_pilot_20261019.json). 다음 단계: K=8 전체 배경의 실제 자원 확인.

## 2026-10-19 / T06 배경 / 전체 테이블 구축 [사후 정리]

- [구축 스크립트](scripts/build_count_background.py)로 배경 2,241문서만 사용했다. 문서별 BOS를 추가하고 문맥을 초기화했으며 pruning은 하지 않았다.
- 결과: 6,909,867개 문맥, 10,895,458개 간선, 구축 36.0초, 최대 RSS 약 2.51GiB, JSONL 326,063,930바이트.
- 읽기 전용 테이블과 해시를 원격 `runs/en-patcher-20261019-01/background_k8.jsonl`에 보존했다. 저장소에는 테이블을 복사하지 않았다.
- 근거: [구축 보고서](evidence/english_background_build_20261019.json). 자원 게이트 통과 후 라벨 생성으로 진행했다.

## 2026-10-19 / T06 라벨 / 생성·재개 검증 [사후 정리]

- [라벨 생성기](scripts/prepare_patcher_labels.py)에서 최대 2047 원문 바이트+BOS, 비중첩, 청크마다 교사·후보 상태 초기화, EOS 추가 없음으로 규약을 고정했다.
- 학습 2,488청크·4,041,644위치, 검증 290청크·463,770위치의 교사 엔트로피와 경계를 생성했다. 강제 위치 0·1은 평가에서 제외하고 가상 위치 n은 포함한다.
- 검증 첫 3문서의 첫 청크에서 64/128/256/n 접두부 진단을 수행했다. 전체 로짓은 저장하지 않았다.
- `--resume`으로 2,778개 청크를 재사용하며 입력·계약·manifest·파일 해시와 개수 일치를 확인했다. 학습/검증 첫 청크의 교사 재실행도 일치했다.
- 근거: [생성](evidence/english_label_generation_20261019.json), [재개](evidence/english_label_resume_20261019.json).
- 한계: W=무제한도 원문 전체가 아니라 독립 청크 안에서의 무제한이다. 최종 평가와 그 접두부 라벨은 생성하지 않았다. 다음 단계: 초기 두 후보의 학습.

## 2026-10-19 / T07 / 초기 두 설정 학습 [사후 정리]

- [학습 스크립트](scripts/fit_count_patcher.py)로 K=8, W=1024/무제한을 각각 학습했다. alpha=kappa=lambda=eta=1, rho=0.001을 사용했다.
- 학습 평균 패치 길이 4.53134와 교사 이력 특징을 고정했다. RMS 스케일링을 적용하되 L2는 원래 모수 좌표에서 계산했다.
- 두 L-BFGS-B 실행은 각각 13회 반복으로 수렴했다. 수치 기울기·유한 손실·부호 제약·투영 기울기 검사를 통과했다. 최대 RSS는 각각 약 3.05GiB였다.
- 특징 배열·학습 계수·해시는 원격 `runs/en-patcher-20261019-01/fits/`에 보존했다.
- 근거: [W=1024](evidence/english_fit_k8_w1024_20261019.json), [W=무제한](evidence/english_fit_k8_wunlimited_20261019.json). 다음 단계: 새 후보 상태로 임계값별 검증.

## 2026-10-19 / T08 / 초기 검증 게이트 미달 [사후 정리]

- 각 설정에서 coarse-to-fine 임계값 15개를 비교했다. 매번 청크 상태를 초기화하고 후보 자신의 이전 경계로 거리를 계산했다.
- W=1024: tau=0.21875, micro F1=0.62515, 문서 bootstrap 95% 구간 0.61671~0.63267.
- W=무제한: tau=0.25, micro F1=0.62581, precision=0.51650, recall=0.79379, 구간 0.61768~0.63270.
- 교사 이력 진단 F1도 약 0.623~0.624였다. 후보 이력의 누적 오차만으로 차이를 설명하기 어렵지만 원인을 확정한 것은 아니다.
- 두 초기 후보가 사전 기준 F1 0.90에 미달해 T09~T11은 보류했다. 24개 설정을 전부 탐색한 것이 아니며 ablation·BLT BPB·전체 속도·최종 평가는 미실행이다.
- 근거: 위 T07의 두 보고서. 검증 자료에서 임계값을 선택했으므로 독립 최종 평가 점수가 아니고 신뢰구간도 선택 후 검증 기술 통계다.

## 2026-10-19 / 실행 정리 / 회귀·보존 확인 [사후 정리]

- 원격 전체 테스트 18개와 `pip check`가 통과했다. 변경한 Python 파일의 에디터 진단·구문 검사를 확인했다.
- 작업 종료 후 GPU는 1MiB·사용률 0%였고 실행 산출물은 약 702MB였다. 원문·테이블·라벨·특징 배열은 원격에만 유지하고 작은 JSON 증거를 로컬로 회수했다.
- 전체 `git diff --check`는 기존 [docs/PLAN.md](docs/PLAN.md)의 무관한 trailing whitespace를 보고했다. 그 변경은 손대지 않았고 이번 README·패키지 설정 범위의 공백 검사는 통과했다.
- [task.md](task.md)에 실제 완료·실패·보류 상태와 재현 명령을 반영했다.

## 2026-10-19 / 결과 해석 / 자료 규모·평가 기준 논의 [사후 정리]

- 사용자 질문에 대해 문장 수를 집계하지 않았음을 명시했다. 학습+검증은 1,009문서, 별도 배경을 포함하면 3,250문서다.
- 현재 자료는 파일럿 규모이며 이 결과만으로 카운트 모형의 가능성을 부정할 수 없음을 정리했다. 정확한 교사 사전학습 문서 수는 확인되지 않았다.
- 자료 부족과 짧은 문맥의 표현력 한계를 구분할 진단으로 문맥 관측률·빈도별 오류·K별 성능·자료 규모별 학습 곡선을 제안했다. 배경 100MB/1GB 확대나 추가 실험을 실행한 것은 아니다.
- 약 0.626은 교사 경계의 정확한 위치를 재현하는 micro F1이다. 생성 품질·BPB가 아니며 경계가 달라도 유용한 패처일 가능성은 아직 평가하지 않았다.
- 다음 실험의 자료·모형·예산 변경은 미확정이다. 잠근 최종 평가 집합을 탐색에 사용하지 않는다.

## 2026-10-19 / 작업 방식 / 단계별 누적 로그 도입

- 사용자 요청: 단계마다 작업 결과를 `log.md`에 순차 저장하고 대화 보고만으로 끝내지 않는다.
- 수행: 이 파일을 생성해 기존 실행을 사후 정리했다. [AGENTS.md](AGENTS.md)에 단계별 즉시 기록·실패와 보류 기록·최종 응답 전 최신화 규칙을 추가하고 [task.md](task.md)에 연결했다.
- 검증: 실행 코드는 변경하지 않았다. `log.md`, `AGENTS.md`, `task.md` 세 문서의 에디터 진단에서 오류가 없음을 확인했다. 코드 테스트나 새 원격 실험은 실행하지 않았다.
- 다음 작업: 이후 실제 단계 전환과 결과가 생길 때 이 파일 끝에 새 기록을 추가한다. 이번 요청으로 새 실험을 시작하지 않는다.

## 2026-10-19 / 원인 진단 준비 / 사용 텍스트의 구성 확인

- 사용자 요청: 낮은 점수의 원인을 별도로 진단하되 우선 어떤 텍스트를 사용했는지 설명한다.
- 수행: [소스 고정 기록](evidence/english_dataset_sources_20261019.json), [최종 분할 기록](evidence/english_data_manifest_20261019.json), [표집 구현](scripts/prepare_english_data.py)을 대조했다. 새 실험이나 추가 다운로드는 실행하지 않았다.
- 확인: 배경·학습·검증·FineWeb 평가 자료는 `HuggingFaceFW/fineweb` v1.4.0의 `CC-MAIN-2025-05`에서 가져왔다. 전체 300개 shard 중 고정한 4개 shard의 11개 row group을 읽고 그룹 안의 행 순서를 무작위화해 표집했다. 전체 말뭉치의 균등 무작위 표본이나 주제별 층화 표본은 아니다.
- 확인: `wikimedia/wikipedia`의 `20231101.en`은 41개 shard 중 2개에서 확보한 별도 평가용 220문서다. 현재 F1 약 0.626 계산에는 사용하지 않았다. FineWeb-Edu, DCLM, 한국어 자료도 이번 학습·검증에 사용하지 않았다.
- 전처리: 256~65,536 UTF-8 바이트의 비어 있지 않은 문서를 대상으로 짧음(<=1024)·중간(<=8192)·김의 길이 구간을 나눴다. 배경을 먼저 분리한 뒤 라벨 대상은 구간별 문서 수 약 8:1:1로 학습·검증·평가를 나눴다. 원문 텍스트와 줄바꿈은 유지했고 소문자화·공백 정규화는 중복 검사에만 사용했다.
- 검증 구성: 학습 898문서는 짧음 356·중간 356·김 186, 검증 111문서는 44·44·23이다. F1은 문서별 평균이 아니라 평가 위치를 합산하므로 긴 문서의 기여가 더 크다.
- 한계: 주제·사이트 도메인·웹페이지 상용구/잡음의 실제 비율은 아직 측정하지 않았다. 데이터 이름만으로 해당 표본의 내용 분포나 교사 학습 자료와의 일치·불일치를 단정하지 않는다. 이 확인만으로 낮은 F1의 원인이 데이터라고 판단하지 않는다.
- 다음 작업: 별도 진단에서 학습·검증의 주제/도메인·길이별 구성과 문맥 관측 빈도별 오류를 확인해 자료 부족·분포 차이·모형 한계를 구분한다. 현재는 진단 방향만 기록했으며 평가 집합은 계속 잠근다.

## 2026-10-19 / 자료 규모 / FineWeb 전체 문서 수 확인

- 사용자 질문에 따라 [공식 데이터 카드](https://huggingface.co/datasets/HuggingFaceFW/fineweb)와 [공식 size API](https://datasets-server.huggingface.co/size?dataset=HuggingFaceFW%2Ffineweb&config=default)를 조회했다.
- 결과: 조회 시점의 전체 `default/train`은 `num_rows=25886364489`, 즉 25,886,364,489개 문서(약 259억 개)다. API의 `partial=false`, `estimated_num_rows=null`을 확인했다. 문장 수나 토큰 수가 아니라 문서 레코드 수다.
- 범위: 현재 공개 전체 구성의 수치이며 특정 수집분이나 실험에 사용한 고정 revision의 개별 표본 크기가 아니다. 페이지 하단의 별도 전체 행 합계를 `default`의 문서 수로 사용하지 않았다. 서로 다른 수집 시점 사이의 전역 중복 없는 URL 수를 뜻하지도 않는다.
- 다음 작업: 이 조회는 자료 규모 확인만이며 추가 다운로드·학습·원인 진단 실험은 실행하지 않았다.

## 2026-10-19 / 자원 추산 / 전체 FineWeb 처리 시간

- 사용자 질문: 전체 FineWeb으로 확률론적 패처를 시험할 경우 소요 시간을 추산한다. 새 원격 실험이나 다운로드는 실행하지 않았다.
- 근거: [배경 구축](evidence/english_background_build_20261019.json), [교사 라벨 생성](evidence/english_label_generation_20261019.json), [K=8·W=무제한 학습/검증](evidence/english_fit_k8_wunlimited_20261019.json)의 실제 처리 바이트 수와 시간을 대조했다.
- 산술 검증: 로컬 Python으로 `실측 초 / 실측 UTF-8 바이트 * 대상 바이트`를 계산했다. TB는 10^12바이트, 연은 365.25일로 환산했다. 원문 길이 필터·청크 길이·배치 1·기존 구현의 처리량이 유지된다는 가정이다.
- 배경 카운트 구축: 10,001,309바이트 / 35.9996초 = 약 277,817바이트/초. 원문 1TB당 약 41.66일.
- 교사 라벨 생성 파이프라인: 4,505,414바이트 / 57.0384초 = 약 78,989바이트/초. 원문 1TB당 약 146.53일. 로딩·저장·진단 호출도 포함한 파일럿 전체 시간이며 순수 GPU 처리량이 아니다.
- 후보 학습 특징 생성: 4,041,644위치 / 233.1588초 = 약 17,334위치/초. 원문 1TB당 약 667.70일. 현재 규약에서 평가 위치 수는 원문 바이트 수와 같다.
- 후보 순차 검증: 463,770위치 / 30.0939초 = 약 15,411위치/초. 원문 1TB·임계값 1개당 약 751.04일. 전체 15개 임계값 탐색은 같은 검증 분량을 반복 처리한다.
- 규모 예시(실제 원문 크기 측정 아님): 원문을 50~100TB로 가정하면 전량 1회 기준 구축 5.70~11.41년, 라벨 20.06~40.12년, 특징 91.40~182.81년, 순차 검증 102.81~205.62년이다. 각 행은 동일한 분량을 해당 단계에 투입하는 독립 시나리오이며 실제 분리된 배경·학습·검증 파이프라인의 총시간으로 합산하지 않는다.
- 공개 size API의 Parquet 파일 합계는 53,417,984,478,442바이트다. 이는 본문 UTF-8 바이트 합계가 아니며 Arrow 메모리 크기도 본문 크기로 간주하지 않았다. 53.4TB 전송만 계산하면 이상적 1Gbit/s에서 약 4.95일이나 실제 네트워크·디스크·서버 비용은 미측정이다. 스트리밍으로 원격 원문 전체의 로컬 저장은 피할 수 있다.
- 자원 한계: 전체 배경에서의 고유 문맥 수·RAM·조회 속도는 알 수 없어 소표본 테이블 크기를 단순 비례해 확정하지 않는다. 현재 float64 특징 5개+라벨 1개 저장 방식은 평가 원문 1TB당 약 48TB를 요구한다. 현 저장 예산과 자료구조 그대로 전체 실행을 시작할 수 없다.
- 해석: 위 수치는 규모를 보여주는 단순 환산이지 완료 일정·성능 상하한이 아니다. 큰 테이블의 캐시 미스·I/O는 비용을 늘릴 수 있고, 배치·컴파일·병렬화·저장 방식 변경은 줄일 수 있다. H200 속도나 GPU 수에 따른 선형 가속은 측정하지 않았다.
- 다음 작업: 전체 데이터 사용 여부를 정하려면 문맥 관측률/오류 진단과 단계적 확대 파일럿, 제한 메모리 카운트 구축 및 특징 처리 설계가 먼저 필요하다. 전체 데이터를 배경 학습과 검증에 중복 사용하지 않으며 이번 추산은 새 실행 예산 승인이나 대규모 작업 시작을 뜻하지 않는다.

## 2026-10-19 / 처리 방식 설명 / 스트리밍과 누적 상태 구분

- 사용자 질문: 전체 원문을 저장하지 않고 API/스트리밍으로 필요한 묶음을 임시 수신해 처리할 수 있는지 확인한다.
- 코드 확인: [수집기](scripts/prepare_english_data.py)는 `HfFileSystem.open`과 `ParquetFile.read_row_group`으로 원격 데이터 일부를 읽는다. 전체 FineWeb을 내려받지 않았으며 최종 선택한 표본만 로컬 JSONL로 보존했다. 다만 후보 문서 목록을 메모리에 모아 중복 검사·분할하므로 현재 구현 전체가 제한 메모리 스트리밍인 것은 아니다.
- 코드 확인: [배경 구축기](scripts/build_count_background.py)는 로컬 JSONL을 한 문서씩 읽지만, 누적 카운트 테이블은 메모리에 유지한다. 입력을 원격 스트림으로 바꾸는 것과 누적 테이블의 메모리 문제를 해결하는 것은 별개다.
- 설명 보충: 원문 전체의 사전 다운로드·영구 저장은 필수가 아니다. 원문 묶음을 읽고 카운트를 반영한 뒤 임시 입력을 폐기하는 처리가 가능하다. 네트워크의 실제 읽기 단위는 문서 한 개가 아니라 Parquet 블록/row group 등일 수 있다.
- 이전 자원 추산의 한계 보충: 원문 1TB당 특징 48TB는 현재 float64 특징/라벨 전체 저장 구현의 비용이지 모형의 필수 저장량이 아니다. 고정 데이터의 블록별 목적함수·기울기 합산과 재읽기/재계산 또는 제한 캐시로 전체 특징 상주·보존을 피할 수 있다. L-BFGS-B의 반복 패스에 따른 전송·재계산 비용은 별도로 남는다.
- 계획상 제약: 배경 카운트를 먼저 구축해 고정한 뒤 별도 학습 스트림으로 경계 계수를 학습하고, 검증은 별도 자료에서 수행한다. 학습 도중 배경 분포를 계속 바꾸면 기존의 고정 특징 최적화 실험과 달라지므로 조용히 변경하지 않는다.
- 재현·재개 요구: 고정 source revision, 문서 ID/해시, 분할·중복 정책, 처리 위치와 누적 카운트 체크포인트를 유지해 재개 때 중복 집계와 평가 누수를 막아야 한다. 원문을 버려도 이 상태는 필요하다.
- 다음 작업: 스트리밍은 저장 공간과 처리 시작 지연을 줄이지만 전량에 대한 카운트 갱신·교사 추론·후보 계산량을 없애지는 않는다. 이번에는 설계 설명과 코드 확인만 수행했으며 데이터 삭제·구현 변경·새 실험은 실행하지 않았다.

## 2026-10-19 / 자료 스키마 / 텍스트 종류 라벨 확인

- 사용자 질문에 따라 [FineWeb 공식 Data Fields](https://huggingface.co/datasets/HuggingFaceFW/fineweb#data-fields)와 [현재 표집 코드](scripts/prepare_english_data.py)를 확인했다.
- 결과: 일반 FineWeb의 공식 필드는 `text`, `id`, `dump`, `url`, `date`, `file_path`, `language`, `language_score`, `token_count`이며 뉴스·블로그·상품 설명 등의 장르나 정치·과학 등의 주제 라벨은 제공하지 않는다. `language_score`는 언어 판정 점수이지 텍스트 품질·장르 점수가 아니다.
- 현재 표본은 본문·ID·URL 및 revision·shard·행 위치·본문 해시를 저장했고 별도 주제/장르 분류는 수행하지 않았다. 웹사이트 도메인은 URL에서 추출할 수 있지만 사이트와 글 종류는 동일하지 않다.
- 다음 작업: 종류별 오류 진단이 필요하면 분류 기준을 먼저 고정하고 수작업 표본 검증을 포함해 별도 라벨을 만들어야 한다. 이번에는 스키마 확인만 했으며 원문 분류·데이터 변경·새 실험은 실행하지 않았다.

## 2026-10-19 / 확대 실험 논의 / 1GB 규모와 2시간 예산

- 사용자 질문: 약 1GB로 재시험하는 경우 문장 수와 2시간 작업량의 적절성을 추산한다. 이번 요청은 규모·예산 논의로 다루며 새 수집이나 장시간 작업을 시작하지 않았다.
- 단위: 1GB는 JSON/Parquet 용량이 아니라 원문 UTF-8 1,000,000,000바이트로 정의했다. [현재 분할](evidence/english_data_manifest_20261019.json)의 배경/학습 평균 문서 길이로 환산하면 약 222,187~224,071문서다. 현재 표집의 길이 분포가 유지된다는 가정이며 FineWeb 전체 평균은 아니다.
- 문장 수: 실제 문장 분할 집계는 아직 없다. 평균 문장당 100~200바이트를 가정하는 산술 예시는 약 500만~1,000만 문장이다. 웹 목록·메뉴·표 등에는 문장 경계가 모호하므로 측정값으로 해석하지 않는다.
- 시간: 기존 K=8 실측 속도를 유지한다고 가정하면 각 단계에 1GB를 따로 투입할 때 배경 구축 약 1.00시간, 교사 라벨 파이프라인 약 3.52시간, 후보 학습 특징 약 16.02시간, 후보 검증은 임계값 1개당 약 18.02시간이다. 큰 테이블·네트워크·전체 저장 및 재로딩 변화는 반영하지 않은 산술 환산이다.
- 2시간 파일럿 제안(미실행·예산 미확정): 기존 학습 약 4.04MB와 검증 약 0.46MB 및 교사 라벨을 고정하고, K=8·W=무제한 한 설정에서 배경 10MB 기준선과 100MB 확대를 먼저 비교한다. 배경별로 특징과 경계 계수를 다시 추정하고 동일 임계값 탐색 규칙을 적용해, 교사 경계 F1과 문맥 관측률/빈도별 오류를 확인한다.
- 비용 참고: 100MB 배경의 순수 구축은 선형 환산 약 6분, 기존 한 설정의 로딩·학습·검증 전체는 실측 약 12.6분이었다. 대규모 수집·중복 검사·카운트 저장·조회 비용은 별도이므로 총시간을 확정하지 않는다. 100MB 실측 RAM과 처리량을 본 뒤에만 300MB 또는 1GB 진행 여부를 결정한다.
- 운영 제안: 2시간은 원격 실험의 상한으로 두고 저장·검증·로그 정리 시간을 확보한다. 기존 RAM 48GiB 등 자원 게이트를 유지하고, 배경 확대 시 학습·검증·최종 평가와의 중복 유입을 막는다. 메모리 초과를 피하기 위해 조용히 pruning하거나 문맥 길이를 바꾸지 않는다.
- 한계 및 다음 작업: 고정 검증 자료는 배경 규모 효과를 비교하기 위한 진단용이며 최종 대표성 검증을 대체하지 않는다. 1GB 전체를 라벨링·학습·검증하는 일을 2시간에 끝내겠다고 약속하지 않는다. 실험 범위 확정 후 별도 실행 ID/설정과 단계별 로그로 진행한다.

## 2026-10-19 / 배경 100MB 확대 / 실행 요청 및 접속 방식 확인

- 사용자 요청: 배경 자료를 100MB로 확대해 다시 학습하고 점수 변화를 확인한다. 네트워크 불안정에 대비해 itcerdo 명령에 SSH 대신 tmux를 사용하도록 지정했다.
- 범위: 기존 학습·검증 자료와 교사 라벨은 고정하고 이전 10MB 결과와 비교한다. 기존 자료와 실험 산출물은 덮어쓰지 않는다. 앞서 제안한 K=8·W=무제한 단일 설정을 출발점으로 삼는다.
- 확인: SSH를 호출하지 않고 현재 터미널의 호스트·tmux 가용성을 조회했다. 호스트는 `Great-Smoky-Mountains.local`, `TMUX` 환경은 없고 `command -v tmux`도 경로를 반환하지 않았다. 원격 tmux 설치 여부는 아직 확인하지 않았다.
- 실행 경로 확인 필요: tmux는 원격 접속 프로토콜이 아니므로 Mac에서 itcerdo의 tmux에 명령을 넣으려면 별도 원격 연결이 필요하다. SSH 금지를 임의로 접속 예외로 해석하지 않고, 접속·전송·상태 확인만 SSH를 허용하는지 또는 다른 연결 수단이 있는지 확인한다.
- 다음 작업: 허용된 연결 방식이 확인되면 서버 tmux 안에서 수집·구축·학습·검증을 실행하고 단계별 파일 로그·종료 결과를 보존한다. 현재는 새 원격 연결·데이터 수집·재학습을 시작하지 않았다.

## 2026-10-19 / 배경 100MB 확대 / 접속 조건 명확화 및 준비

- 사용자 정정: SSH 접속을 금지한 것이 아니라 네트워크 단절에 대비해 장시간 작업을 itcerdo의 tmux 안에서 유지하라는 의미다. 앞 항목의 접속 확인 차단 사유는 해소됐다.
- 확인: SSH로 `/usr/bin/tmux` 존재, 실행 중인 tmux 세션 없음, 가용 RAM 약 58GiB·여유 디스크 약 261GiB를 확인했다. 기존 작업·환경을 변경하지 않았다.
- 실행 범위: 원문 UTF-8 총 100MB 배경에 기존 10MB를 포함하고, 기존 학습·검증과 교사 라벨을 고정한다. K=8·W=무제한, alpha=kappa=lambda=eta=1, rho=.001, 동일 임계값 탐색으로 배경 규모 효과를 비교한다. 최종 평가 라벨·성능은 사용하지 않는다.
- 다음 작업: 재사용 가능한 학습 진입점과 중복 배제·해시·자원 제한을 갖춘 확대 실행기를 준비하고 테스트한다. 수집·구축·학습은 새 tmux 세션과 별도 실행 디렉터리에서 수행하며 각 단계의 결과를 즉시 로그에 추가한다.

## 2026-10-19 / 배경 100MB 확대 / 학습 진입점 검증 및 실행기 준비

- 학습 스크립트에 별도 배경 보고서·출력 경로·단계별 로그를 추가했다. 기존 특징·최적화·임계값 탐색 계산은 유지하고 문서별 집계를 보존해 paired bootstrap 비교에 사용한다.
- 검증: 로컬 기본 테스트 3개 통과, 수치/GPU 의존 테스트 15개는 환경 부재로 skip. 원격 후보 테스트 12개는 전부 통과했고 새 CLI 옵션도 확인했다.
- 준비: 별도 실행 `en-patcher-bg100-20261019-01`, tmux `blt-bg100-20261019`, 원문 100,000,000바이트 목표, 7,200초 상한을 설정했다. 기존 10MB를 포함하고 기존 5개 분할 원문은 중복 배제에만 사용한다. 평가 라벨/성능은 읽지 않는다.
- 다음 작업: 확대 표집의 원문 보존·중복 배제 합성 테스트와 전체 회귀 검사를 통과한 뒤 원격 tmux에서 실행한다. 수집·구축은 프로세스를 분리해 임시 메모리를 해제하고 학습 결과는 새 경로에만 기록한다.

## 2026-10-19 / 배경 100MB 확대 / 시간 제한 철회

- 사용자 지시에 따라 앞서 제안한 2시간 상한을 철회했다. 이번 실행은 수집·구축·학습·비교 모두 임의의 벽시계 시간 제한 없이 진행한다. 기존 학습 스크립트의 6시간 상한도 명시적 옵션으로 이번 실행에서 해제한다.
- RAM 48GiB와 디스크 여유 공간 등 자원 보호는 유지한다. 임계값 후보 수·최적화 수렴 설정은 비교 조건이므로 변경하지 않는다.
- 직전 원격 전체 테스트 호출은 도구 출력이 기록되지 않아 통과 여부를 아직 확인하지 못했다. 원격 상태 확인 후 검증을 완료하고 tmux 작업을 시작한다.

## 2026-10-19 / 배경 100MB 확대 / 실행 전 검증 완료

- 원격에서 기존 검증·실험 프로세스가 없는 것을 확인하고 코드를 동기화했다. `OPENBLAS_NUM_THREADS=8 ../.venv/bin/python -m unittest discover -s tests -v`: 전체 19개 통과, skip 없음. 확대 합성 테스트에서 기존 배경 보존·기존 분할 중복 배제·동일 seed 재현성을 확인했다. `pip check`도 통과했다.
- 변경된 Python 파일 3개 편집기 진단 오류 없음. `--no-time-limit` CLI를 확인했고 실행기는 subprocess timeout을 사용하지 않는다. 기준 배경과 동일하게 BOS+원문 바이트 ID, EOS 미추가, 원문 문서별 문맥 초기화로 구축한다.
- 원격 자원 실측: RAM 총 60GiB/가용 58GiB, 디스크 여유 261GiB. 기존 tmux 세션 없음. 현재까지 100MB 수집·학습 결과는 아직 없으며 다음 단계에서 새 세션을 시작한다.
- 다음 작업: 원격 tmux에서 수집→구축→재학습→동일 검증 문서 paired 비교를 수행한다. 단계별 로그는 원격 source/log.md에 즉시 추가하고 로컬에도 가져온다. 기존 학습·검증 라벨을 재사용하므로 GPU 교사 추론은 하지 않는다.
## 2026-10-19 / en-patcher-bg100-20261019-01 / Started

- Server tmux: `blt-bg100-20261019`; elapsed: 0.0s.
- Result: {"target_utf8_bytes": 100000000, "next": "Nested background sampling", "wall_clock_limit": null, "host_ram_gib": 48}

## 2026-10-19 / en-patcher-bg100-20261019-01 / prepare started

- Server tmux: `blt-bg100-20261019`; elapsed: 0.0s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/data_preparation.json"}

## 2026-10-19 / en-patcher-bg100-20261019-01 / prepare completed

- Server tmux: `blt-bg100-20261019`; elapsed: 110.9s.
- Result: {"status": "prepared", "documents": 20947, "utf8_bytes": 100000419, "elapsed_seconds": 110.19228679034859, "peak_host_rss_bytes": 961056768}

## 2026-10-19 / en-patcher-bg100-20261019-01 / build started

- Server tmux: `blt-bg100-20261019`; elapsed: 110.9s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/background_build.json"}

## 2026-10-19 / en-patcher-bg100-20261019-01 / build completed

- Server tmux: `blt-bg100-20261019`; elapsed: 584.8s.
- Result: {"status": "built", "documents": 20947, "utf8_bytes": 100000419, "contexts": 30948756, "table_bytes": 1506425405, "elapsed_seconds": 471.8086334178224, "peak_host_rss_bytes": 11869417472}

## 2026-10-19 / en-patcher-bg100-20261019-01 / fit started

- Server tmux: `blt-bg100-20261019`; elapsed: 584.8s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit/report.json"}

## 2026-10-19 / 100MB follow-up / Background loaded and verified

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 83.0s.
- Result: {"seconds": 82.97771720215678, "sha256": "36e21f7c5420ca8a2fe49c62e1aa3f324d97233cb2670d5c35c8917f32b0e5a4"}

## 2026-10-19 / 100MB follow-up / Fixed training features completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 348.2s.
- Result: {"positions": 4041644, "seconds": 264.78701470419765, "next": "Constrained fit"}

## 2026-10-19 / 100MB follow-up / Boundary fit completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 349.5s.
- Result: {"fit": {"coefficients": [-4.484732340712917, 0.0, 0.0, 2.1917862256548677, 0.09723356032873723], "rho": 0.001, "loss": 0.29668917372548087, "iterations": 14, "evaluations": 15, "message": "CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL", "feature_scale": [1.0, 6.216751139212366, 169.74619372441887, 1.5381555801289404, 3.868221269945194], "gradient": [-1.422604156003926e-09, 0.01822104404814276, 0.5932631590971649, -9.495801552624611e-09, -2.500033495516805e-09], "scaled_projected_gradient_max": 6.173498750905677e-09}, "next": "Fresh sequential threshold trials"}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 390.4s.
- Result: {"tp": 104640, "fp": 359130, "fn": 0, "precision": 0.22562908338184876, "recall": 1.0, "f1": 0.3681849369293292, "threshold": 0.0, "elapsed_seconds": 40.58530273381621}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 431.3s.
- Result: {"tp": 99274, "fp": 99392, "fn": 5366, "precision": 0.4997030191376481, "recall": 0.9487194189602447, "f1": 0.6546128332443143, "threshold": 0.125, "elapsed_seconds": 40.91686011478305}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 472.1s.
- Result: {"tp": 88724, "fp": 55684, "fn": 15916, "precision": 0.6143980942884051, "recall": 0.8478975535168196, "f1": 0.7125052198772928, "threshold": 0.25, "elapsed_seconds": 40.8120469446294}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 512.7s.
- Result: {"tp": 78064, "fp": 38003, "fn": 26576, "precision": 0.6725770460165249, "recall": 0.7460244648318043, "f1": 0.7073994028281839, "threshold": 0.375, "elapsed_seconds": 40.60233246628195}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 553.1s.
- Result: {"tp": 67673, "fp": 25752, "fn": 36967, "precision": 0.7243564356435643, "recall": 0.6467220948012232, "f1": 0.6833413273420342, "threshold": 0.5, "elapsed_seconds": 40.4295607348904}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 593.5s.
- Result: {"tp": 55597, "fp": 14478, "fn": 49043, "precision": 0.7933927934356048, "recall": 0.5313168960244649, "f1": 0.6364307586641101, "threshold": 0.625, "elapsed_seconds": 40.39765777764842}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 633.9s.
- Result: {"tp": 38499, "fp": 6019, "fn": 66141, "precision": 0.8647962621860821, "recall": 0.3679185779816514, "f1": 0.5162177020340847, "threshold": 0.75, "elapsed_seconds": 40.41916962200776}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 674.2s.
- Result: {"tp": 12773, "fp": 1403, "fn": 91867, "precision": 0.9010299097065463, "recall": 0.12206613149847095, "f1": 0.21500471316994343, "threshold": 0.875, "elapsed_seconds": 40.20546589791775}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 714.7s.
- Result: {"tp": 0, "fp": 0, "fn": 104640, "precision": 0.0, "recall": 0.0, "f1": 0.0, "threshold": 1.0, "elapsed_seconds": 40.581165122333914}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 755.6s.
- Result: {"tp": 96816, "fp": 83853, "fn": 7824, "precision": 0.5358749979243811, "recall": 0.9252293577981652, "f1": 0.678674700062038, "threshold": 0.15625, "elapsed_seconds": 40.84569265879691}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 795.8s.
- Result: {"tp": 94224, "fp": 71733, "fn": 10416, "precision": 0.5677615285887309, "recall": 0.9004587155963303, "f1": 0.6964157030565749, "threshold": 0.1875, "elapsed_seconds": 40.20702310791239}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 836.3s.
- Result: {"tp": 91497, "fp": 62803, "fn": 13143, "precision": 0.5929812054439404, "recall": 0.8743979357798165, "f1": 0.7067042558121572, "threshold": 0.21875, "elapsed_seconds": 40.519197998102754}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 876.6s.
- Result: {"tp": 85958, "fp": 50027, "fn": 18682, "precision": 0.6321138360848623, "recall": 0.8214640672782875, "f1": 0.7144561038961039, "threshold": 0.28125, "elapsed_seconds": 40.328261198010296}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 916.9s.
- Result: {"tp": 83288, "fp": 45343, "fn": 21352, "precision": 0.6474955492843871, "recall": 0.7959480122324158, "f1": 0.7140879063406939, "threshold": 0.3125, "elapsed_seconds": 40.22302505373955}

## 2026-10-19 / 100MB follow-up / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 957.0s.
- Result: {"tp": 80644, "fp": 41424, "fn": 23996, "precision": 0.6606481633188059, "recall": 0.7706804281345566, "f1": 0.7114349736224571, "threshold": 0.34375, "elapsed_seconds": 40.182310733012855}

## 2026-10-19 / 100MB follow-up / Fit and validation finished

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/fit`; elapsed: 1028.8s.
- Result: {"status": "validation_gate_failed", "f1": 0.7144561038961039, "error": null, "next": "Paired baseline comparison if successful"}

## 2026-10-19 / en-patcher-bg100-20261019-01 / fit completed

- Server tmux: `blt-bg100-20261019`; elapsed: 1615.2s.
- Result: {"status": "validation_gate_failed", "elapsed_seconds": 1028.778076855, "peak_host_rss_bytes": 12326137856}

## 2026-10-19 / en-patcher-bg100-20261019-01 / compare started

- Server tmux: `blt-bg100-20261019`; elapsed: 1615.2s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/comparison.json"}

## 2026-10-19 / en-patcher-bg100-20261019-01 / compare completed

- Server tmux: `blt-bg100-20261019`; elapsed: 1663.8s.
- Result: {"status": "compared", "f1_difference": 0.08864994392985714, "documents": 111, "quality_gate_passed": false}

## 2026-10-19 / en-patcher-bg100-20261019-01 / Finished

- Server tmux: `blt-bg100-20261019`; elapsed: 1663.8s.
- Result: {"status": "completed", "report": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg100-20261019-01/run_report.json", "next": "Review measured comparison or failure"}

## 2026-10-19 / 배경 100MB 확대 / 결과 회수 및 비교 해석

- 시간 상한 없이 원격 tmux 실행이 완료됐다. 위 단계별 기록은 서버 실행 중 즉시 기록된 로그를 동기화한 것이다. 원문·테이블은 서버에 보존하고 작은 JSON 보고서 5개만 `evidence/english_bg100_{data,build,fit,comparison,run}_20261019.json`으로 회수했다.
- 배경은 기존 2,241문서를 모두 포함한 20,947문서·100,000,419 UTF-8 바이트다. 기존 train/validation 라벨과 K=8/W=무제한, 평활화 계수 1, rho=.001을 유지했다. 기준 테이블로 검증을 재실행해 기존 F1 재현을 확인했다.
- 실측 검증 F1: 10MB 0.6258061599662468 → 100MB 0.7144561038961039. 개선 +0.08864994392985714(100점 척도 +8.865점), 동일 111개 문서 paired bootstrap 2,000회 차이 95% 구간 [0.0837005310504829, 0.0926197235751663]. 정밀도 0.51650→0.63211, 재현율 0.79379→0.82146, entropy MAE 0.75249→0.57353. 선택 임계값은 .25→.28125다.
- 자원/시간 실측: 수집 110.2초, 배경 구축·저장 471.8초(카운트 구축 430.2초), 학습·검증 1,028.8초, 전체 1,663.8초(약 27.7분). 구축 RSS 11,869,417,472바이트, 학습 RSS 12,326,137,856바이트(약 11.48GiB), 배경 테이블 1,506,425,405바이트. 이 100MB 설정은 현재 하드웨어 보호 범위 내에서 완료됐다.
- 해석/한계: 배경 확대가 이 구성의 경계 근사를 개선한 관측이며, 초기 .625 점수가 모델의 고정된 상한은 아니었다. 다만 .90 목표 미달이고 추가 표집의 구성도 바뀌므로 모든 개선을 자료량 하나의 효과로 분리하지 않는다. 같은 검증 자료로 임계값을 선택했으므로 위 구간은 독립 평가 신뢰구간이 아니다. BLT BPB·생성 품질·전체 모델 속도·다른 자료로 일반화하지 않는다. 최종 평가 라벨/성능은 열지 않았다.
- 다음 작업: 회수 보고서 해시와 집계 일치성을 검사하고 이번 비교 결과를 사용자에게 전달한다. 더 큰 배경·새 모델 탐색은 이번 요청 범위에서 자동 실행하지 않는다.

## 2026-10-19 / 배경 100MB 확대 / 최종 무결성 검증 완료

- 회수한 단계 보고서 4개의 SHA256이 실행 보고서와 일치했다. 확대 계획 해시, 기존 라벨 보고서 해시, 시간 상한 null, 기존 배경 2,241문서 보존 보고, 100,000,419바이트 집계가 모두 일치했다.
- 111개 문서별 TP/FP/FN의 합계가 최종 검증 집계와 일치했고 비교 보고서의 새 F1도 학습 보고서와 일치했다. 기준 점수 재현 완료 상태를 확인했다. 검사 명령은 모든 assertion을 통과했다.
- 이번 요청의 100MB 재학습·점수 비교는 완료됐다. task.md를 완료 상태로 갱신했고 결과·한계를 사용자에게 전달한다. 추가 실험은 시작하지 않는다.

## 2026-10-20 / 배경 1GB 확대 / 요청 및 자원 검토

- 사용자 요청에 따라 배경을 1,000,000,000 UTF-8 바이트로 확대한다. 기존 100MB 전체를 포함하고 학습·검증 라벨, K=8/W=무제한, 평활화·정규화·임계값 탐색 규약을 유지한다. 시간 상한 없이 itcerdo tmux에서 수행한다.
- 원격 자원 실측: 총 RAM 60GiB/가용 58GiB, 디스크 여유 259GiB, 기존 tmux 세션 및 후보 학습 프로세스 없음. 이전 100MB 구축·학습 최대 RSS는 약 11.48GiB였으므로 1GB 전체 사전을 한 프로세스에 적재하는 방식은 메모리 초과 위험이 있다. 1GB 메모리 사용량은 아직 측정하지 않았다.
- 구현 가설: 문서 경계를 지켜 블록별 전체 카운트를 저장하고, 고정된 학습·검증 입력의 모든 접두부/짧은 접미부/가상 다음 위치에서 조회되는 문맥만 정확히 합산하면 전체 테이블과 수치적으로 동일하다. 모든 카운트는 디스크에 보존하며 모델 차수·카운트·확률을 근사하거나 가지치기하지 않는다. 검증 라벨은 이 로딩 선택에 사용하지 않는다.
- 다음 작업: 합성 입력으로 전체 카운트·확률·교사 특징·순차 경계 일치를 검증한 뒤 실행기에 적용한다. 아직 1GB 데이터 수집이나 학습은 시작하지 않았다.

## 2026-10-20 / 배경 1GB 확대 / 블록 합산 동등성 테스트 통과

- 로컬 기본 3개 테스트 통과, 수치 의존성 부재로 17개 skip. 원격 후보 테스트는 13개 모두 통과했다. 새 테스트는 여러 문서의 블록 합산과 전체 카운트 일치, EOS/가상 슬롯을 포함한 조회 문맥 선택, 확률 배열·교사 특징 배열·여러 임계값의 순차 경계 완전 일치 및 변조된 manifest 거부를 확인했다.
- 다음 구현: 기존 100MB 전체를 확대 배경의 앞부분으로 보존하고 25MB 원문 단위/문서 경계에서 블록을 저장한다. 실제 100MB 전체 검증 문서의 F1·오차·문서별 집계가 기존 저장 방식과 동일한지 검증하는 사전 단계를 추가했다. 1GB의 직접 비교 기준은 100MB F1 .714456이며 학습·검증 라벨은 최초 실험에서 고정한다.
- 동작 변경 범위는 실험 실행기와 로더이며 공개 패키지의 확률·경계 계산은 수정하지 않았다. 로딩 최적화 시간은 일반 패처 추론 속도로 보고하지 않는다. 다음 단계는 블록 구축 포함 전체 회귀 검증이다.

## 2026-10-20 / 배경 1GB 확대 / 실행 전 검증 완료

- 원격 `OPENBLAS_NUM_THREADS=8 ../.venv/bin/python -m unittest discover -s tests -v`: 전체 21개 통과, skip 없음. 문서 경계에서 나눈 블록의 전체 카운트·바이트 합계·기존 출력 덮어쓰기 거부도 확인했다. `pip check` 통과.
- Pylance로 실행기·학습 스크립트 문법 오류 없음, 수정 테스트 및 1GB 계획 편집기 진단 오류 없음. 날짜가 바뀐 실험을 정확히 기록하도록 새 실행 로그는 실제 서버 시각과 실행 ID를 기록한다. 기존 로그는 수정하지 않았다.
- 실행 계획: `en-patcher-bg1gb-20261020-01`, tmux `blt-bg1gb-20261020`. RAM 48GiB 주소 공간 제한, 디스크 여유 최소 100GiB, 배경 블록 저장 합계 최대 100GiB를 유지하며 시간 제한은 없다. 입력 1GB는 원문 UTF-8 기준이고 전체 문서 보존으로 마지막 문서만큼 초과할 수 있다.
- 다음 단계: tmux에서 실제 100MB 배경의 로딩 동등성 검사를 수행한다. 통과해야 1GB 수집으로 진행하며, 기존 20,947문서 전체를 포함한다. 아직 1GB 점수·메모리 사용량은 측정하지 않았다.

## 2026-10-19T22:29:33+00:00 / en-patcher-bg1gb-20261020-01 / Started

- Server tmux: `blt-bg1gb-20261020`; elapsed: 0.0s.
- Result: {"target_utf8_bytes": 1000000000, "next": "Nested background sampling", "wall_clock_limit": null, "host_ram_gib": 48}

## 2026-10-19T22:29:33+00:00 / en-patcher-bg1gb-20261020-01 / verify started

- Server tmux: `blt-bg1gb-20261020`; elapsed: 0.0s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/storage_equivalence.json"}

## 2026-10-19T22:32:43+00:00 / en-patcher-bg1gb-20261020-01 / verify completed

- Server tmux: `blt-bg1gb-20261020`; elapsed: 190.4s.
- Result: {"status": "verified", "elapsed_seconds": 188.2676539211534, "peak_host_rss_bytes": 12497739776}

## 2026-10-19T22:32:43+00:00 / en-patcher-bg1gb-20261020-01 / prepare started

- Server tmux: `blt-bg1gb-20261020`; elapsed: 190.4s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/data_preparation.json"}

## 2026-10-20 / 배경 1GB 확대 / 진행 확인 및 남은 시간 추정

- 사용자 완료 시간 질문에 따라 원격 상태를 확인했다. 관측 시각은 서버 2026-10-19T23:03:20+00:00, 전체 경과 약 33분 48초다. 사전 실제 자료 동등성 검사는 통과했고 수집·중복 배제 후 217,669문서·1,000,000,955 UTF-8 바이트가 준비됐다.
- 실측 구축 진행: 8개 블록, 37,375문서, 200,075,019바이트(약 20.0%) 완료. 구축 단계 누적 907.2초이며 최근 25MB 블록은 약 112~114초/개다. 구축 단계 최고 RSS는 5,282,766,848바이트(약 4.92GiB)이고 현재 프로세스는 CPU 약 100%로 진행 중이다. 사전 검사 최고 RSS와 구축 최고 RSS는 별도 단계 값이다.
- 추정: 같은 속도가 유지되면 남은 약 800MB 구축은 약 60분. 이후 전체 블록 스캔·조회 문맥 합산, 학습·임계값 탐색·100MB 비교에 약 30~60분을 잠정 배정해 지금부터 약 1시간 30분~2시간을 예상한다. 1GB 블록 로딩 시간은 아직 측정하지 않았으므로 보장된 완료 시각이나 제한 시간이 아니다. 단계별 실측으로 추정을 갱신한다.
- 원격 실행은 그대로 계속한다. 이 항목은 로컬에서 추가한 상태 관측 기록이며, 이후 원격 로그를 가져올 때 덮어쓰지 말고 병합해야 한다.


## 2026-10-20 / 배경 1GB 확대 / 원격 단계별 로그 회수

- 아래는 서버가 각 단계 실행 시 기록한 로그의 회수본이다. 로컬 진행 관측과 시간상 겹치는 과거 기록을 원본 시각 그대로 뒤에 추가하며, 기존 로컬 기록은 보존한다.


## 2026-10-19T22:35:14+00:00 / en-patcher-bg1gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg1gb-20261020`; elapsed: 150.5s.
- Result: {"shard": "data/CC-MAIN-2025-05/003_00015.parquet", "candidate_bytes": 450001016}

## 2026-10-19T22:37:55+00:00 / en-patcher-bg1gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg1gb-20261020`; elapsed: 312.0s.
- Result: {"shard": "data/CC-MAIN-2025-05/001_00011.parquet", "candidate_bytes": 450005725}

## 2026-10-19T22:40:23+00:00 / en-patcher-bg1gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg1gb-20261020`; elapsed: 459.7s.
- Result: {"shard": "data/CC-MAIN-2025-05/002_00008.parquet", "candidate_bytes": 450000174}

## 2026-10-19T22:43:47+00:00 / en-patcher-bg1gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg1gb-20261020`; elapsed: 663.4s.
- Result: {"shard": "data/CC-MAIN-2025-05/004_00040.parquet", "candidate_bytes": 450002479}

## 2026-10-19T22:47:57+00:00 / en-patcher-bg1gb-20261020-01 / prepare completed

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1104.8s.
- Result: {"status": "prepared", "documents": 217669, "utf8_bytes": 1000000955, "elapsed_seconds": 911.253495470155, "peak_host_rss_bytes": 7345192960}

## 2026-10-19T22:47:57+00:00 / en-patcher-bg1gb-20261020-01 / build started

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1104.8s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_build.json"}

## 2026-10-19T22:49:53+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 114.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00000.jsonl", "table_sha256": "48c5d140ef079f966394793045033bc4676f90be2f45f2300c8966cb3977fe9c", "table_bytes": 597268295, "documents": 4767, "utf8_bytes": 25005291, "contexts": 12480893, "edges": 20349195, "completed_documents": 4767, "completed_utf8_bytes": 25005291, "peak_host_rss_bytes": 5113217024}

## 2026-10-19T22:51:45+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 226.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00001.jsonl", "table_sha256": "bd2e408b2f0cf17f044162513c8d40f3bb6596c728e226a39f7030707c3e3f6b", "table_bytes": 593955276, "documents": 3960, "utf8_bytes": 25020142, "contexts": 12396031, "edges": 20260152, "completed_documents": 8727, "completed_utf8_bytes": 50025433, "peak_host_rss_bytes": 5113217024}

## 2026-10-19T22:53:37+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 338.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00002.jsonl", "table_sha256": "e4c9d4f152b29f27a16b5b8cb5cb74f6b38603cc2d3650b27c1a87643e9c5e6f", "table_bytes": 594690576, "documents": 4125, "utf8_bytes": 25001075, "contexts": 12409517, "edges": 20289780, "completed_documents": 12852, "completed_utf8_bytes": 75026508, "peak_host_rss_bytes": 5113217024}

## 2026-10-19T22:55:33+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 454.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00003.jsonl", "table_sha256": "097806b2c800aef517a943c5725425ebc07405a82b4f449821bdcd417f76a982", "table_bytes": 624104624, "documents": 8101, "utf8_bytes": 25009387, "contexts": 13071460, "edges": 21217478, "completed_documents": 20953, "completed_utf8_bytes": 100035895, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T22:57:27+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 568.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00004.jsonl", "table_sha256": "29f2cff4408a7a6b4dee4bba2644651da49187923097702b0570bf2f0616897e", "table_bytes": 594662621, "documents": 4188, "utf8_bytes": 25004956, "contexts": 12414670, "edges": 20283710, "completed_documents": 25141, "completed_utf8_bytes": 125040851, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T22:59:21+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 682.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00005.jsonl", "table_sha256": "1ebfd9a11f75073812a5751becca09483e1f90073e8a12d7e0453e83d3c5bcb8", "table_bytes": 600818829, "documents": 4116, "utf8_bytes": 25014995, "contexts": 12543622, "edges": 20491600, "completed_documents": 29257, "completed_utf8_bytes": 150055846, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:01:13+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 794.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00006.jsonl", "table_sha256": "846a6723ea382810ff68700b646f44ef417f4cfc046ed5f1c1e1c36cf794e04f", "table_bytes": 591301857, "documents": 4053, "utf8_bytes": 25002233, "contexts": 12340780, "edges": 20171469, "completed_documents": 33310, "completed_utf8_bytes": 175058079, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:03:05+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 907.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00007.jsonl", "table_sha256": "afb4fe77980de9e2f3889e590929f42a0de39a314b46ef40de7e858dcf51024d", "table_bytes": 600209666, "documents": 4065, "utf8_bytes": 25016940, "contexts": 12543084, "edges": 20448810, "completed_documents": 37375, "completed_utf8_bytes": 200075019, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:05:00+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1021.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00008.jsonl", "table_sha256": "b76f0120e60c9b10155e2535aabf62108b55de106eef430b53124be714b2e72e", "table_bytes": 602340044, "documents": 4089, "utf8_bytes": 25012712, "contexts": 12596515, "edges": 20517713, "completed_documents": 41464, "completed_utf8_bytes": 225087731, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:06:53+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1134.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00009.jsonl", "table_sha256": "293644d597f511125cf4032f7b3d98149845905ed55cd11ff6975f2f0483874c", "table_bytes": 606895848, "documents": 4062, "utf8_bytes": 25001392, "contexts": 12687980, "edges": 20662559, "completed_documents": 45526, "completed_utf8_bytes": 250089123, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:08:45+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1246.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00010.jsonl", "table_sha256": "cb87ee2785aae34f1ecbd57e3c5421c3250cde4e380536434e9ebef78f7dca2d", "table_bytes": 594315550, "documents": 4158, "utf8_bytes": 25002120, "contexts": 12413041, "edges": 20262541, "completed_documents": 49684, "completed_utf8_bytes": 275091243, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:10:38+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1359.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00011.jsonl", "table_sha256": "66221d81a1233360c4dc592ce0c13e3134d4618d8406e196f131c9dd2ec952be", "table_bytes": 593432801, "documents": 4198, "utf8_bytes": 25000056, "contexts": 12385244, "edges": 20238475, "completed_documents": 53882, "completed_utf8_bytes": 300091299, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:12:31+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1472.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00012.jsonl", "table_sha256": "a83d9c1b47023a8121a5a9bbec52fd15191ef31af09e6103f9ffa4188d715a66", "table_bytes": 589198298, "documents": 4100, "utf8_bytes": 25003398, "contexts": 12297444, "edges": 20101159, "completed_documents": 57982, "completed_utf8_bytes": 325094697, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:14:26+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1587.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00013.jsonl", "table_sha256": "89071853090c13aee079dafec16a9ce2206c3b65830e425deddc35654f10e29d", "table_bytes": 596231109, "documents": 4158, "utf8_bytes": 25000951, "contexts": 12462248, "edges": 20315079, "completed_documents": 62140, "completed_utf8_bytes": 350095648, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:16:20+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1701.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00014.jsonl", "table_sha256": "92b71561f50e8b27b139045eb317e7c190a78abaad09c44c1c58defedc1a88c3", "table_bytes": 596680555, "documents": 4026, "utf8_bytes": 25003964, "contexts": 12465395, "edges": 20333461, "completed_documents": 66166, "completed_utf8_bytes": 375099612, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:18:13+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1815.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00015.jsonl", "table_sha256": "254c49f36740886c4e7029414b6c772c98c27ec5bd11ca62a5d786ea2bdca836", "table_bytes": 594976401, "documents": 4179, "utf8_bytes": 25016793, "contexts": 12425585, "edges": 20288240, "completed_documents": 70345, "completed_utf8_bytes": 400116405, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:20:09+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 1930.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00016.jsonl", "table_sha256": "01b59fc92f952d8262e132feadd988bd97bcfc97d9b32a77901ea7c089be556a", "table_bytes": 603263122, "documents": 4092, "utf8_bytes": 25036048, "contexts": 12600684, "edges": 20554358, "completed_documents": 74437, "completed_utf8_bytes": 425152453, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:22:02+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2043.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00017.jsonl", "table_sha256": "cfa5193538933e4a4ecfc29f888e16d32fb01365d5720527527ce1541c51dc47", "table_bytes": 587057184, "documents": 4086, "utf8_bytes": 25012481, "contexts": 12248259, "edges": 20031681, "completed_documents": 78523, "completed_utf8_bytes": 450164934, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:23:57+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2158.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00018.jsonl", "table_sha256": "a0b2bcc1e30e044696a128a4f8dc1f0da121168c4fbd7f585062a9372226a8b2", "table_bytes": 597912262, "documents": 4155, "utf8_bytes": 25020543, "contexts": 12483405, "edges": 20386821, "completed_documents": 82678, "completed_utf8_bytes": 475185477, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:25:51+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2272.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00019.jsonl", "table_sha256": "e4c5c7983f99c437c39f579f284281b766f8e383d027032f7ae9edb67c30bdba", "table_bytes": 596477281, "documents": 4047, "utf8_bytes": 25001520, "contexts": 12460186, "edges": 20329523, "completed_documents": 86725, "completed_utf8_bytes": 500186997, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:27:46+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2387.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00020.jsonl", "table_sha256": "840036734652fa6a2f93137aac06d54a709319fedeeed1fea45d16e55ac562e9", "table_bytes": 595987685, "documents": 4155, "utf8_bytes": 25007432, "contexts": 12442063, "edges": 20326338, "completed_documents": 90880, "completed_utf8_bytes": 525194429, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:29:40+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2502.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00021.jsonl", "table_sha256": "17afbe9b8a3421a1864d093450aea916a4b6f542f47aa2bb3ab7fb263ed8932c", "table_bytes": 600137744, "documents": 4107, "utf8_bytes": 25053225, "contexts": 12534002, "edges": 20458459, "completed_documents": 94987, "completed_utf8_bytes": 550247654, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:31:35+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2616.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00022.jsonl", "table_sha256": "84fd108f54cecb7502e89248f2a64fa0d13ebb34395ac88b6119eb91e0729323", "table_bytes": 590619677, "documents": 4139, "utf8_bytes": 25002288, "contexts": 12328149, "edges": 20147894, "completed_documents": 99126, "completed_utf8_bytes": 575249942, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:33:31+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2732.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00023.jsonl", "table_sha256": "38e82bf5d810f95f3b812f3f18531176343805eee3c83390d94746b21fb25750", "table_bytes": 602352138, "documents": 4141, "utf8_bytes": 25001920, "contexts": 12596857, "edges": 20512536, "completed_documents": 103267, "completed_utf8_bytes": 600251862, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:35:27+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2848.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00024.jsonl", "table_sha256": "0ca6f44fd11b6dd13238917ad6ae55f7476de8b96b762a4d9a36fc29b7f5323f", "table_bytes": 599970973, "documents": 4026, "utf8_bytes": 25008906, "contexts": 12535464, "edges": 20445858, "completed_documents": 107293, "completed_utf8_bytes": 625260768, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:37:22+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 2963.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00025.jsonl", "table_sha256": "ca881c0a2980b5b138fb53ea69987d907d42af665e95918dcae696b5f6927062", "table_bytes": 602762640, "documents": 4020, "utf8_bytes": 25008990, "contexts": 12601916, "edges": 20532543, "completed_documents": 111313, "completed_utf8_bytes": 650269758, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:39:17+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3078.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00026.jsonl", "table_sha256": "d9389d8689db26b19bf4ca675640b76e94e7fd1a13210c1bb61e7bfa6e7a2730", "table_bytes": 595064347, "documents": 4122, "utf8_bytes": 25003170, "contexts": 12422764, "edges": 20293829, "completed_documents": 115435, "completed_utf8_bytes": 675272928, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:41:12+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3193.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00027.jsonl", "table_sha256": "14b666dc77c832882e479be49da04570192bc58c76bd5051c5d856406cb02c56", "table_bytes": 592775281, "documents": 4149, "utf8_bytes": 25016594, "contexts": 12364623, "edges": 20233127, "completed_documents": 119584, "completed_utf8_bytes": 700289522, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:43:07+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3309.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00028.jsonl", "table_sha256": "54dfa96e7d3c6b817bc7061378dffb3d08a5c0407c843f3de5867b30967f215f", "table_bytes": 607224706, "documents": 4155, "utf8_bytes": 25000535, "contexts": 12697172, "edges": 20673474, "completed_documents": 123739, "completed_utf8_bytes": 725290057, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:45:03+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3424.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00029.jsonl", "table_sha256": "f5eaa8e04c6447b972875c0a023afca6ae2303d562965d242f95019e12ba7cb6", "table_bytes": 602565239, "documents": 4145, "utf8_bytes": 25000127, "contexts": 12586543, "edges": 20537837, "completed_documents": 127884, "completed_utf8_bytes": 750290184, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:46:58+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3539.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00030.jsonl", "table_sha256": "083bfeafbd1af0c9eb6940d2d853b67119920fc7fc883199e5765dc719c72c24", "table_bytes": 599257949, "documents": 4101, "utf8_bytes": 25000850, "contexts": 12514003, "edges": 20427271, "completed_documents": 131985, "completed_utf8_bytes": 775291034, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:48:53+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3654.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00031.jsonl", "table_sha256": "127ac55b17910636ae159b796fbf97d6b182681ec9a8ce68e51a079272c25249", "table_bytes": 595981694, "documents": 3999, "utf8_bytes": 25001063, "contexts": 12440951, "edges": 20331707, "completed_documents": 135984, "completed_utf8_bytes": 800292097, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:50:48+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3769.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00032.jsonl", "table_sha256": "2fd93e5a9e67654a4c1f7884aaa54cf6b04cfcc24ee33a517eeaa6cb595e1dee", "table_bytes": 596255714, "documents": 4093, "utf8_bytes": 25001614, "contexts": 12445245, "edges": 20338485, "completed_documents": 140077, "completed_utf8_bytes": 825293711, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:52:44+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 3885.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00033.jsonl", "table_sha256": "fd616ee757a3374b7f1c4d03cc79784c4565fd7d9a29360419d357b9b5a455f7", "table_bytes": 599065546, "documents": 4125, "utf8_bytes": 25013397, "contexts": 12517342, "edges": 20414968, "completed_documents": 144202, "completed_utf8_bytes": 850307108, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:54:42+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 4003.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00034.jsonl", "table_sha256": "9d0c4f41c55746b9664da436332f26a5abaa41dff9d706f60874acf2719c62aa", "table_bytes": 624076692, "documents": 8467, "utf8_bytes": 25000134, "contexts": 13066612, "edges": 21213401, "completed_documents": 152669, "completed_utf8_bytes": 875307242, "peak_host_rss_bytes": 5282766848}

## 2026-10-19T23:56:42+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 4124.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00035.jsonl", "table_sha256": "02ceb536c08f102d0b1a784abd8986b155178c2d22e35668e0f0c51cf14ea373", "table_bytes": 650006988, "documents": 13036, "utf8_bytes": 25000423, "contexts": 13639678, "edges": 22044464, "completed_documents": 165705, "completed_utf8_bytes": 900307665, "peak_host_rss_bytes": 5446836224}

## 2026-10-19T23:58:43+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 4244.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00036.jsonl", "table_sha256": "e357ecfbdb4961b9a49182aadd1b6763abea70dc1284a051ca486a08b1420032", "table_bytes": 653346243, "documents": 13042, "utf8_bytes": 25000355, "contexts": 13722066, "edges": 22137712, "completed_documents": 178747, "completed_utf8_bytes": 925308020, "peak_host_rss_bytes": 5470105600}

## 2026-10-20T00:00:43+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 4364.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00037.jsonl", "table_sha256": "e37cbd07258d0d07ed90e6f7a95335b11e5661f8921cfdd911387ac877b933dc", "table_bytes": 646807684, "documents": 13054, "utf8_bytes": 25000909, "contexts": 13570290, "edges": 21932932, "completed_documents": 191801, "completed_utf8_bytes": 950308929, "peak_host_rss_bytes": 5470105600}

## 2026-10-20T00:02:43+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 4484.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00038.jsonl", "table_sha256": "dd1094e9fbf1b50f7bfceab0d1e33d698ebfc0f4139f082794be2933b7c1b909", "table_bytes": 649662714, "documents": 13022, "utf8_bytes": 25001278, "contexts": 13631669, "edges": 22029784, "completed_documents": 204823, "completed_utf8_bytes": 975310207, "peak_host_rss_bytes": 5470105600}

## 2026-10-20T00:04:42+00:00 / en-patcher-bg1gb-20261020-01 / Background block saved

- Server tmux: `blt-bg1gb-20261020`; elapsed: 4603.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00039.jsonl", "table_sha256": "1724154633bd6a99e4c3c65db1f187cd118c85997f9265c33b926a229f57b51c", "table_bytes": 647400769, "documents": 12846, "utf8_bytes": 24690748, "contexts": 13595070, "edges": 21934452, "completed_documents": 217669, "completed_utf8_bytes": 1000000955, "peak_host_rss_bytes": 5470105600}

## 2026-10-20T00:04:43+00:00 / en-patcher-bg1gb-20261020-01 / build completed

- Server tmux: `blt-bg1gb-20261020`; elapsed: 5710.3s.
- Result: {"status": "built", "documents": 217669, "utf8_bytes": 1000000955, "table_bytes": 24207114622, "elapsed_seconds": 4604.590900741052, "peak_host_rss_bytes": 5470105600}

## 2026-10-20T00:04:43+00:00 / en-patcher-bg1gb-20261020-01 / fit started

- Server tmux: `blt-bg1gb-20261020`; elapsed: 5710.3s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit/report.json"}

## 2026-10-20T00:05:01+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 18.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00000.jsonl", "loaded_contexts": 2572061}

## 2026-10-20T00:05:15+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 31.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00001.jsonl", "loaded_contexts": 2880390}

## 2026-10-20T00:05:29+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 45.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00002.jsonl", "loaded_contexts": 3033563}

## 2026-10-20T00:05:43+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 59.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00003.jsonl", "loaded_contexts": 3138469}

## 2026-10-20T00:05:57+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 73.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00004.jsonl", "loaded_contexts": 3206174}

## 2026-10-20T00:06:11+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 87.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00005.jsonl", "loaded_contexts": 3258295}

## 2026-10-20T00:06:24+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 101.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00006.jsonl", "loaded_contexts": 3299036}

## 2026-10-20T00:06:38+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 115.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00007.jsonl", "loaded_contexts": 3333836}

## 2026-10-20T00:06:52+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 129.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00008.jsonl", "loaded_contexts": 3365263}

## 2026-10-20T00:07:06+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 143.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00009.jsonl", "loaded_contexts": 3390517}

## 2026-10-20T00:07:20+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 157.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00010.jsonl", "loaded_contexts": 3412356}

## 2026-10-20T00:07:34+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 171.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00011.jsonl", "loaded_contexts": 3432108}

## 2026-10-20T00:07:48+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 184.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00012.jsonl", "loaded_contexts": 3448610}

## 2026-10-20T00:08:02+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 198.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00013.jsonl", "loaded_contexts": 3465310}

## 2026-10-20T00:08:16+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 212.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00014.jsonl", "loaded_contexts": 3479112}

## 2026-10-20T00:08:30+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 226.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00015.jsonl", "loaded_contexts": 3492161}

## 2026-10-20T00:08:44+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 240.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00016.jsonl", "loaded_contexts": 3504444}

## 2026-10-20T00:08:58+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 254.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00017.jsonl", "loaded_contexts": 3515297}

## 2026-10-20T00:09:12+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 268.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00018.jsonl", "loaded_contexts": 3525547}

## 2026-10-20T00:09:26+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 282.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00019.jsonl", "loaded_contexts": 3535956}

## 2026-10-20T00:09:40+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 296.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00020.jsonl", "loaded_contexts": 3544755}

## 2026-10-20T00:09:54+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 310.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00021.jsonl", "loaded_contexts": 3553382}

## 2026-10-20T00:10:08+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 324.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00022.jsonl", "loaded_contexts": 3561533}

## 2026-10-20T00:10:22+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 338.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00023.jsonl", "loaded_contexts": 3569431}

## 2026-10-20T00:10:36+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 352.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00024.jsonl", "loaded_contexts": 3576637}

## 2026-10-20T00:10:50+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 366.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00025.jsonl", "loaded_contexts": 3583426}

## 2026-10-20T00:11:04+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 380.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00026.jsonl", "loaded_contexts": 3589719}

## 2026-10-20T00:11:18+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 394.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00027.jsonl", "loaded_contexts": 3595549}

## 2026-10-20T00:11:32+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 409.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00028.jsonl", "loaded_contexts": 3601628}

## 2026-10-20T00:11:47+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 423.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00029.jsonl", "loaded_contexts": 3606953}

## 2026-10-20T00:12:01+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 437.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00030.jsonl", "loaded_contexts": 3612744}

## 2026-10-20T00:12:15+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 451.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00031.jsonl", "loaded_contexts": 3617716}

## 2026-10-20T00:12:29+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 466.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00032.jsonl", "loaded_contexts": 3622830}

## 2026-10-20T00:12:44+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 480.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00033.jsonl", "loaded_contexts": 3627560}

## 2026-10-20T00:12:58+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 495.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00034.jsonl", "loaded_contexts": 3632286}

## 2026-10-20T00:13:13+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 510.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00035.jsonl", "loaded_contexts": 3637200}

## 2026-10-20T00:13:29+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 525.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00036.jsonl", "loaded_contexts": 3642149}

## 2026-10-20T00:13:44+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 540.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00037.jsonl", "loaded_contexts": 3646912}

## 2026-10-20T00:13:59+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 556.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00038.jsonl", "loaded_contexts": 3651366}

## 2026-10-20T00:14:14+00:00 / en-patcher-bg1gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 571.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/background_blocks/block-00039.jsonl", "loaded_contexts": 3655674}

## 2026-10-20T00:14:14+00:00 / en-patcher-bg1gb-20261020-01 / Background loaded and verified

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 571.3s.
- Result: {"seconds": 571.2707430771552, "sha256": "9f8747d1986ee59896e9eb384fe8d97e553f9f03cdef4a95c72f01370567e4d8"}

## 2026-10-20T00:19:31+00:00 / en-patcher-bg1gb-20261020-01 / Fixed training features completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 887.5s.
- Result: {"positions": 4041644, "seconds": 316.2719398722984, "next": "Constrained fit"}

## 2026-10-20T00:19:32+00:00 / en-patcher-bg1gb-20261020-01 / Boundary fit completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 888.6s.
- Result: {"fit": {"coefficients": [-4.445996598980672, 0.0, 0.0, 2.3950389631265634, 0.1771112057139943], "rho": 0.001, "loss": 0.2629052584658777, "iterations": 13, "evaluations": 14, "message": "CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL", "feature_scale": [1.0, 6.216751139212366, 169.74619372441887, 1.4935301569099142, 3.868221269945194], "gradient": [-2.4721159095492107e-09, 0.050811466350804455, 0.7405936077142891, -7.354929318793141e-09, 1.342715458203846e-08], "scaled_projected_gradient_max": 4.924526823087624e-09}, "next": "Fresh sequential threshold trials"}

## 2026-10-20T00:20:10+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 927.0s.
- Result: {"tp": 104640, "fp": 359130, "fn": 0, "precision": 0.22562908338184876, "recall": 1.0, "f1": 0.3681849369293292, "threshold": 0.0, "elapsed_seconds": 38.0876184203662}

## 2026-10-20T00:20:48+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 965.3s.
- Result: {"tp": 99443, "fp": 85116, "fn": 5197, "precision": 0.5388141461538045, "recall": 0.9503344801223241, "f1": 0.6877133046794768, "threshold": 0.125, "elapsed_seconds": 38.322448993101716}

## 2026-10-20T00:21:27+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1003.7s.
- Result: {"tp": 91081, "fp": 45125, "fn": 13559, "precision": 0.6687003509390188, "recall": 0.8704224006116208, "f1": 0.7563422269832175, "threshold": 0.25, "elapsed_seconds": 38.38695848779753}

## 2026-10-20T00:22:05+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1041.9s.
- Result: {"tp": 82324, "fp": 28903, "fn": 22316, "precision": 0.7401440297769426, "recall": 0.7867354740061162, "f1": 0.7627289025186805, "threshold": 0.375, "elapsed_seconds": 38.28184681199491}

## 2026-10-20T00:22:44+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1080.4s.
- Result: {"tp": 74053, "fp": 19872, "fn": 30587, "precision": 0.788426936385414, "recall": 0.7076930428134557, "f1": 0.7458817012061542, "threshold": 0.5, "elapsed_seconds": 38.4334633173421}

## 2026-10-20T00:23:22+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1119.0s.
- Result: {"tp": 64737, "fp": 12944, "fn": 39903, "precision": 0.8333698072887836, "recall": 0.6186639908256881, "f1": 0.7101430992589992, "threshold": 0.625, "elapsed_seconds": 38.66844197316095}

## 2026-10-20T00:24:01+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1157.4s.
- Result: {"tp": 51111, "fp": 6867, "fn": 53529, "precision": 0.8815585221980752, "recall": 0.4884461009174312, "f1": 0.6286019997786223, "threshold": 0.75, "elapsed_seconds": 38.359207628294826}

## 2026-10-20T00:24:39+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1195.7s.
- Result: {"tp": 25197, "fp": 2202, "fn": 79443, "precision": 0.9196321033614365, "recall": 0.24079701834862385, "f1": 0.3816599641015155, "threshold": 0.875, "elapsed_seconds": 38.256185735575855}

## 2026-10-20T00:25:17+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1234.2s.
- Result: {"tp": 0, "fp": 0, "fn": 104640, "precision": 0.0, "recall": 0.0, "f1": 0.0, "threshold": 1.0, "elapsed_seconds": 38.55277771688998}

## 2026-10-20T00:25:56+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1272.7s.
- Result: {"tp": 88797, "fp": 39793, "fn": 15843, "precision": 0.6905435881483786, "recall": 0.8485951834862385, "f1": 0.7614543583587017, "threshold": 0.28125, "elapsed_seconds": 38.48069095565006}

## 2026-10-20T00:26:34+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1311.1s.
- Result: {"tp": 86599, "fp": 35487, "fn": 18041, "precision": 0.7093278508592303, "recall": 0.8275898318042814, "f1": 0.763908859151575, "threshold": 0.3125, "elapsed_seconds": 38.39998543681577}

## 2026-10-20T00:27:13+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1349.5s.
- Result: {"tp": 84399, "fp": 31876, "fn": 20241, "precision": 0.7258568049881746, "recall": 0.806565366972477, "f1": 0.7640857343322092, "threshold": 0.34375, "elapsed_seconds": 38.43026091204956}

## 2026-10-20T00:27:51+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1387.8s.
- Result: {"tp": 80163, "fp": 26289, "fn": 24477, "precision": 0.7530436252959081, "recall": 0.7660837155963303, "f1": 0.7595077028025695, "threshold": 0.40625, "elapsed_seconds": 38.292729161679745}

## 2026-10-20T00:28:29+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1426.2s.
- Result: {"tp": 78087, "fp": 23965, "fn": 26553, "precision": 0.7651687375063693, "recall": 0.7462442660550459, "f1": 0.7555880246937472, "threshold": 0.4375, "elapsed_seconds": 38.36439718492329}

## 2026-10-20T00:29:08+00:00 / en-patcher-bg1gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1464.6s.
- Result: {"tp": 76012, "fp": 21826, "fn": 28628, "precision": 0.7769169443365563, "recall": 0.7264143730886851, "f1": 0.7508173727516075, "threshold": 0.46875, "elapsed_seconds": 38.3660705271177}

## 2026-10-20T00:30:23+00:00 / en-patcher-bg1gb-20261020-01 / Fit and validation finished

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/fit`; elapsed: 1539.5s.
- Result: {"status": "validation_gate_failed", "f1": 0.7640857343322092, "error": null, "next": "Paired baseline comparison if successful"}

## 2026-10-20T00:30:23+00:00 / en-patcher-bg1gb-20261020-01 / fit completed

- Server tmux: `blt-bg1gb-20261020`; elapsed: 7250.7s.
- Result: {"status": "validation_gate_failed", "elapsed_seconds": 1539.4832030422986, "peak_host_rss_bytes": 2905587712}

## 2026-10-20T00:30:23+00:00 / en-patcher-bg1gb-20261020-01 / compare started

- Server tmux: `blt-bg1gb-20261020`; elapsed: 7250.7s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/comparison.json"}

## 2026-10-20T00:32:28+00:00 / en-patcher-bg1gb-20261020-01 / compare completed

- Server tmux: `blt-bg1gb-20261020`; elapsed: 7375.1s.
- Result: {"status": "compared", "f1_difference": 0.04962963043610524, "documents": 111, "quality_gate_passed": false}

## 2026-10-20T00:32:28+00:00 / en-patcher-bg1gb-20261020-01 / Finished

- Server tmux: `blt-bg1gb-20261020`; elapsed: 7375.1s.
- Result: {"status": "completed", "report": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg1gb-20261020-01/run_report.json", "next": "Review measured comparison or failure"}

## 2026-10-20 / 배경 1GB 확대 / 결과 회수·무결성 검증 및 완료

- 시간 상한 없이 tmux 실험 완료. 작은 보고서 6개를 `evidence/english_bg1gb_{equivalence,data,build,fit,comparison,run}_20261020.json`으로 회수했고 원문·블록 카운트는 서버에 보존했다. 원격 단계별 로그는 기존 로컬 상태 관측 기록을 덮어쓰지 않고 회수본으로 덧붙였다. 병합 후 기존 로컬 내용이 바이트 단위로 보존되고 원격 후속 기록 전체가 포함되는 것을 검사했다.
- 검증 완료: 5개 단계 보고서 SHA256, 계획·기존 라벨·100MB 부모 학습 보고서 SHA256, 블록 manifest 해시, 40개 블록의 문서/바이트 합계, 111개 문서의 TP/FP/FN 합계, 보고서 간 F1 일치가 모두 assertion을 통과했다. 100MB 기준 검증 재현과 사전 로딩 동등성 검사도 통과했다. 배경은 기존 20,947문서 전체를 포함한 217,669문서·1,000,000,955 UTF-8 바이트다.
- 실측 점수: 10MB F1 0.625806 → 100MB 0.714456 → 1GB 0.7640857343322092. 100MB 대비 개선 +0.04962963043610524, 같은 111개 문서 paired bootstrap 2,000회 차이 95% 구간 [0.046650435677442856, 0.05243056374868767]. 1GB 정밀도 .7258568, 재현율 .8065654, entropy MAE .4874750, RMSE .7099911, Spearman .8164987, log-loss .2529021, AUPRC .8224226. 임계값 .34375, 후보 평균 패치 길이 3.97373, 교사 4.41313.
- 모수: [a0, beta1, beta2, gamma, delta] = [-4.445996598980672, 0, 0, 2.3950389631265634, 0.1771112057139943]. L-BFGS-B 13회 반복/14회 평가, projected gradient 약 4.92e-9로 종료했다. 이번 조건에서도 길이 계수는 0이지만 다른 설정에서도 불필요하다는 결론은 아니다.
- 실제 시간: 동등성 검사 188.3초, 수집·중복 배제 911.3초, 블록 구축·저장 4,604.6초, 로딩 포함 학습·검증 1,539.5초, 전체 7,375.1초(122.9분). 학습 단계 중 배경 로딩 571.3초, 특징 계산 316.3초, 계수 최적화 1.06초다. 이전 경과 약 34분 시점 잔여 90~120분 예상에 비해 실제 잔여 시간은 약 89분이었다.
- 자원: 블록 저장 합계 24,207,114,622바이트(24.21GB). 구축 최대 RSS 5,470,105,600바이트(5.09GiB), 학습 최대 RSS 2,905,587,712바이트(2.71GiB). 사전 검사는 전체 100MB 테이블을 함께 적재해 최대 RSS 12,497,739,776바이트였다. 학습 로더는 고정 입력이 조회하는 4,055,232개 문맥에 대해 블록 카운트를 정확히 합산하므로 이 수치를 1GB 전체 테이블 상주 메모리나 일반 추론 성능으로 해석하지 않는다.
- 한계: 배경 확대에 따른 이 검증 집합의 개선은 지속됐지만 10배 확대의 F1 증가폭은 이전 +.08865보다 작은 +.04963이다. 두 구간만으로 포화점이나 다음 배율의 성능을 단정하지 않는다. 정밀도는 증가하고 재현율은 100MB 대비 소폭 감소했다. .90 목표는 여전히 미달이며, 같은 검증 자료로 임계값을 선택했으므로 신뢰구간은 선택 이후의 기술적 요약이다. 최종 평가 라벨·BLT BPB·생성 품질·통합 속도는 측정하지 않았다.
- 이번 요청의 1GB 재학습·비교를 완료하고 task.md를 갱신했다. 추가 규모 확대나 모형 탐색은 자동 실행하지 않는다.

## 2026-10-20 / 배경 5GB 확대 / 요청 및 자원 검토

- 사용자 요청에 따라 기존 1GB 전체를 포함하는 5,000,000,000 UTF-8 바이트 배경을 구축하고 동일 학습·검증 라벨, K=8/W=무제한, 계수 최적화·임계값 탐색 조건으로 비교한다. 시간 상한 없이 원격 tmux에서 수행한다.
- 원격 자원 실측: RAM 총 60GiB/가용 58GiB, 디스크 여유 235GiB, 기존 1GB 실행 디렉터리 약 24GiB, 실행 중인 tmux 세션 없음. 1GB 블록 저장량 24.21GB를 단순 비례시키면 5GB는 약 121GB라 기존 100GiB 저장 한도를 초과할 수 있다. 이는 추정이며 5GB 실제 크기는 아직 측정하지 않았다.
- 기존 보호 조건을 늘리거나 데이터를 삭제하지 않고 새 블록에 무손실 gzip 압축을 선택 적용한다. 모든 정수 카운트를 그대로 보존하고 로딩 시 압축을 해제한다. 공개 패키지의 확률 계산은 바꾸지 않는다. 부모 1GB가 블록 형식이므로 최종 비교도 조회 문맥을 정확히 합산하는 기존 로더를 사용하도록 확장한다.
- 다음 작업: 압축/비압축 구축·로딩의 카운트 일치를 테스트하고, 부모 1GB 검증 재현을 사전 단계에 연결한다. 아직 5GB 수집·학습은 시작하지 않았다.

## 2026-10-20 / 배경 5GB 확대 / 압축 저장 검증 및 실행 계획

- 원격 전체 테스트 21개 통과. 합성 문서로 gzip/비압축 블록 구축 결과를 다시 로딩해 모든 카운트가 동일한지 확인했고 새 압축 출력 경로에 불필요한 비압축 사본이 남지 않는 것도 확인했다. 기존 실험 파일은 변경하지 않았다.
- 새 실행 `en-patcher-bg5gb-20261020-01`, tmux `blt-bg5gb-20261020`, 계획 `experiments/english_background_5gb.json`. 기존 1GB 부모를 보존하고 25MB 원문 단위 블록을 gzip level 1로 저장한다. RAM 48GiB 및 디스크 여유/저장 한도는 기존대로 유지한다.
- 사전 검사는 부모 1GB 전체 카운트를 메모리에 올리지 않고 조회 문맥만 합산한 뒤 저장된 학습 특징 일부와 전체 검증 111문서 집계·F1·오차를 재현한다. 최종 비교도 같은 부모 검증 결과를 재현한 뒤 paired bootstrap으로 차이를 계산한다.
- 다음 작업: 블록 형식 부모의 사전 검사/최종 비교 회귀 테스트와 문법 검사를 통과한 뒤 tmux에서 실행한다. 5GB 시간·메모리·압축률은 아직 미측정이다.

## 2026-10-20 / 배경 5GB 확대 / 실행 전 검증 완료

- 원격 `OPENBLAS_NUM_THREADS=8 ../.venv/bin/python -m unittest discover -s tests -v`: 22개 통과, skip 없음. 블록 부모의 저장 특징 일치, 검증 재현 및 동일 결과 간 paired 차이 0, 변조된 특징 거부를 추가 검증했다. `pip check` 통과.
- Pylance 문법 검사에서 실행기·학습 스크립트 오류 없음. 변경 Python/테스트/5GB 설정 편집기 진단 오류 없음. 확률·경계 계산, 학습/검증 라벨과 탐색 규약은 변경하지 않았다.
- 다음 단계: 새 tmux에서 부모 1GB 검증 F1 0.7640857343322092 및 특징을 재현한 뒤 5GB 수집·구축·재학습·비교를 수행한다. 신규 GPU 추론이나 최종 평가 라벨 생성은 하지 않는다. 각 단계와 블록 저장·합산 결과는 원격 source/log.md에 즉시 기록한다.

## 2026-10-20T02:27:37+00:00 / en-patcher-bg5gb-20261020-01 / Started

- Server tmux: `blt-bg5gb-20261020`; elapsed: 0.0s.
- Result: {"target_utf8_bytes": 5000000000, "next": "Nested background sampling", "wall_clock_limit": null, "host_ram_gib": 48}

## 2026-10-20T02:27:37+00:00 / en-patcher-bg5gb-20261020-01 / verify started

- Server tmux: `blt-bg5gb-20261020`; elapsed: 0.0s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/storage_equivalence.json"}

## 2026-10-20 / GitHub 게시 / 원격 연결 및 범위 확인

- 사용자 요청으로 기존 작업을 커밋·푸시한다. 원격 `origin`은 `https://github.com/esoterikosQ/26-14_CACHE.git`, 로컬 브랜치는 `main`이다. 조회한 원격 main과 로컬 HEAD는 모두 `2aa6cf5d2cdd0b82c89251245d5dcff850a7fb8f`로 일치했다. 새 브랜치나 강제 푸시는 사용하지 않는다.
- 대상은 현재 코드·테스트·문서·실험 설정·작은 JSON 근거·진행 로그다. macOS `.DS_Store`, 환경 파일, 원문/실행 산출물 디렉터리는 제외한다. 기존 사용자 변경은 보존한다. 게시 전 크기·잠재 자격 증명·패키지 검증을 수행한다.
- 원격 5GB 작업은 계속 진행 중이다. 이번 확인에서 사전 검사를 지나 4개 shard 후보 표집 로그가 확인됐고 마지막 기록은 서버 2026-10-20T03:17:58+00:00이다. 이는 후보 수집 기록이며 최종 중복 배제/5GB 구축·학습 완료를 뜻하지 않는다. 원격 실행 소스나 작업을 중단·변경하지 않는다.
- 이 게시 기록은 로컬 추가 항목이므로 향후 서버 로그 회수 시 덮어쓰지 말고 병합한다. 다음 단계는 게시 대상 검사 후 커밋·푸시다.

## 2026-10-20 / GitHub 게시 / 게시 전 검증 완료

- 스테이징 검사 시 48개 파일, 합계 636,647바이트였다. 최대 파일은 약 106KB 로그이며 원문·가중치·카운트 블록·대형 배열은 포함되지 않았다. 모든 신규 JSON 구문 검사 통과. 토큰/개인키/자격 증명 패턴 휴리스틱 검사에서 후보가 발견되지 않았지만 비밀정보 부재의 완전한 증명은 아니다.
- `.DS_Store`, `.env`, `.env.local`, `datasets/`, `runs/` 제외 규칙을 `git check-ignore`로 확인했다. `.env.example`은 명시적으로 허용한다.
- 로컬 기본 테스트 3개 통과/의존성 부재 19개 skip. 원격 전체 22개 테스트는 모두 통과했다. 기존 환경을 변경하지 않는 `pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/blt-cache-publish-20261020 .`도 통과했다.
- `git diff --cached --check`는 BLT-PATCHER.md, blt-pipeline-workflow.md, docs/PLAN.md의 기존 사용자 문서 후행 공백 8곳을 보고했다. 실행 오류가 아니며 이번 게시에서 사용자 서식을 임의로 정리하지 않았다.
- 다음 단계: 현재 작업을 main에 커밋하고 기존 origin으로 일반 푸시한다. 5GB 최종 성능은 아직 없으므로 1GB까지의 결과와 5GB 실행 중 상태를 게시한다.

## 2026-10-20 / GitHub 게시 / 작업 푸시 및 원격 일치 확인

- 작업 커밋 `67b93750c6847fa9d1c527a8489f8bb9e2434106` (`Add count patcher research and background scaling experiments`)을 생성하고 `git push origin main`에 성공했다. 48개 파일의 코드·테스트·문서·설정·소규모 근거를 게시했다.
- `git rev-parse HEAD`와 `git ls-remote origin refs/heads/main`이 같은 SHA를 반환했고 작업 트리는 깨끗했다. GitHub 저장소는 `https://github.com/esoterikosQ/26-14_CACHE`다. 강제 푸시나 브랜치 생성은 하지 않았다.
- 이 완료 기록도 별도 문서 커밋으로 같은 main에 게시한다. 진행 중인 원격 5GB 실험과 데이터·가중치에는 변경하지 않았다. 이후 서버 로그를 회수할 때 이 로컬 게시 기록을 보존해 병합한다.
