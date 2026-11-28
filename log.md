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

## 2026-10-20 / 배경 5GB 확대 / 적합 결과 조회: 카운트 구축 중

- 사용자 요청으로 원격 `en-patcher-bg5gb-20261020-01/progress.md`와 산출물 목록, tmux 상태를 읽었다. 최신 확인 기록은 서버 2026-10-20T08:14:54+00:00의 `Background block saved`이며 블록 `00143`까지 144개를 저장했다.
- 완료 원문은 3,601,121,968바이트/목표 5,000,000,000바이트(약 72.0%), 645,510문서다. 해당 구축 프로세스의 기록된 최대 RSS는 5,472,051,200바이트(약 5.10GiB)다. 전체 테이블 상주 메모리나 적합 메모리로 해석하지 않는다.
- 데이터 준비 보고서와 원문, 부모 재현 검사 보고서는 존재하지만 아직 구축 완료·적합·최종 비교 보고서는 없었다. tmux `blt-bg5gb-20261020`은 유지되고 있다. 현재 5GB F1·계수·임계값 결과는 없으며 기존 1GB F1 0.764086을 5GB 결과로 제시하지 않는다.
- 이번 기록은 조회 시점의 요약이며 서버의 블록별 원본 로그를 대체하지 않는다. 실행·환경·데이터는 변경하지 않았다. 다음 단계는 실행 프로세스를 확인하고, 구축 후 적합·임계값 탐색·1GB 비교가 끝나면 보고서 및 원격 로그를 기존 로컬 기록과 함께 회수·검증하는 것이다.
- 후속 확인: `ps`에서 실행기 PID 571532와 `--stage build` 자식 PID 571934가 유지됐으며, 구축 프로세스는 `Rl+`, CPU 99.9%, 경과 04:39:53으로 확인됐다. 실행기 전체 경과는 05:49:06이다. `git diff --check -- log.md task.md` 통과. 작업을 재시작하거나 별도 실험을 제출하지 않았으며 다음 확인 대상은 구축 완료 후 적합 보고서다.

## 2026-10-20 / 배경 5GB 확대 / 재조회: 구축 완료 및 적합 진행 중

- 사용자 재조회 요청으로 원격 진행 기록·JSON 파일 목록·실행 프로세스를 확인했다. 서버 2026-10-20T10:06:58+00:00에 `build completed`와 `fit started`가 기록됐다. 이전 72.0% 상태 이후 구축이 완료됐으며, 원격 작업은 계속 실행 중이다.
- 구축 결과: 1,264,612문서, 5,000,000,008 UTF-8 바이트, 200개 gzip 블록, 압축 테이블 총 21,642,161,844바이트(21.64GB). 구축 시간 23,404.1628초(약 6시간 30분), 구축 최대 RSS 5,477,359,616바이트(약 5.10GiB). 이는 배경 카운트 구축 측정이며 적합 성능이나 일반 추론 비용이 아니다.
- 조회 시 실행기 전체 경과 08:09:36, 적합 PID 625613 경과 00:30:16, 상태 `Rl+`, CPU 100%를 확인했다. 기존 라벨 설정, W=무제한, 새 5GB 배경 및 `--no-time-limit`으로 실행 중이다. `fit/report.json`은 존재하지만 0바이트이며 최종 비교 보고서는 없다. 파일의 존재만으로 적합 완료로 판단하지 않는다.
- 5GB F1·추정 계수·선택 임계값은 아직 확인할 수 없다. 아직 1GB와의 최종 성능 비교나 완료 시각을 제시하지 않는다. 로컬 상태 문서만 갱신하며 실행·환경·데이터는 변경하지 않는다. 다음 단계는 적합 보고서가 완성되고 비교가 끝난 뒤 해시·문서 집계·라벨 동일성을 검증하는 것이다. 서버 원본 로그 회수 시 로컬 게시·조회 기록을 보존해 병합한다.

## 2026-10-20 / 배경 5GB 확대 / 완료 알림 및 결과 회수 착수

- 서버 완료 시각 2026-10-20T11:28:17+00:00, 실행 상태 `completed`, 전체 32,439.5319초(약 9시간 1분)를 최종 실행 보고서에서 확인했다. 적합의 `validation_gate_failed`는 실행 실패가 아니라 사전 품질 기준 미달이다.
- 원격 최종 비교 보고서에서 F1 0.7640857343→0.7804204850, 차이 +0.0163347506, 111문서 paired bootstrap 95% 구간 [0.0145115188, 0.0179297787]을 확인했다. 임계값은 양쪽 모두 0.34375이며 부모 검증 재현은 일치했다. 원격 보고서 기반 관측으로, 로컬 회수 후 무결성 검증은 다음 단계다.
- 목표 F1 0.90 미달이다. 같은 검증 자료로 임계값을 선택했으므로 독립 평가 개선으로 일반화하지 않으며 BLT BPB·전체 속도·최종 평가는 측정하지 않았다. 다음 단계는 소규모 JSON 보고서 회수와 해시·라벨 식별자·문서 및 블록 집계 검증이다. 원문·가중치·카운트 블록은 전송하지 않으며 기존 로컬 게시·조회 기록을 보존한다.

## 2026-10-20 / 배경 5GB 확대 / 보고서 무결성 확인

- `evidence/english_bg5gb_{equivalence,data,build,fit,comparison,run}_20261020.json` 6개를 회수했다. 실행 보고서의 verify/prepare/build/fit/compare 해시 5개, 5GB 계획·원래 실험 설정 해시, 실행 코드 3개의 식별자가 모두 로컬 파일과 일치했다. 원격 전체 로그는 별도 임시 경로로 회수해 기존 로컬 파일을 덮어쓰지 않았다.
- 보고서의 계수 [a0,beta1,beta2,gamma,delta]는 [-4.4112812166,0,0,2.4714297839,0.2123904362], 임계값 0.34375다. 최적화 14회 반복으로 수렴했고 실제 최적화 시간은 약 1.10초다. 적합 단계 전체 4,362.25초 중 카운트 로딩 3,266.52초, 특징 생성 359.33초이며 나머지에는 임계값 탐색과 진단이 포함된다.
- 데이터 준비 최대 RSS 약 30.60GiB, 구축 약 5.10GiB, 적합 약 3.52GiB다. 적합 메모리는 고정 학습·검증 입력에 필요한 문맥만 정확 합산한 결과이며 전체 5GB 모델 상주 메모리가 아니다. 다음 검사는 라벨·부모 동일성, 블록 합계 및 111문서 TP/FP/FN 집계다.

## 2026-10-20 / 배경 5GB 확대 / 원격 단계별 로그 회수

- 아래는 서버가 실행 당시 기록한 단계·블록·적합 로그의 사후 회수본이다. 로컬 게시·진행 조회와 시간상 겹치는 과거 기록을 원본 시각 그대로 추가하며, 기존 로컬 기록을 보존한다. 이미 공유된 시작 기록 이후의 원격 부분만 병합한다.
- 병합 전 결과 집계 검증도 통과했다. 원래 라벨 보고서 해시, 1GB와 같은 설정·카운트 모수·학습 위치 수·검증 문서 순서, 111문서 TP/FP/FN 합계 및 F1 재계산, 부모/후보 보고서 해시와 부모 재현, 보고된 부모 217,669문서 보존, 200개 gzip 블록의 문서/바이트/저장량 합계 및 블록 매니페스트 해시가 모두 일치했다. 이번 회수에서는 원격 원문이나 21.64GB 블록 본체를 다시 읽어 검증하지 않았다.
- 완료 결과와 한계를 task.md에 반영했다. 개선은 관측됐지만 F1 0.90 게이트 실패로 최종 평가·BLT 통합은 보류한다. 추가 실험이나 Git 커밋·푸시는 실행하지 않는다. 병합은 공통 접두부 일치 및 기존 로컬 바이트 보존을 검사하고 중복 회수를 거부하는 방식으로 수행한다.


## 2026-10-20T02:35:37+00:00 / en-patcher-bg5gb-20261020-01 / verify completed

- Server tmux: `blt-bg5gb-20261020`; elapsed: 479.8s.
- Result: {"status": "verified", "elapsed_seconds": 479.111538156867, "peak_host_rss_bytes": 999219200}

## 2026-10-20T02:35:37+00:00 / en-patcher-bg5gb-20261020-01 / prepare started

- Server tmux: `blt-bg5gb-20261020`; elapsed: 479.8s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/data_preparation.json"}

## 2026-10-20T02:46:17+00:00 / en-patcher-bg5gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg5gb-20261020`; elapsed: 639.3s.
- Result: {"shard": "data/CC-MAIN-2025-05/003_00015.parquet", "candidate_bytes": 2000006209}

## 2026-10-20T02:56:48+00:00 / en-patcher-bg5gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1270.5s.
- Result: {"shard": "data/CC-MAIN-2025-05/001_00011.parquet", "candidate_bytes": 2000027683}

## 2026-10-20T03:07:25+00:00 / en-patcher-bg5gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1907.0s.
- Result: {"shard": "data/CC-MAIN-2025-05/002_00008.parquet", "candidate_bytes": 2000003723}

## 2026-10-20T03:17:58+00:00 / en-patcher-bg5gb-20261020-01 / Shard sampled

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2540.5s.
- Result: {"shard": "data/CC-MAIN-2025-05/004_00040.parquet", "candidate_bytes": 2000005484}

## 2026-10-20T03:36:51+00:00 / en-patcher-bg5gb-20261020-01 / prepare completed

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4153.2s.
- Result: {"status": "prepared", "documents": 1264612, "utf8_bytes": 5000000008, "elapsed_seconds": 3660.7857855740003, "peak_host_rss_bytes": 32859451392}

## 2026-10-20T03:36:51+00:00 / en-patcher-bg5gb-20261020-01 / build started

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4153.2s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_build.json"}

## 2026-10-20T03:38:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 113.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00000.jsonl.gz", "table_sha256": "8c45ae06281d0871799287dac2172e48612ac43715f8b0f4796371f113303276", "table_bytes": 105937122, "compression": "gzip", "uncompressed_table_bytes": 597268295, "documents": 4767, "utf8_bytes": 25005291, "contexts": 12480893, "edges": 20349195, "completed_documents": 4767, "completed_utf8_bytes": 25005291, "peak_host_rss_bytes": 5115318272}

## 2026-10-20T03:40:40+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 226.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00001.jsonl.gz", "table_sha256": "cacd86601d7a93f54c04e77a74b4d73975d7e21085b3032febe5ce061db32bd3", "table_bytes": 105513936, "compression": "gzip", "uncompressed_table_bytes": 593955276, "documents": 3960, "utf8_bytes": 25020142, "contexts": 12396031, "edges": 20260152, "completed_documents": 8727, "completed_utf8_bytes": 50025433, "peak_host_rss_bytes": 5115318272}

## 2026-10-20T03:42:33+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 340.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00002.jsonl.gz", "table_sha256": "a5d28bd89f3b81bbd0eed1c15892125468ff6bf7995bb327fc2d3b5407299b02", "table_bytes": 105683081, "compression": "gzip", "uncompressed_table_bytes": 594690576, "documents": 4125, "utf8_bytes": 25001075, "contexts": 12409517, "edges": 20289780, "completed_documents": 12852, "completed_utf8_bytes": 75026508, "peak_host_rss_bytes": 5115318272}

## 2026-10-20T03:44:31+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 457.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00003.jsonl.gz", "table_sha256": "c6bcf220478f30323eb77188253e2f311caa183413bcee062506a75b30113bc8", "table_bytes": 110359668, "compression": "gzip", "uncompressed_table_bytes": 624104624, "documents": 8101, "utf8_bytes": 25009387, "contexts": 13071460, "edges": 21217478, "completed_documents": 20953, "completed_utf8_bytes": 100035895, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:46:26+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 572.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00004.jsonl.gz", "table_sha256": "14dbc20bc0101d4deb3cbc2ac1c6778367ec011ab04d605da43120819ffbe0e6", "table_bytes": 105614557, "compression": "gzip", "uncompressed_table_bytes": 594662621, "documents": 4188, "utf8_bytes": 25004956, "contexts": 12414670, "edges": 20283710, "completed_documents": 25141, "completed_utf8_bytes": 125040851, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:48:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 687.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00005.jsonl.gz", "table_sha256": "10183e34c3f942cfb1d178ad33c5b46525178c0a562b4950e71a883701e0e5d0", "table_bytes": 106707445, "compression": "gzip", "uncompressed_table_bytes": 600818829, "documents": 4116, "utf8_bytes": 25014995, "contexts": 12543622, "edges": 20491600, "completed_documents": 29257, "completed_utf8_bytes": 150055846, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:50:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 801.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00006.jsonl.gz", "table_sha256": "02524ee34c8cc29b1f4285a5e8df36e6fc2ecf020143fa382da0a20120901d21", "table_bytes": 105037820, "compression": "gzip", "uncompressed_table_bytes": 591301857, "documents": 4053, "utf8_bytes": 25002233, "contexts": 12340780, "edges": 20171469, "completed_documents": 33310, "completed_utf8_bytes": 175058079, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:52:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 915.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00007.jsonl.gz", "table_sha256": "5341400c10dedae835bb49e829df5449a13820f20b48eb96e61f5dcd1362bacd", "table_bytes": 106398291, "compression": "gzip", "uncompressed_table_bytes": 600209666, "documents": 4065, "utf8_bytes": 25016940, "contexts": 12543084, "edges": 20448810, "completed_documents": 37375, "completed_utf8_bytes": 200075019, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:54:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1031.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00008.jsonl.gz", "table_sha256": "335c2ce3863632c9479d6b5bbd80d2c0e075c27f3440662393835ca934c0fac5", "table_bytes": 106745003, "compression": "gzip", "uncompressed_table_bytes": 602340044, "documents": 4089, "utf8_bytes": 25012712, "contexts": 12596515, "edges": 20517713, "completed_documents": 41464, "completed_utf8_bytes": 225087731, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:55:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1145.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00009.jsonl.gz", "table_sha256": "5a81fc94ea7ee63d0d1310dabe716d82a3e5f89d29e2214895f2adbc8c7e3732", "table_bytes": 107500210, "compression": "gzip", "uncompressed_table_bytes": 606895848, "documents": 4062, "utf8_bytes": 25001392, "contexts": 12687980, "edges": 20662559, "completed_documents": 45526, "completed_utf8_bytes": 250089123, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:57:53+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1259.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00010.jsonl.gz", "table_sha256": "11189dbcbfa6f0cc0204fedec7522dffeb7c7cf92382f3b1203a52454d5e6f9b", "table_bytes": 105523761, "compression": "gzip", "uncompressed_table_bytes": 594315550, "documents": 4158, "utf8_bytes": 25002120, "contexts": 12413041, "edges": 20262541, "completed_documents": 49684, "completed_utf8_bytes": 275091243, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T03:59:46+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1372.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00011.jsonl.gz", "table_sha256": "1a54e075a05209dd35b75f459d257a4ba1401115c0c9487a0a9e7bf8e6d5c8d5", "table_bytes": 105428739, "compression": "gzip", "uncompressed_table_bytes": 593432801, "documents": 4198, "utf8_bytes": 25000056, "contexts": 12385244, "edges": 20238475, "completed_documents": 53882, "completed_utf8_bytes": 300091299, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:01:40+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1486.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00012.jsonl.gz", "table_sha256": "1b648c419a350b685f59d1243652072f626b55d5ce8a7f0e008d65e5d96cb13b", "table_bytes": 104718620, "compression": "gzip", "uncompressed_table_bytes": 589198298, "documents": 4100, "utf8_bytes": 25003398, "contexts": 12297444, "edges": 20101159, "completed_documents": 57982, "completed_utf8_bytes": 325094697, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:03:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1601.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00013.jsonl.gz", "table_sha256": "d584bde55eb06699f35708e0962f87636fa705a2b24c505b6920db0c1ecc2d95", "table_bytes": 105747159, "compression": "gzip", "uncompressed_table_bytes": 596231109, "documents": 4158, "utf8_bytes": 25000951, "contexts": 12462248, "edges": 20315079, "completed_documents": 62140, "completed_utf8_bytes": 350095648, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:05:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1716.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00014.jsonl.gz", "table_sha256": "bec4ed8f14f431f0fccbeb69d4f7c42e3f9df1554d99f0d85da2c5cb2c26667d", "table_bytes": 105815945, "compression": "gzip", "uncompressed_table_bytes": 596680555, "documents": 4026, "utf8_bytes": 25003964, "contexts": 12465395, "edges": 20333461, "completed_documents": 66166, "completed_utf8_bytes": 375099612, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:07:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1831.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00015.jsonl.gz", "table_sha256": "d652f4bcf896662cc7b960968ecdeb7cc5426eb5cd0162ecaab4a19b8d4701da", "table_bytes": 105664296, "compression": "gzip", "uncompressed_table_bytes": 594976401, "documents": 4179, "utf8_bytes": 25016793, "contexts": 12425585, "edges": 20288240, "completed_documents": 70345, "completed_utf8_bytes": 400116405, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:09:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 1947.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00016.jsonl.gz", "table_sha256": "640ee9ed3a73b5c51783ac15d3d30e85867e107158bd31becfb7f26d28419e34", "table_bytes": 107049601, "compression": "gzip", "uncompressed_table_bytes": 603263122, "documents": 4092, "utf8_bytes": 25036048, "contexts": 12600684, "edges": 20554358, "completed_documents": 74437, "completed_utf8_bytes": 425152453, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:11:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2061.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00017.jsonl.gz", "table_sha256": "e7e6be11b028d59ca83781654c278dee3a076c0f1b8b559cf25c4badb78ad0a0", "table_bytes": 104339957, "compression": "gzip", "uncompressed_table_bytes": 587057184, "documents": 4086, "utf8_bytes": 25012481, "contexts": 12248259, "edges": 20031681, "completed_documents": 78523, "completed_utf8_bytes": 450164934, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:13:11+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2177.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00018.jsonl.gz", "table_sha256": "cb2bb6cd4235022c1b0bc736085448c8f93a90d371e424590b61ec41715b121c", "table_bytes": 106183166, "compression": "gzip", "uncompressed_table_bytes": 597912262, "documents": 4155, "utf8_bytes": 25020543, "contexts": 12483405, "edges": 20386821, "completed_documents": 82678, "completed_utf8_bytes": 475185477, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:15:06+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2292.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00019.jsonl.gz", "table_sha256": "3db834c89d2f5126eeb81eda662ad2f2a7733aca6318fbdefc93452fdb165001", "table_bytes": 105847351, "compression": "gzip", "uncompressed_table_bytes": 596477281, "documents": 4047, "utf8_bytes": 25001520, "contexts": 12460186, "edges": 20329523, "completed_documents": 86725, "completed_utf8_bytes": 500186997, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:17:02+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2408.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00020.jsonl.gz", "table_sha256": "5481f2fd632f86b07a7f9fda537b5fe95154279dbaa5779bce2f17a8a697d135", "table_bytes": 105856933, "compression": "gzip", "uncompressed_table_bytes": 595987685, "documents": 4155, "utf8_bytes": 25007432, "contexts": 12442063, "edges": 20326338, "completed_documents": 90880, "completed_utf8_bytes": 525194429, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:18:58+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2524.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00021.jsonl.gz", "table_sha256": "4e52c3ba7f5b0ccb8420f7e977960eeda1e655b38c4a214162ca56b83c10b82f", "table_bytes": 106504004, "compression": "gzip", "uncompressed_table_bytes": 600137744, "documents": 4107, "utf8_bytes": 25053225, "contexts": 12534002, "edges": 20458459, "completed_documents": 94987, "completed_utf8_bytes": 550247654, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:20:53+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2639.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00022.jsonl.gz", "table_sha256": "9d036482c9ca224595e83d8055fb33e5dfa0a7b7424a56bdbc904f3dd9bfb350", "table_bytes": 104930644, "compression": "gzip", "uncompressed_table_bytes": 590619677, "documents": 4139, "utf8_bytes": 25002288, "contexts": 12328149, "edges": 20147894, "completed_documents": 99126, "completed_utf8_bytes": 575249942, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:22:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2755.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00023.jsonl.gz", "table_sha256": "bdfa502997b247f9ebeaab549f5d6868b8c1f01669793f7f754863120b8c72bc", "table_bytes": 106726624, "compression": "gzip", "uncompressed_table_bytes": 602352138, "documents": 4141, "utf8_bytes": 25001920, "contexts": 12596857, "edges": 20512536, "completed_documents": 103267, "completed_utf8_bytes": 600251862, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:24:44+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2871.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00024.jsonl.gz", "table_sha256": "c46e5c1f5e4761a30ace99e1c24cdc1d574f2e9a404748a71f0db944ee67ea9b", "table_bytes": 106442343, "compression": "gzip", "uncompressed_table_bytes": 599970973, "documents": 4026, "utf8_bytes": 25008906, "contexts": 12535464, "edges": 20445858, "completed_documents": 107293, "completed_utf8_bytes": 625260768, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:26:40+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 2986.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00025.jsonl.gz", "table_sha256": "c5da2a9e7791e6341339793e4b265fb49febd9818cd6eac406462520ed594b58", "table_bytes": 106859150, "compression": "gzip", "uncompressed_table_bytes": 602762640, "documents": 4020, "utf8_bytes": 25008990, "contexts": 12601916, "edges": 20532543, "completed_documents": 111313, "completed_utf8_bytes": 650269758, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:28:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3101.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00026.jsonl.gz", "table_sha256": "d0a1f05e35b3cf3dcf5cfb2730d31c1fa6b18885f61798fe94445da25be7c9ef", "table_bytes": 105678536, "compression": "gzip", "uncompressed_table_bytes": 595064347, "documents": 4122, "utf8_bytes": 25003170, "contexts": 12422764, "edges": 20293829, "completed_documents": 115435, "completed_utf8_bytes": 675272928, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:30:31+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3218.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00027.jsonl.gz", "table_sha256": "36a659ba681df5bb4e099ed098d3b3130e8b0a79041c496dbf31b500ed613d38", "table_bytes": 105383810, "compression": "gzip", "uncompressed_table_bytes": 592775281, "documents": 4149, "utf8_bytes": 25016594, "contexts": 12364623, "edges": 20233127, "completed_documents": 119584, "completed_utf8_bytes": 700289522, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:32:27+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3333.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00028.jsonl.gz", "table_sha256": "13e3ae46e9a83b03cdfd192caafb9551a89df0b977cb10273ba3b6f1b7e1d938", "table_bytes": 107590618, "compression": "gzip", "uncompressed_table_bytes": 607224706, "documents": 4155, "utf8_bytes": 25000535, "contexts": 12697172, "edges": 20673474, "completed_documents": 123739, "completed_utf8_bytes": 725290057, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:34:23+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3449.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00029.jsonl.gz", "table_sha256": "0a0efa8bf84eb4b55c89427915e627419c04c2534ff56ecbda3edfc23aab1094", "table_bytes": 106953609, "compression": "gzip", "uncompressed_table_bytes": 602565239, "documents": 4145, "utf8_bytes": 25000127, "contexts": 12586543, "edges": 20537837, "completed_documents": 127884, "completed_utf8_bytes": 750290184, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:36:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3565.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00030.jsonl.gz", "table_sha256": "40675428f1bdfb065e401077cc0ac4c9de77bc4a8498b04d537dc11608f3f855", "table_bytes": 106374762, "compression": "gzip", "uncompressed_table_bytes": 599257949, "documents": 4101, "utf8_bytes": 25000850, "contexts": 12514003, "edges": 20427271, "completed_documents": 131985, "completed_utf8_bytes": 775291034, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:38:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3680.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00031.jsonl.gz", "table_sha256": "d0d8e9ffe79b31f11046e2df776f8d01412705c978756a298e9131a2d9ae02db", "table_bytes": 105863595, "compression": "gzip", "uncompressed_table_bytes": 595981694, "documents": 3999, "utf8_bytes": 25001063, "contexts": 12440951, "edges": 20331707, "completed_documents": 135984, "completed_utf8_bytes": 800292097, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:40:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3795.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00032.jsonl.gz", "table_sha256": "8822a78eaaa0dec9887a0e4f540a8ded76d0258c6a09b6d38cf76bb863b24894", "table_bytes": 105910373, "compression": "gzip", "uncompressed_table_bytes": 596255714, "documents": 4093, "utf8_bytes": 25001614, "contexts": 12445245, "edges": 20338485, "completed_documents": 140077, "completed_utf8_bytes": 825293711, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:42:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 3911.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00033.jsonl.gz", "table_sha256": "0b5e57a89c2314650333ee58059129f01339e6c8df9fc4763846b60c02e3813e", "table_bytes": 106280264, "compression": "gzip", "uncompressed_table_bytes": 599065546, "documents": 4125, "utf8_bytes": 25013397, "contexts": 12517342, "edges": 20414968, "completed_documents": 144202, "completed_utf8_bytes": 850307108, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:44:03+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4029.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00034.jsonl.gz", "table_sha256": "f3512689d3c61f225c18bccac24a95b44056cb00b465eaa27f0c28f00bb06ecb", "table_bytes": 110376171, "compression": "gzip", "uncompressed_table_bytes": 624076692, "documents": 8467, "utf8_bytes": 25000134, "contexts": 13066612, "edges": 21213401, "completed_documents": 152669, "completed_utf8_bytes": 875307242, "peak_host_rss_bytes": 5284986880}

## 2026-10-20T04:46:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4151.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00035.jsonl.gz", "table_sha256": "72212db497095fb1ced5add6d9d9ddfcf3f548a3c48aefc3ab376a714fab2554", "table_bytes": 114642304, "compression": "gzip", "uncompressed_table_bytes": 650006988, "documents": 13036, "utf8_bytes": 25000423, "contexts": 13639678, "edges": 22044464, "completed_documents": 165705, "completed_utf8_bytes": 900307665, "peak_host_rss_bytes": 5449252864}

## 2026-10-20T04:48:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4272.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00036.jsonl.gz", "table_sha256": "1b63e1088b364768ec129c311d7e6f85a784e746e259870017fe018e174412a2", "table_bytes": 115056296, "compression": "gzip", "uncompressed_table_bytes": 653346243, "documents": 13042, "utf8_bytes": 25000355, "contexts": 13722066, "edges": 22137712, "completed_documents": 178747, "completed_utf8_bytes": 925308020, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T04:50:06+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4393.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00037.jsonl.gz", "table_sha256": "714406e8bfa506afee593721d8c69708bc3a25f64f45038c343c98f7dff46bf8", "table_bytes": 114083542, "compression": "gzip", "uncompressed_table_bytes": 646807684, "documents": 13054, "utf8_bytes": 25000909, "contexts": 13570290, "edges": 21932932, "completed_documents": 191801, "completed_utf8_bytes": 950308929, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T04:52:07+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4513.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00038.jsonl.gz", "table_sha256": "b2f90fa1cf2e5fc7767e632c5f8f4f75a72efca000469b6fe1241fdf0f2c3341", "table_bytes": 114555912, "compression": "gzip", "uncompressed_table_bytes": 649662714, "documents": 13022, "utf8_bytes": 25001278, "contexts": 13631669, "edges": 22029784, "completed_documents": 204823, "completed_utf8_bytes": 975310207, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T04:54:08+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4634.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00039.jsonl.gz", "table_sha256": "49721d4c0a7769542a7ede78867813636b97547e25c9596bbe8652b2f4b77d3c", "table_bytes": 114948157, "compression": "gzip", "uncompressed_table_bytes": 652080596, "documents": 12899, "utf8_bytes": 25000220, "contexts": 13689217, "edges": 22101473, "completed_documents": 217722, "completed_utf8_bytes": 1000310427, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T04:56:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4750.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00040.jsonl.gz", "table_sha256": "a179c0b39206863717ee2b32eadcad3654b97fb783bbff4bc1a7878ed10ad081", "table_bytes": 106276620, "compression": "gzip", "uncompressed_table_bytes": 599325483, "documents": 4119, "utf8_bytes": 25000730, "contexts": 12520817, "edges": 20421981, "completed_documents": 221841, "completed_utf8_bytes": 1025311157, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T04:58:01+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4867.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00041.jsonl.gz", "table_sha256": "a9c2adbe24c84d8847231da1a1d0d2b7ae168232689d9e13dfc794433d483902", "table_bytes": 106628289, "compression": "gzip", "uncompressed_table_bytes": 601899421, "documents": 4093, "utf8_bytes": 25009318, "contexts": 12585150, "edges": 20500337, "completed_documents": 225934, "completed_utf8_bytes": 1050320475, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T04:59:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 4983.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00042.jsonl.gz", "table_sha256": "f17255ba4b27664cb66f1b81298b25bf487c0f6e12066f6cf606c2e4c479953d", "table_bytes": 106887154, "compression": "gzip", "uncompressed_table_bytes": 602809857, "documents": 4152, "utf8_bytes": 25018080, "contexts": 12596374, "edges": 20537669, "completed_documents": 230086, "completed_utf8_bytes": 1075338555, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:01:53+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5099.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00043.jsonl.gz", "table_sha256": "d0533c63f81492fa425508f3de63047748f521505aae173e2517914c2d22391a", "table_bytes": 105851775, "compression": "gzip", "uncompressed_table_bytes": 596424697, "documents": 4209, "utf8_bytes": 25003593, "contexts": 12459812, "edges": 20329611, "completed_documents": 234295, "completed_utf8_bytes": 1100342148, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:03:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5216.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00044.jsonl.gz", "table_sha256": "84b4496713fdb5a1e325317375fbb22eaf1698767abe83946d39f3b0fd43157f", "table_bytes": 106386655, "compression": "gzip", "uncompressed_table_bytes": 599135822, "documents": 4098, "utf8_bytes": 25010504, "contexts": 12510811, "edges": 20431264, "completed_documents": 238393, "completed_utf8_bytes": 1125352652, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:05:45+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5332.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00045.jsonl.gz", "table_sha256": "b9a9b99ba06a359480f02d9f99e17ca0091d5ba67e97510c62a7f1e5ce2e6bd6", "table_bytes": 105282549, "compression": "gzip", "uncompressed_table_bytes": 592441259, "documents": 4147, "utf8_bytes": 25000345, "contexts": 12367539, "edges": 20213112, "completed_documents": 242540, "completed_utf8_bytes": 1150352997, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:07:42+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5448.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00046.jsonl.gz", "table_sha256": "754c8365d05c8e33650e972c46ff45d6a03f6848a98a4c47ed63a0367c6ca54d", "table_bytes": 106262422, "compression": "gzip", "uncompressed_table_bytes": 598865548, "documents": 4151, "utf8_bytes": 25008940, "contexts": 12509087, "edges": 20411653, "completed_documents": 246691, "completed_utf8_bytes": 1175361937, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:09:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5564.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00047.jsonl.gz", "table_sha256": "4b1fc8005d4f7387e27f3b62c39ec3f1faa8da60236fba4f8e3cbf11aac9cd44", "table_bytes": 106031460, "compression": "gzip", "uncompressed_table_bytes": 597232785, "documents": 4083, "utf8_bytes": 25014048, "contexts": 12470354, "edges": 20363393, "completed_documents": 250774, "completed_utf8_bytes": 1200375985, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:11:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5680.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00048.jsonl.gz", "table_sha256": "ed2acf597ded01a56f0f89158efb1e6efbf1fdc8ed1dcdff7bbd8abfb851f117", "table_bytes": 105871573, "compression": "gzip", "uncompressed_table_bytes": 596464690, "documents": 4059, "utf8_bytes": 25007213, "contexts": 12452515, "edges": 20336351, "completed_documents": 254833, "completed_utf8_bytes": 1225383198, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:13:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5796.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00049.jsonl.gz", "table_sha256": "4b584d83f1fc92bed720b65e6b109ff1b0f281877653830f20fc694c4c2eacda", "table_bytes": 106618019, "compression": "gzip", "uncompressed_table_bytes": 601341869, "documents": 4125, "utf8_bytes": 25014500, "contexts": 12568341, "edges": 20484749, "completed_documents": 258958, "completed_utf8_bytes": 1250397698, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:15:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 5911.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00050.jsonl.gz", "table_sha256": "9cdd44f31f0a4787f0451e75ec5cda7c439a693fbbd470d3417d2d1d1af38bbb", "table_bytes": 105873866, "compression": "gzip", "uncompressed_table_bytes": 596169935, "documents": 4122, "utf8_bytes": 25004395, "contexts": 12444878, "edges": 20336907, "completed_documents": 263080, "completed_utf8_bytes": 1275402093, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:17:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6027.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00051.jsonl.gz", "table_sha256": "ea63ddf7d3c9d931e22467342a5f0cf8a12d9ca52e47822cc801aa44be64f5c1", "table_bytes": 106124478, "compression": "gzip", "uncompressed_table_bytes": 597972378, "documents": 4116, "utf8_bytes": 25040745, "contexts": 12491072, "edges": 20382756, "completed_documents": 267196, "completed_utf8_bytes": 1300442838, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:19:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6142.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00052.jsonl.gz", "table_sha256": "c116c7cd8d238c38ec93462a0736a6dd4d22da5831eb4488afc5b2cdfd143438", "table_bytes": 105853491, "compression": "gzip", "uncompressed_table_bytes": 596255760, "documents": 4149, "utf8_bytes": 25007491, "contexts": 12450913, "edges": 20327065, "completed_documents": 271345, "completed_utf8_bytes": 1325450329, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:21:13+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6259.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00053.jsonl.gz", "table_sha256": "0ed96766cfcf62d5a646a9c91415b61d4498d968ab7bc14478647ecc2eb2eb19", "table_bytes": 106468316, "compression": "gzip", "uncompressed_table_bytes": 599395619, "documents": 4095, "utf8_bytes": 25009043, "contexts": 12510982, "edges": 20439250, "completed_documents": 275440, "completed_utf8_bytes": 1350459372, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:23:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6375.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00054.jsonl.gz", "table_sha256": "53b6a9cbc56ed969797fd28cc73a873b5204bb53dfb44e1af87ca95976bba63b", "table_bytes": 105908749, "compression": "gzip", "uncompressed_table_bytes": 596725006, "documents": 4149, "utf8_bytes": 25000393, "contexts": 12462530, "edges": 20342684, "completed_documents": 279589, "completed_utf8_bytes": 1375459765, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:25:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6492.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00055.jsonl.gz", "table_sha256": "32923aeead0ca18e06a6d032e92bdb775c781180c82d6fcda9c5d84b68d2757c", "table_bytes": 106705231, "compression": "gzip", "uncompressed_table_bytes": 600913036, "documents": 4069, "utf8_bytes": 25000434, "contexts": 12545739, "edges": 20487363, "completed_documents": 283658, "completed_utf8_bytes": 1400460199, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:27:01+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6608.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00056.jsonl.gz", "table_sha256": "3aa6abeb48f6208421e07f6437b8da3515b1368eceb7360615e97d0396117150", "table_bytes": 107085425, "compression": "gzip", "uncompressed_table_bytes": 604048161, "documents": 4129, "utf8_bytes": 25000436, "contexts": 12624413, "edges": 20576577, "completed_documents": 287787, "completed_utf8_bytes": 1425460635, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:28:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6723.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00057.jsonl.gz", "table_sha256": "7a9de09ceac16c7768b0936d2a93ce1e16011dd94c73aebdcd264298fa00f9cd", "table_bytes": 106156452, "compression": "gzip", "uncompressed_table_bytes": 598441382, "documents": 4078, "utf8_bytes": 25008444, "contexts": 12505638, "edges": 20387676, "completed_documents": 291865, "completed_utf8_bytes": 1450469079, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:30:52+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6838.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00058.jsonl.gz", "table_sha256": "a6653c34f50c8d623d52c7f6236c2deef8919e6759e36036bbe70d1b6a5f2c2e", "table_bytes": 105147148, "compression": "gzip", "uncompressed_table_bytes": 591977542, "documents": 4089, "utf8_bytes": 25008153, "contexts": 12354241, "edges": 20197403, "completed_documents": 295954, "completed_utf8_bytes": 1475477232, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:32:48+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 6954.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00059.jsonl.gz", "table_sha256": "bd51c6e4bc7b9bf811d7bd0992f3428b0cabf21657f82e2ecdddea9c91e600bb", "table_bytes": 105967173, "compression": "gzip", "uncompressed_table_bytes": 596960314, "documents": 4062, "utf8_bytes": 25012208, "contexts": 12462817, "edges": 20351807, "completed_documents": 300016, "completed_utf8_bytes": 1500489440, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:34:43+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7069.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00060.jsonl.gz", "table_sha256": "a326805b7ea9c07a73bfd3fcf87508550471e1d0817e4369d71a38a255923cfb", "table_bytes": 105854447, "compression": "gzip", "uncompressed_table_bytes": 595930198, "documents": 4085, "utf8_bytes": 25003706, "contexts": 12443512, "edges": 20324320, "completed_documents": 304101, "completed_utf8_bytes": 1525493146, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:36:38+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7185.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00061.jsonl.gz", "table_sha256": "2e9417c6e14022e618bed802015063871db32881af63873990c2c85ab8ef66ac", "table_bytes": 106523842, "compression": "gzip", "uncompressed_table_bytes": 600101742, "documents": 4105, "utf8_bytes": 25019477, "contexts": 12533609, "edges": 20456055, "completed_documents": 308206, "completed_utf8_bytes": 1550512623, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:38:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7300.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00062.jsonl.gz", "table_sha256": "b28fa884c16e3a353127684bcde17041860a7e1aca52c9b0346391b38ec8026f", "table_bytes": 105298632, "compression": "gzip", "uncompressed_table_bytes": 593076081, "documents": 4104, "utf8_bytes": 25011781, "contexts": 12385652, "edges": 20222308, "completed_documents": 312310, "completed_utf8_bytes": 1575524404, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:40:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7415.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00063.jsonl.gz", "table_sha256": "e070c64d26f25f52773cf97bbd432bb315042747059f5c234f1bd84d216a8518", "table_bytes": 105410358, "compression": "gzip", "uncompressed_table_bytes": 593294980, "documents": 4050, "utf8_bytes": 25005255, "contexts": 12382605, "edges": 20239190, "completed_documents": 316360, "completed_utf8_bytes": 1600529659, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:42:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7531.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00064.jsonl.gz", "table_sha256": "cc4e1dd632533c58925006e7644ee22c2ada3ac082b36c20faa7d25c63401eed", "table_bytes": 106247975, "compression": "gzip", "uncompressed_table_bytes": 598562236, "documents": 4077, "utf8_bytes": 25007383, "contexts": 12498560, "edges": 20410057, "completed_documents": 320437, "completed_utf8_bytes": 1625537042, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:44:20+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7646.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00065.jsonl.gz", "table_sha256": "e149460a5bd63cb9c40a11fe216d40c45c7c3ace871aafd42946d68621f15136", "table_bytes": 105321605, "compression": "gzip", "uncompressed_table_bytes": 594003175, "documents": 3972, "utf8_bytes": 25008431, "contexts": 12417159, "edges": 20241269, "completed_documents": 324409, "completed_utf8_bytes": 1650545473, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:46:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7761.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00066.jsonl.gz", "table_sha256": "ef28803251b20f4a16d5e5103a0e510255b46aeb0c4d39a4dc477f2473608333", "table_bytes": 105250895, "compression": "gzip", "uncompressed_table_bytes": 592996485, "documents": 4080, "utf8_bytes": 25010806, "contexts": 12385270, "edges": 20216980, "completed_documents": 328489, "completed_utf8_bytes": 1675556279, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:48:10+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7876.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00067.jsonl.gz", "table_sha256": "2b9471940aa5ba7c5977e2bc687f2b83226b45ef549c17ee212f97ef9b89dad3", "table_bytes": 106137464, "compression": "gzip", "uncompressed_table_bytes": 598151569, "documents": 4134, "utf8_bytes": 25006992, "contexts": 12497528, "edges": 20383152, "completed_documents": 332623, "completed_utf8_bytes": 1700563271, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:50:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 7991.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00068.jsonl.gz", "table_sha256": "55de9a86f1f4095f1373b4dcc802b07604942408ca3c659e44f612363332dc95", "table_bytes": 106052231, "compression": "gzip", "uncompressed_table_bytes": 597506081, "documents": 4121, "utf8_bytes": 25000746, "contexts": 12481417, "edges": 20368752, "completed_documents": 336744, "completed_utf8_bytes": 1725564017, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:52:00+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8107.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00069.jsonl.gz", "table_sha256": "f89576d48ac506016bbfa7be6fa06fb832fd1587c1985c33ac3b55603d19d8f7", "table_bytes": 105426220, "compression": "gzip", "uncompressed_table_bytes": 593666893, "documents": 4093, "utf8_bytes": 25006062, "contexts": 12392168, "edges": 20245873, "completed_documents": 340837, "completed_utf8_bytes": 1750570079, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:53:56+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8222.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00070.jsonl.gz", "table_sha256": "4b02706a86e46535893a2dea1b8b5e46551827f55f2cfc1e54968551f1153b95", "table_bytes": 106118424, "compression": "gzip", "uncompressed_table_bytes": 598435158, "documents": 4146, "utf8_bytes": 25007759, "contexts": 12508282, "edges": 20394019, "completed_documents": 344983, "completed_utf8_bytes": 1775577838, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:55:51+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8337.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00071.jsonl.gz", "table_sha256": "dce7e01e240226979a89fe014703367c83a9adce463728f818709dd5829e3cc5", "table_bytes": 105889174, "compression": "gzip", "uncompressed_table_bytes": 596523035, "documents": 4166, "utf8_bytes": 25000686, "contexts": 12457505, "edges": 20338129, "completed_documents": 349149, "completed_utf8_bytes": 1800578524, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:57:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8453.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00072.jsonl.gz", "table_sha256": "c76895c64830791a986dc6f064cb8194b9c3acbb16c101910f97968716baf7e7", "table_bytes": 106396279, "compression": "gzip", "uncompressed_table_bytes": 600114328, "documents": 4120, "utf8_bytes": 25027109, "contexts": 12539243, "edges": 20451760, "completed_documents": 353269, "completed_utf8_bytes": 1825605633, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T05:59:42+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8568.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00073.jsonl.gz", "table_sha256": "da36b781d06791191fe1eb67cbefde937edeeec8e68147007ee269c81e4b2e8d", "table_bytes": 104849356, "compression": "gzip", "uncompressed_table_bytes": 589822432, "documents": 4119, "utf8_bytes": 25003622, "contexts": 12309467, "edges": 20130104, "completed_documents": 357388, "completed_utf8_bytes": 1850609255, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:01:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8684.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00074.jsonl.gz", "table_sha256": "8bd3e7c1518b0cffda3e966ff68f284967f2ff186d6e634946b3d77c856201ff", "table_bytes": 105564280, "compression": "gzip", "uncompressed_table_bytes": 595218952, "documents": 4139, "utf8_bytes": 25001872, "contexts": 12440396, "edges": 20281501, "completed_documents": 361527, "completed_utf8_bytes": 1875611127, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:03:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8800.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00075.jsonl.gz", "table_sha256": "0a693fe2729fa502217b4552d32f868ba44e345ddb6ec38d823c0b96974e416a", "table_bytes": 106139173, "compression": "gzip", "uncompressed_table_bytes": 597494990, "documents": 4123, "utf8_bytes": 25006218, "contexts": 12473766, "edges": 20375506, "completed_documents": 365650, "completed_utf8_bytes": 1900617345, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:05:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 8917.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00076.jsonl.gz", "table_sha256": "882f3fc530dfe4bc7ef0747682105ff42965bfb36864755c866f011b277bbd7e", "table_bytes": 107550906, "compression": "gzip", "uncompressed_table_bytes": 606742083, "documents": 4173, "utf8_bytes": 25027047, "contexts": 12683370, "edges": 20662599, "completed_documents": 369823, "completed_utf8_bytes": 1925644392, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:07:33+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9040.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00077.jsonl.gz", "table_sha256": "5fd5279b119e39a2956a21a609352a45872bdf0fe8993e6ebe7b9ff8a1194cb4", "table_bytes": 105781492, "compression": "gzip", "uncompressed_table_bytes": 595944303, "documents": 4077, "utf8_bytes": 25006400, "contexts": 12445386, "edges": 20324690, "completed_documents": 373900, "completed_utf8_bytes": 1950650792, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:09:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9155.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00078.jsonl.gz", "table_sha256": "aa4481d42c022a5d0c1c72e1c42f1b2bfe8ffeaca31a224942b0c82f8e192434", "table_bytes": 105842342, "compression": "gzip", "uncompressed_table_bytes": 595939963, "documents": 4104, "utf8_bytes": 25010349, "contexts": 12437967, "edges": 20326474, "completed_documents": 378004, "completed_utf8_bytes": 1975661141, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:11:24+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9270.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00079.jsonl.gz", "table_sha256": "2f032ec3101e327961487f0bded5db1bba31869af573a79caeef18c6c5102830", "table_bytes": 105015966, "compression": "gzip", "uncompressed_table_bytes": 590939245, "documents": 4089, "utf8_bytes": 25004576, "contexts": 12326993, "edges": 20162747, "completed_documents": 382093, "completed_utf8_bytes": 2000665717, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:13:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9385.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00080.jsonl.gz", "table_sha256": "b05f0c9046b6124e3b68f36d6da161824119834f36440a15fc8487d78691729d", "table_bytes": 105928969, "compression": "gzip", "uncompressed_table_bytes": 598047596, "documents": 4068, "utf8_bytes": 25015862, "contexts": 12505622, "edges": 20360761, "completed_documents": 386161, "completed_utf8_bytes": 2025681579, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:15:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9501.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00081.jsonl.gz", "table_sha256": "1a626a55b1357a692c07ac6fc88b8bd08bb4c967bf90ee4249fe5ec318467f1b", "table_bytes": 105721905, "compression": "gzip", "uncompressed_table_bytes": 595586683, "documents": 4215, "utf8_bytes": 25004189, "contexts": 12436795, "edges": 20310383, "completed_documents": 390376, "completed_utf8_bytes": 2050685768, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:17:10+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9616.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00082.jsonl.gz", "table_sha256": "c02d62c9a6996ae6609b4e929a2a087de756e2d6d630f2ca56d859d9fdd4bf3e", "table_bytes": 105588773, "compression": "gzip", "uncompressed_table_bytes": 594496927, "documents": 4116, "utf8_bytes": 25006145, "contexts": 12410713, "edges": 20277540, "completed_documents": 394492, "completed_utf8_bytes": 2075691913, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:19:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9731.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00083.jsonl.gz", "table_sha256": "7bf0cde187ab6e3d69f076e50067f9d8001d86f73efd566701b2f3231fbc842b", "table_bytes": 106626131, "compression": "gzip", "uncompressed_table_bytes": 601758277, "documents": 4050, "utf8_bytes": 25002114, "contexts": 12580497, "edges": 20495543, "completed_documents": 398542, "completed_utf8_bytes": 2100694027, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:21:00+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9846.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00084.jsonl.gz", "table_sha256": "8240f9e2548613175982e2e9c97361165d072d07a67965646ebfb1e0bca44175", "table_bytes": 106561941, "compression": "gzip", "uncompressed_table_bytes": 601401431, "documents": 4107, "utf8_bytes": 25002281, "contexts": 12575356, "edges": 20480895, "completed_documents": 402649, "completed_utf8_bytes": 2125696308, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:22:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 9963.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00085.jsonl.gz", "table_sha256": "f09d2ccf3859e875924d8df08141e3319c06696d37dbf0eb5dffca983a034feb", "table_bytes": 107004897, "compression": "gzip", "uncompressed_table_bytes": 603146416, "documents": 4116, "utf8_bytes": 25002789, "contexts": 12600379, "edges": 20559864, "completed_documents": 406765, "completed_utf8_bytes": 2150699097, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:24:52+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10079.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00086.jsonl.gz", "table_sha256": "7473f27ee2989182e8a34e9901da7e0d83b9d15a2d9f806ba701fb6a16b3a18a", "table_bytes": 106529333, "compression": "gzip", "uncompressed_table_bytes": 600732187, "documents": 4119, "utf8_bytes": 25038000, "contexts": 12553013, "edges": 20466004, "completed_documents": 410884, "completed_utf8_bytes": 2175737097, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:26:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10195.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00087.jsonl.gz", "table_sha256": "a0f692d340d1d0a598e90e2a882ab4723ed3c1e8e5246244c6d5b54979e1db6b", "table_bytes": 106976190, "compression": "gzip", "uncompressed_table_bytes": 603087635, "documents": 4101, "utf8_bytes": 25030016, "contexts": 12599413, "edges": 20555477, "completed_documents": 414985, "completed_utf8_bytes": 2200767113, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:28:44+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10310.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00088.jsonl.gz", "table_sha256": "5be1b5ab6818ea22c8cc139054026bd8568b2962acad6f62a690780e9fd3b878", "table_bytes": 106029589, "compression": "gzip", "uncompressed_table_bytes": 597554974, "documents": 4200, "utf8_bytes": 25012855, "contexts": 12481517, "edges": 20364588, "completed_documents": 419185, "completed_utf8_bytes": 2225779968, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:30:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10426.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00089.jsonl.gz", "table_sha256": "06c2151be48872a6a67d02eb27f60af15bd21fb90774ec51a9b50d9670909107", "table_bytes": 106367774, "compression": "gzip", "uncompressed_table_bytes": 599595187, "documents": 4149, "utf8_bytes": 25006310, "contexts": 12526136, "edges": 20427326, "completed_documents": 423334, "completed_utf8_bytes": 2250786278, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:32:36+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10542.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00090.jsonl.gz", "table_sha256": "f8b4487841b924fe0161b6d907feb05dc862ffd7d82ce57f0abc11a940e7d21d", "table_bytes": 105875731, "compression": "gzip", "uncompressed_table_bytes": 595982851, "documents": 4245, "utf8_bytes": 25014212, "contexts": 12438502, "edges": 20325330, "completed_documents": 427579, "completed_utf8_bytes": 2275800490, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:34:31+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10657.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00091.jsonl.gz", "table_sha256": "3986cd16c167f03d43911777929471099c9477931ea79997ff288c5882c4edd6", "table_bytes": 105250854, "compression": "gzip", "uncompressed_table_bytes": 593136000, "documents": 4146, "utf8_bytes": 25000491, "contexts": 12390339, "edges": 20217850, "completed_documents": 431725, "completed_utf8_bytes": 2300800981, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:36:27+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10773.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00092.jsonl.gz", "table_sha256": "397d771012eef63e9d1d6d9f882e9a81d3c85afaf15ad33ef03f965ea06c352e", "table_bytes": 106376332, "compression": "gzip", "uncompressed_table_bytes": 599293410, "documents": 4113, "utf8_bytes": 25006320, "contexts": 12517883, "edges": 20430721, "completed_documents": 435838, "completed_utf8_bytes": 2325807301, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:38:22+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 10889.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00093.jsonl.gz", "table_sha256": "7ee196818d97f2ac014d6a062f27023b1f6e9dd3e86f9ae833647c28c288bc8a", "table_bytes": 105744864, "compression": "gzip", "uncompressed_table_bytes": 594890399, "documents": 4146, "utf8_bytes": 25004487, "contexts": 12414617, "edges": 20292901, "completed_documents": 439984, "completed_utf8_bytes": 2350811788, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:40:18+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11004.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00094.jsonl.gz", "table_sha256": "f58ef44739fcba8f870a55b69b2db13b114c857b69d9ecf30526c3b327551d27", "table_bytes": 106555994, "compression": "gzip", "uncompressed_table_bytes": 600410239, "documents": 4155, "utf8_bytes": 25002494, "contexts": 12537206, "edges": 20464023, "completed_documents": 444139, "completed_utf8_bytes": 2375814282, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:42:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11120.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00095.jsonl.gz", "table_sha256": "cdd2cc775b93c3379231e185991ebf6922b0c2c7fdbc5d6404ac1324d1823b2a", "table_bytes": 106081732, "compression": "gzip", "uncompressed_table_bytes": 598086782, "documents": 4179, "utf8_bytes": 25026878, "contexts": 12495695, "edges": 20383516, "completed_documents": 448318, "completed_utf8_bytes": 2400841160, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:44:10+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11236.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00096.jsonl.gz", "table_sha256": "9a73dede9f9850b5498e3b1dd33c5c918fce77d7c168b45796c87ac1c38c6695", "table_bytes": 107207915, "compression": "gzip", "uncompressed_table_bytes": 605392974, "documents": 4032, "utf8_bytes": 25013909, "contexts": 12664449, "edges": 20603229, "completed_documents": 452350, "completed_utf8_bytes": 2425855069, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:46:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11352.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00097.jsonl.gz", "table_sha256": "f35b468f92fe1dd0d211a92aacf4681b44bf67cd42b0c881a6f8163f12d2b8cd", "table_bytes": 105607993, "compression": "gzip", "uncompressed_table_bytes": 595135746, "documents": 4118, "utf8_bytes": 25001766, "contexts": 12432644, "edges": 20286130, "completed_documents": 456468, "completed_utf8_bytes": 2450856835, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:48:01+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11467.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00098.jsonl.gz", "table_sha256": "f692b7c0736ae63ef391e75e4b6b591b2cb4262e8f72ce1e75f5e7f93c4bb9de", "table_bytes": 104340739, "compression": "gzip", "uncompressed_table_bytes": 587579442, "documents": 4105, "utf8_bytes": 25002116, "contexts": 12265084, "edges": 20041110, "completed_documents": 460573, "completed_utf8_bytes": 2475858951, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:49:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11583.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00099.jsonl.gz", "table_sha256": "7f66da9c7f00df6c419c4ddf23829aa7d6eaf9dd2a3b1a0a4a2ffcce1045a907", "table_bytes": 107391564, "compression": "gzip", "uncompressed_table_bytes": 606819582, "documents": 4158, "utf8_bytes": 25002980, "contexts": 12699474, "edges": 20649340, "completed_documents": 464731, "completed_utf8_bytes": 2500861931, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:51:54+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11700.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00100.jsonl.gz", "table_sha256": "f820ec5f0f712b4f1c75d3a4943f8e601a96ccccd4e156032abd4bace75932fb", "table_bytes": 106604509, "compression": "gzip", "uncompressed_table_bytes": 600174064, "documents": 4124, "utf8_bytes": 25007500, "contexts": 12529470, "edges": 20468063, "completed_documents": 468855, "completed_utf8_bytes": 2525869431, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:53:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11816.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00101.jsonl.gz", "table_sha256": "2fafd1d1beeaa554dae69858ed0bc43aef8b172bc8e84d0b27c8182a2b81e8ec", "table_bytes": 106413433, "compression": "gzip", "uncompressed_table_bytes": 599895520, "documents": 4129, "utf8_bytes": 25004801, "contexts": 12532582, "edges": 20438251, "completed_documents": 472984, "completed_utf8_bytes": 2550874232, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:55:45+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 11932.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00102.jsonl.gz", "table_sha256": "f7347da70778b67dd5246c9222f1270b3f80be8333dd56a7eb2b93d8ef4c67d7", "table_bytes": 105344925, "compression": "gzip", "uncompressed_table_bytes": 593267359, "documents": 4212, "utf8_bytes": 25002440, "contexts": 12388374, "edges": 20223095, "completed_documents": 477196, "completed_utf8_bytes": 2575876672, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:57:41+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12047.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00103.jsonl.gz", "table_sha256": "f575acd97d0b4c8ed113d96477f0a6cda9ff4cafe1724dcb794d66b4055b615a", "table_bytes": 105558825, "compression": "gzip", "uncompressed_table_bytes": 594373730, "documents": 4056, "utf8_bytes": 25004627, "contexts": 12409803, "edges": 20273681, "completed_documents": 481252, "completed_utf8_bytes": 2600881299, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T06:59:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12163.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00104.jsonl.gz", "table_sha256": "f266e5c7adb7b49bc473eea44a35e27f1d91df0dfb051c8cf33e9103865bacab", "table_bytes": 106296961, "compression": "gzip", "uncompressed_table_bytes": 599042663, "documents": 4128, "utf8_bytes": 25004612, "contexts": 12512336, "edges": 20413035, "completed_documents": 485380, "completed_utf8_bytes": 2625885911, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:01:33+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12279.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00105.jsonl.gz", "table_sha256": "8086d281a195cd2946b424dd217bc2c5125381c52d4ffda1d5867c6b09aa3af4", "table_bytes": 105749983, "compression": "gzip", "uncompressed_table_bytes": 596069653, "documents": 4223, "utf8_bytes": 25001788, "contexts": 12450731, "edges": 20321889, "completed_documents": 489603, "completed_utf8_bytes": 2650887699, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:03:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12396.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00106.jsonl.gz", "table_sha256": "1db3f41d8beb6c52502f5221722fc9a1c762b8e91e34f936386c43b418eaa373", "table_bytes": 107154046, "compression": "gzip", "uncompressed_table_bytes": 603928240, "documents": 4066, "utf8_bytes": 25023563, "contexts": 12616316, "edges": 20583596, "completed_documents": 493669, "completed_utf8_bytes": 2675911262, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:05:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12511.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00107.jsonl.gz", "table_sha256": "b384c46cfe9d5d82d4d7e2ef0d38bc8ad199d043a7d99f68a8fb86677aea30af", "table_bytes": 106003823, "compression": "gzip", "uncompressed_table_bytes": 597359486, "documents": 4095, "utf8_bytes": 25008320, "contexts": 12479197, "edges": 20361293, "completed_documents": 497764, "completed_utf8_bytes": 2700919582, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:07:20+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12627.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00108.jsonl.gz", "table_sha256": "1d41b041fc2203210d65172fec9ff3f2fb359f93beb38b007e8da65e8bf52f44", "table_bytes": 105622306, "compression": "gzip", "uncompressed_table_bytes": 595270051, "documents": 4104, "utf8_bytes": 25031246, "contexts": 12433705, "edges": 20290382, "completed_documents": 501868, "completed_utf8_bytes": 2725950828, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:09:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12742.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00109.jsonl.gz", "table_sha256": "b1472caf31b2d714f66e302aff2c19173551dbfc475240a2f35ea3dcc04447a8", "table_bytes": 106827349, "compression": "gzip", "uncompressed_table_bytes": 601954954, "documents": 4173, "utf8_bytes": 25007627, "contexts": 12572020, "edges": 20520685, "completed_documents": 506041, "completed_utf8_bytes": 2750958455, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:11:11+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12858.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00110.jsonl.gz", "table_sha256": "fbdbebb6b8eead8711d3ec58f83cb13bd660ea34285eb0e31adb80c4b747129f", "table_bytes": 106429175, "compression": "gzip", "uncompressed_table_bytes": 600208815, "documents": 4098, "utf8_bytes": 25002440, "contexts": 12541678, "edges": 20449800, "completed_documents": 510139, "completed_utf8_bytes": 2775960895, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:13:08+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 12974.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00111.jsonl.gz", "table_sha256": "8a3009484bfa8505c8f4739ca8c5c2fcd71c77ab62e3c1903ee28e49c3fe0010", "table_bytes": 106525268, "compression": "gzip", "uncompressed_table_bytes": 600061567, "documents": 4084, "utf8_bytes": 25000383, "contexts": 12529811, "edges": 20459134, "completed_documents": 514223, "completed_utf8_bytes": 2800961278, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:15:03+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13090.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00112.jsonl.gz", "table_sha256": "49cd0755d3fa979b85f9e579b5b3719242f156699c131da30c945e4a5c3cfc4a", "table_bytes": 105960277, "compression": "gzip", "uncompressed_table_bytes": 596997615, "documents": 4160, "utf8_bytes": 25005884, "contexts": 12468589, "edges": 20351956, "completed_documents": 518383, "completed_utf8_bytes": 2825967162, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:16:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13205.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00113.jsonl.gz", "table_sha256": "3c944099b8d88f635f2413c7fde67dd277b0dc11547f907f7b39c4989c85fee7", "table_bytes": 105224095, "compression": "gzip", "uncompressed_table_bytes": 592930496, "documents": 4053, "utf8_bytes": 25003659, "contexts": 12384604, "edges": 20215220, "completed_documents": 522436, "completed_utf8_bytes": 2850970821, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:18:54+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13321.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00114.jsonl.gz", "table_sha256": "35736b61f7a6a36dfdd56dffc15cb6ded59a70a67e31604df45c0b88305c98d9", "table_bytes": 105989932, "compression": "gzip", "uncompressed_table_bytes": 597680477, "documents": 4112, "utf8_bytes": 25002374, "contexts": 12488507, "edges": 20364881, "completed_documents": 526548, "completed_utf8_bytes": 2875973195, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:20:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13436.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00115.jsonl.gz", "table_sha256": "2045816484ad4a766af9bc552b2c2f76317ed9262dd7b3a9740b818a5216dd7b", "table_bytes": 104932860, "compression": "gzip", "uncompressed_table_bytes": 591208515, "documents": 4063, "utf8_bytes": 25010451, "contexts": 12348428, "edges": 20156101, "completed_documents": 530611, "completed_utf8_bytes": 2900983646, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:22:45+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13551.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00116.jsonl.gz", "table_sha256": "50fd24b54640a73b0ef6c26f24db4dd8f20e459270083f66c185b22aeaf0ccab", "table_bytes": 105935425, "compression": "gzip", "uncompressed_table_bytes": 596385395, "documents": 4118, "utf8_bytes": 25006256, "contexts": 12450038, "edges": 20336993, "completed_documents": 534729, "completed_utf8_bytes": 2925989902, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:24:40+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13667.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00117.jsonl.gz", "table_sha256": "5b8909318373fb6b0f62136685052fc71ba66372352f70bf401d1770aeadfc54", "table_bytes": 106146610, "compression": "gzip", "uncompressed_table_bytes": 598680896, "documents": 4093, "utf8_bytes": 25010601, "contexts": 12509045, "edges": 20401077, "completed_documents": 538822, "completed_utf8_bytes": 2951000503, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:26:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13783.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00118.jsonl.gz", "table_sha256": "0d7cd2aa021f2e7ee95963e4f6b92784edeea91c6235d26c197dc9482293b3af", "table_bytes": 107319440, "compression": "gzip", "uncompressed_table_bytes": 605358451, "documents": 4068, "utf8_bytes": 25015734, "contexts": 12652320, "edges": 20620706, "completed_documents": 542890, "completed_utf8_bytes": 2976016237, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:28:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 13900.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00119.jsonl.gz", "table_sha256": "ec58fb0f9f5871f932c6726b1ee8f1e27760a1305f6e66401118ee1413654984", "table_bytes": 106565193, "compression": "gzip", "uncompressed_table_bytes": 601282373, "documents": 4101, "utf8_bytes": 25004437, "contexts": 12571448, "edges": 20478527, "completed_documents": 546991, "completed_utf8_bytes": 3001020674, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:30:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14015.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00120.jsonl.gz", "table_sha256": "635c3188240db00f1a71889a8a31967c31bd7702d50932cea2017b1d71fcab8a", "table_bytes": 105995435, "compression": "gzip", "uncompressed_table_bytes": 596980316, "documents": 4115, "utf8_bytes": 25000088, "contexts": 12464973, "edges": 20356931, "completed_documents": 551106, "completed_utf8_bytes": 3026020762, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:32:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14131.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00121.jsonl.gz", "table_sha256": "1f1ae8ea730568b802454b147ebc4665b33dd0b990fa8da8fdb8ee86a860be85", "table_bytes": 106208499, "compression": "gzip", "uncompressed_table_bytes": 598749254, "documents": 4156, "utf8_bytes": 25020266, "contexts": 12509926, "edges": 20406094, "completed_documents": 555262, "completed_utf8_bytes": 3051041028, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:34:20+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14247.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00122.jsonl.gz", "table_sha256": "4701ace02137edc00ec1b500cf02a14acd831e9c81e59a7229683e2dd93f538a", "table_bytes": 106518712, "compression": "gzip", "uncompressed_table_bytes": 600620984, "documents": 4082, "utf8_bytes": 25001015, "contexts": 12547170, "edges": 20463041, "completed_documents": 559344, "completed_utf8_bytes": 3076042043, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:36:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14362.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00123.jsonl.gz", "table_sha256": "aa75bed6bfad650abc3601353ada22a7bf4268fe160370c58b365a39e5e7fa3a", "table_bytes": 106321006, "compression": "gzip", "uncompressed_table_bytes": 598738625, "documents": 4125, "utf8_bytes": 25000640, "contexts": 12503959, "edges": 20411724, "completed_documents": 563469, "completed_utf8_bytes": 3101042683, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:38:12+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14479.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00124.jsonl.gz", "table_sha256": "0602d56fd0941769bca9eb7745959a71d88bb301611245bf091376a2a4c3be65", "table_bytes": 106827302, "compression": "gzip", "uncompressed_table_bytes": 602509910, "documents": 4142, "utf8_bytes": 25000800, "contexts": 12597735, "edges": 20522766, "completed_documents": 567611, "completed_utf8_bytes": 3126043483, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:40:08+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14594.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00125.jsonl.gz", "table_sha256": "40291ad0baebbbe5a017ee25dc8f58eadccedb2f5563e4ea471ef1013e997d06", "table_bytes": 106403634, "compression": "gzip", "uncompressed_table_bytes": 599963368, "documents": 4106, "utf8_bytes": 25001087, "contexts": 12537939, "edges": 20440705, "completed_documents": 571717, "completed_utf8_bytes": 3151044570, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:42:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14710.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00126.jsonl.gz", "table_sha256": "4804330624c2553bcd4a70b7c4973bffd1b619310692add4d414e142dd0db214", "table_bytes": 106075593, "compression": "gzip", "uncompressed_table_bytes": 597167041, "documents": 4169, "utf8_bytes": 25000015, "contexts": 12464551, "edges": 20371361, "completed_documents": 575886, "completed_utf8_bytes": 3176044585, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:43:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14826.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00127.jsonl.gz", "table_sha256": "0e8b19bc1c60b236521100f8856513de852e7160a11adc193d11aa4e9307f191", "table_bytes": 105685490, "compression": "gzip", "uncompressed_table_bytes": 595782598, "documents": 4075, "utf8_bytes": 25002394, "contexts": 12447515, "edges": 20307529, "completed_documents": 579961, "completed_utf8_bytes": 3201046979, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:45:55+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 14941.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00128.jsonl.gz", "table_sha256": "8198ff82e366c965b0d66f620d1ff46f2e52a0b66386c187ca8f57b7ee63942f", "table_bytes": 106463915, "compression": "gzip", "uncompressed_table_bytes": 599690262, "documents": 4109, "utf8_bytes": 25004738, "contexts": 12523292, "edges": 20445942, "completed_documents": 584070, "completed_utf8_bytes": 3226051717, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:47:51+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15058.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00129.jsonl.gz", "table_sha256": "c785ec6a7c6b39d2dfda2fc5662846611127caead7cdee8acd695701bb620ef2", "table_bytes": 106936523, "compression": "gzip", "uncompressed_table_bytes": 603342062, "documents": 4116, "utf8_bytes": 25003924, "contexts": 12617143, "edges": 20548177, "completed_documents": 588186, "completed_utf8_bytes": 3251055641, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:49:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15173.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00130.jsonl.gz", "table_sha256": "d41e3d5dc6c19933d6f94287844f3364cdb79e8e1fc91e91e553b4b1f1f8ec26", "table_bytes": 106057326, "compression": "gzip", "uncompressed_table_bytes": 597729473, "documents": 4108, "utf8_bytes": 25011221, "contexts": 12486732, "edges": 20378256, "completed_documents": 592294, "completed_utf8_bytes": 3276066862, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:51:43+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15289.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00131.jsonl.gz", "table_sha256": "5bb3963da069e711cfa02f589d266ac09cb57a609b37a7ffadc4054084e64b88", "table_bytes": 106646717, "compression": "gzip", "uncompressed_table_bytes": 600623348, "documents": 4077, "utf8_bytes": 25010349, "contexts": 12539449, "edges": 20477364, "completed_documents": 596371, "completed_utf8_bytes": 3301077211, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:53:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15405.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00132.jsonl.gz", "table_sha256": "3ea047b8858b1bb731efa2f705d3477dd19dd4921f58fd4f68416ccf0d706207", "table_bytes": 106810708, "compression": "gzip", "uncompressed_table_bytes": 602411950, "documents": 4235, "utf8_bytes": 25000583, "contexts": 12590642, "edges": 20518971, "completed_documents": 600606, "completed_utf8_bytes": 3326077794, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:55:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15522.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00133.jsonl.gz", "table_sha256": "032e3e6e66ec58c1edd9e34e566b423af0c0bb47bc84fdba513f38a4613e4634", "table_bytes": 107496266, "compression": "gzip", "uncompressed_table_bytes": 606349343, "documents": 4054, "utf8_bytes": 25002649, "contexts": 12675671, "edges": 20645617, "completed_documents": 604660, "completed_utf8_bytes": 3351080443, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:57:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15636.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00134.jsonl.gz", "table_sha256": "96d114159890f574543ce8cbeca1d77d90b9256ee1fd17410087772fe932d807", "table_bytes": 104463598, "compression": "gzip", "uncompressed_table_bytes": 588238625, "documents": 4101, "utf8_bytes": 25003266, "contexts": 12283455, "edges": 20062059, "completed_documents": 608761, "completed_utf8_bytes": 3376083709, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T07:59:26+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15752.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00135.jsonl.gz", "table_sha256": "b2b7c047f918137a178c88fd56804e4a31a27e020d3c6430edc8e381bd80afcc", "table_bytes": 105821094, "compression": "gzip", "uncompressed_table_bytes": 595971649, "documents": 4150, "utf8_bytes": 25000320, "contexts": 12442486, "edges": 20319759, "completed_documents": 612911, "completed_utf8_bytes": 3401084029, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:01:22+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15868.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00136.jsonl.gz", "table_sha256": "88b33a82b07b1c0bd563bc395b5535d5bcc703924c35dd8946ce46e4026b0784", "table_bytes": 106507180, "compression": "gzip", "uncompressed_table_bytes": 600089069, "documents": 4071, "utf8_bytes": 25000503, "contexts": 12532293, "edges": 20457742, "completed_documents": 616982, "completed_utf8_bytes": 3426084532, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:03:18+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 15984.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00137.jsonl.gz", "table_sha256": "4954025c034d7dcef095d4c3dc553206cf0c260887d4d8878602ceb4eda7be3e", "table_bytes": 105764040, "compression": "gzip", "uncompressed_table_bytes": 595778281, "documents": 4046, "utf8_bytes": 25002924, "contexts": 12439794, "edges": 20309701, "completed_documents": 621028, "completed_utf8_bytes": 3451087456, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:05:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16100.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00138.jsonl.gz", "table_sha256": "3d97b9eaecbd7d593de0777196557823e67519fd622d6d50b62b49693c0b9ee7", "table_bytes": 106760362, "compression": "gzip", "uncompressed_table_bytes": 602266864, "documents": 4089, "utf8_bytes": 25012241, "contexts": 12588905, "edges": 20519059, "completed_documents": 625117, "completed_utf8_bytes": 3476099697, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:07:10+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16216.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00139.jsonl.gz", "table_sha256": "98cf81a027dc46d7342eae7bc7e898f13109829c35cbe3911a46baba4e3362c1", "table_bytes": 107033289, "compression": "gzip", "uncompressed_table_bytes": 603334411, "documents": 4059, "utf8_bytes": 25000671, "contexts": 12605469, "edges": 20568638, "completed_documents": 629176, "completed_utf8_bytes": 3501100368, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:09:06+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16332.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00140.jsonl.gz", "table_sha256": "83edbff59d66a58227b330eac05d2566b4464e8fd12676fc511b0ad0387b45ca", "table_bytes": 105594546, "compression": "gzip", "uncompressed_table_bytes": 594411725, "documents": 3999, "utf8_bytes": 25011923, "contexts": 12406487, "edges": 20278025, "completed_documents": 633175, "completed_utf8_bytes": 3526112291, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:11:02+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16448.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00141.jsonl.gz", "table_sha256": "3c5488e8aa6dfb0e57438fe8055698b8126bf93c6d1a84fbc54ff280139da0ad", "table_bytes": 106295364, "compression": "gzip", "uncompressed_table_bytes": 598803023, "documents": 4134, "utf8_bytes": 25002023, "contexts": 12503833, "edges": 20416302, "completed_documents": 637309, "completed_utf8_bytes": 3551114314, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:12:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16564.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00142.jsonl.gz", "table_sha256": "017d1176fb9e373329685748637997e6156a267b24223a79a68dd65c0059ce8a", "table_bytes": 106012769, "compression": "gzip", "uncompressed_table_bytes": 596917180, "documents": 4089, "utf8_bytes": 25005955, "contexts": 12459954, "edges": 20357606, "completed_documents": 641398, "completed_utf8_bytes": 3576120269, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:14:54+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16680.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00143.jsonl.gz", "table_sha256": "ebd3177a01313859286c6a1b8e4e8c6754e5262f5247e575e47907b44d646838", "table_bytes": 107071057, "compression": "gzip", "uncompressed_table_bytes": 603651850, "documents": 4112, "utf8_bytes": 25001699, "contexts": 12610260, "edges": 20566987, "completed_documents": 645510, "completed_utf8_bytes": 3601121968, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:16:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16796.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00144.jsonl.gz", "table_sha256": "23a63c805039d6b3db6baf9294877aced3a73a6f4501991a52560b6391aebbb9", "table_bytes": 105692970, "compression": "gzip", "uncompressed_table_bytes": 594558917, "documents": 4035, "utf8_bytes": 25001863, "contexts": 12407476, "edges": 20288372, "completed_documents": 649545, "completed_utf8_bytes": 3626123831, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:18:46+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 16912.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00145.jsonl.gz", "table_sha256": "d3aaae7c2af9163f349788ae2f0bfa16876661acac5e4e0f62771b9f644b83c7", "table_bytes": 106466713, "compression": "gzip", "uncompressed_table_bytes": 599944662, "documents": 4093, "utf8_bytes": 25002975, "contexts": 12532849, "edges": 20447424, "completed_documents": 653638, "completed_utf8_bytes": 3651126806, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:20:41+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17027.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00146.jsonl.gz", "table_sha256": "29f1bcc11d4b3fda5bae92435d8d7f965e7aacbe083b221610ea332830e8315d", "table_bytes": 105216519, "compression": "gzip", "uncompressed_table_bytes": 591887111, "documents": 4071, "utf8_bytes": 25007599, "contexts": 12349642, "edges": 20201035, "completed_documents": 657709, "completed_utf8_bytes": 3676134405, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:22:38+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17144.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00147.jsonl.gz", "table_sha256": "b89bc0c81bf9056edb324b5559db35815e5ad49526c6d95928588a193bdd96ba", "table_bytes": 107105247, "compression": "gzip", "uncompressed_table_bytes": 604329530, "documents": 4146, "utf8_bytes": 25001126, "contexts": 12632669, "edges": 20580550, "completed_documents": 661855, "completed_utf8_bytes": 3701135531, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:24:33+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17260.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00148.jsonl.gz", "table_sha256": "d969509a15be3673222ec139a3b8066b6009153dc23d779ef9e090f48cb1197d", "table_bytes": 105405121, "compression": "gzip", "uncompressed_table_bytes": 593507303, "documents": 4025, "utf8_bytes": 25005913, "contexts": 12388222, "edges": 20236566, "completed_documents": 665880, "completed_utf8_bytes": 3726141444, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:26:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17376.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00149.jsonl.gz", "table_sha256": "51ba5a69838d5d80878d7bf729b54fece23e6981fd3bbabdbf95ba0900370d3c", "table_bytes": 107281051, "compression": "gzip", "uncompressed_table_bytes": 604423003, "documents": 4092, "utf8_bytes": 25003886, "contexts": 12620603, "edges": 20601074, "completed_documents": 669972, "completed_utf8_bytes": 3751145330, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:28:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17491.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00150.jsonl.gz", "table_sha256": "23e46f9c76f0f85b5c81c3f457d34238fa8ebcec3f8de26af1edd345417d9ea1", "table_bytes": 106194905, "compression": "gzip", "uncompressed_table_bytes": 598328190, "documents": 4084, "utf8_bytes": 25006612, "contexts": 12494862, "edges": 20399117, "completed_documents": 674056, "completed_utf8_bytes": 3776151942, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:30:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17607.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00151.jsonl.gz", "table_sha256": "a0f59471a27df6b29baa2efbab665415c16914148cd03b8c1ba65b690f2daaac", "table_bytes": 105682757, "compression": "gzip", "uncompressed_table_bytes": 595673642, "documents": 4128, "utf8_bytes": 25006586, "contexts": 12447696, "edges": 20302776, "completed_documents": 678184, "completed_utf8_bytes": 3801158528, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:32:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17723.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00152.jsonl.gz", "table_sha256": "27c79c0d5906b59c038be962b353b73788282ea2579ad5b0c498cbadd7244942", "table_bytes": 104707759, "compression": "gzip", "uncompressed_table_bytes": 588888490, "documents": 4205, "utf8_bytes": 25000502, "contexts": 12285522, "edges": 20102593, "completed_documents": 682389, "completed_utf8_bytes": 3826159030, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:34:12+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17838.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00153.jsonl.gz", "table_sha256": "dd754044a5806db2a50d8ec36dca03fea87770fa12ca296e8307612e2c966f0f", "table_bytes": 105903989, "compression": "gzip", "uncompressed_table_bytes": 596820703, "documents": 4050, "utf8_bytes": 25003925, "contexts": 12469072, "edges": 20342697, "completed_documents": 686439, "completed_utf8_bytes": 3851162955, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:36:08+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 17954.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00154.jsonl.gz", "table_sha256": "93e4c4cc3b108d642deb753c79296ce93469a5651ac5a99fe11e5d3bf424965b", "table_bytes": 107034545, "compression": "gzip", "uncompressed_table_bytes": 603044532, "documents": 4090, "utf8_bytes": 25008322, "contexts": 12593697, "edges": 20555742, "completed_documents": 690529, "completed_utf8_bytes": 3876171277, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:38:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18070.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00155.jsonl.gz", "table_sha256": "1825242f972bef861e3279422d1155115c8ed1f995c2fc12e7f6da16d3e2c532", "table_bytes": 106277584, "compression": "gzip", "uncompressed_table_bytes": 599245714, "documents": 4152, "utf8_bytes": 25004133, "contexts": 12521772, "edges": 20417475, "completed_documents": 694681, "completed_utf8_bytes": 3901175410, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:40:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18190.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00156.jsonl.gz", "table_sha256": "309b03f69de7351737f5a1433966e0d5fcf23691c79f0a45ec2da0c5577003a4", "table_bytes": 111547615, "compression": "gzip", "uncompressed_table_bytes": 631506629, "documents": 9495, "utf8_bytes": 25002198, "contexts": 13235984, "edges": 21444656, "completed_documents": 704176, "completed_utf8_bytes": 3926177608, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:42:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18311.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00157.jsonl.gz", "table_sha256": "46ab720cec29798d32948d08f78859e1a163a170df5395d0985c602704233a11", "table_bytes": 114830935, "compression": "gzip", "uncompressed_table_bytes": 651101844, "documents": 13096, "utf8_bytes": 25000245, "contexts": 13660933, "edges": 22076257, "completed_documents": 717272, "completed_utf8_bytes": 3951177853, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:44:06+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18432.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00158.jsonl.gz", "table_sha256": "2bc96a82670fc5861dee13ddbef0d511991374d5ae301d409ffacd085f06ec27", "table_bytes": 114570701, "compression": "gzip", "uncompressed_table_bytes": 649616763, "documents": 12956, "utf8_bytes": 25000888, "contexts": 13632377, "edges": 22027248, "completed_documents": 730228, "completed_utf8_bytes": 3976178741, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:46:08+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18554.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00159.jsonl.gz", "table_sha256": "283661e38b9fe3256b6a539e74b40f0f72daf9c680e2ec7e75f0a3aabc5cae02", "table_bytes": 114699720, "compression": "gzip", "uncompressed_table_bytes": 650384599, "documents": 13182, "utf8_bytes": 25003300, "contexts": 13647337, "edges": 22050840, "completed_documents": 743410, "completed_utf8_bytes": 4001182041, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:48:08+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18675.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00160.jsonl.gz", "table_sha256": "bb0f40acf676aeafd289554bd041d67d91c6dce3780966b44ed7403d01ef1b1f", "table_bytes": 114201302, "compression": "gzip", "uncompressed_table_bytes": 647450962, "documents": 13128, "utf8_bytes": 25001537, "contexts": 13585292, "edges": 21954157, "completed_documents": 756538, "completed_utf8_bytes": 4026183578, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:50:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18795.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00161.jsonl.gz", "table_sha256": "ea2df72425da0fd6cdcff0402c2e0a5124763dac46fcfe2301d974321acd3e0f", "table_bytes": 114178781, "compression": "gzip", "uncompressed_table_bytes": 647013252, "documents": 13006, "utf8_bytes": 25001838, "contexts": 13570277, "edges": 21946732, "completed_documents": 769544, "completed_utf8_bytes": 4051185416, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:52:10+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 18916.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00162.jsonl.gz", "table_sha256": "a3e02622959037c8d654c077740cb849e68d8d998f87ae3f3365db871bb396c3", "table_bytes": 114444165, "compression": "gzip", "uncompressed_table_bytes": 648519540, "documents": 13044, "utf8_bytes": 25002921, "contexts": 13601001, "edges": 22001271, "completed_documents": 782588, "completed_utf8_bytes": 4076188337, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:54:11+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19038.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00163.jsonl.gz", "table_sha256": "b68019af58f0817cd2dfbff1e895e7f37f3468cd84f1f27c4fe3435568217b81", "table_bytes": 114793582, "compression": "gzip", "uncompressed_table_bytes": 650761703, "documents": 12964, "utf8_bytes": 25001088, "contexts": 13653719, "edges": 22068504, "completed_documents": 795552, "completed_utf8_bytes": 4101189425, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:56:12+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19159.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00164.jsonl.gz", "table_sha256": "a42e83228aab4f3ffceddf533cb54ee7a79daa9bea31603409f85195de6b45d6", "table_bytes": 114044336, "compression": "gzip", "uncompressed_table_bytes": 646801253, "documents": 13086, "utf8_bytes": 25001215, "contexts": 13574803, "edges": 21925416, "completed_documents": 808638, "completed_utf8_bytes": 4126190640, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T08:58:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19280.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00165.jsonl.gz", "table_sha256": "4a64b06c80a6a599748c01f5b9c949636e1740f887b2d02991d6f1e4718b853d", "table_bytes": 115199498, "compression": "gzip", "uncompressed_table_bytes": 653332604, "documents": 13202, "utf8_bytes": 25001410, "contexts": 13712231, "edges": 22148985, "completed_documents": 821840, "completed_utf8_bytes": 4151192050, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T09:00:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19401.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00166.jsonl.gz", "table_sha256": "1c0e0815c0f40f9e33892e93169d8b9705d8eda21439cf05306f98d35abc4fd2", "table_bytes": 114995106, "compression": "gzip", "uncompressed_table_bytes": 652440456, "documents": 13108, "utf8_bytes": 25003981, "contexts": 13694510, "edges": 22114626, "completed_documents": 834948, "completed_utf8_bytes": 4176196031, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T09:02:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19522.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00167.jsonl.gz", "table_sha256": "cbec7f77ba0b01d0a15a04a55014d7a9f63f1e6855c1ee2647e5318eced6a8f9", "table_bytes": 114447158, "compression": "gzip", "uncompressed_table_bytes": 649126991, "documents": 12964, "utf8_bytes": 25000494, "contexts": 13623288, "edges": 22008200, "completed_documents": 847912, "completed_utf8_bytes": 4201196525, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T09:04:17+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19643.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00168.jsonl.gz", "table_sha256": "008b7651eabb1d0015aa5e40b9fd0aa075e9c3dc85696efe22d13e6ee49463c3", "table_bytes": 114688860, "compression": "gzip", "uncompressed_table_bytes": 650451369, "documents": 12950, "utf8_bytes": 25001149, "contexts": 13648212, "edges": 22050559, "completed_documents": 860862, "completed_utf8_bytes": 4226197674, "peak_host_rss_bytes": 5472051200}

## 2026-10-20T09:06:18+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19764.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00169.jsonl.gz", "table_sha256": "da00dc1089e9009baea7b8133c95f98bdf878e9e2f5ee043d043e196ec7fbce1", "table_bytes": 115368789, "compression": "gzip", "uncompressed_table_bytes": 654660661, "documents": 12912, "utf8_bytes": 25003482, "contexts": 13742981, "edges": 22187750, "completed_documents": 873774, "completed_utf8_bytes": 4251201156, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:08:20+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 19886.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00170.jsonl.gz", "table_sha256": "aeb5e9f81750fffa397af2f3b7a2d6c7d1c254deb4273aa576a6db5607aaab47", "table_bytes": 114654755, "compression": "gzip", "uncompressed_table_bytes": 650168418, "documents": 13030, "utf8_bytes": 25002088, "contexts": 13643360, "edges": 22043642, "completed_documents": 886804, "completed_utf8_bytes": 4276203244, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:10:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20008.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00171.jsonl.gz", "table_sha256": "bfd528a8b0c4fef13325454ef5f14cbd66e681facd736ceecd881d7d54083ad8", "table_bytes": 114323856, "compression": "gzip", "uncompressed_table_bytes": 647984898, "documents": 12917, "utf8_bytes": 25000134, "contexts": 13593362, "edges": 21973989, "completed_documents": 899721, "completed_utf8_bytes": 4301203378, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:12:23+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20129.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00172.jsonl.gz", "table_sha256": "bf1d14e873a9773ee4e277873bb15ec0fc4ed84e66bea9c544c4c6daca4fbd59", "table_bytes": 114894421, "compression": "gzip", "uncompressed_table_bytes": 651627422, "documents": 13113, "utf8_bytes": 25001368, "contexts": 13675381, "edges": 22088242, "completed_documents": 912834, "completed_utf8_bytes": 4326204746, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:14:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20251.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00173.jsonl.gz", "table_sha256": "7e9ad73deb227c0b21fbedca3f4192284e3634b7e0664bd226c65d9a886029da", "table_bytes": 114532026, "compression": "gzip", "uncompressed_table_bytes": 649614212, "documents": 13046, "utf8_bytes": 25000726, "contexts": 13634612, "edges": 22020376, "completed_documents": 925880, "completed_utf8_bytes": 4351205472, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:16:27+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20373.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00174.jsonl.gz", "table_sha256": "f59142c85c4a9a3f19def493d5e2c9714193f042123e3601c442b4c44b0b9cf2", "table_bytes": 114272981, "compression": "gzip", "uncompressed_table_bytes": 647728796, "documents": 13114, "utf8_bytes": 25003666, "contexts": 13588289, "edges": 21966568, "completed_documents": 938994, "completed_utf8_bytes": 4376209138, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:18:28+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20494.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00175.jsonl.gz", "table_sha256": "a85257e8b459e418871a0f2941c3a73ad65a95299a75b9ee8b1b776ac53dae44", "table_bytes": 114950111, "compression": "gzip", "uncompressed_table_bytes": 651979799, "documents": 13040, "utf8_bytes": 25002988, "contexts": 13682713, "edges": 22102439, "completed_documents": 952034, "completed_utf8_bytes": 4401212126, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:20:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20616.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00176.jsonl.gz", "table_sha256": "5aa5edd014bbf45e0883e6b4695e1716dc25500436f0d802c7932f95a42ba1d2", "table_bytes": 114877908, "compression": "gzip", "uncompressed_table_bytes": 651497570, "documents": 13104, "utf8_bytes": 25000007, "contexts": 13672413, "edges": 22089896, "completed_documents": 965138, "completed_utf8_bytes": 4426212133, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:22:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20736.9s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00177.jsonl.gz", "table_sha256": "4c366a44d6fff93a1c2715ff0a39bc819800455767079fd096ce4bae745dfe49", "table_bytes": 114160617, "compression": "gzip", "uncompressed_table_bytes": 647201974, "documents": 12980, "utf8_bytes": 25000846, "contexts": 13577691, "edges": 21950318, "completed_documents": 978118, "completed_utf8_bytes": 4451212979, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:24:32+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20858.8s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00178.jsonl.gz", "table_sha256": "d20dadf6a6ab6bd232ccb4f84dbfaeb1e90afd5122d36012ffaf330085a0b45f", "table_bytes": 114508797, "compression": "gzip", "uncompressed_table_bytes": 649693104, "documents": 13076, "utf8_bytes": 25003262, "contexts": 13637784, "edges": 22021249, "completed_documents": 991194, "completed_utf8_bytes": 4476216241, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:26:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 20980.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00179.jsonl.gz", "table_sha256": "1f37b1e3dd4fb749bf3b309ce10c4faa0b25b70308533ba8c4e52a367f42a39c", "table_bytes": 114713857, "compression": "gzip", "uncompressed_table_bytes": 650595350, "documents": 12996, "utf8_bytes": 25004107, "contexts": 13653881, "edges": 22055950, "completed_documents": 1004190, "completed_utf8_bytes": 4501220348, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:28:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21101.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00180.jsonl.gz", "table_sha256": "c2b713d91fdb4f0970c4bc6a6dec92cb26f9b4e720c1791ef6694f574c803cd2", "table_bytes": 115200626, "compression": "gzip", "uncompressed_table_bytes": 653489810, "documents": 13114, "utf8_bytes": 25000737, "contexts": 13718038, "edges": 22150289, "completed_documents": 1017304, "completed_utf8_bytes": 4526221085, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:30:36+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21222.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00181.jsonl.gz", "table_sha256": "9da53c6e0e3d2dcd126c62c8e8d2e003a3b4c5d1c30af10c26b2f52c953155b7", "table_bytes": 114688853, "compression": "gzip", "uncompressed_table_bytes": 650498222, "documents": 13193, "utf8_bytes": 25000341, "contexts": 13650318, "edges": 22052642, "completed_documents": 1030497, "completed_utf8_bytes": 4551221426, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:32:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21343.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00182.jsonl.gz", "table_sha256": "c57f068f1f1a76511bcebd1e1506287125d4ff70dc3e210a70db31967f50032c", "table_bytes": 114877053, "compression": "gzip", "uncompressed_table_bytes": 651629142, "documents": 13026, "utf8_bytes": 25000112, "contexts": 13676430, "edges": 22089488, "completed_documents": 1043523, "completed_utf8_bytes": 4576221538, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:34:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21465.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00183.jsonl.gz", "table_sha256": "f0ddc2d513e2dee5b4be029a2aa5b299fa5524402a54a2f417cbdb31483dd7d0", "table_bytes": 114688614, "compression": "gzip", "uncompressed_table_bytes": 650314917, "documents": 13045, "utf8_bytes": 25002190, "contexts": 13645257, "edges": 22050487, "completed_documents": 1056568, "completed_utf8_bytes": 4601223728, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:36:41+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21587.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00184.jsonl.gz", "table_sha256": "28e31f2f811220fb0e6f847caad38b39985942f04f2c0def400551cc7a8d61b4", "table_bytes": 114874256, "compression": "gzip", "uncompressed_table_bytes": 651286263, "documents": 13221, "utf8_bytes": 25000212, "contexts": 13666351, "edges": 22083149, "completed_documents": 1069789, "completed_utf8_bytes": 4626223940, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:38:42+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21708.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00185.jsonl.gz", "table_sha256": "9113c4a92b374fffc2ee5aef6400770af738536932937c379dc52f0edabcf0ff", "table_bytes": 114880822, "compression": "gzip", "uncompressed_table_bytes": 651982610, "documents": 12966, "utf8_bytes": 25000840, "contexts": 13687958, "edges": 22093104, "completed_documents": 1082755, "completed_utf8_bytes": 4651224780, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:40:43+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21830.1s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00186.jsonl.gz", "table_sha256": "9d0a3f1ac76011eeb1088e08442c62cff555fb825c2746289270f1e9b33e2bee", "table_bytes": 114458537, "compression": "gzip", "uncompressed_table_bytes": 649122665, "documents": 13011, "utf8_bytes": 25002434, "contexts": 13622345, "edges": 22007767, "completed_documents": 1095766, "completed_utf8_bytes": 4676227214, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:42:44+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 21950.5s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00187.jsonl.gz", "table_sha256": "f8e5c63b65a7d6fac2799fc95d0faf2aa17273c128e7b79b20210aedb3496273", "table_bytes": 114855373, "compression": "gzip", "uncompressed_table_bytes": 651640200, "documents": 13052, "utf8_bytes": 25003865, "contexts": 13677338, "edges": 22088827, "completed_documents": 1108818, "completed_utf8_bytes": 4701231079, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:44:45+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22071.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00188.jsonl.gz", "table_sha256": "28cb345782ec3e13486bffc8811f79eb7040e8d933c93299841523f0ca3f4892", "table_bytes": 115015203, "compression": "gzip", "uncompressed_table_bytes": 652475715, "documents": 13023, "utf8_bytes": 25000504, "contexts": 13696591, "edges": 22114563, "completed_documents": 1121841, "completed_utf8_bytes": 4726231583, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:46:46+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22192.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00189.jsonl.gz", "table_sha256": "f037b28b4ec13b0cadcee203a3b3daf29586bc1355c01e5a9f46609d7b247ad6", "table_bytes": 114193263, "compression": "gzip", "uncompressed_table_bytes": 647247972, "documents": 12975, "utf8_bytes": 25002553, "contexts": 13574721, "edges": 21953599, "completed_documents": 1134816, "completed_utf8_bytes": 4751234136, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:48:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22314.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00190.jsonl.gz", "table_sha256": "95a0df24f73724f08f04133d789192103b700b8873453458812c5327fef2366f", "table_bytes": 114778864, "compression": "gzip", "uncompressed_table_bytes": 650785300, "documents": 13096, "utf8_bytes": 25000589, "contexts": 13656305, "edges": 22063447, "completed_documents": 1147912, "completed_utf8_bytes": 4776234725, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:50:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22435.3s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00191.jsonl.gz", "table_sha256": "65b22018e5f159a0ba4fdece3263061a135f6b65d73649d4d4dab96da2c56a48", "table_bytes": 115031147, "compression": "gzip", "uncompressed_table_bytes": 652522934, "documents": 12990, "utf8_bytes": 25000756, "contexts": 13696153, "edges": 22116715, "completed_documents": 1160902, "completed_utf8_bytes": 4801235481, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:52:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22556.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00192.jsonl.gz", "table_sha256": "7705505be6db2bc3468f88bd1831fd98936f7434bd15598fbfd37a0ffa00dadf", "table_bytes": 114684674, "compression": "gzip", "uncompressed_table_bytes": 650893625, "documents": 13004, "utf8_bytes": 25000958, "contexts": 13667112, "edges": 22058355, "completed_documents": 1173906, "completed_utf8_bytes": 4826236439, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:54:51+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22678.0s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00193.jsonl.gz", "table_sha256": "cf1110a972d569dcba0cd6561dd6f98d63cd46ed44b0bbc695d6736990adca04", "table_bytes": 114071754, "compression": "gzip", "uncompressed_table_bytes": 646561017, "documents": 12982, "utf8_bytes": 25000834, "contexts": 13562387, "edges": 21932552, "completed_documents": 1186888, "completed_utf8_bytes": 4851237273, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:56:53+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22799.7s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00194.jsonl.gz", "table_sha256": "7b1f8ddc56d719955ca06e9b316c05de96195cc8c0be38cb31a0642c5662d54b", "table_bytes": 114759074, "compression": "gzip", "uncompressed_table_bytes": 651045915, "documents": 13123, "utf8_bytes": 25000557, "contexts": 13665278, "edges": 22069904, "completed_documents": 1200011, "completed_utf8_bytes": 4876237830, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T09:58:55+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 22921.6s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00195.jsonl.gz", "table_sha256": "c352282f4cd47ee1b744160e122b9858ce52f3fc8f58acdec12a53ea7a7e1649", "table_bytes": 115319600, "compression": "gzip", "uncompressed_table_bytes": 654169913, "documents": 12947, "utf8_bytes": 25001364, "contexts": 13729675, "edges": 22174676, "completed_documents": 1212958, "completed_utf8_bytes": 4901239194, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T10:00:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 23043.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00196.jsonl.gz", "table_sha256": "be953952b0d3c26bb0692d6ed348f17a5b8452a0eac4153a5e0799e8c53597cc", "table_bytes": 114424012, "compression": "gzip", "uncompressed_table_bytes": 648912934, "documents": 13149, "utf8_bytes": 25000609, "contexts": 13617614, "edges": 22003101, "completed_documents": 1226107, "completed_utf8_bytes": 4926239803, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T10:02:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 23165.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00197.jsonl.gz", "table_sha256": "65ea9f974578bb6b4254def9760bebcb75c63f5a1439eb717654e66a105dd4f5", "table_bytes": 114451704, "compression": "gzip", "uncompressed_table_bytes": 649158023, "documents": 13065, "utf8_bytes": 25006573, "contexts": 13623451, "edges": 22009339, "completed_documents": 1239172, "completed_utf8_bytes": 4951246376, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T10:05:01+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 23287.2s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00198.jsonl.gz", "table_sha256": "bc878b8657dd789282730add95d7decdceb79feff2986b86baaafc9ad0d0f339", "table_bytes": 114704980, "compression": "gzip", "uncompressed_table_bytes": 650090195, "documents": 13043, "utf8_bytes": 25000971, "contexts": 13637518, "edges": 22046642, "completed_documents": 1252215, "completed_utf8_bytes": 4976247347, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T10:06:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block saved

- Server tmux: `blt-bg5gb-20261020`; elapsed: 23403.4s.
- Result: {"table_path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00199.jsonl.gz", "table_sha256": "19f458ffaff989056a538b874a24f0faa86e09e69e2782653f23d2bed250ee21", "table_bytes": 110299037, "compression": "gzip", "uncompressed_table_bytes": 626345581, "documents": 12397, "utf8_bytes": 23752661, "contexts": 13153863, "edges": 21216143, "completed_documents": 1264612, "completed_utf8_bytes": 5000000008, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T10:06:58+00:00 / en-patcher-bg5gb-20261020-01 / build completed

- Server tmux: `blt-bg5gb-20261020`; elapsed: 27560.1s.
- Result: {"status": "built", "documents": 1264612, "utf8_bytes": 5000000008, "table_bytes": 21642161844, "elapsed_seconds": 23404.162784256972, "peak_host_rss_bytes": 5477359616}

## 2026-10-20T10:06:58+00:00 / en-patcher-bg5gb-20261020-01 / fit started

- Server tmux: `blt-bg5gb-20261020`; elapsed: 27560.1s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit/report.json"}

## 2026-10-20T10:07:18+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 19.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00000.jsonl.gz", "loaded_contexts": 2572061}

## 2026-10-20T10:07:33+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 35.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00001.jsonl.gz", "loaded_contexts": 2880390}

## 2026-10-20T10:07:48+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 50.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00002.jsonl.gz", "loaded_contexts": 3033563}

## 2026-10-20T10:08:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 66.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00003.jsonl.gz", "loaded_contexts": 3138469}

## 2026-10-20T10:08:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 81.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00004.jsonl.gz", "loaded_contexts": 3206174}

## 2026-10-20T10:08:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 96.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00005.jsonl.gz", "loaded_contexts": 3258295}

## 2026-10-20T10:08:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 112.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00006.jsonl.gz", "loaded_contexts": 3299036}

## 2026-10-20T10:09:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 127.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00007.jsonl.gz", "loaded_contexts": 3333836}

## 2026-10-20T10:09:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 143.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00008.jsonl.gz", "loaded_contexts": 3365263}

## 2026-10-20T10:09:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 158.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00009.jsonl.gz", "loaded_contexts": 3390517}

## 2026-10-20T10:09:52+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 174.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00010.jsonl.gz", "loaded_contexts": 3412356}

## 2026-10-20T10:10:07+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 189.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00011.jsonl.gz", "loaded_contexts": 3432108}

## 2026-10-20T10:10:23+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 204.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00012.jsonl.gz", "loaded_contexts": 3448610}

## 2026-10-20T10:10:38+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 220.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00013.jsonl.gz", "loaded_contexts": 3465310}

## 2026-10-20T10:10:54+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 235.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00014.jsonl.gz", "loaded_contexts": 3479112}

## 2026-10-20T10:11:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 251.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00015.jsonl.gz", "loaded_contexts": 3492161}

## 2026-10-20T10:11:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 266.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00016.jsonl.gz", "loaded_contexts": 3504444}

## 2026-10-20T10:11:40+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 282.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00017.jsonl.gz", "loaded_contexts": 3515297}

## 2026-10-20T10:11:56+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 297.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00018.jsonl.gz", "loaded_contexts": 3525547}

## 2026-10-20T10:12:11+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 313.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00019.jsonl.gz", "loaded_contexts": 3535956}

## 2026-10-20T10:12:27+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 328.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00020.jsonl.gz", "loaded_contexts": 3544755}

## 2026-10-20T10:12:42+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 344.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00021.jsonl.gz", "loaded_contexts": 3553382}

## 2026-10-20T10:12:58+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 359.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00022.jsonl.gz", "loaded_contexts": 3561533}

## 2026-10-20T10:13:13+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 375.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00023.jsonl.gz", "loaded_contexts": 3569431}

## 2026-10-20T10:13:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 391.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00024.jsonl.gz", "loaded_contexts": 3576637}

## 2026-10-20T10:13:45+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 407.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00025.jsonl.gz", "loaded_contexts": 3583426}

## 2026-10-20T10:14:00+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 422.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00026.jsonl.gz", "loaded_contexts": 3589719}

## 2026-10-20T10:14:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 437.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00027.jsonl.gz", "loaded_contexts": 3595549}

## 2026-10-20T10:14:32+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 453.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00028.jsonl.gz", "loaded_contexts": 3601628}

## 2026-10-20T10:14:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 469.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00029.jsonl.gz", "loaded_contexts": 3606953}

## 2026-10-20T10:15:03+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 485.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00030.jsonl.gz", "loaded_contexts": 3612744}

## 2026-10-20T10:15:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 500.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00031.jsonl.gz", "loaded_contexts": 3617716}

## 2026-10-20T10:15:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 516.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00032.jsonl.gz", "loaded_contexts": 3622830}

## 2026-10-20T10:15:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 532.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00033.jsonl.gz", "loaded_contexts": 3627560}

## 2026-10-20T10:16:06+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 548.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00034.jsonl.gz", "loaded_contexts": 3632286}

## 2026-10-20T10:16:23+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 565.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00035.jsonl.gz", "loaded_contexts": 3637200}

## 2026-10-20T10:16:40+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 581.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00036.jsonl.gz", "loaded_contexts": 3642149}

## 2026-10-20T10:16:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 598.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00037.jsonl.gz", "loaded_contexts": 3646912}

## 2026-10-20T10:17:13+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 615.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00038.jsonl.gz", "loaded_contexts": 3651366}

## 2026-10-20T10:17:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 632.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00039.jsonl.gz", "loaded_contexts": 3655705}

## 2026-10-20T10:17:46+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 648.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00040.jsonl.gz", "loaded_contexts": 3659187}

## 2026-10-20T10:18:02+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 664.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00041.jsonl.gz", "loaded_contexts": 3662594}

## 2026-10-20T10:18:18+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 680.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00042.jsonl.gz", "loaded_contexts": 3665859}

## 2026-10-20T10:18:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 695.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00043.jsonl.gz", "loaded_contexts": 3669076}

## 2026-10-20T10:18:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 711.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00044.jsonl.gz", "loaded_contexts": 3672391}

## 2026-10-20T10:19:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 727.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00045.jsonl.gz", "loaded_contexts": 3675300}

## 2026-10-20T10:19:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 742.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00046.jsonl.gz", "loaded_contexts": 3678214}

## 2026-10-20T10:19:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 758.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00047.jsonl.gz", "loaded_contexts": 3680775}

## 2026-10-20T10:19:52+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 774.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00048.jsonl.gz", "loaded_contexts": 3683325}

## 2026-10-20T10:20:08+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 790.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00049.jsonl.gz", "loaded_contexts": 3686044}

## 2026-10-20T10:20:24+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 805.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00050.jsonl.gz", "loaded_contexts": 3688577}

## 2026-10-20T10:20:40+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 821.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00051.jsonl.gz", "loaded_contexts": 3691442}

## 2026-10-20T10:20:55+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 837.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00052.jsonl.gz", "loaded_contexts": 3693878}

## 2026-10-20T10:21:11+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 853.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00053.jsonl.gz", "loaded_contexts": 3696176}

## 2026-10-20T10:21:27+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 869.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00054.jsonl.gz", "loaded_contexts": 3698692}

## 2026-10-20T10:21:43+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 885.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00055.jsonl.gz", "loaded_contexts": 3700912}

## 2026-10-20T10:21:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 901.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00056.jsonl.gz", "loaded_contexts": 3703160}

## 2026-10-20T10:22:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 917.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00057.jsonl.gz", "loaded_contexts": 3705579}

## 2026-10-20T10:22:31+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 933.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00058.jsonl.gz", "loaded_contexts": 3707589}

## 2026-10-20T10:22:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 948.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00059.jsonl.gz", "loaded_contexts": 3709550}

## 2026-10-20T10:23:03+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 964.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00060.jsonl.gz", "loaded_contexts": 3711752}

## 2026-10-20T10:23:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 981.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00061.jsonl.gz", "loaded_contexts": 3713838}

## 2026-10-20T10:23:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 997.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00062.jsonl.gz", "loaded_contexts": 3715715}

## 2026-10-20T10:23:51+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1013.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00063.jsonl.gz", "loaded_contexts": 3717540}

## 2026-10-20T10:24:07+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1029.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00064.jsonl.gz", "loaded_contexts": 3719480}

## 2026-10-20T10:24:23+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1045.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00065.jsonl.gz", "loaded_contexts": 3721215}

## 2026-10-20T10:24:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1061.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00066.jsonl.gz", "loaded_contexts": 3723016}

## 2026-10-20T10:24:55+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1077.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00067.jsonl.gz", "loaded_contexts": 3724891}

## 2026-10-20T10:25:11+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1093.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00068.jsonl.gz", "loaded_contexts": 3726617}

## 2026-10-20T10:25:27+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1109.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00069.jsonl.gz", "loaded_contexts": 3728180}

## 2026-10-20T10:25:43+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1125.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00070.jsonl.gz", "loaded_contexts": 3729894}

## 2026-10-20T10:25:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1141.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00071.jsonl.gz", "loaded_contexts": 3731598}

## 2026-10-20T10:26:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1157.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00072.jsonl.gz", "loaded_contexts": 3733317}

## 2026-10-20T10:26:31+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1173.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00073.jsonl.gz", "loaded_contexts": 3734764}

## 2026-10-20T10:26:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1189.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00074.jsonl.gz", "loaded_contexts": 3736201}

## 2026-10-20T10:27:03+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1205.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00075.jsonl.gz", "loaded_contexts": 3737958}

## 2026-10-20T10:27:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1221.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00076.jsonl.gz", "loaded_contexts": 3739572}

## 2026-10-20T10:27:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1237.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00077.jsonl.gz", "loaded_contexts": 3741277}

## 2026-10-20T10:27:51+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1253.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00078.jsonl.gz", "loaded_contexts": 3742624}

## 2026-10-20T10:28:07+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1269.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00079.jsonl.gz", "loaded_contexts": 3744061}

## 2026-10-20T10:28:23+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1285.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00080.jsonl.gz", "loaded_contexts": 3745867}

## 2026-10-20T10:28:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1301.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00081.jsonl.gz", "loaded_contexts": 3747257}

## 2026-10-20T10:28:56+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1317.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00082.jsonl.gz", "loaded_contexts": 3748540}

## 2026-10-20T10:29:12+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1333.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00083.jsonl.gz", "loaded_contexts": 3749846}

## 2026-10-20T10:29:28+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1350.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00084.jsonl.gz", "loaded_contexts": 3751175}

## 2026-10-20T10:29:44+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1366.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00085.jsonl.gz", "loaded_contexts": 3752433}

## 2026-10-20T10:30:00+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1382.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00086.jsonl.gz", "loaded_contexts": 3753585}

## 2026-10-20T10:30:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1398.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00087.jsonl.gz", "loaded_contexts": 3754832}

## 2026-10-20T10:30:32+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1414.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00088.jsonl.gz", "loaded_contexts": 3756068}

## 2026-10-20T10:30:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1430.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00089.jsonl.gz", "loaded_contexts": 3757481}

## 2026-10-20T10:31:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1446.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00090.jsonl.gz", "loaded_contexts": 3758828}

## 2026-10-20T10:31:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1462.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00091.jsonl.gz", "loaded_contexts": 3760062}

## 2026-10-20T10:31:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1478.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00092.jsonl.gz", "loaded_contexts": 3761538}

## 2026-10-20T10:31:53+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1494.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00093.jsonl.gz", "loaded_contexts": 3762627}

## 2026-10-20T10:32:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1510.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00094.jsonl.gz", "loaded_contexts": 3763618}

## 2026-10-20T10:32:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1526.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00095.jsonl.gz", "loaded_contexts": 3764761}

## 2026-10-20T10:32:41+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1543.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00096.jsonl.gz", "loaded_contexts": 3765719}

## 2026-10-20T10:32:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1559.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00097.jsonl.gz", "loaded_contexts": 3766886}

## 2026-10-20T10:33:12+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1574.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00098.jsonl.gz", "loaded_contexts": 3767860}

## 2026-10-20T10:33:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1590.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00099.jsonl.gz", "loaded_contexts": 3769018}

## 2026-10-20T10:33:45+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1606.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00100.jsonl.gz", "loaded_contexts": 3770056}

## 2026-10-20T10:34:01+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1623.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00101.jsonl.gz", "loaded_contexts": 3771247}

## 2026-10-20T10:34:17+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1639.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00102.jsonl.gz", "loaded_contexts": 3772372}

## 2026-10-20T10:34:33+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1655.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00103.jsonl.gz", "loaded_contexts": 3773329}

## 2026-10-20T10:34:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1671.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00104.jsonl.gz", "loaded_contexts": 3774299}

## 2026-10-20T10:35:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1687.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00105.jsonl.gz", "loaded_contexts": 3775252}

## 2026-10-20T10:35:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1703.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00106.jsonl.gz", "loaded_contexts": 3776301}

## 2026-10-20T10:35:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1719.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00107.jsonl.gz", "loaded_contexts": 3777161}

## 2026-10-20T10:35:53+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1735.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00108.jsonl.gz", "loaded_contexts": 3778027}

## 2026-10-20T10:36:10+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1751.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00109.jsonl.gz", "loaded_contexts": 3779019}

## 2026-10-20T10:36:26+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1767.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00110.jsonl.gz", "loaded_contexts": 3779882}

## 2026-10-20T10:36:42+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1783.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00111.jsonl.gz", "loaded_contexts": 3780765}

## 2026-10-20T10:36:58+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1800.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00112.jsonl.gz", "loaded_contexts": 3781682}

## 2026-10-20T10:37:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1816.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00113.jsonl.gz", "loaded_contexts": 3782531}

## 2026-10-20T10:37:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1832.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00114.jsonl.gz", "loaded_contexts": 3783419}

## 2026-10-20T10:37:46+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1848.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00115.jsonl.gz", "loaded_contexts": 3784406}

## 2026-10-20T10:38:02+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1864.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00116.jsonl.gz", "loaded_contexts": 3785203}

## 2026-10-20T10:38:18+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1880.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00117.jsonl.gz", "loaded_contexts": 3786007}

## 2026-10-20T10:38:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1896.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00118.jsonl.gz", "loaded_contexts": 3786876}

## 2026-10-20T10:38:51+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1913.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00119.jsonl.gz", "loaded_contexts": 3787597}

## 2026-10-20T10:39:07+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1929.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00120.jsonl.gz", "loaded_contexts": 3788335}

## 2026-10-20T10:39:23+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1945.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00121.jsonl.gz", "loaded_contexts": 3789124}

## 2026-10-20T10:39:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1961.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00122.jsonl.gz", "loaded_contexts": 3789982}

## 2026-10-20T10:39:56+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1977.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00123.jsonl.gz", "loaded_contexts": 3790707}

## 2026-10-20T10:40:12+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 1994.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00124.jsonl.gz", "loaded_contexts": 3791460}

## 2026-10-20T10:40:28+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2010.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00125.jsonl.gz", "loaded_contexts": 3792330}

## 2026-10-20T10:40:44+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2026.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00126.jsonl.gz", "loaded_contexts": 3793033}

## 2026-10-20T10:41:00+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2042.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00127.jsonl.gz", "loaded_contexts": 3793759}

## 2026-10-20T10:41:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2058.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00128.jsonl.gz", "loaded_contexts": 3794657}

## 2026-10-20T10:41:33+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2074.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00129.jsonl.gz", "loaded_contexts": 3795434}

## 2026-10-20T10:41:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2091.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00130.jsonl.gz", "loaded_contexts": 3796215}

## 2026-10-20T10:42:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2107.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00131.jsonl.gz", "loaded_contexts": 3796930}

## 2026-10-20T10:42:22+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2123.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00132.jsonl.gz", "loaded_contexts": 3797663}

## 2026-10-20T10:42:38+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2140.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00133.jsonl.gz", "loaded_contexts": 3798438}

## 2026-10-20T10:42:54+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2156.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00134.jsonl.gz", "loaded_contexts": 3799064}

## 2026-10-20T10:43:10+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2172.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00135.jsonl.gz", "loaded_contexts": 3799640}

## 2026-10-20T10:43:26+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2188.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00136.jsonl.gz", "loaded_contexts": 3800297}

## 2026-10-20T10:43:43+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2204.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00137.jsonl.gz", "loaded_contexts": 3800967}

## 2026-10-20T10:43:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2221.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00138.jsonl.gz", "loaded_contexts": 3801614}

## 2026-10-20T10:44:15+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2237.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00139.jsonl.gz", "loaded_contexts": 3802238}

## 2026-10-20T10:44:31+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2253.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00140.jsonl.gz", "loaded_contexts": 3802849}

## 2026-10-20T10:44:48+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2270.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00141.jsonl.gz", "loaded_contexts": 3803487}

## 2026-10-20T10:45:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2286.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00142.jsonl.gz", "loaded_contexts": 3804129}

## 2026-10-20T10:45:20+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2302.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00143.jsonl.gz", "loaded_contexts": 3804721}

## 2026-10-20T10:45:36+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2318.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00144.jsonl.gz", "loaded_contexts": 3805312}

## 2026-10-20T10:45:53+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2335.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00145.jsonl.gz", "loaded_contexts": 3806168}

## 2026-10-20T10:46:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2351.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00146.jsonl.gz", "loaded_contexts": 3806706}

## 2026-10-20T10:46:25+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2367.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00147.jsonl.gz", "loaded_contexts": 3807349}

## 2026-10-20T10:46:41+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2383.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00148.jsonl.gz", "loaded_contexts": 3808056}

## 2026-10-20T10:46:58+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2399.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00149.jsonl.gz", "loaded_contexts": 3808742}

## 2026-10-20T10:47:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2416.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00150.jsonl.gz", "loaded_contexts": 3809274}

## 2026-10-20T10:47:30+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2432.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00151.jsonl.gz", "loaded_contexts": 3809799}

## 2026-10-20T10:47:46+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2448.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00152.jsonl.gz", "loaded_contexts": 3810344}

## 2026-10-20T10:48:02+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2464.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00153.jsonl.gz", "loaded_contexts": 3810911}

## 2026-10-20T10:48:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2480.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00154.jsonl.gz", "loaded_contexts": 3811559}

## 2026-10-20T10:48:35+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2497.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00155.jsonl.gz", "loaded_contexts": 3812172}

## 2026-10-20T10:48:52+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2514.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00156.jsonl.gz", "loaded_contexts": 3812829}

## 2026-10-20T10:49:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2531.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00157.jsonl.gz", "loaded_contexts": 3813570}

## 2026-10-20T10:49:27+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2549.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00158.jsonl.gz", "loaded_contexts": 3814225}

## 2026-10-20T10:49:44+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2566.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00159.jsonl.gz", "loaded_contexts": 3814855}

## 2026-10-20T10:50:02+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2583.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00160.jsonl.gz", "loaded_contexts": 3815552}

## 2026-10-20T10:50:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2601.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00161.jsonl.gz", "loaded_contexts": 3816104}

## 2026-10-20T10:50:36+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2618.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00162.jsonl.gz", "loaded_contexts": 3816769}

## 2026-10-20T10:50:54+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2636.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00163.jsonl.gz", "loaded_contexts": 3817472}

## 2026-10-20T10:51:11+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2653.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00164.jsonl.gz", "loaded_contexts": 3818123}

## 2026-10-20T10:51:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2671.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00165.jsonl.gz", "loaded_contexts": 3818751}

## 2026-10-20T10:51:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2688.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00166.jsonl.gz", "loaded_contexts": 3819400}

## 2026-10-20T10:52:04+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2706.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00167.jsonl.gz", "loaded_contexts": 3820007}

## 2026-10-20T10:52:21+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2723.5s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00168.jsonl.gz", "loaded_contexts": 3820659}

## 2026-10-20T10:52:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2741.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00169.jsonl.gz", "loaded_contexts": 3821363}

## 2026-10-20T10:52:56+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2758.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00170.jsonl.gz", "loaded_contexts": 3821922}

## 2026-10-20T10:53:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2775.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00171.jsonl.gz", "loaded_contexts": 3822495}

## 2026-10-20T10:53:31+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2793.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00172.jsonl.gz", "loaded_contexts": 3823204}

## 2026-10-20T10:53:49+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2810.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00173.jsonl.gz", "loaded_contexts": 3823807}

## 2026-10-20T10:54:06+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2828.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00174.jsonl.gz", "loaded_contexts": 3824340}

## 2026-10-20T10:54:24+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2845.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00175.jsonl.gz", "loaded_contexts": 3824945}

## 2026-10-20T10:54:41+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2863.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00176.jsonl.gz", "loaded_contexts": 3825551}

## 2026-10-20T10:54:59+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2880.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00177.jsonl.gz", "loaded_contexts": 3826039}

## 2026-10-20T10:55:16+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2898.2s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00178.jsonl.gz", "loaded_contexts": 3826529}

## 2026-10-20T10:55:34+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2915.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00179.jsonl.gz", "loaded_contexts": 3827062}

## 2026-10-20T10:55:51+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2933.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00180.jsonl.gz", "loaded_contexts": 3827675}

## 2026-10-20T10:56:09+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2950.9s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00181.jsonl.gz", "loaded_contexts": 3828172}

## 2026-10-20T10:56:26+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2968.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00182.jsonl.gz", "loaded_contexts": 3828685}

## 2026-10-20T10:56:44+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 2986.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00183.jsonl.gz", "loaded_contexts": 3829204}

## 2026-10-20T10:57:01+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3003.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00184.jsonl.gz", "loaded_contexts": 3829743}

## 2026-10-20T10:57:19+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3021.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00185.jsonl.gz", "loaded_contexts": 3830681}

## 2026-10-20T10:57:37+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3038.8s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00186.jsonl.gz", "loaded_contexts": 3831225}

## 2026-10-20T10:57:54+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3056.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00187.jsonl.gz", "loaded_contexts": 3831702}

## 2026-10-20T10:58:12+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3074.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00188.jsonl.gz", "loaded_contexts": 3832248}

## 2026-10-20T10:58:29+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3091.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00189.jsonl.gz", "loaded_contexts": 3832699}

## 2026-10-20T10:58:47+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3109.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00190.jsonl.gz", "loaded_contexts": 3833193}

## 2026-10-20T10:59:05+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3126.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00191.jsonl.gz", "loaded_contexts": 3833683}

## 2026-10-20T10:59:22+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3144.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00192.jsonl.gz", "loaded_contexts": 3834336}

## 2026-10-20T10:59:39+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3161.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00193.jsonl.gz", "loaded_contexts": 3834771}

## 2026-10-20T10:59:57+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3179.0s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00194.jsonl.gz", "loaded_contexts": 3835251}

## 2026-10-20T11:00:14+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3196.6s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00195.jsonl.gz", "loaded_contexts": 3835820}

## 2026-10-20T11:00:32+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3214.1s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00196.jsonl.gz", "loaded_contexts": 3836245}

## 2026-10-20T11:00:50+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3231.7s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00197.jsonl.gz", "loaded_contexts": 3836727}

## 2026-10-20T11:01:07+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3249.3s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00198.jsonl.gz", "loaded_contexts": 3837156}

## 2026-10-20T11:01:24+00:00 / en-patcher-bg5gb-20261020-01 / Background block merged

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3266.4s.
- Result: {"path": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/background_blocks/block-00199.jsonl.gz", "loaded_contexts": 3837591}

## 2026-10-20T11:01:24+00:00 / en-patcher-bg5gb-20261020-01 / Background loaded and verified

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3266.5s.
- Result: {"seconds": 3266.5224044560455, "sha256": "94121d3f12f6b1c7ab020f79569610f472b4d9b16a3feb3a2d24377443bd9acb"}

## 2026-10-20T11:07:24+00:00 / en-patcher-bg5gb-20261020-01 / Fixed training features completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3625.9s.
- Result: {"positions": 4041644, "seconds": 359.3270245459862, "next": "Constrained fit"}

## 2026-10-20T11:07:25+00:00 / en-patcher-bg5gb-20261020-01 / Boundary fit completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3626.9s.
- Result: {"fit": {"coefficients": [-4.411281216613937, 0.0, 0.0, 2.471429783870789, 0.21239043616993136], "rho": 0.001, "loss": 0.2515189460428993, "iterations": 14, "evaluations": 15, "message": "CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL", "feature_scale": [1.0, 6.216751139212366, 169.74619372441887, 1.4796525363246986, 3.868221269945194], "gradient": [1.0395571903298872e-10, 0.062066542873536294, 0.7725169721998264, 1.8401771599563244e-10, -8.454054812429522e-10], "scaled_projected_gradient_max": 2.1855147941289567e-10}, "next": "Fresh sequential threshold trials"}

## 2026-10-20T11:08:08+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3670.2s.
- Result: {"tp": 104640, "fp": 359130, "fn": 0, "precision": 0.22562908338184876, "recall": 1.0, "f1": 0.3681849369293292, "threshold": 0.0, "elapsed_seconds": 43.0135717461817}

## 2026-10-20T11:08:51+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3713.5s.
- Result: {"tp": 99276, "fp": 81092, "fn": 5364, "precision": 0.5504080546438392, "recall": 0.9487385321100917, "f1": 0.696654129006905, "threshold": 0.125, "elapsed_seconds": 43.24851915705949}

## 2026-10-20T11:09:35+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3756.8s.
- Result: {"tp": 91834, "fp": 42427, "fn": 12806, "precision": 0.6839960971540507, "recall": 0.877618501529052, "f1": 0.7688038141322138, "threshold": 0.25, "elapsed_seconds": 43.359783818013966}

## 2026-10-20T11:10:18+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3800.0s.
- Result: {"tp": 83684, "fp": 26156, "fn": 20956, "precision": 0.7618718135469774, "recall": 0.7997324159021407, "f1": 0.780343155538978, "threshold": 0.375, "elapsed_seconds": 43.19102455396205}

## 2026-10-20T11:11:01+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3843.2s.
- Result: {"tp": 75778, "fp": 17557, "fn": 28862, "precision": 0.8118926447742004, "recall": 0.7241781345565749, "f1": 0.7655310013890643, "threshold": 0.5, "elapsed_seconds": 43.1789612416178}

## 2026-10-20T11:11:44+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3886.4s.
- Result: {"tp": 67368, "fp": 11658, "fn": 37272, "precision": 0.8524789309847391, "recall": 0.6438073394495413, "f1": 0.7335924994283101, "threshold": 0.625, "elapsed_seconds": 43.17510961694643}

## 2026-10-20T11:12:27+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3929.6s.
- Result: {"tp": 55086, "fp": 6580, "fn": 49554, "precision": 0.8932961437420945, "recall": 0.5264334862385321, "f1": 0.6624655755053936, "threshold": 0.75, "elapsed_seconds": 43.207381727639586}

## 2026-10-20T11:13:11+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 3972.9s.
- Result: {"tp": 31317, "fp": 2488, "fn": 73323, "precision": 0.9264014199082976, "recall": 0.2992832568807339, "f1": 0.4524107046119398, "threshold": 0.875, "elapsed_seconds": 43.29022005805746}

## 2026-10-20T11:13:54+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4016.2s.
- Result: {"tp": 0, "fp": 0, "fn": 104640, "precision": 0.0, "recall": 0.0, "f1": 0.0, "threshold": 1.0, "elapsed_seconds": 43.312651849817485}

## 2026-10-20T11:14:37+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4059.3s.
- Result: {"tp": 89712, "fp": 37092, "fn": 14928, "precision": 0.7074855682786032, "recall": 0.8573394495412844, "f1": 0.7752372064084616, "threshold": 0.28125, "elapsed_seconds": 43.16111028101295}

## 2026-10-20T11:15:21+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4102.9s.
- Result: {"tp": 87672, "fp": 32798, "fn": 16968, "precision": 0.7277496472150743, "recall": 0.8378440366972477, "f1": 0.7789258584691928, "threshold": 0.3125, "elapsed_seconds": 43.50733690522611}

## 2026-10-20T11:16:04+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4146.3s.
- Result: {"tp": 85673, "fp": 29243, "fn": 18967, "precision": 0.7455271676702983, "recall": 0.8187404434250765, "f1": 0.7804204849787754, "threshold": 0.34375, "elapsed_seconds": 43.41028334479779}

## 2026-10-20T11:16:47+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4189.6s.
- Result: {"tp": 81728, "fp": 23607, "fn": 22912, "precision": 0.7758864574927612, "recall": 0.7810397553516819, "f1": 0.7784545779259435, "threshold": 0.40625, "elapsed_seconds": 43.31617204705253}

## 2026-10-20T11:17:31+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4233.2s.
- Result: {"tp": 79722, "fp": 21351, "fn": 24918, "precision": 0.7887566412395002, "recall": 0.7618692660550459, "f1": 0.7750798442490265, "threshold": 0.4375, "elapsed_seconds": 43.61457701260224}

## 2026-10-20T11:18:15+00:00 / en-patcher-bg5gb-20261020-01 / Threshold validation completed

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4276.7s.
- Result: {"tp": 77706, "fp": 19335, "fn": 26934, "precision": 0.8007543203388259, "recall": 0.7426032110091743, "f1": 0.7705832478022223, "threshold": 0.46875, "elapsed_seconds": 43.528370067011565}

## 2026-10-20T11:19:40+00:00 / en-patcher-bg5gb-20261020-01 / Fit and validation finished

- Output: `/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/fit`; elapsed: 4362.2s.
- Result: {"status": "validation_gate_failed", "f1": 0.7804204849787754, "error": null, "next": "Paired baseline comparison if successful"}

## 2026-10-20T11:19:41+00:00 / en-patcher-bg5gb-20261020-01 / fit completed

- Server tmux: `blt-bg5gb-20261020`; elapsed: 31923.6s.
- Result: {"status": "validation_gate_failed", "elapsed_seconds": 4362.248221369926, "peak_host_rss_bytes": 3783307264}

## 2026-10-20T11:19:41+00:00 / en-patcher-bg5gb-20261020-01 / compare started

- Server tmux: `blt-bg5gb-20261020`; elapsed: 31923.6s.
- Result: {"artifact": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/comparison.json"}

## 2026-10-20T11:28:17+00:00 / en-patcher-bg5gb-20261020-01 / compare completed

- Server tmux: `blt-bg5gb-20261020`; elapsed: 32439.5s.
- Result: {"status": "compared", "f1_difference": 0.0163347506465662, "documents": 111, "quality_gate_passed": false}

## 2026-10-20T11:28:17+00:00 / en-patcher-bg5gb-20261020-01 / Finished

- Server tmux: `blt-bg5gb-20261020`; elapsed: 32439.5s.
- Result: {"status": "completed", "report": "/home/itcmaster/projects/blt-cache/runs/en-patcher-bg5gb-20261020-01/run_report.json", "next": "Review measured comparison or failure"}

## 2026-10-20 / 배경 5GB 확대 / 회수 및 검증 완료

- 원격 단계 기록 433개를 공통 접두부 검사 후 사후 회수 구간에 병합했다. 기존 로컬 로그가 바이트 단위로 보존됐고 원격의 누락 부분 전체가 그대로 추가됐음을 검사했다. 문서 변경의 공백 검사도 통과했다.
- 최종 검증 F1 0.7804204850, 정밀도 0.7455271677, 재현율 0.8187404434, 임계값 0.34375. 1GB 대비 차이는 +0.0163347506이며 paired 문서 구간은 [0.0145115188,0.0179297787]이다. 최종 계수에서 beta1=beta2=0이다. 배경 확대에 따른 검증 개선은 있으나 게이트 0.90 미달이며 독립 평가·BLT BPB·속도 개선의 근거는 아니다.
- 결과 보고서 6개와 task.md 및 이 로그를 로컬에 보존했다. 추가 실험·환경 변경·Git 커밋/푸시는 하지 않았다. 다음 단계는 이 결과를 검토해 후속 실험 여부를 결정하는 것이다.

## 2026-10-23 / 5GB 적합 결과 재검토

- 단계: 결과 검토. `evidence/english_bg5gb_fit_20261020.json`, `evidence/english_bg5gb_comparison_20261020.json`, 5GB 설정과 구현의 특성 정의를 대조했다.
- 측정 결과: 학습은 4,041,644개 위치로 수행됐고 L-BFGS-B는 14회 반복·15회 평가 후 projected-gradient 기준으로 수렴했다. 최적화 자체는 1.10초였지만 배경 카운트 로딩은 3,266.5초, 특징 생성은 359.3초였으며 적합 단계 총 4,362.2초, 최대 RSS 3.78GB였다. 수렴 실패가 아니라 검증 품질 게이트 실패다.
- 적합 규칙 계수는 `[-4.4113, 0, 0, 2.4714, 0.2124]`, 임계값은 0.34375다. 구현의 특성 순서가 `[상수, 경계까지 거리, 평균 패치 길이 초과분 제곱, 엔트로피, 음의 반복 길이]`이므로 거리·길이 초과 계수 두 개는 0으로 추정됐다. 이는 이 설정에서 해당 항의 추가 기여가 선택되지 않았다는 뜻이며, 다른 데이터·설정에서도 불필요함을 증명하지 않는다.
- 동일한 111개 검증 문서에서 1GB 대비 F1은 0.764086→0.780420(+0.016335), 정밀도 0.725857→0.745527, 재현율 0.806565→0.818740, 엔트로피 MAE 0.487475→0.459353, log loss 0.252902→0.240324로 개선됐다. F1 차이의 paired 문서 bootstrap 95% 구간은 [0.014512, 0.017930]이고 임계값은 양쪽 모두 0.34375다.
- 판정·한계: F1 0.90 통과 기준에 못 미친다. 같은 검증 집합을 임계값 선택과 비교에 재사용했고 bootstrap 구간도 그 문서 집합의 기술적 paired 구간이므로 독립 평가 성능으로 해석하지 않는다. 따라서 T09~T11, 최종 평가, BLT BPB·속도 비교로 진행할 근거는 없다. 결과는 배경 확대에 따른 해당 검증 지표의 개선을 보였을 뿐, 실제 BLT 품질이나 추론 속도 개선을 측정하지 않았다.
- 다음 조치: 같은 검증 집합에 대한 추가 튜닝은 하지 않는다. 후속 실험은 새로 고정한 학습·검증 절차와 별도 미사용 평가 자료 및 승인된 예산이 있을 때만 설계한다. 그 전까지 기존 5GB 산출물은 보존하고 추가 실행은 보류한다.

## 2026-10-23 / F0.5·F1 지표 불일치 기록

- 단계: 지표 설명 정정. 사용자가 앞선 논의에서는 F0.5를 사용했다고 지적해 현재 계획·실행 설정·적합 코드를 대조했다.
- 확인 결과: 보존된 5GB 실행은 `primary_metric=sequential_micro_boundary_f1`, `minimum_validation_f1=0.9`로 설정되어 있고, `fit_count_patcher.py`가 threshold 후보를 F1 최대화로 선택하고 F1로 gate를 판정한다. F0.5 계산 흔적은 현재 조사한 task/config/script/log에 없으며, 5GB의 0.780420은 F1이지 F0.5가 아니다.
- 정정: 앞선 대화에서 F0.5라고 안내했다면 이번 F1 요약과 일치하지 않는 설명이며 내 실수다. 기존 F1 결과를 F0.5의 점수나 F0.5 gate 실패로 해석해서는 안 된다. F0.5는 정밀도에 더 큰 가중치를 주므로 threshold와 점수도 달라질 수 있다.
- 추가 모호성: `task.md` T00에는 이번 파일럿의 BPB 주지표라는 문구도 있으나 실행 설정의 주지표는 F1이다. 목표 지표가 F0.5인지, F1인지, 또는 BPB인지 맞추기 전에는 새 적합·통과 판정을 진행하지 않는다. 기존 실행 산출물은 변경하지 않고, F0.5 기준 재평가는 별도 명시 후 수행한다.

## 2026-10-23 / 기존 1GB·5GB 결과의 F0.5 재산출

- 단계: 지표 혼선에 대한 정정 분석. 사용자가 이전 비교의 일관성을 지적해 기존 1GB·5GB 적합 보고서에 저장된 15개 공통 threshold trial의 TP/FP/FN으로 `F0.5 = 1.25 TP / (1.25 TP + FP + 0.25 FN)`을 계산했다. 실행이나 모델 재적합은 하지 않았다.
- 관측 결과: 두 배경 크기 모두 시험한 임계값 중 0.625에서 F0.5 최대였다. 1GB는 precision 0.833370, recall 0.618664, F0.5 0.779280; 5GB는 precision 0.852479, recall 0.643807, F0.5 0.800582다. 동일 후보 비교 차이는 +0.021301이다.
- 해석 제한: 이는 기존 실행의 원본 결과가 아니라 보존된 집계 threshold trial에서 재구성한 F0.5 비교다. trial 후보는 F1 기준 threshold 탐색에서 만들어진 15개라 더 촘촘한 F0.5 최적화가 아니며, threshold 선택에 같은 검증 집합을 썼다. 보존된 문서별 카운트는 원래 선택된 F1 임계값 0.34375에 대한 것이므로 F0.5 후보 0.625의 paired bootstrap 구간은 산출하지 않았다. 이 결과를 F1 0.90 gate와 혼용하지 않는다.
- 정정·다음 조치: 앞선 안내에서 F0.5와 F1을 혼용한 것은 내 오류다. 이후 비교는 사전에 확정한 동일 지표로 진행해야 하며, 현재 F0.5 값은 탐색 결과가 아닌 기존 저장치로 계산한 제한적 비교로 표시한다. task.md에 보완을 기록했다.

## 2026-10-23 / 대화 연속성 및 F0.5 비교 상태 재정정

- 사용자 확인: 기존 논의의 비교 지표는 F0.5였다. 현 대화에는 이전 transcript가 전달되지 않았고 이 환경에서 조회 가능한 세션 기록에서도 해당 대화를 찾지 못했다. 저장소 원본 설정·코드는 F1 threshold 선택을 하고 있어, 이를 이전 합의와 대조하지 않고 실행 기준으로 간주한 것은 내 잘못이다.
- 상태 정정: 방금 산출한 1GB/5GB F0.5 0.779280/0.800582(+0.021301)는 F1 중심으로 만든 15개 저장 임계값 중 최대를 재계산한 예비 비교다. 이를 정식 F0.5 재적합, 충분한 임계값 탐색, 또는 paired 통계 검정 결과라고 제시할 수 없다. F0.5 기준의 정식 비교는 아직 미완료다.
- 다음 조치: 기존 F1 결과를 F0.5 결론으로 사용하지 않는다. 원본 5GB 임계값 sweep이 F0.5 합의에 맞았는지 확인하려면 보존된 산출물의 한계를 명시하고, F0.5 기준으로 생성된 검증 예측/임계값 자료를 확보하거나 필요한 재평가 절차를 다시 실행해야 한다. 이전 환경·데이터·작업은 변경하지 않는다.

## 2026-10-23 / Copilot 대화 보존 경로 진단

- 단계: same-machine VS Code Copilot Chat 저장소를 read-only로 조사했다. `Code/User/workspaceStorage/*/workspace.json`에서 동일 `blt-cache` 폴더를 가리키는 여러 storage ID를 확인했다.
- 확인 결과: 기존 Copilot Chat은 `workspaceStorage/7d23e3b361e160c59a353d1a365874cf`의 `chat.ChatSessionStore.index`에 존재한다. 제목은 `문서 내용 재검토 요청`, session ID `a7bee659-1eba-4864-bb69-5360076532c1`, 마지막 기록은 2026-10-20 20:28(+09:00)이다. `chatSessions/<session-id>.jsonl`(13.4 MB)과 `GitHub.copilot-chat/transcripts/<session-id>.jsonl`(1.76 MB)도 확인했다. 기존 대화는 디스크에서 삭제되지 않았다.
- 현재 대화는 다른 storage ID `c775cfe55799151d94bf71ab42ffe386`의 인덱스에 있으며 `agent-host-copilotcli:/5cac3d24-5b96-4be1-8d27-6ff102ffab6d`로 기록된다. 현재 도구의 `list_sessions`는 agent-host 세션만 반환했고, 이전 `GitHub.copilot-chat` 세션을 조회하지 못했다. 앞서 “이전 기록을 찾을 수 없다/남지 않았다”고 단정한 설명은 틀렸다.
- 판정 한계: 같은 폴더 URI가 서로 다른 workspaceStorage ID에 놓인 사실은 확인했지만, VS Code가 왜 별도 storage ID를 만들었는지 또는 UI history 목록에서 숨긴 직접 원인은 아직 확인되지 않았다. 데이터베이스와 원본 transcript는 수정하지 않았다.
- 조치: VS Code 공식 세션 기록 문서는 `/chronicle:reindex` 또는 Command Palette의 `Reindex Sessions`로 로컬 인덱스를 재구성하고 `/chronicle:search <query>`로 검색하도록 안내한다. 이 저장 세션을 찾는 쿼리는 `문서 내용 재검토 요청` 또는 `5GB 적합 결과 확인해봐`다. 같은 기기에서는 cloud sync가 복구 전제조건이 아니다. 재색인 후에도 UI에 안 나오면 원본 JSONL 및 `state.vscdb`를 백업한 뒤 별도 복구 절차를 확인한다.
- 시도 결과: 사용자가 `/chronicle:reindex`를 이 대화에 보냈지만 현재 agent-host는 이를 slash command로 dispatch하지 않고 일반 메시지로 전달했다. `code` CLI도 PATH에 없어 여기서는 VS Code command를 실행하지 못했다. 따라서 reindex는 아직 실행되지 않았다. 사용자가 VS Code Command Palette에서 `Reindex Sessions`를 직접 실행해야 한다.

## 2026-10-23 / Copilot 세션 가져오기 파일 생성

- 단계: 저장된 원본 세션의 안전한 가져오기 경로 확인 및 변환. 설치된 VS Code 1.143.0 번들에서 `workbench.action.chat.import` 명령을 확인했다. 이 명령은 JSON export를 읽어 가져온 세션으로 연다.
- 수행: 로컬 원본 `chatSessions/a7bee659-1eba-4864-bb69-5360076532c1.jsonl`의 초기 스냅샷과 incremental patches를 순서대로 적용하고, VS Code export 형식(`responderUsername`, `initialLocation`, `requests`)으로 변환했다. 결과는 세션 폴더 바깥의 session-state `files/recovered-chat-doc-review.json`에 저장했다.
- 검증: 결과 JSON을 다시 읽어 검증했고 43개 요청, 약 22.0 MB임을 확인했다. 저장소의 원본 JSONL, `state.vscdb`, 데이터나 산출물은 수정하지 않았다. VS Code UI에서 가져오기는 아직 실행하지 않았다.
- 사용 방법: VS Code Command Palette의 `Chat: Import Chat...`에서 생성한 JSON을 선택한다. 이것은 새 imported copy를 여는 방법이며 원래 세션 ID를 복원하거나 기존 세션 인덱스를 변경하는 동작은 아니다.

## 2026-10-23 / 5GB 터미널 완료 출력 재확인

- 단계: 사용자가 전달한 완료 터미널 출력과 로컬 회수 보고서를 대조했다. 출력의 앞부분은 과거 1GB 작업 로그이며, 마지막 비교 결과는 완료된 5GB run `en-patcher-bg5gb-20261020-01`이다.
- 5GB 저장 보고서와 일치하는 F1 결과는 0.78042048498, 1GB 대비 +0.01633475065, 111문서 paired 차이 95% 구간 [0.01451151879, 0.01792977872]다. 이는 F1 기준으로 최적화·판정한 원래 실행 결과이며, 기준 지표가 F0.5라면 직접적인 채택 결론으로 사용하지 않는다.
- 1GB와 5GB의 보존된 15개 threshold trial TP/FP/FN을 다시 계산했다. 두 보고서 모두 시험 후보 중 threshold 0.625에서 F0.5 최대: 1GB 0.77928034206, 5GB 0.80058182648, 차이 +0.02130148442. `git status`에서 보고서 6개는 아직 untracked이고 log.md/task.md는 수정 상태임을 확인했다. 이 F0.5 값은 제한된 기존 sweep의 사후 집계이며 F0.5 전체 탐색이나 threshold 0.625 문서별 paired CI가 아니다. 새 적합 실행은 하지 않았다.

## 2026-10-23 / 배경 10GB 확대 / 요청 및 실행 계획

- 직전 F1 비교에 이어 사용자가 10GB 확대를 요청했다. 이번 실행은 F1 기준의 5GB→10GB 비교로 명시하며 기존 F0.5 정식 재평가를 완료한 것으로 취급하지 않는다. 기존 학습·검증 라벨과 K=8/W=무제한, 모수 적합·F1 임계값 탐색을 유지한다.
- 계획 experiments/english_background_10gb.json, 실행 en-patcher-bg10gb-20261023-01, tmux blt-bg10gb-20261023. 부모 5GB 전체를 보존하고 10,000,000,000 UTF-8 바이트를 목표로 같은 4개 고정 shard/근사 중복 제거/25MB gzip 블록을 사용한다. 원문·카운트·가중치는 Git에 넣지 않는다.
- 서버 가용 RAM 약 58GiB, 디스크 여유 264GiB, 기존 tmux 세션 없음 확인. RAM 48GiB, 기존 저장량·여유 디스크 보호와 시간 제한 없음 조건을 유지한다. 5GB 준비 최대 RSS 30.60GiB보다 부모/후보가 커져 이번 표집·중복 제거가 한도를 초과할 위험이 있다. 실제 가능 여부는 미측정이며 한도를 임의 상향하지 않고 실패 시 기록·중단한다.
- 다음 단계: 설정 및 부모 산출물 확인, 원격 테스트 후 분리된 tmux 실행. 기존 실행·데이터를 삭제하거나 덮어쓰지 않는다.

## 2026-10-23 / 배경 10GB 확대 / 실행 전 검사 완료

- 새 계획의 목표·부모/비교 경로·기존 공통 설정 검증 통과. 서버 5GB 실행 완료 상태와 단계별 보고서 해시 5개, 실행 코드 3개가 기존 보고서와 일치했다. 부모 카운트 200블록이 보고된 파일 크기로 존재하며 새 실행 경로는 사용되지 않았다. 블록 본체 해시는 이후 기존 로더의 부모 재현 검사에서 확인한다.
- 원격 전체 테스트 22개 통과(3.118초), pip check 통과. 실행 코드는 변경하지 않고 새 계획만 전송했다. 다음 단계는 blt-bg10gb-20261023 세션에서 부모 재현→표집→구축→적합→F1 비교 순서로 실행하는 것이다.
- 원격 source/log.md는 로컬의 게시·조회 기록과 분기되어 있으므로 덮어쓰지 않는다. 서버는 기존 기록 뒤에 실행 단계를 즉시 기록하며 이후 공통 접두부를 확인해 병합한다.

## 2026-10-23 / 배경 10GB 확대 / tmux 실행 시작 확인

- 서버 2026-10-23T03:07:07+00:00에 Started 및 verify started가 기록됐다. tmux blt-bg10gb-20261023, 실행기 PID 713746, 부모 재현 검사 PID 713764가 동작 중임을 확인했다. 목표 10,000,000,000바이트, RAM 48GiB, wall_clock_limit null이 시작 로그에 기록됐다.
- 로컬 문서 변경 공백 검사 통과. 새 실행 계획 외에 원격 코드·환경·기존 산출물은 변경하지 않았다. SSH가 종료돼도 tmux 작업은 계속된다. 현재는 사전 검사 단계이며 10GB 수집 완료·적합 점수는 아직 없다.
- 다음 단계: 부모 재현 검사 통과 후 표집·중복 제거·블록 구축·적합·5GB 대비 F1 비교. 단계별 결과/실패는 원격 source/log.md 및 실행 progress.md에 즉시 누적된다. Git 커밋·푸시는 하지 않았다.

## 2026-10-23 / 현재 Copilot 대화 목록 누락 진단

- 사용자 요청으로 현재 세션 검색 인덱스와 두 workspaceStorage의 state.vscdb를 읽기 전용 조사했다. 현재 세션 ee1513d3-192d-4f91-a443-9cc822561ea4는 검색 인덱스에 제목 '10gb로 늘려서 해보자', agent_name panel/editAgent로 존재하며 6개 turn이 확인됐다. 검색 인덱스의 존재만으로 전체 대화 원본 복구 가능성을 보증하지 않는다.
- c775cfe55799151d94bf71ab42ffe386의 ChatSessionStore 목록에는 다른 agent-host-copilotcli 세션들만 있고 현재 세션 ID는 없다. 이 저장소에 chatSessions 디렉터리는 없으며 현재 ID의 debug-logs 디렉터리는 있다. 이전 7d23e3b361e160c59a353d1a365874cf에는 a7bee659-1eba-4864-bb69-5360076532c1 원본 JSONL과 '문서 내용 재검토 요청' 목록 항목이 남아 있다.
- 관측은 검색 기록과 UI 목록 인덱스의 불일치를 뒷받침하나, 목록 누락의 직접 원인(저장/등록/복원/필터)은 확정하지 못했다. 기존 대화와 현재 대화의 ID가 다르므로 과거 복구 파일이 현재 대화 전체를 담는다고 가정하지 않는다.
- 복구 권고: 현재 열린 창에서 Chat: Export Chat...으로 JSON을 먼저 보존한 다음 같은 폴더/프로필에서 목록 필터(Archived/Done, 적용 가능한 External)를 확인하고 창을 Reload한다. 필요시 내보낸 JSON을 Chat: Import Chat...으로 가져와 사본을 연다. 이는 원래 세션 ID의 인덱스 복구와는 다르다. Reindex Sessions는 검색 인덱스 재구성이며 UI 목록 복원을 보장하지 않는다. 원본 DB/세션 기록이나 설정은 수정하지 않았고 실제 export/import/reload는 실행하지 않았다.

## 2026-10-23 / 가져온 대화 닫기 후 목록 누락 / 설치 코드 확인 및 안내 정정

- 사용자는 가져온 대화가 열린 동안만 목록에 보이고 닫으면 사라지며 핀·제목 변경도 효과가 없다고 보고했다. 설치 버전 1.143.1의 workbench.desktop.main.js를 읽기 전용으로 확인했다.
- 직접 확인한 조건: shouldStoreSession은 로컬 panel 세션 중 !isImported인 것만 저장하며, shouldBeInHistory도 !isImported를 요구한다. 가져온 export 데이터로 생성된 모델은 isImported가 true가 된다. 따라서 가져온 대화에 대한 이 증상은 해당 저장/이력 제외 조건과 일치한다. 핀·이름 변경이나 검색 재색인이 이 조건을 해제한다고 볼 근거는 없다. 일반 원본 세션의 다른 목록 누락까지 이 원인으로 일반화하지 않는다.
- 이전 Import 안내는 내용 보기·보존에는 유효하지만 영구 목록 복원 방법으로는 불충분했다. 최근 renderer/Copilot/session 로그에서 이 문제의 저장 오류는 발견하지 못했으며 진단 도구 자체의 잘못된 경로 조회 오류는 구분했다.
- 우회 후보: Fork Conversation의 로컬 경로는 모델 toJSON 내부 데이터를 복제해 새 sessionId/creationDate를 부여하고 loadSessionFromData로 새 세션을 연다. export 형식을 그대로 다시 Import하는 것과 다르다. 가져온 대화의 마지막 메시지에서 Fork Conversation을 사용할 수 있다면 분기 사본을 생성해 닫은 후 유지 여부를 확인하도록 안내한다. 읽기 전용 등으로 메뉴가 없을 수 있으며 실제 UI 분기·저장 성공은 아직 검증하지 않았다. 원본 JSON·DB·VS Code 코드는 수정하지 않았다.

## 2026-10-23 / 포크 후 재시작 시 목록 누락 / 저장소 분리 확인

- 사용자 보고: 포크·이름 변경·핀 후에도 창 재시작 시 목록에서 사라졌다. 동일 폴더 URI를 가리키는 workspaceStorage를 모두 읽기 전용 조사했다. 포크로 보이는 '확률론 패처' 세션 f5efb4ae-2a0e-4839-9e54-f93985ba2f91은 89b21f739e33c95d58fed2828f7873af 인덱스와 약 15MB JSONL에 실제 보존돼 있다. 반면 현재 25b2ef08c089f73bc493aff6c1cb725d 저장소 목록에는 해당 세션이 없다. 세션 파일 삭제가 아니라 다른 저장소를 보는 상태다.
- 설치 mainImpl.js의 폴더 식별자 생성은 경로와 플랫폼별 파일 시스템 값(생성 시각/식별값)을 MD5에 사용한다. 저장된 .code-workspace 식별자는 파일 경로로 생성한다. 현재 프로젝트 폴더 생성 시각은 2026-10-23T03:24:34Z이고 보존된 포크 파일 수정 시각은 03:23:53Z다. 폴더 재생성/메타데이터 변화가 저장소 분리의 유력 원인이지만 수행 주체는 미확정이다. Nextcloud 동기화가 원인이라고 확정하지 않는다. 현재 생성 시각으로 계산한 해시는 294cbff33089bb100ba02704771c3705로 현재 창 ID와 불일치해 정확한 전환 시점·원인은 추가 확인이 필요하다.
- 완화 조치: 동기화 경로 밖 /Users/esoterikos/VSCode-Workspaces/blt-cache.code-workspace를 생성해 기존 프로젝트 폴더를 참조하게 했다. 원문·코드·실험을 이동하지 않고 원본 DB와 세션 파일을 변경하지 않는다. 사용자가 이 workspace 파일을 열고 내보낸 JSON을 가져온 뒤 일반 세션으로 분기하면, 이후 동일 workspace 파일로 열어 경로 기반의 안정된 저장소를 사용하도록 할 수 있다. 실제 창 재시작 유지 여부는 아직 미검증이다. 이전 폴더 저장소에서 기록이 자동 병합되지는 않는다.
- 완료 검사: 생성 JSON 파싱과 참조 폴더 존재 검사 통과. 설치 코드의 경로 기반 계산으로 새 workspace ID는 cfb4d4302bd47a974dcf761e383be22a다. UI 열기·기록 가져오기·재시작은 사용자 창을 중단하지 않기 위해 수행하지 않았다. 원격 10GB 작업에는 영향을 주지 않는다.

## 2026-10-23 / 대화 목록 원인 재진단 / 폴더 식별정보와 현재 저장소 일치

- 동일 blt-cache 폴더 URI를 가진 workspaceStorage 8개와 별도 .code-workspace 저장소 1개를 읽기 전용으로 확인했다. 원래 대화 a7bee659는 7d23e3b361e160c59a353d1a365874cf에, 포크 '확률론 패처' f5efb4ae는 89b21f739e33c95d58fed2828f7873af의 목록 및 16,238,932바이트 JSONL에 실제 보존돼 있다. 가져온 대화 저장 제외와 별개로, 일반 포크가 저장된 뒤 다른 workspace 저장소를 보게 되는 문제가 확인된다.
- 설치 코드의 실제 위치는 app/out/mainImpl.js다. macOS 폴더 식별자는 MD5(folder.fsPath + String(stat.birthtime.getTime()))다. 현재 측정한 생성 시각 2026-10-23T03:31:06.000Z(1792726266000)으로 직접 계산한 값이 34a86f9d4e2656dd0cb006028b4fee10으로 현재 창 저장소 ID와 정확히 일치했다. 앞선 로그의 03:24:34 생성 시각 관측과 달라 폴더 식별정보가 안정적이지 않다는 가설을 뒷받침한다. 폴더 재생성/생성시각 변화의 수행 주체는 확인하지 않았다.
- 따라서 주된 관측은 세션 파일 소실이 아니라 폴더 identity 변화로 서로 다른 저장소를 여는 것이다. Nextcloud File Provider 경로이므로 동기화 계층은 조사 후보지만, Nextcloud가 실제 생성 시각을 바꿨다는 직접 증거는 없다. 다중 창 충돌을 입증한 것도 아니다. 앞서 Nextcloud와 무관한 듯 안내한 것은 지나치게 단정적이었다.
- 정정: 저장된 .code-workspace ID는 macOS에서 경로를 소문자로 만든 뒤 MD5한다. /Users/esoterikos/VSCode-Workspaces/blt-cache.code-workspace의 정확한 ID는 be8487059737a8f7367c6a44fff73610이며 해당 workspace.json/DB가 실제 존재한다. 앞선 cfb4d4302bd47a974dcf761e383be22a 계산은 대소문자 정규화를 누락한 값이었다. 원본 이력은 보존하고 이 항목으로 정정한다.
- 권고: 기존 폴더 자체를 다시 여는 대신 위 고정 workspace 파일로 일관되게 열고, 보관 JSON을 가져와 일반 세션으로 분기한 뒤 닫기·재시작 유지 여부를 확인한다. 경로 기반 ID라 프로젝트 폴더 생성 시각과 분리된다. 현재 workspace 저장소에도 JSONL 파일은 있지만 어느 파일이 사용자 복원 대상인지 및 재시작 후 유지 성공은 아직 확인하지 않았다. 원본 DB/VS Code 코드/프로젝트 경로를 변경하지 않았고 원격 실험도 건드리지 않았다.

## 2026-10-23 / 배경 10GB 확대 / tmux 진행 확인

- 서버 관측 시각 2026-10-23T03:47:41+00:00. tmux blt-bg10gb-20261023과 실행기 PID 713746, 부모 재현 검사 PID 713764가 유지되고 있다. 시작 이후 40분 34초이며 현재 --stage verify다. 10GB 표집·구축·적합은 아직 시작하지 않았다.
- 검사 프로세스는 Rl+, CPU 100%, 현재 RSS 1,123,480KiB(약 1.07GiB)다. 서버 가용 RAM 약 57GiB, 디스크 여유 264GiB. progress.md는 verify started 상태이며 표준 출력에 오류가 없고 최종 run_report.json은 아직 없다. CPU 활동은 관측됐지만 중간 진행률이나 검사 통과를 확인한 것은 아니다.
- 작업·환경·데이터를 변경하거나 재시작하지 않았다. 다음 단계는 부모 검증 완료/실패 기록 확인이며, 통과하면 기존 실행기가 10GB 표집부터 F1 비교까지 이어서 수행한다. 시간 제한 없이 기존 RAM·디스크 보호를 유지한다.

## 2026-10-24 / 배경 10GB 확대 / 실패 확인: 중복 제거 MemoryError

- 서버 조회 시각 2026-10-23T22:53:02+00:00에 최종 보고서 status failed를 확인했다. 실제 종료 기록은 2026-10-23T05:27:46+00:00이며 전체 경과 8,438.8134초(약 2시간 21분)다. 이전 조회 이후 실행이 종료됐고 현재 tmux/실험 Python 프로세스는 없다.
- 완료 단계는 부모 5GB 재현 검사 verify뿐이다. 후보 표집 후 prepare의 expanded_background→deduplicate→datasketch LSH index.insert→storage._dict[key].update에서 MemoryError가 발생했다. RAM 48GiB 주소 공간 보호가 적용된 실행이며 정확한 실패 시 RSS는 보고되지 않았다. 물리 RAM 전체 고갈이나 GPU 메모리 오류로 단정하지 않는다.
- 10GB 데이터 준비 완료·카운트 구축·적합·F1 비교는 수행되지 않아 점수가 없다. 현재 서버 가용 RAM 약 58GiB/디스크 여유 264GiB다. 기존 5GB 결과는 그대로 유지하며 재시작·메모리 한도 상향·표집 규약 변경은 하지 않았다.
- 다음 단계는 작은 실패 보고서·부모 재현 보고서를 회수하고 해시 검증 후 task.md를 실패 상태로 갱신하는 것이다. 재시도하려면 준비 단계의 메모리 사용을 줄이는 방식부터 별도 검토해야 한다.

## 2026-10-24 / 배경 10GB 확대 / 실패 근거 회수·검증 완료

- evidence/english_bg10gb_run_20261023.json 및 evidence/english_bg10gb_equivalence_20261023.json 회수. status failed, 완료 단계가 verify 하나뿐인 점, 재현 보고서 SHA256 및 실행 계획 해시 일치를 검증했다. 문서 공백 검사 통과. task.md에 실패·미실행 범위와 재시도 보류를 반영했다.
- 부모 재현 검사 실측: 2,612.71초, 최대 RSS 1,247,309,824바이트, 111문서 F1 0.78042048498 일치. 이후 prepare에서 실패했으며 10GB 품질 판정에 도달하지 않았다. 서버 파일·한도·코드는 변경하지 않았고 커밋·푸시도 하지 않았다.

## 2026-10-24 / 메모리 절감 및 C++ 가속 / 구현 착수

- 사용자 승인으로 두 개선을 함께 진행한다. 가설: 원문·서명·LSH 인덱스를 디스크 기반으로 바꾸면 메모리 상주량을 줄일 수 있고 MinHash 순열 계산의 C++ 구현은 Python 경계의 비용을 줄일 수 있다. 실제 속도/메모리 개선은 아직 미측정이다.
- 기존 Python 정규화·5단어 shingle·SHA1 32bit·datasketch 순열·LSH 버킷·0.8 추정 Jaccard·표집 순서를 유지한다. 새 경로는 명시적 opt-in으로 분리하며 기존 실행과 기본 캐시 API를 변경하지 않는다. 동일 합성 입력의 서명·중복 배제·최종 문서 순서 비교가 차이를 보이면 확대 실행하지 않는다.
- 첫 구현은 독립 C++ MinHash128 커널과 Python ctypes 어댑터다. uint64 overflow 및 빈 입력에 대한 작은 산술 oracle 테스트를 먼저 실행하고, 이후 SQLite 디스크 인덱스/원문 spool을 연결한다. 실패한 10GB 산출물은 보존한다.

## 2026-10-24 / C++ 커널 / 첫 집중 검증

- 로컬 Mac 컴파일은 C++ 표준 헤더 algorithm 부재로 실패했다. 테스트가 통과했다고 취급하지 않는다. 서버에 새 커널/어댑터/테스트만 전송해 같은 테스트를 실행했고 1개 테스트가 0.214초에 통과했다. uint64 overflow·빈 서명의 산술 일치만 확인한 결과이며 datasketch 일치/속도 개선은 아직 검증 전이다.
- 다음 단계는 SQLite 원문·서명·LSH 버킷 저장과 기존 순서대로 ID 표집을 구현하고, datasketch 서명 및 기존 expanded_background 결과와 대조하는 것이다. 서버 SQLite 개발 헤더는 없으므로 Python 표준 sqlite3 모듈을 사용한다.

## 2026-10-24 / 디스크 경로 / 라이브러리 규약 차이 발견·수정

- 첫 datasketch 비교는 기존 hashvalues로 초기화할 때 scheme을 명시해야 한다는 ValueError로 실패했다. 설치된 datasketch 2.0의 실제 update_batch/생성자를 조회해 기본값이 affine32임을 확인했다. 앞선 legacy uint64 oracle 통과는 현재 실험의 서명 일치를 의미하지 않는다.
- C++에 affine32 MurmurHash3 finalizer 및 uint32 wrap 순열을 추가하고 datasketch 객체의 실제 scheme/dtype을 사용하도록 수정했다. legacy도 별도 지원하며 알려지지 않은 scheme은 거부한다. 기존 실험의 기본값을 legacy로 강제하지 않는다. 동일 집중 테스트를 재실행한다.

## 2026-10-24 / 디스크·C++ 경로 / 합성 동등성 통과 및 실행기 연결

- 서버 집중 테스트 2개가 0.701초에 통과했다. 실제 affine32 datasketch 서명 비트 일치(빈 문자열·짧은 문서·Unicode 포함), 정확/URL/근사 중복 배제, 길이대별 3개 byte 목표의 최종 문서/순서/총량, 보호 split 충돌 거부를 검증했다. 전체 데이터 동등성이나 속도 개선의 증거는 아니다.
- 실행기에 preparation_backend=sqlite_cpp_v1 opt-in을 추가했다. 기존 기본 경로는 그대로다. 원문·서명·LSH 버킷은 SQLite, 셔플은 ID만 사용한다. 후보 quota/샤드/seed/난수 순서는 유지한다. 48GiB 주소 공간 보호 및 100GiB 디스크 보호/시간 무제한을 유지하고 새 scratch는 성공한 준비 단계에서만 제거한다.
- 별도 재실행 계획 experiments/english_background_10gb_disk_cpp.json 작성. 실패 실행/기존 5GB는 보존한다. 다음은 집중 회귀 테스트와 실제 자료의 메모리/시간 사전 측정이며 아직 장기 실행은 시작하지 않았다.

## 2026-10-24 / 실행기 연결 / 집중 회귀 통과

- 원격 python -m unittest tests.test_data_preparation -v: 7개 테스트가 0.763초에 통과했다. 기존 블록 카운트·gzip·부모 재현 검사도 통과했다. Parquet 표집 연결 자체의 동등성은 아직 확인 전이므로 고정 합성 Parquet로 전체 prepare 출력 해시 비교를 추가한다.
- 로컬 SDK의 C++ 표준 라이브러리 헤더 문제는 커널이 사용하지 않는 STL 의존성을 제거하는 작은 변경으로 확인한다. 기본 C 정수 헤더와 명시적 최소 비교만 남기며 산술은 유지한다. 재검증 전 로컬 빌드 가능 여부는 미확정이다.

## 2026-10-24 / Parquet 표집 연결 / 전체 출력 동등성 통과

- 서버 준비 테스트 8개가 0.778초에 통과했다. 고정 합성 Parquet와 부모 background를 사용해 두 prepare 경로의 최종 JSONL SHA256·문서/바이트/길이대·표집 row groups·배제 건수·부모 식별자 일치 및 성공 시 새 scratch 제거를 확인했다.
- 로컬 컴파일은 헤더 제거 후 런타임 libc++ 링크 부재로 실패했다. 런타임 기능을 사용하지 않는 커널에 한해 macOS -nostdlib++를 적용해 재검증한다. 서버 C++ 빌드는 통과했다.
- 실제 5GB 원문 접두부에서 별도 프로세스로 기존 Python 대비 disk/C++ 시간·RSS·출력 해시 및 서명 생성 시간/비트 일치를 측정하는 재현용 벤치마크를 추가했다. 실제 10GB 메모리 상한이나 처리 시간으로 일반화하지 않는다.

## 2026-10-24 / 실제 자료 사전 측정 / 메모리 절감·속도 한계 확인

- 첫 측정은 20,000개 실제 문서에서 출력 JSONL SHA256 일치, Python 12.2116초/RSS 494,268,416바이트, disk/C++ 15.1633초/RSS 375,529,472바이트였다. 측정기의 disk worker도 처음에 원문 전체를 읽고 해제해 RSS를 높이는 문제가 있었다. 서명 생성은 Python 0.3105초/C++ 0.3218초로 빨라지지 않았다. 초기 보고서는 evidence/english_disk_cpp_preflight_initial_20261024.json에 보존했다.
- 측정기를 streaming 사전 스캔으로 바꾸고 C++의 입력 mixing을 문서 shingle마다 한 번 수행하도록 수정했다. 서버 준비 테스트 8개가 0.775초에 통과했다. 두 번째 실제 측정은 양쪽 8,004문서/49,092,838바이트, 출력 해시 3b39d7ce1a48831c668815ad5bcbfb9c3c74f0a14da12b30c2e509982d9bf98b 일치다. Python 12.4753초/RSS 494,919,680바이트, disk/C++ 14.1841초/RSS 200,339,456바이트(약 59.5% 감소, 시간 약 13.7% 증가), SQLite 165,408,768바이트다.
- 500문서 서명 비트 전부 일치. shingle/SHA1/순열 포함 생성 시간 Python 0.3181초/C++ 0.3022초(약 1.053배)이나 단회 소폭 차이여서 일반 가속을 주장하지 않는다. 핵심 성과는 메모리 절감이며 디스크 I/O의 시간 비용이 있다. evidence/english_disk_cpp_preflight_20261024.json 회수 완료. 전체 10GB 실행의 피크/시간은 아직 미측정이다.
- 로컬 Mac은 헤더 및 libc++ 문제를 넘긴 후에도 System 링크 라이브러리가 없어 세 번째 네이티브 빌드 시도가 실패했다. SDK/환경은 변경하지 않았으며 로컬 빌드 수정을 더 반복하지 않는다. 서버 빌드·실행으로 검증하며 Mac SDK 복구는 별도 사용자 환경 작업이다.
- 다음 단계: 디스크 보호/실패 산출물 보존 테스트, 전체 서버 회귀 및 의존성 검사 후 별도 tmux 10GB 재실행. 새로운 경로의 기본 API opt-in과 기존 실험 데이터는 유지한다.

## 2026-10-24 / 재실행 사전 검증 / 전체 테스트 통과

- 서버 python -m unittest discover -s tests -v: 25개 테스트 모두 통과(1.579초, skip 없음). python -m pip check: No broken requirements found. 추가한 보호 검사는 저장 예산 0에서 prepare 중단, 실패 scratch 보존, 기존 SQLite 덮어쓰기 거부, 보호 background 순서 및 미지원 backend 거부다.
- opt-in 실행기 연결·기존 캐시 API·카운트/적합·Parquet 표집 동등성을 검증했다. 로컬 Mac 네이티브 빌드는 SDK 링크 문제로 실패 상태이며 서버 결과와 구분한다. 전체 10GB prepare/품질은 아직 확인 전이다.
- 다음 단계는 새 실행 ID en-patcher-bg10gb-diskcpp-20261024-01 및 tmux blt-bg10gb-diskcpp-20261024로 재시작하는 것이다. 동일 표집 seed 20261023, 원래 후보 quota·부모 5GB·고정 라벨·F1 비교를 유지한다. 기존 실패 실행/데이터/환경을 삭제하거나 RAM 한도를 상향하지 않는다.

## 2026-10-24 / 디스크·C++ 10GB 재실행 / tmux 시작 확인

- 실제 서버 시작 2026-10-23T23:06:56+00:00(한국 2026-10-24 08:06:56). 새 tmux blt-bg10gb-diskcpp-20261024, 실행 en-patcher-bg10gb-diskcpp-20261024-01. 명령: .venv/bin/python -u -m scripts.run_background_expansion --plan experiments/english_background_10gb_disk_cpp.json. stdout는 runs/en-patcher-bg10gb-diskcpp-20261024-01.stdout.log, 단계별 결과는 같은 run의 progress.md에 기록된다.
- 서버 관측 2026-10-23T23:07:19+00:00에 실행기 PID 745008 및 부모 재현 verify PID 745062 생존을 확인했다. 현재 verify이며 10GB prepare·구축·적합이 시작된 것은 아니다. 초기 stdout 오류 없음, 가용 RAM 약 57GiB/디스크 263GiB. 계획 SHA256 6e6b79a6e262bdbf0ebdc94a79eff11d8c8b516084dad36407dabcc83b674b16. 실행기는 새 C++/Python 코드 해시를 최종 보고서에 보존한다.
- 새 경로 및 stdout 파일이 없음을 확인하고 시작했으며 이전 5GB·실패 10GB·사전 측정 산출물은 보존했다. RAM 48GiB/디스크 여유 100GiB/새 산출물 100GiB/시간 상한 없음 확인. 자동 재시도는 없다.
- Pylance prepare_disk_background.py/disk_dedup.py 문법 검사 통과(최초 workspaceRoot 누락 요청은 매개변수를 명시해 재실행). 변경한 Python 6개 파일 편집기 오류 없음, 변경 문서·코드 공백 검사 통과. task.md에 실행 상태를 반영했다. Mac SDK 링크 문제는 해결되지 않았으며 네이티브 검증은 서버에서 수행했다.
- 다음 단계는 부모 재현 통과 후 SQLite 준비 진행·실제 최대 RSS·디스크 사용 관측, 이후 기존 F1 구축/적합/비교다. 아직 10GB 메모리 문제의 완전한 해결이나 F1 개선을 주장하지 않는다. 커밋·푸시는 하지 않았다.

## 2026-10-24 / 디스크·C++ 10GB / 완료 시간 추정(실측 아님)

- 사용자 완료 시간 문의에 따라 서버 2026-10-23T23:08:58+00:00 상태를 확인했다. 시작 후 2분 2초, 부모 verify PID 745062 유지/초기 오류 없음. 작업 설정과 프로세스를 변경하지 않았다.
- 근거: 5GB build 23,404.16초의 2배는 13.00시간. 5GB fit 전체 4,362.25초 중 배경 로딩은 3,266.52초로, 고정 feature/적합을 모두 2배로 볼 필요는 없다. 현재와 같은 5GB 부모 재현은 앞선 실패 실행에서 2,612.71초였다.
- 후보 수 가정: 이전 5GB의 8GB 후보/2,267,392문서 비율로 새 10GB 후보를 외삽하면 약 283만 후보 + 부모 126만 = 약 410만 문서다. 20,000문서/14.1841초를 그대로 외삽한 처리 시간은 48.45분이다. 이 수치는 HF 다운로드/대규모 인덱스 증가/실제 새 문서 분포를 반영하지 않아 전체 prepare 예상으로 사용하지 않는다. 실제 후보 수는 아직 모른다.
- 정상 완료를 전제로 한 공학적 예산: 부모 재현 약 40~50분, 다운로드·SQLite 준비 약 2~4시간, 카운트 구축 약 12~15시간, 로딩·적합·검증 약 1.5~2.5시간, 비교·기타 여유를 포함해 시작부터 약 18~24시간(중심 약 20시간). 통계적 신뢰구간/완료 보장이 아니며 메모리·디스크 실패 가능성도 남아 있다. 08:06:56 한국시간 시작 기준 2026-10-25 02~08시, 중심 04시 부근이다.
- SQLite도 page cache/OS 파일 캐시 등 RAM을 사용한다. 작은 비교에서 전체 준비 시간이 약 14% 늘어난 것은 디스크 저장·조회와 어댑터 등 변경을 합한 결과이며 SQLite 단독 기여를 분리 측정하지 않았다. 변경은 prepare에만 적용되어 전체 실행 시간을 일괄 14% 늘려 추정하지 않는다.
- 계산용 첫 일회성 스니펫은 괄호 오류로 실패했고 수정 재실행으로 위 기준값을 확인했다. 실험 작업에는 영향이 없다. 다음 ETA 보정 시점은 prepare 처리율 및 카운트 블록별 진행 기록이 확보된 뒤다.

## 2026-10-24 / 로컬 작업 경로 이동 / 접근 권한 확인

- 사용자 요청으로 위치와 권한만 점검했다. 현재 VS Code 파일 검색 및 터미널 pwd -P/Git 루트는 /Users/esoterikos/NextCloud/projects_on/blt-cache다. 고정 workspace /Users/esoterikos/VSCode-Workspaces/blt-cache.code-workspace의 folders.path도 ../NextCloud/projects_on/blt-cache로 이미 변경돼 있다. workspace 설정은 수정하지 않았다.
- 기존 CloudStorage 경로와 새 NextCloud 경로는 같은 장치지만 inode가 각각 198623134/203438295로 다른 별도 디렉터리다. 링크로 간주하지 않으며 앞으로 새 경로만 편집한다. 실행기와 10GB 계획의 두 로컬 사본 SHA256은 동일했고 이전 변경 파일들도 새 Git 작업 트리에 유지됐다. 다른 모든 파일의 동일성을 검사한 것은 아니다. 이전 사본은 삭제·동기화하지 않았다.
- 새 경로의 AGENTS.md 읽기 및 log.md/task.md/scripts 쓰기 권한 비트 확인. 이번 기록을 새 경로에 편집하는 것으로 편집 도구 접근도 확인한다. SSH BatchMode 접속 성공, 서버 source 읽기/쓰기 및 runs 쓰기 접근 확인. 서버 work_root는 여전히 /home/itcmaster/projects/blt-cache다. 현재 점검에서 추가 승인·권한 오류·인증 갱신 요구가 발생하지 않았으며 chmod/관리자 권한/전체 디스크 접근 권한은 요청하거나 변경하지 않았다.

## 2026-10-24 / 경로 점검 중 관측 / 10GB 부모 재현 실패

- 서버 관측 2026-10-24T00:43:27+00:00에 새 10GB 실행의 최종 status failed를 확인했다. 실제 종료는 2026-10-23T23:51:01+00:00(한국 10월 24일 08:51:01), 경과 2,644.74초(약 44분 5초), 완료 단계 없음이다. 앞선 진행 중/ETA 기록은 당시 관측과 조건부 추정이며 현재 진행 상태가 아니다.
- stdout의 실제 실패: scripts/run_background_expansion.py verify에서 ValueError: Projected background changed baseline validation. 권한 오류가 아니라 부모 검증 결과 불일치로 중단됐으며 구체적인 수치 원인은 이번 경로 점검에서 진단하지 않았다. SQLite/C++ prepare·카운트 구축·적합은 시작하지 않아 10GB 점수가 없다. 이동과 실패의 인과관계는 확인하지 않았다.
- 서버 source·계획·데이터·한도는 변경하지 않았고 재시작하지 않았다. 기존 산출물과 실패 기록을 보존한다. 다음 실험 단계는 별도 범위로 부모 재현 불일치 원인을 조사하는 것이다. 로컬 경로 접근은 정상이며 이 중단과 구분한다.

## 2026-10-24 / 부모 재현 불일치 / 사용자 승인 진단 착수

- 사용자가 원인 분석 후 재개를 요청했다. 실패 줄에 도달하기 전에 6개 학습 특징과 문서별 TP/FP/FN 및 순서의 정확 비교는 통과하는 코드 경로를 확인했다. 가설은 집계 부동소수점 차이지만 아직 실제 차이값이 없어 확정하지 않는다. SQLite/C++ 준비는 이 검사 뒤이므로 아직 실행되지 않았다.
- 기존 검증 기준은 변경하지 않고 불일치 지표별 reference/replayed/saved 값·절대차, 배열 재생 artifact를 실패 시 저장하도록 진단 출력을 추가했다. evaluate_threshold 기본 계산은 그대로이며 optional replay 수집만 추가했다. 1 ULP 변화를 의도적으로 넣었을 때 여전히 실패하면서 지표 이름/근거 파일을 남기는 집중 테스트를 추가했다.
- 다음은 서버 집중 테스트 후 새 진단 디렉터리에서 부모 재현을 실행해 실제 수치와 원인을 확인하는 것이다. 과거 실패 실행, 부모 보고서/라벨/블록, RAM·디스크 한도는 보존하며 숫자 허용 오차를 임의로 늘리지 않는다.

## 2026-10-24 / 진단 출력 집중 검증 / BLAS 환경 가설

- 원격 부모 재현 합성 테스트 1개가 0.417초에 통과했다. 1 ULP를 넣은 지표는 여전히 실패하고 지표별 JSON/배열 파일을 남긴다. 기준을 느슨하게 바꾸지 않았다.
- 이전 log의 검증 명령에 OPENBLAS_NUM_THREADS=8이 있고 현재 SSH 환경은 OPENBLAS/OMP/MKL 스레드 변수가 모두 unset이다. average_precision이 np.dot을 사용하므로 병렬 reduction의 마지막 비트 차이 가능성을 추가 가설로 삼는다. 실제 실패 지표/차이는 아직 미확인이다. np.show_runtime은 NumPy 2.4.6/Python 3.11.16을 확인했고 threadpoolctl 미설치 경고를 냈다. 의존성은 설치하지 않았다.
- 부모 fit에는 train 특징/라벨만 있고 검증 재생 배열은 없어 한 차례 전체 재생이 필요하다. 진단 계획에서만 capture_validation_replay를 켜 성공 여부와 무관하게 배열을 보존하고 블록별 진행을 기록한다. 이후 동일 배열의 집계를 BLAS 설정별로 비교할 수 있다. 새 진단 tmux에서 수행하며 기존 실패 run은 수정하지 않는다.

## 2026-10-24 / 진단 확장 / 집중 검사 실패·복구

- 진단 플래그·환경 기록 확장 후 첫 집중 테스트는 run_background_expansion.py의 IndentationError로 import 단계에서 실패했다. 진단 실험 시작 전 발견했으며 해당 분기와 JSON 항목 들여쓰기만 수정했다. 같은 테스트를 재실행해 1개가 0.413초에 통과했다.
- 다음 단계는 en-patcher-bg10gb-replaydiag-20261024-01 디렉터리와 blt-bg10gb-replaydiag-20261024 tmux에서 실제 부모 verify를 수행하는 것이다. NumPy 스레드 변수가 없는 현재 환경을 먼저 재현하며 48GiB 제한을 유지한다. 단계 완료 후에만 실제 불일치와 BLAS 설정별 재집계를 비교한다.

## 2026-10-24 / 실제 부모 재생 진단 / tmux 시작

- 서버 2026-10-24T00:50:23+00:00에 blt-bg10gb-replaydiag-20261024 tmux 시작을 확인했다. run en-patcher-bg10gb-replaydiag-20261024-01에서 capture_validation_replay=true로 기존 부모 5GB를 재생한다. 원래 10GB run은 재시작하지 않았다.
- 진단은 48GiB 주소 공간 보호 및 기존 라벨/배경 해시·특징·문서 카운트·지표 정확 비교를 유지한다. 블록별 로딩 기록은 새 run/progress.md와 서버 source/log.md에 남긴다. stdout는 runs/en-patcher-bg10gb-replaydiag-20261024-01.stdout.log다. 종료 시 tmux wait-for 채널 blt-replaydiag-20261024-done으로 알린다.
- 다음 단계는 진단 종료 알림 후 validation_replay_mismatch.json/validation_replay.npz를 확인하고 같은 배열의 집계만 BLAS 환경별로 재실행해 원인을 판별하는 것이다. 성공해도 배열을 남긴다. 허용 오차 완화·부모 결과 변경·이전 산출물 삭제는 하지 않는다.

## 2026-10-24 / 사용자 원인 설명 요청 / 진단 진행 확인

- 서버 2026-10-24T00:58:20+00:00 확인: 진단 진행 중, 마지막 완료 블록 block-00037(200개 중 38개, 약 19%), 경과 476.2초. validation_replay_mismatch.json은 아직 생성되지 않았다. stdout 오류는 관측되지 않았다. 실행/설정은 변경하지 않았다.
- 현재 확정 범위는 기존 5GB 학습 특징/문서별 TP·FP·FN/문서 순서 비교 뒤 집계 지표의 정확 비교에서 이전 실행이 실패했다는 점이다. 실패 지표 이름과 차이값은 아직 모른다. BLAS 설정에 따른 미세 차이라는 설명은 가설이며 확정 원인으로 보고하지 않는다. 10GB SQLite/C++ prepare에 들어가기 전의 중단이다.
- 최초 검사에서 지표별 불일치 값을 저장하지 않아 부모 배경을 다시 읽어야 하는 진단 비용이 발생했다. 이번 진단에 배열/차이값 보존을 추가했으며, 완료 후 같은 배열로 원인을 확인하고 수정·재개한다.

## 2026-10-24 / 부모 재현 불일치 / AP 1 ULP 및 BLAS 원인 확인

- 실제 진단 종료 알림 시각은 서버 2026-10-24T01:34:01+00:00, 경과 2,618.44초다. 저장된 지표에서 유일한 차이는 AP 0.8409333314375305→0.8409333314375304, 절대차 1.1102230246251565e-16(1 ULP)였다. F1 0.7804204849787754, entropy MAE/RMSE, log loss는 정확히 일치했다. 6개 학습 특징 및 문서별 카운트/순서 비교도 통과했다.
- 동일 validation_replay.npz의 scores/labels만 별도 Python 프로세스에서 재집계했다. OPENBLAS_NUM_THREADS unset/24는 AP 0x1.ae8ed04947f27p-1, 1/8은 0x1.ae8ed04947f28p-1로 기존 AP와 정확히 일치했다. 따라서 이번 불일치는 AP의 np.dot 병렬 reduction 설정에 따른 수치 차이임을 확인했다. 새 데이터/모델 재생 없이 동일 배열로 재현한 결과다.
- 최초 스레드별 확인 명령은 SSH 인용 때문에 배열 key의 따옴표가 빠져 실패했고, 코드를 stdin으로 전달해 수정 재실행했다. 저장 데이터·실험에는 영향이 없다.
- 원인 수정은 허용 오차 완화가 아니라 명시적 BLAS 환경 고정이다. 별도 재개 계획 english_background_10gb_disk_cpp_repro.json에 openblas_num_threads=8을 선언하고 실행기에서 NumPy import 이전 실행 환경이 다르면 긴 작업 전에 즉시 거부하도록 추가했다. 부모/라벨/카운트/계산식·정확 비교는 유지한다. 최근 실행에서 환경을 고정하지 않은 것은 실행 구성 누락이었다.
- 다음 단계는 fail-fast 집중 테스트와 전체 회귀, 실제 배열 지표 재검증 및 작은 근거 JSON 회수 후 새 -02 tmux 재시작이다. 이전 실패/진단 run은 보존한다.

## 2026-10-24 / BLAS 환경 고정 / 실제 배열·전체 회귀 통과

- 집중 테스트 2개가 0.382초에 통과했다. 스레드 설정 누락/잘못된 값은 작업 시작 전 거부하고, 기존 1 ULP 불일치 테스트도 여전히 실패로 처리한다. AP 계산식과 엄격한 지표 비교는 바꾸지 않았다.
- OPENBLAS_NUM_THREADS=8의 새 프로세스에서 저장된 부모 보고서와 배열의 SHA256을 확인하고 재집계했다. 문서별 카운트 및 f1/entropy_mae/entropy_rmse/log_loss/auprc_average_precision 전부 저장된 5GB 지표와 정확히 일치했다. 이는 저장 배열의 재집계 결과이며 새 -02 실행의 전체 부모 재현 검사를 대체하지 않는다.
- evidence/english_bg10gb_replay_mismatch_20261024.json, evidence/english_bg10gb_aggregation_repro_20261024.json, evidence/english_bg10gb_disk_cpp_failed_20261024.json 회수 완료. 큰 validation_replay.npz는 서버에만 보존했다. 전체 OPENBLAS_NUM_THREADS=8 unittest 26개 통과(1.319초, skip 없음), pip check 정상.
- 다음은 새 -02 계획/환경 식별자와 48GiB/디스크 보호/경로 유일성을 확인한 뒤 detached tmux에서 재시작하는 것이다. 초기에는 다시 전체 부모 재현을 수행하고 통과 시에만 10GB SQLite/C++ 준비로 넘어간다.

## 2026-10-24 / 환경 고정 10GB / 새 -02 실행 재개

- 실제 서버 시작 2026-10-24T02:00:19+00:00(한국 11:00:19), tmux blt-bg10gb-diskcpp-20261024-02, 실행 en-patcher-bg10gb-diskcpp-20261024-02. 명령은 OPENBLAS_NUM_THREADS=8 .venv/bin/python -u -m scripts.run_background_expansion --plan experiments/english_background_10gb_disk_cpp_repro.json이다. 계획 SHA256 ea45d5e8107c23591e8e18ec19b9ae67bbea03cd9858915c2cb4b86dff549531.
- 서버 2026-10-24T02:00:41+00:00 관측: 실행기 PID 748099 및 verify PID 748117 유지. progress.md에 OPENBLAS_NUM_THREADS=8이 기록됐고 초기 stdout 오류 없음. 현재 다시 전체 부모 verify를 수행 중이며 아직 10GB prepare·구축·적합은 시작하지 않았다.
- 사전 검사에서 새 출력/로그 경로 유일성, 48GiB/RAM·디스크 여유 100GiB·새 산출물 100GiB·시간 무제한과 수치 환경 검증을 통과했다. 이전 -01 실패, replaydiag, 5GB 결과, 로컬 이전 경로 사본은 보존했고 새로운 숫자 허용 오차를 적용하지 않았다. 변경 Python/새 계획 편집기 오류 없음, 변경 문서·코드 공백 검사 통과. task.md와 README 실행 명령을 갱신했다. 커밋·푸시는 하지 않았다.
- 다음 단계는 -02 부모 verify 통과 후 SQLite/C++ 준비의 실제 처리율·메모리·디스크 사용량을 확인하고 기존 F1 구축/적합/비교를 계속하는 것이다. AP 환경 원인은 실제 배열로 확인했으나 전체 10GB 성공/점수는 아직 미확정이다.

## 2026-10-24 / BLAS 8·24스레드 비교 / 사용자 승인 측정 착수

- 사용자가 스레드 비교를 승인했다. 현재 -02 10GB 작업과 엄격한 판정 기준은 변경하지 않고 보존한다. 서버 2026-10-24T02:01:41+00:00에 -02 verify가 약 1코어 CPU/가용 RAM 57GiB에서 진행 중임을 확인했다.
- 가설: 큰 BLAS 내적/계수 적합은 24스레드가 유리할 수 있지만 5열의 얇은 특징 행렬과 Python 카운트 구축은 같거나 느릴 수도 있다. 같은 저장 검증 배열의 AP, 실제 5GB train 특징 전체 적합, 같은 whole-document 원문 약 1MB의 K8 카운트 구축을 구분해서 측정한다.
- 새 benchmark_blas_threads.py는 별도 프로세스를 8→24/24→8 순서로 4회씩 반복하고 worker nice +10으로 기존 작업 우선권을 유지한다. AP·fit은 워밍업 후 측정하고 입력/카운트 fingerprint·계수 차이·AP 값도 기록한다. 동시 실행 부하와 작은 count 표본이라는 한계가 있어 전체 10GB 속도로 일반화하지 않는다. 아직 비교 결과는 없다.

## 2026-10-24 / BLAS 8·24스레드 / 교차 실측 완료

- 별도 blt-blas-compare-20261024 tmux에서 4회씩 순서를 번갈아 8개 worker 실행을 완료했다. 전체 85.37초. 각 worker는 AP 워밍업 후 3회, 고정 특징 전체 적합 워밍업 후 2회, 원문 약 1MB의 K8 카운트 구축 1회를 측정했다. 기존 -02 실행과 판정 기준은 변경하지 않았다.
- 중앙값: 8스레드 AP 0.0362003초/fit 1.2206742초/count 3.1502794초, 24스레드 AP 0.0420211초/fit 1.9524299초/count 3.1308817초. 이번 표본에서 24는 AP 약 16.1%, fit 약 59.9% 느리고 count 약 0.6% 차이로 실질적인 개선을 확인하지 못했다. thin 5-column 행렬·Python count에서 스레드 수 증가가 전체 가속으로 이어진다는 가설을 지지하지 않는다.
- 모든 count fingerprint/문서 수/바이트 수 정확 일치. AP는 앞선 결과대로 8=.8409333314375305, 24=.8409333314375304. fitted 계수의 설정 간 최대 절대차는 1.7763568394002505e-15였으며 두 설정 모두 기존 optimizer 수렴 조건을 통과했다. 새 순차 검증 rollout을 수행한 것은 아니므로 fitted 계수의 실제 경계 일치를 주장하지 않는다.
- 한계: -02 verify와 동시 실행, benchmark nice +10, 순차 프로세스/워밍 캐시이며 전체 데이터 준비·블록 I/O·10GB 학습 전체 시간은 측정하지 않았다. 측정 구간에서 파일 파싱/해시 계산은 제외했다. 결론은 현재 8스레드를 유지하는 것이 타당하다는 것이며, AP 허용 오차나 현재 실험 설정을 자동 변경하지 않는다.
- 다음 단계는 작은 report.json 회수 및 원시 반복/중앙값·입력 해시 검증 후 task.md에 결과를 반영하는 것이다. 원시 측정은 runs/blas-thread-comparison-20261024-01에 보존한다.

## 2026-10-24 / 스레드 비교 / 보고서 회수·검증 완료

- evidence/english_blas_threads_20261024.json 회수. 4회씩 8개 worker, 원시 AP/fit/count 중앙값 재계산, count fingerprint/문서·바이트 합계, 측정 코드/부모 fit/재생 배열 SHA256 일치를 검증했다. count 입력은 1,004,380 UTF-8 바이트였다. 24스레드의 시간 변화는 AP +16.0794%, fit +59.9468%, count -0.6157%다.
- 변경 문서·benchmark 공백 검사 통과. task.md에 측정 결과와 근거 링크를 반영했다. 기존 -02 실행을 중단·재시작하거나 환경·판정 기준을 변경하지 않았다. 이후 실제 10GB 단계 관측은 해당 run의 progress.md를 따른다. 커밋·푸시는 하지 않았다.

## 2026-10-24 / -02 10GB / 초기 ETA 재확인

- 사용자 시간 문의로 서버 2026-10-24T02:23:53+00:00을 조회했다. -02 시작 후 23분 34초, 실행기/부모 verify 프로세스 유지, stdout 오류 없음, 최종 보고서 없음. 현재 prepare/build/fit 미진입이며 단계별 실제 처리 속도는 아직 없다. 작업/환경은 변경하지 않았다.
- 정상 완료 전제의 기존 초기 추정 시작부터 18~24시간(중심 약 20시간)을 유지한다. 이번 -02 시작 한국시간 10월 24일 11:00:19 기준 예상은 10월 25일 05~11시(중심 07시 부근)다. 앞선 08:07 시작 실패 실행 기준 ETA와 구분한다. 현재 시점의 남은 시간은 약 17시간 36분~23시간 36분이라는 산술값이며 정밀한 처리율 추정이 아니다.
- 8/24 비교는 AP·계수 적합·작은 count 표본 측정으로, 10GB 전체 시간을 크게 줄인다는 증거가 없다. 전체 비용의 큰 부분인 카운트 구축 약 13시간 추정은 그대로다. 이 범위는 완료 보장/통계적 신뢰구간이 아니며, 준비 단계·블록별 실측 후 보정한다.

## 2026-10-24 / -02 10GB / 정상 진행 확인 및 단계 전환 소급 기록

- 사용자 요청으로 서버 2026-10-24T05:20:33+00:00(한국 14:20:33), 시작 후 3시간 20분 14초에 읽기 전용 조회했다. tmux와 실행기 PID 748099, build PID 749562가 유지됐다. build는 실행 52분 59초/누적 CPU 52분 55초/CPU 99.8%, 현재 RSS 3,272,084KiB였다. 최근 stdout에 오류가 없고 최종 run_report.json은 아직 없다. 작업을 중단·재시작하거나 설정을 바꾸지 않았다.
- 단계 전환 소급 확인: progress.md에 부모 verify가 02:44:10 UTC 완료(약 43분 51초)됐고 stdout 상태는 verified다. prepare도 prepared로 완료됐으며 2,752,379문서/10,000,002,264 UTF-8 바이트를 확보했다. 준비 단계 peak RSS는 362,360,832바이트(약 346MiB)였다. 이는 실제 완료 로그 관측이며 전체 10GB 적합/비교 성공을 뜻하지 않는다.
- 구축은 05:08:02 UTC의 21블록/525,194,429바이트에서 05:19:39 UTC의 27블록/675,272,928바이트로 증가했다. 최근 약 116초마다 블록 저장이 이어져 정체가 아니라 실제 진척을 확인했다. 현재 115,435문서, 목표 바이트 기준 약 6.75%이며 전체 작업 진행률이 아니다. 구축 peak RSS는 5,283,246,080바이트(약 4.92GiB), 해당 파일시스템 가용 공간은 df -h 기준 250G로 관측됐다.
- 다음은 현재 구축을 그대로 유지하고 이후 블록 진행 및 build 완료/fit 전환을 확인하는 것이다. 이번 조회는 상태 확인이며 데이터 전체 해시 재검증이나 ETA 재산정은 수행하지 않았다.
<!--  -->
## 2026-10-24 / -02 10GB / 구축 35.5% 진행 확인

- 서버 2026-10-24T09:05:04+00:00(한국 18:05:04) 읽기 전용 조회: 시작 후 7시간 4분 44초, tmux/실행기 PID 748099/build PID 749562 유지. build 실행 4시간 37분 30초, 누적 CPU 4시간 37분 23초, CPU 99.9%, 현재 RSS 3,849,264KiB. 최근 stdout에 오류가 없고 최종 보고서는 아직 없다.
- 최신 완료 블록은 09:03:47 UTC의 block-00141(총 142개), 637,309문서/3,551,114,314 UTF-8 바이트로 준비된 10,000,002,264바이트의 약 35.51%다. 이는 카운트 구축 바이트 진행률이며 전체 작업 진행률이 아니다. 이전 관측 27블록/675,272,928바이트에서 계속 증가했고 최근 두 저장 간격은 약 119초/117초다.
- 구축 peak RSS 5,470,478,336바이트(약 5.10GiB), 파일시스템 가용 공간 df -h 기준 239G. 작업/설정 변경 없음. 부모 verify와 prepare는 앞서 완료됐으며 다음은 build 완료 후 fit/비교 진행 확인이다. 이번 조회에서 전체 데이터 재검증이나 ETA 재산정은 하지 않았다.

## 2026-10-24 / -02 10GB / 구축 71.0% 진행 확인

- 서버 2026-10-24T13:46:47+00:00(한국 22:46:47) 읽기 전용 조회: 시작 후 11시간 46분 28초, 기존 tmux/실행기 PID 748099/build PID 749562 유지. build 실행 9시간 19분 13초, 누적 CPU 9시간 19분 5초, CPU 99.9%, 현재 RSS 3,730,392KiB. 최근 stdout에 오류가 없고 최종 보고서는 아직 없다.
- 최신 저장 13:45:43 UTC의 block-00283(총 284개), 1,826,146문서/7,101,816,175 UTF-8 바이트. 준비된 10,000,002,264바이트 기준 구축 진행률 약 71.02%이며 전체 작업 진행률은 아니다. 이전 확인 142블록/35.51%에서 증가했고 최근 저장 간격 약 122초로 지속적인 진척을 확인했다.
- 구축 peak RSS 5,477,064,704바이트(약 5.10GiB), 디스크 가용 df -h 기준 224G. 작업과 설정은 변경하지 않았다. 다음은 남은 구축 및 fit/최종 비교 전환 확인이며, 이번 조회에서 전체 데이터 재검증이나 ETA 재산정은 하지 않았다.

## 2026-10-25 / -02 10GB / 전체 완료 확인 및 단계 전환 소급 기록

- 서버 2026-10-24T21:35:01+00:00(한국 10월 25일 06:35:01)에 사용자 요청으로 읽기 전용 조회했다. progress.md와 run_report.json은 completed이며 verify/prepare/build/fit/compare 5개 단계 산출물 경로와 SHA256을 기록한다. 완료 시각은 2026-10-24T20:33:51+00:00(한국 10월 25일 05:33:51), 총 66,812.468초(약 18시간 33분 32초)다. tmux 서버와 해당 Python 프로세스가 없는 것은 이번 완료 기록과 일치한다. 작업 재실행/설정 변경 없음.
- 단계 전환 소급 확인: fit는 19:49:16 UTC 완료됐고 소요 7,851.935초, peak RSS 4,234,096,640바이트였다. compare는 같은 시각 시작해 20:33:51 UTC 완료, 상태 compared, 동일 검증 111문서 비교다. 이번 조회는 서버 보고서와 로그 관측이며 산출물을 로컬 회수하거나 전체 해시를 독립 재검증한 것은 아니다.
- 측정된 F1 기준 10GB 결과: threshold 0.375, TP 84,063/FP 25,370/FN 20,577, precision 0.7681686511381394, recall 0.8033543577981651, F1 0.7853676082457853. 5GB F1 0.7804204849787754 대비 차이 +0.004947123267009967(약 +0.495%p). entropy MAE 0.4511278819663696, RMSE 0.6659295808824975, log loss 0.23707470571073025, AP 0.8458702744572413. F0.5 재튜닝 결과가 아니다.
- fit의 validation_gate_failed 및 comparison의 quality_gate_passed=false는 F1 0.90 품질 목표 미달이며 실행 중단/예외가 아니다. stdout의 error는 null, 실행 보고서는 completed다. 디스크 가용 df -h 기준 212G. 전체 실험 완료와 품질 목표 충족은 구분한다. 다음 별도 분석 시 작은 보고서 회수/해시 검증 및 paired 차이 신뢰구간 등을 검토할 수 있으며, 이번 상태 확인에서 새 실험·재시작·커밋·푸시는 하지 않았다.

## 2026-10-25 / 배경 크기별 F1 / 증가폭 추세 정리

- 사용자 요청으로 기존 unlimited fit JSON 4개(english_fit_k8_wunlimited_20261019, english_bg100_fit_20261019, english_bg1gb_fit_20261020, english_bg5gb_fit_20261020)의 validation F1/threshold/111문서를 구조화 파싱으로 확인했다. 10GB 값은 앞서 서버 최종 보고서와 stdout에서 확인한 결과를 사용했으며 로컬 증거 파일을 새로 회수한 것은 아니다. 새 학습/평가는 수행하지 않았다.
- 배경 10MB/100MB/1GB/5GB/10GB의 F1은 각각 0.6258061599662468/0.7144561038961039/0.7640857343322092/0.7804204849787754/0.7853676082457853이다. 직전 대비 증가폭은 +8.864994/+4.962963/+1.633475/+0.494712%p, 상대 F1 개선률은 +14.165719/+6.946491/+2.137816/+0.633905%다. 점수 차이와 상대 개선률을 구분했다.
- 확대 배수가 10/10/5/2로 다르므로 delta_F1/log2(배수)로 구간 평균 증가폭을 계산했다. 데이터 2배당 환산 증가폭은 약 2.668629/1.494001/0.703499/0.494712%p로 감소한다. 이는 구간별 로그 크기 기준 서술 통계이지 실제 각 2배 지점의 실측 또는 미래 점수 예측이 아니다.
- 관측 범위에서는 F1이 계속 상승하면서 추가 데이터의 수익이 줄어드는 추세다. 상한이나 20GB/100GB 점수를 단정할 수 없고 동일 검증 111문서 재사용에 따른 선택 편향도 남는다. 이 표는 F1이며 F0.5 결과가 아니다. 다음 조치는 사용자 판단에 따르며 추가 확대/실험은 시작하지 않았다.

## 2026-10-25 / -02 10GB / 예상 대비 실제 실행 시간 분석

- 사용자 속도 문의로 서버 progress.md의 단계 시작/완료와 background_build.json/data_preparation.json을 읽기 전용 확인했다. 단계 보고서 시간: verify 2,629.988초(약 44분), prepare 6,201.700초(약 1시간 43분), build 47,439.985초(약 13시간 11분), fit 7,851.935초(약 2시간 11분). compare는 progress 누적 경과 64,137.2초에서 66,812.5초까지 약 2,675초(45분)다. 각 하위 보고서의 타이머 범위와 실행기 단계 전환 오버헤드가 달라 합계가 전체와 완전히 같지는 않다.
- 전체 66,812.468초(18시간 33분 32초)는 초기 18~24시간 범위의 하단이며 24시간 대비 약 5시간 26분 28초/22.7% 짧다. 중심 추정 20시간 대비 약 1시간 26분 28초/7.2% 짧다. 원래 24시간은 단일 확정 예측이 아닌 상단 예산이었다. prepare 실측 약 1.72시간은 초기 2~4시간보다 짧았고 build 약 13.18시간은 초기 12~15시간/중심 13시간과 대체로 일치했다. 절감 시간을 전부 SQLite/C++ 효과로 귀속할 수는 없다.
- 역사적 5GB 총 32,439.532초(약 9시간 1분) 대비 10GB는 약 2.06배, build 23,404.163초 대비 약 2.03배다. 배경 바이트도 약 2배여서 구축 처리율은 대체로 선형이며 대폭 가속된 측정이 아니다. 서로 다른 데이터 규모·문서 구성·준비 backend이므로 엄격한 동일 입력 A/B 비교는 아니다.
- 이번 결과는 배경 준비/카운트 구축/계수 적합/검증 파이프라인의 CPU 실행 시간이다. 신경망 패처 대비 추론 가속이나 BLT end-to-end 속도를 새로 측정하지 않았다. SQLite/C++ 변경의 입증된 핵심 성과는 이번 10GB 실행에서 준비 peak RSS 약 346MiB로 메모리 실패 없이 끝난 점이며, 언어 변경에 의한 전체 속도 향상으로 일반화하지 않는다. 새 실험/설정 변경은 하지 않았다.

## 2026-10-25 / BLT 패처 교체 / 다음 실험 범위 검토

- 사용자는 배경 데이터 추가 확대를 나중으로 미루고 현재 적합 패처로 BLT 실행 실험을 제안했다. HANDOFF/PLAN/개발 skill 및 BLT-PATCHER.md 평가 절차를 확인했다. 현재 10GB 후보(K8/W 무제한/threshold 0.375)는 F1 품질 게이트 미달 상태이며, 이를 게이트 통과나 정식 채택으로 바꾸지 않고 downstream 진단 후보로 다루는 것을 권고한다.
- 제안한 비교는 동일 BLT 본체 가중치/BF16/장치/입력에서 기존 신경망 패처와 10GB count 패처만 교체하고, 우선 캐시 비활성화·batch 1·beam 1로 영향을 분리하는 것이다. 튜닝에 쓰지 않은 별도 개발평가 표본의 BPB, 동일 접두부 재생의 고정 작업량 시간, 패치 수/평균 길이, 이후 짧은 자유 생성의 EOS/UTF-8/출력 변화와 시간·메모리를 비교한다. 자유 생성 출력 동일성은 채택 조건이 아니며 캐시 parity와 구분한다. 최종 test는 튜닝에 사용하지 않는다. 품질 허용 폭은 평가 전에 정해야 한다.
- scripts/fit_count_patcher.py:load_background를 확인했다. 지금까지의 적합은 required 문맥만 정확히 합산했으며 required=None이면 전체 블록을 메모리 dictionary에 합산한다. 고정 입력 문맥 projection의 메모리/속도를 새로운 문맥이 생기는 자유 생성 serving으로 일반화할 수 없다. 실제 통합 전 배경 조회 방식과 메모리·지연의 사전 확인이 필요하며, 디스크 dedup SQLite는 추론용 count 조회 backend가 아니다.
- 이번 단계는 실험 제안/근거 확인이며 통합 코드 수정·GPU 작업·재학습·추가 데이터 확대는 시작하지 않았다. 실제 패처 교체 경로의 계약 검사와 작은 고정 입력 비교를 먼저 준비하고, 자유 생성의 배경 조회 제약을 해결한 뒤 확장하는 순서를 권고했다. 기존 체크포인트·환경·작업은 변경하지 않았다.

## 2026-10-25 / LMDB 전체 배경 조회 / 구현 착수

- 사용자가 LMDB 진행을 승인했다. 데이터 추가 확대는 하지 않고 전체 배경 통계를 임의 문맥에서 조회하는 backend를 구현한다. 조회 비용이 실용적으로 작을 수 있다는 의견은 가설이며 아직 BLT 전체 지연으로 검증되지 않았다.
- 국소 경로 확인: CountModel.probabilities가 background/online의 private dictionary를 직접 읽고 있으므로 CountTable.lookup(context)로 카운트 행과 합계를 함께 반환하게 분리했다. 기존 계산 순서와 수식은 바꾸지 않았다. 첫 검증은 기존 count 패처 테스트와 누락 키의 비변경성 테스트다. 이후 LMDB 읽기/변환 및 동일 입력 비교를 연결한다. 패키지 기본 import/기존 backend는 유지한다.

## 2026-10-25 / LMDB / 조회 경계 회귀 검증 및 backend 구현

- 로컬 기본 python3에는 NumPy가 없어 count 테스트 14개 전부 skip됐다. 이는 검증 통과가 아니다. 서버 기존 count_patcher.py SHA256이 직전 측정 코드와 일치함을 확인한 뒤 변경본을 전달했다. 서버 기존 .venv에 lmdb 2.3.0만 추가 설치했고 OPENBLAS_NUM_THREADS=8 count 테스트 14개 모두 0.292초에 통과했다.
- 다음 작은 구현: 선택적 LMDB reader, 기존 블록의 스트리밍 정수 합산 변환, 제한된 행 캐시, 불완전/부분 변환 기본 거부, 원본 해시 검증, 배치별 디스크 보호를 추가한다. 기본 패키지 import는 LMDB를 요구하지 않는다. LMDB state_dict 내장 직렬화는 거부하며 DB를 명시적으로 다시 열어야 한다. 전체 문맥의 확률/엔트로피/경계가 메모리 backend와 정확히 같은지 검증한다. 아직 실제 10GB 변환이나 GPU 실험은 시작하지 않았다.

## 2026-10-25 / LMDB / 정확성 통과 및 실제 블록 사전 측정 준비

- 서버 OPENBLAS_NUM_THREADS=8 count 패처 테스트 15개 모두 0.326초 통과. LMDB와 전체 메모리 테이블의 정수 카운트/확률 배열/엔트로피/순차 경계 정확 일치, 캐시 상한, 누락 문맥, 종료 후 조회 거부, partial/incomplete DB 거부를 확인했다.
- 실제 10GB 첫 블록으로 사전 변환/조회 비용을 측정할 준비를 했다. 전체 블록 변환은 아직 시작하지 않았다. source block hash와 manifest hash를 검증하며, 합산 후에도 토큰별 삽입 순서를 보존해 계산 순서 차이를 피한다. 디스크 보호 실패 시 complete로 표시하기 전 검사를 수행하도록 보강했다.
- CLI 기본 LMDB map 32GiB/주소공간 48GiB/최소 가용 100GiB/출력 100GiB. mmap은 RAM 상주량과 별개로 RLIMIT_AS에 포함되므로 자동 map 확대나 메모리 보호 상향은 하지 않는다. 실제 DB 크기/성능은 사전 측정 전 미확정이다. README에 설치/변환/부분 DB 및 snapshot 제한을 명시했다.

## 2026-10-25 / LMDB / 전체 회귀 통과 및 실제 prefix 실험 시작 준비

- 서버 OPENBLAS_NUM_THREADS=8 unittest discover 전체 28개를 1.658초에 통과(skip 없음), pip check 정상. 추가한 최대 출력 보호 실패 테스트도 미완성 DB 접근을 거부했다. 로컬에는 NumPy/LMDB가 없어 서버 실행 결과를 검증 근거로 삼았다.
- 다음 실행 설정: 새 runs/en-count-lmdb-preflight-20261025-01, detached tmux blt-count-lmdb-preflight-20261025-01. 기존 10GB background_build.json의 첫 블록만 변환(block_limit=1, map 8GiB), 주소공간 48GiB/최소 가용 100GiB/새 산출물 100GiB 보호 유지. 전체 블록 DB와 명확히 구분하며 기존 원본/체크포인트는 변경하지 않는다.
- 변환 성공 시 같은 run의 benchmark.json에 실제 background 문서 앞 4개/문서당 최대 512바이트의 카운트·확률·경계 동등성과 메모리 projected/LMDB cache 0/4096의 warmup 1회·측정 5회 조회/패처 시간을 기록한다. 이는 warmed prefix screening이며 full-source DB/최적 fitted rule/BLT end-to-end 속도 결과가 아니다. 전체 변환의 크기·소요·map 제약은 이 결과 후 판단한다.

## 2026-10-25 / LMDB prefix / manifest 검증 실패와 국소 수정

- 실제 서버 시작 2026-10-24T21:57:37+00:00(한국 10월 25일 06:57:37). 최초 preflight-01은 output DB 생성 전 Background block manifest hash mismatch로 중단됐다. 기존 원본과 DB 데이터는 변경하지 않았다. 실패 로그는 해당 run/stdout.log에 보존했다.
- 실제 서버 함수 inspect 결과 기존 manifest는 json.dumps(sort_keys=True, separators=(",", ":"))의 compact JSON이다. 새 변환기는 기본 공백 JSON만 가정했다. 원본 background_build.json 파일 SHA256 d133f2e4025070fa8e175b8f1120b8e58acb5ab6c708a7cb2b869d921f437e1a는 앞선 완료 보고서와 일치했다. compact manifest ba0c138104e60ab960effc2b4aef5896cb8b8ddc746992f0ee6ca3d54baaff3a도 저장 값과 일치한다.
- 원본 변경이나 해시 검증 생략 없이 compact/default 두 기존 직렬화 형식을 각각 정확 계산해 저장 값과 비교하도록 수정하고 실제 선택 형식을 메타데이터에 기록한다. 합성 회귀에서 두 형식을 모두 사용하도록 추가했다. 첫 로컬 grep/&& 조회는 함수 정의가 그 파일에 없어 후속 SSH가 실행되지 않았으며, 실제 import 함수 직접 조회로 바로잡았다. 다음은 동일 집중 테스트 재실행 후 새 -02 경로에서만 재시도다.

## 2026-10-25 / LMDB prefix / 수정 검증 후 -02 실행

- 수정 후 서버 count 집중 테스트 15개 모두 0.330초 통과. 편집기에서 새 backend/변환기/benchmark 및 변경 count/test 파일 진단 오류 없음. 기존 source code, 문서, 설정 변경 공백 검사도 통과했다.
- 실제 재시작 2026-10-24T21:58:42+00:00(한국 10월 25일 06:58:42), 새 run en-count-lmdb-preflight-20261025-02, tmux blt-count-lmdb-preflight-20261025-02. 첫 블록의 모든 문맥을 변환하고 성공 시 warmed 실제 개발 prefix 비교를 실행한다. map 8GiB/주소공간 48GiB/최소 가용 100GiB/출력 100GiB 및 partial 명시 조건은 동일하다. 이전 -01 로그는 보존했다. 완료·성능 결과는 아직 없다.

## 2026-10-25 / LMDB prefix / 실제 측정 완료·증거 검증

- 서버 2026-10-24T22:01:20+00:00(한국 07:01:20) 완료 신호 확인. 원본 400블록 중 첫 25,005,291 UTF-8 바이트 블록의 모든 12,480,893문맥 행을 142.0596초에 변환했다. DB/lock 합계 838,443,008바이트(약 0.781GiB), 변환 peak RSS 900,857,856바이트(약 859MiB). complete_source=false인 prefix 실험이며 전체 10GB DB가 아니다.
- 실제 기존 background 앞 4개 문서 최대 512바이트씩, 총 2,011 IDs/조회 17,991회/고유 문맥 10,204개에서 정수 카운트·확률 배열·엔트로피가 포함된 경계 결정 정확 일치를 확인했다. 참조는 같은 첫 블록에서 필요한 문맥을 합산한 메모리 테이블이다. warmup 1회 후 5회 중앙값: lookup 메모리 1.3285ms/LMDB cache0 51.7673ms/cache4096 16.8577ms, 패처 전체 메모리 115.8231ms/cache0 170.9558ms/cache4096 139.3480ms. cache4096의 패처 차이는 약 23.525ms/해당 입력 전체로, 전체 BLT 지연 비중은 미측정이다. 캐시 4096개 상한을 유지했고 benchmark peak RSS는 468,410,368바이트였다.
- 정확성 검사와 반복으로 페이지 캐시가 warmed된 작은 prefix 결과다. cold lookup/전체 DB working set/최적 fitted rule/자유 생성/BLT 전체 가속을 주장하지 않는다. DB 크기는 문맥 중복 합산과 B-tree 구성에 의존하므로 첫 블록 크기에 400을 곱해 전체 크기를 확정할 수 없다.
- evidence/english_lmdb_preflight_build_20261025.json SHA256 48be9afe618da4d3d48d1be08e1ce4f2273efe84bb10e552e12c70d22f367632, lookup 보고서 6edbb45bbe5c98d282d8e47ae7bea78d8267db8957f901b33975efcfd1691fe0을 회수하고 서버와 해시 일치 확인. backend c97138309c8f13309965b3a06b50aee931f369b736649e0ca69d12b37b23bddf/benchmark 0835f2deb855dfc7fa6945cd6d29249c690ec57027b7baf03d18e578074c2231 코드 식별자도 보고서와 일치한다. 원문/DB는 서버에 보존한다.
- 다음은 새 en-count-lmdb-full-20261025-01 경로에서 400개 기존 블록의 전체 변환이다. map 32GiB/주소공간 48GiB/최소 가용 100GiB/출력 100GiB/시간 상한 없음, detached tmux. MapFullError/디스크 보호 발생 시 자동 재시도나 한도 상향 없이 보존·보고한다. 원본과 적합 계수는 변경하지 않으며 BLT GPU 실험은 아직 시작하지 않는다.

## 2026-10-25 / LMDB 전체 변환 / 실행 및 초기 진척 확인

- 실제 시작 2026-10-24T22:02:44+00:00(한국 10월 25일 07:02:44), tmux blt-count-lmdb-full-20261025-01, run en-count-lmdb-full-20261025-01. 명령은 OPENBLAS_NUM_THREADS=8 .venv/bin/python -u -m scripts.build_lmdb_background --report runs/en-patcher-bg10gb-diskcpp-20261024-02/background_build.json --output runs/en-count-lmdb-full-20261025-01/counts.lmdb(실제 절대 경로 사용). CLI 기본 map32GiB/주소공간48GiB/최소 가용100GiB/출력100GiB를 유지하며 stdout.log에 배치 진척을 남긴다.
- 서버 22:02:55 UTC 관측: PID 779810 실행 중, 약 10초 경과, RSS 201,044KiB, status building/400블록 선택/누적 1,220,000입력 행/첫 블록 미완료. 초기 DB/lock 합계 152,375,296바이트, df -h 가용 211G. 오류 없음. complete_source=true는 전체 블록을 선택했다는 뜻이며 status가 building이므로 완성된 DB로 사용할 수 없다.
- 사전 보고서 6개 timing 중앙값을 원시 반복으로 재계산해 일치 확인했다. 변경 파일 공백 검사 및 최종 backend/benchmark/test 편집기 오류 없음. 테스트 근거는 전체 28개 통과와 manifest 수정 후 집중 15개 통과다. 기록을 로컬에 갱신했으며 서버 root log를 덮어쓰지 않았다. 전체 변환 완료와 BLT 통합/품질·속도 측정은 아직 남아 있다. 새 데이터 확대·재학습·커밋·푸시는 하지 않았다.

## 2026-10-25 / LMDB 전체 변환 / 9블록 완료 진행 확인

- 서버 2026-10-24T22:34:40+00:00(한국 10월 25일 07:34:40)에 읽기 전용 조회했다. 시작 후 31분 56초, tmux와 PID 779810 유지, 최근 stdout에 오류 없음, counts.report.json은 아직 없다. status building이며 전체 변환과 BLT 실험은 미완료다.
- 400블록 중 9개 완료(블록 기준 2.25%), 완료 블록 원문 합계 225,087,731 UTF-8 바이트(약 0.225GB). 10번째 블록 처리 중 누적 입력 행 116,640,000개이며 이는 블록 간 중복 포함 행 수이지 고유 문맥 수가 아니다. 최근 로그 1.22초 사이 116,570,000행에서 116,640,000행으로 증가해 실제 진행을 확인했다.
- DB/lock 합계 3,480,539,136바이트(약 3.24GiB), 현재 RSS 3,462,028KiB(약 3.30GiB), 가용 디스크 df -h 기준 208G. 프로세스 관측 상태 Dl+, 누적 CPU 10분 17초/평균 CPU 32.2%로 해당 순간 I/O 대기를 포함한다. 단일 관측만으로 전체 병목을 확정하지 않는다. 설정/프로세스/기존 산출물 변경 없이 유지했고 ETA는 재산정하지 않았다.

## 2026-10-25 / LMDB 전체 변환 / 51블록 진행 및 조건부 ETA

- 사용자 진행/종료 시각 문의로 서버 2026-10-25T01:36:17+00:00(한국 10:36:17)에 조회했다. 시작 후 3시간 33분 32초, PID 779810/tmux 유지, 51/400블록 완료(12.75%) 및 52번째 처리 중, 완료 블록 원문 1,275,402,093 UTF-8 바이트(약 1.28GB). 최근 로그 오류/최종 보고서 없음. RSS 10,176,980KiB(약 9.71GiB), 가용 디스크 df -h 기준 202G. 작업/설정 변경 없음.
- 01:36:48 UTC 기존 stdout JSON을 스트리밍 파싱해 블록 완료 전환점을 추출했다. 최신 누적 입력 645,740,000행/전체 중복 포함 5,146,141,302행(12.548%), 경과 12,843.773초, DB/lock 합계 10,493,140,992바이트(약 9.77GiB). 입력 행 수는 고유 문맥 수가 아니다.
- 최근 5/10/20/40블록 평균은 각각 272.31/270.02/274.49/261.94초/블록이다. 각 구간의 실제 행 처리율과 남은 행 수로 계산한 남은 시간은 27.26/27.01/26.79/25.90시간, 한국시간 10월 26일 13:52/13:37/13:23/12:30 예상이다. 전체 평균 단순 외삽은 남은 24.86시간/26일 11:28이지만 최근 속도를 우선해 사용자에게 26일 12~14시를 조건부 시간 전망으로 제시한다. 통계적 신뢰구간/완료 보장이 아니며 이후 문맥·값 크기/디스크 접근 특성 변화에 따라 달라진다.
- 중요한 용량 한계: 최근 5/10/20/40블록의 바이트 증가/입력 행 비율을 남은 행에 선형 외삽하면 최종 약 53.5/54.5/58.1/64.3GiB로 현재 map32GiB를 넘는다. 중복 합산·문맥 분포·페이지 재사용 때문에 이는 측정된 최종 크기나 확정 실패 예측은 아니지만 현재 설정으로 완료를 보장할 수 없는 위험이다. mmap 크기는 RAM 상주량과 달리 주소공간48GiB 보호에 포함되므로 map만 임의 확대할 수 없다. 한도 변경/자동 재시작은 하지 않았고 필요 시 별도 사용자 승인 후 용량/주소공간 또는 분할 방식을 결정해야 한다. BLT 실험은 아직 미실행이다.

## 2026-10-25 / LMDB map 128GiB 제안 / 실제 디스크 여유 확인

- 사용자 저장 공간 문의로 서버 2026-10-25T01:40:07+00:00(한국 10:40:07)에 df -B1/stat/최근 stdout을 읽기 전용 조회했다. 가용 215,786,196,992바이트(약 200.97GiB), data.mdb 논리 크기 10,598,158,336바이트(약 9.87GiB), 실제 할당 stat 20,699,536개 512바이트 블록이다. stdout은 51블록 완료/다음 블록 처리 중이며 오류 없음. 설정/실행 변경은 하지 않았다.
- map 128GiB는 가상 매핑/DB 최대 크기 설정이지 즉시 RAM/디스크 128GiB를 채운다는 뜻이 아니다. 기존 사전 실험에서도 map8GiB에 실제 DB 약 0.781GiB였다. 최근 최종 크기 추정 약 53~64GiB라면 현 DB에서 추가 약 43~54GiB, 다른 사용량이 고정일 때 남는 디스크는 약 147~158GiB로 최소 가용100GiB 조건 안에 있다. 추정치/다른 작업의 공간 소비가 변하면 재판단해야 한다.
- 반대로 실제 DB가 128GiB까지 성장하면 현 시점 대비 추가 약 118GiB가 필요해 가용 약 83GiB로 최소 가용100GiB 조건을 위반한다. 따라서 map128GiB 제안을 실제 산출물128GiB 사용 승인이나 저장 공간 무제한으로 해석하지 않는다. 최소 가용100GiB/산출물 최대100GiB 보호를 유지하고 map/주소공간 변경은 별도 승인 후 수행해야 한다. 현재 설정은 map32GiB/주소공간48GiB 그대로다.

## 2026-10-25 / LMDB 128GiB 전환 / 사용자 승인 작업 사전 계획

- 사용자가 저장 공간은 직접 확보하겠다고 밝히고 map128GiB 전환을 승인했다. 반드시 구현 후 테스트하고, 그 뒤 현재 작업을 중단·재개하며, 착수 전에 log.md/task.md에 내용을 기록하도록 요청했다. 이 항목은 구현/프로세스 변경 전 작성한 계획이며 결과가 아니다. 현재 실행은 아직 중단하지 않았다.
- 1단계 구현: 기존 building DB의 커밋 메타데이터와 원본 report/manifest/config/선택 블록을 검증하는 명시적 resume 옵션을 추가한다. 완료 블록 및 현재 블록에서 이미 커밋한 행을 건너뛰어 중복 합산을 막고, 부분 트랜잭션은 LMDB 원자성에 따라 버린다. SIGTERM/사용자 인터럽트 후에도 마지막 커밋으로 이어지게 하고 이전 포맷 체크포인트도 지원한다. 임의 DB 덮어쓰기/완성 DB 재합산은 거부한다.
- 2단계 검증: 중간 행 커밋 이후 실패/미커밋 행 롤백/블록 경계 중단/더 큰 map 재개가 한 번에 변환한 DB와 모든 정수 행·확률·순차 경계에서 정확히 같은지 확인한다. 원본 불일치와 잘못된 체크포인트·완성 DB 거부, 기존 28개 회귀 및 CLI 옵션도 검사한다. 이 단계까지 기존 변환 프로세스는 계속 둔다.
- 3단계 중단: 검증 통과 후 대상 PID/명령/소스 해시를 다시 확인하고 해당 변환 프로세스만 SIGTERM으로 중단한다. 종료와 writer 해제를 확인하고 DB 메타데이터의 마지막 커밋 위치·파일 식별자를 기록한다. 원본 블록/기존 DB/이전 stdout을 보존하고 삭제·강제 SIGKILL·중복 writer는 사용하지 않는다.
- 4단계 재개: 동일 DB에 --resume/--map-size-gib 128로 새 detached tmux에서 재개한다. mmap을 수용하도록 RLIMIT_AS는 160GiB로 명시 조정하고, 실제 peak RSS는 48GiB 소프트 검사(배치 점검, 커널 강제 상한 아님)를 추가한다. 기존 최소 가용100GiB/산출물100GiB/시간 무제한은 유지한다. 자원 실패 시 자동 재시도/추가 상향은 하지 않는다. resume 이력·원본 식별자·실제 새 map·코드 해시·한도·진척을 로그/보고서에 남긴다.
- 5단계 확인: 재개 직후 DB map/마지막 커밋 위치와 기존 위치 이후 행 증가를 확인하고 log.md/task.md 갱신 후 사용자에게 보고한다. 전체 변환 완료나 BLT 성능 측정은 이 재개 작업의 성공과 구분한다. 데이터 추가 확대·재적합·BLT GPU 실험·커밋·푸시는 이번 범위에 포함하지 않는다.

## 2026-10-25 / LMDB 재개 / 구현 및 첫 집중 검증 완료

- 재개 API/CLI, 기존 포맷 누적 행 위치 복원, 새 블록 내부 위치 저장, 원본·선택·상태 검증, SIGTERM 처리, 주소공간/RSS 분리 검사를 구현했다. 실제 실행 소스는 아직 교체하지 않고 runs/en-count-lmdb-resume-check-20261025-01에 src/scripts/tests 사본을 만들어 검증했다. 기존 PID 779810에 신호를 보내지 않았다.
- 검증 사본의 OPENBLAS_NUM_THREADS=8/PYTHONPATH=해당 src에서 count 집중 테스트 16개가 2.514초에 통과했다. 중간 커밋/미커밋 행 실패/블록 경계/기존 체크포인트 재개 모두 전체 메모리 카운트·확률·경계와 정확 일치했다. 작은 map에서 더 큰 map으로 재개한 행 수가 원본 합계와 일치했다.
- 다음 검증으로 실제 CLI subprocess의 SIGTERM→코드130 중단→map128GiB/주소공간160GiB 재개와 원본/행 위치/선택 불일치·RSS 보호 거부를 추가했다. 이 검증과 전체 회귀 통과 전에는 기존 writer를 계속 유지한다.

## 2026-10-25 / LMDB 재개 / CLI 실제 전환 테스트 통과

- 검증 사본에서 집중 테스트 16개가 0.702초에 통과했다. 실제 subprocess CLI를 3행 커밋 후 SIGTERM으로 중단해 exit130/interrupted 기록을 확인하고, 동일 DB를 map128GiB/주소공간160GiB로 --resume해 정확한 전체 카운트를 얻었다. 실제 env map 크기와 CLI 주소공간 보고 값도 확인했다. 원본 report 바이트 변경/블록 선택 변경/행 합계 불일치/RSS 초과는 거부됐다.
- 기존 실행기는 초기 버전으로 SIGTERM handler가 없으므로 추가로 기본 SIGTERM 종료 중 미커밋 행 롤백 및 legacy 메타데이터 복원 테스트를 추가했다. README에 승인된 재개 명령·세션 시간 한계·RSS 배치 검사의 성격을 명시했다. 다음은 이 테스트와 전체 회귀 실행이다. 기존 실제 writer에는 아직 신호를 보내지 않았다.

## 2026-10-25 / LMDB 128GiB 전환 / 중단 전 전체 검증 통과

- 검증 사본에서 전체 unittest 29개가 2.261초에 통과(skip 없음), pip check 정상. 기본 SIGTERM(-15)으로 미커밋 4번째 행이 있는 프로세스를 종료했을 때 3행 체크포인트만 남았고, legacy 위치 복원 후 전체 정수 카운트가 정확 일치했다. CLI SIGTERM exit130 및 실제 map128GiB/주소공간160GiB 재개도 통과했다.
- 구현과 테스트 단계는 완료했다. 다음 단계부터 실제 PID 779810의 명령/대상 DB/원본 report·코드 식별자를 재확인하고 해당 프로세스만 SIGTERM으로 중단한다. 원본 block/report, counts.lmdb, 기존 stdout.log를 보존한다. 종료 확인 후 이전 소스 사본과 커밋 위치를 기록하고, 테스트한 코드를 배포해 동일 DB를 새 resume tmux/stdout으로 재개한다.

## 2026-10-25 / LMDB 실제 전환 / 종료 신호 전 제어 기능 제약 확인

- PID 779810의 명령·대상 DB와 기존 backend c97138309c8f13309965b3a06b50aee931f369b736649e0ca69d12b37b23bddf, 원본 report d133f2e4025070fa8e175b8f1120b8e58acb5ab6c708a7cb2b869d921f437e1a를 확인했다. 서버 01:48:21 UTC에 53블록 완료/누적 678,090,000행이었고 공백 검사/편집기 오류 없음.
- 이전 backend/CLI 사본을 기존 run의 migration-128gib-01에 보존한 뒤 종료 제어를 시도했으나 프로젝트 .venv Python에 os.pidfd_open이 없어 AttributeError로 실패했다. 이 호출은 signal 전달보다 앞이므로 기존 writer에는 신호를 보내지 않았다. DB/원본/기존 stdout은 그대로다. 다음은 시스템 Python의 pidfd 지원을 확인해 동일 대상만 안전하게 종료하는 것이다. 강제 종료/임의 PID 범위 신호는 사용하지 않는다.

## 2026-10-25 / LMDB 128GiB 전환 / 기존 writer 종료·체크포인트 확보

- 시스템 Python 3.12.3의 pidfd_open/pidfd_send_signal 지원을 확인했고 원래 PID/명령/원본 해시를 다시 검사했다. 2026-10-25T01:49:31.492449+00:00(한국 10:49:31)에 pidfd로 PID 779810만 SIGTERM 종료하고 종료 이벤트를 확인했다. 다른 작업에 신호를 보내거나 SIGKILL을 사용하지 않았다.
- 테스트한 프로젝트 환경에서 종료 후 DB를 읽어 legacy 체크포인트를 검증했다: completed_blocks=54/400, input_rows=681,170,000, 완료 블록 행 합계=681,011,314, 다음 55번째 블록의 커밋 행=158,686, source_utf8_bytes=1,350,459,372. status building/source report·manifest·config/선택이 모두 일치했다.
- data.mdb inode 21646330, 크기 10,865,332,224바이트를 기록했다. 기존 run/migration-128gib-01/stop.json 및 stop_control.json과 이전 backend/CLI 소스 사본을 보존했다. 기존 DB·원본 블록·stdout.log는 삭제/덮어쓰기하지 않았다. 다음은 검증한 backend 0015276d5f20277b8c32f74a1a6d4b4faef545c681e7f16da1df8aa6bc94637a/CLI 69aa23158f2403d86211c338725cf34693ac59e6737605705245f1ca1913bd47를 배포하고 동일 DB를 명시적 --resume으로 여는 것이다.

## 2026-10-25 / LMDB 128GiB 전환 / 배포본 검증 완료

- writer 종료 후 격리 검증 사본의 backend/CLI/count 테스트 세 파일만 live source로 복사했다. backend/CLI SHA256이 위 검증본과 정확히 일치했다. live source에서 OPENBLAS_NUM_THREADS=8, PYTHONPATH=src로 count/재개 unittest 16개를 2.599초에 통과했다.
- 다음은 기존 DB를 blt-count-lmdb-resume128-20261025-01 tmux에서 --resume --map-size-gib 128 --memory-limit-gib 160 --rss-limit-gib 48로 재개한다. 기존 stdout을 보존하고 resume128-20261025-01.stdout.log에 새 세션 출력을 남긴다. 최소 가용100GiB/출력100GiB 보호는 유지한다. 128GiB는 map 한도이며 실제 디스크 할당이나 물리 RAM 제한이 아니다.

## 2026-10-25 / LMDB 128GiB 전환 / 새 재개 writer 시작

- 2026-10-25T01:50:51+00:00 서버 관측 시 blt-count-lmdb-resume128-20261025-01 tmux에 새 PID 781732(python)가 시작됐다. 동일 count.lmdb가 아니라 원래 counts.lmdb 경로를 정확히 사용했고, --resume/map128/주소공간160/RSS48, OPENBLAS_NUM_THREADS=8 및 live src PYTHONPATH를 명시했다. 기존 stdout.log 대신 새 resume128-20261025-01.stdout.log를 사용했다.
- 이것은 프로세스 시작 확인이며 아직 실제 진척 검증 결과가 아니다. 다음은 시작 이벤트의 마지막 커밋 일치, metadata map128GiB, /proc 주소공간160GiB, 동일 DB inode, 원본 동일성 및 누적 입력 행 증가를 확인한다. 전체 변환 완료와 구분한다.

## 2026-10-25 / LMDB 128GiB 전환 / 동일 DB 재개·실제 진척 검증 완료

- 재개 시작 이벤트 시각 2026-10-25T01:50:51.948874+00:00(한국 10:50:51). 시작 이벤트의 completed_blocks=54/input_rows=681,170,000/current_block_rows=158,686이 종료 체크포인트와 정확히 일치했고 data.mdb inode 21646330도 유지됐다. backend/code/source report/manifest/config/전체400블록 선택이 검증한 값과 일치했다.
- 2026-10-25T01:51:20.740197+00:00(한국 10:51:20)에 PID 781732가 살아 있고 status building이었다. 체크포인트는 input_rows=682,390,000(+1,220,000 새 커밋), completed_input_rows=681,011,314/current_block_rows=1,378,686으로 합계 및 블록 위치 검증을 통과했다. 이는 실제 재개와 행 증가 확인이며 전체 DB의 최종 정확성 검증은 아직 아니다.
- DB metadata map_size_bytes=137,438,953,472(128GiB), /proc Max address space soft=171,798,691,840(160GiB), hard unlimited를 확인했다. VmRSS 10,256,532KiB(약9.78GiB), VmSize 134,656,372KiB였다. RSS48GiB는 배치별 peak 검사이며 커널 물리메모리 제한이 아니다. 최소 가용100GiB/출력100GiB 보호도 그대로다.
- 실제 검사 결과는 기존 run/migration-128gib-01/resume_validation.json에 기록했다. 실행 tmux blt-count-lmdb-resume128-20261025-01, 새 stdout은 기존 run/resume128-20261025-01.stdout.log다. 이전 stdout/체크포인트/소스 사본을 보존했다.
- 사용자 요청의 사전 기록 → 구현 → 전체29개 테스트/pip check → 기존 writer 중단 → 배포본16개 테스트 → 동일 DB 128GiB 재개 → 실제 진척 확인을 마쳤다. 전체 변환은 계속 실행 중이며 BLT GPU 실험은 시작하지 않았다. 다음은 변환 완료/보호 조건에 의한 종료를 관측하고, 완료 보고서 검증 후 승인된 BLT 연동 작업으로 넘어가는 것이다. 저장 공간 확보는 사용자가 담당한다.

## 2026-10-25 / LMDB 128GiB 변환 / 재개 후 상태 확인

- 서버 관측 2026-10-25T02:02:45+00:00(한국 11:02:45): PID 781732 생존, 재개 경과 약11분53초, status building. 56/400블록 완료 후 57번째 블록 처리 중이다. 최신 연속 로그의 input_rows가 714,240,000→714,250,000으로 증가했고, 재개 시작 681,170,000 대비 33,080,000행 추가 처리됐다. 전체 선언 행 5,146,141,302 기준 약13.9%다.
- output_bytes=11,179,245,568(약10.41GiB), RSS=10,798,960KiB(약10.30GiB), 디스크 가용 df 표시201GiB. map128GiB/RSS 검사48GiB/최소 가용100GiB/출력100GiB 설정은 유지된다. 재개 stdout에서 Traceback/MemoryError/MapFullError/MDB_MAP_FULL/No space left/RuntimeError 패턴이 발견되지 않았다.
- 관측 시 정상 진행 근거는 실제 커밋 증가와 살아 있는 writer이며, 이후 완료 보장은 아니다. 프로세스·설정은 변경하지 않았다. 다음은 변환 완료 또는 보호 조건 종료를 확인하는 것이다.

## 2026-10-26 / LMDB 전체 변환 / 진행률 86.35% 확인

- 읽기 전용 서버 조회: 2026-10-26T07:08:11+00:00(한국 16:08:11)에 PID 781732 생존, 재개 경과 29시간17분, status building. 연속 로그 input_rows=4,442,370,000→4,442,380,000으로 커밋 증가를 확인했다. 346/400블록 완료 후 347번째 처리 중이며 완료 보고서는 아직 없다. 보고서 부재는 진행 중 상태와 부합하며 그 자체로 실패가 아니다.
- 2026-10-26T07:08:52.002201+00:00(한국 16:08:52)에 최신 stdout 누적 4,443,750,000/5,146,141,302행, 진행률 86.3511%, output 약33.45GiB를 확인했다. 최근 10,000줄에서 Traceback/MemoryError/MapFullError/MDB_MAP_FULL/No space left/RuntimeError 패턴이 발견되지 않았다. RSS=35,057,168KiB(약33.43GiB), df 가용352GiB로 RSS 검사48GiB/최소 가용100GiB 조건 이내다. 프로세스·설정 변경은 없다.
- 최근 899.84초 및 1800.11초 구간의 실제 처리량은 각각 약35,662/36,165행/초다. 이 속도 유지 시 남은 시간 약5.47/5.40시간, 완료 예상은 한국시간 오늘 21:37/21:32다. 이는 처리 속도에 따른 조건부 추정이며 완료 보장이 아니고, 앞선 10월26일 12~14시 추정은 현 관측으로 더 이상 유효하지 않다.
- 다음은 전체 변환 완료 또는 보호 조건 종료를 확인하고 완료 보고서를 검증하는 것이다. 이번 조회는 전체 DB 정확성 검증이나 BLT 실행이 아니다.

## 2026-10-27 / LMDB 전체 변환 / 100% 완료 확인

- 서버 관측 2026-10-27T10:38:26+00:00(한국 19:38:26)에 기존 PID 781732는 종료됐으며, 새 stdout 마지막 결과와 counts.report.json 모두 status complete/400블록 완료였다. 완료 보고서 수정 시각은 2026-10-26T21:38:20.233873+09:00다. 이는 파일 수정 시각 관측이며 별도로 저장된 프로세스 종료 시각은 아니다.
- 2026-10-27T10:38:49.741080+00:00에 DB를 readonly로 열어 메타데이터와 보고서의 status/completed_blocks/input_rows/completed_input_rows/current_block_rows/source report·manifest 해시/map 크기를 대조해 모두 일치했다. 400/400블록, input_rows=completed_input_rows=5,146,141,302, current_block_rows=0이며 원본400블록의 선언 contexts 합계와 정확히 일치했다. 원본 report SHA256도 기존 d133f2e4025070fa8e175b8f1120b8e58acb5ab6c708a7cb2b869d921f437e1a와 일치했다.
- 고유 컨텍스트 579,634,386개가 실제 LMDB entry 수(메타데이터 1개 제외)와 일치했다. 최종 output_bytes=39,354,662,912(약36.65GiB), 재개 세션 elapsed_seconds=125,247.56(약34시간47분), 해당 세션 peak RSS=37,476,298,752바이트(약34.90GiB), 가용 디스크 df 표시349GiB다. 재개 전 세션을 포함한 전체 실행 시간/전체 peak로 해석하지 않는다. map128GiB/주소공간160GiB 및 기존 보호 설정은 보고서에 유지됐다.
- 원격 산출물: runs/en-count-lmdb-full-20261025-01/counts.report.json, counts.lmdb, resume128-20261025-01.stdout.log. 이번 조회는 프로세스·원본·DB 설정을 바꾸지 않았다. 완료 상태/행 합계/컨텍스트 개수 교차 검증은 통과했지만 전체 개별 카운트 재계산이나 BLT GPU 연동·품질·속도 측정은 수행하지 않았다. 다음 단계는 완료된 LMDB 배경을 사용하는 BLT 연동 실험 범위를 정하는 것이다.

## 2026-10-27 / BLT count 패처 연동 / 착수 계획

- 사용자 진행 승인에 따라 완성된 LMDB와 기존10GB fit 규칙을 실제 BLT에 opt-in으로 연결한다. 기존 guarded cache, 원본 BLT 소스/가중치/데이터/다른 작업은 변경하지 않는다. 서버 GPU 관측상 사용1MiB/가용32087MiB이며 실행 중인 학습 작업은 발견하지 않았다.
- 확인한 지역 가설: 기존 decision_patch_lengths가 가상 다음 바이트를 포함한 길이를 계산하므로 실제 BltPatcher 반환 계약에 맞춘 임시 어댑터로 BLT 본체를 실행할 수 있다. batch1/비패딩/추론 전용으로 시작하고 문서 간 상태를 초기화한다. 접두부 확장 시 새 ID만 관측하고, 재실행·분기·짧아진 입력은 상태를 재구성한다. 학습 규칙/threshold는 기존 F1 선택을 그대로 쓰며 새 F0.5 최적화나 재적합은 하지 않는다.
- 순서: 어댑터/실제 계약 확인 및 한 번에 계산한 rollout 대비 증분 경계 테스트 → 서버 집중/회귀 테스트 → 원본 BLT와 후보의 작은 고정 입력 forward·짧은 greedy 생성 실행 → 가능하면 동일 입력 BPB/생성시간/메모리 진단. 캐시 재사용은 비활성화하고 패처 교체만 분리한다. 출력 동일성은 채택 조건이 아니며 기존 A100 cache parity를 인용해 보장하지 않는다.
- 각 단계 결과/제약/블로커를 기록한다. 실제 모델 경로/로딩 계약 및 자원 상한은 기존 preflight에서 확인해 명시하며 모델 파일을 이 패키지에 복사하지 않는다. 결과는 좁은 smoke 검증으로 보고하고 전체 데이터 품질/속도 개선으로 일반화하지 않는다.

## 2026-10-27 / BLT count 패처 연동 / 증분 어댑터 집중 검증 통과

- 실제 BLT 본체가 patch_lengths를 직접 받으므로 처음 제안한 임시 forward 교체 대신 명시적 입력 주입을 선택했다. CountPatcherAdapter는 package 독립성을 유지하고 기본 API에 import되지 않는다. batch1/비패딩/추론 모드·정수 ID를 검사하며, 완전 접두부에서 새 ID만 관측한다. 문서 reset을 제공하고 다른 분기/짧아진 입력은 재구성한다. 최대 패치 길이의 선택적 분할도 제공한다.
- 서버 live source에서 새 집중 unittest 2개가 0.028초에 통과했다. 접두부 확장/동일 입력 재실행/분기/짧아짐/reset 후 경계가 매번 fresh rollout과 같고 패치 길이 합계가 입력 길이+가상 슬롯1이었다. 잘못된 입력/추론 모드 밖 호출 거부와 길이 상한도 통과했다.
- 다음은 기존 모델 로딩 및 max_patch_length 처리 계약을 확인한 smoke 실행기다. 실제 LMDB/학습 규칙으로 forward 및 짧은 greedy 생성을 비교하고, 후보와 원래 패처 각각의 teacher-forced BPB·시간·메모리를 작은 고정 입력에서 측정한다. 아직 GPU smoke 결과는 없다.

## 2026-10-27 / BLT count 패처 연동 / smoke CLI·전체 회귀 통과

- scripts/smoke_blt_count_patcher.py를 추가했다. 저장된 selected_rule(threshold .375)을 재사용하고 fit/LMDB의 config·원본 report 해시를 대조한다. 원래 패처와 후보 각각 동일한 합성 문자열3개에서 BF16 OSC eager forward/BPB 및 최대16개 새 ID greedy 생성을 측정하며, 후보 길이를 fresh rollout과 비교한다. 초기 warmup 후 측정하며 생성시간은 CPU 조회/텐서 전송을 포함하고 모델 로딩은 제외한다. 원본 모델/프로젝트를 수정하거나 캐시를 활성화하지 않는다.
- 서버 --help import/CLI 검사 및 전체 unittest 31개가 2.184초에 통과했다. 기본 API/기존 LMDB 재개/데이터 준비 회귀도 통과했다. 실제 모델의 max_patch_length=None을 기존 preflight에서 확인했다.
- 다음 GPU smoke는 기존 blt-1b-hf-own 변환 모델과 완료된 10GB LMDB로 실행한다. 테스트 통과는 아직 실제 모델 연동 성공이나 품질·속도 개선을 의미하지 않는다.

## 2026-10-27 / BLT count 패처 연동 / 실제 배경 출처 검사·GPU 실행 설정

- LMDBCountTable의 공개 metadata를 사용하도록 실행기를 좁게 보완했다. 실제 완료 LMDB metadata.source_report_sha256과 10GB fit.background_report_sha256 일치 검사가 통과했고 수정본 CLI도 통과했다. 내부 속성을 추정해 접근하지 않는다.
- 모델은 /home/itcmaster/projects/phdq3/artifacts/converted/blt-1b-hf-own, conversion report는 기존 english_patcher_pilot.json에 기록된 /home/itcmaster/projects/phdq3/blt_hf_checks/manifests/conversion_B_20260915.json을 사용한다. 원본 loader가 가중치 해시/누락·추가 키를 검사한다.
- 실행 예산: GPU0/BF16 OSC eager, CPU/OpenBLAS8, batch1, 합성 입력3개, 모델당 입력별 최대16개 새 ID, 전체 timeout600초, 캐시 재사용 없음. CUDA 가상주소공간 제약을 임의 적용하지 않으며 메모리 peak를 기록한다. 실패 시 결과를 보존하고 자동 재시도하지 않는다. 출력은 별도 runs/en-blt-count-smoke-20261027-01/report.json과 stdout.log이며 기존 모델·DB·보고서를 덮어쓰지 않는다.

## 2026-10-27 / BLT count 패처 연동 / 실제 모델 smoke 실행 통과

- 실행 직전 GPU0 사용1MiB/가용32087MiB를 확인했다. 기존 loader의510개 가중치 로드 후 completed_cases 1/2/3을 출력하고 실행 명령이 exit0으로 종료했다. timeout600초 안에 합성 입력3개에서 원래 패처/완료 LMDB count 패처 각각 forward 및 최대16개 ID 생성이 완료됐다.
- 실행기는 각 forward의 유한 로짓과 후보 패치 길이의 fresh rollout 일치를 검사했다. 기본 모델이나 BLT 메서드를 수정하지 않고 명시적 patch_lengths 입력만 사용했다. 다음은 저장 report의 status/BPB/시간/메모리/출력 상태를 확인하고 작은 증거 JSON을 보존하는 것이다. 이 단계의 성공은 GPU 연결·실행 smoke 통과이지 품질/속도 개선 채택 결과가 아니다.

- 결과 조회용 SSH 명령의 셸 인용이 닫히지 않아 로컬 continuation prompt에서 대기했다. Ctrl-C로 취소했으며 그 명령의 원격 조회/복사는 실행되지 않았다. 이미 exit0으로 종료한 GPU smoke 및 저장 보고서는 영향 없다. 편집기 진단은 새 Python 세 파일 모두 오류 없음이었다. 다음은 단순 scp로 기존 보고서만 보존해 읽는 것이며 GPU 실행을 반복하지 않는다.

## 2026-10-27 / BLT count 패처 연동 / 실측 결과·증거 보존 완료

- 기존 보고서를 evidence/english_blt_count_smoke_20261027.json으로 보존했다. SHA256=24b6da06838d0c2c9e62aa512fed00b4898eb98582a8e0f9c344b07bb6d2d7ed, status passed/3 cases다. JSON 일관성 검사에서 모든 BPB 유한/6개 생성 모두16 ID·유효 UTF-8/후보 길이 합계가 입력 길이+1임을 통과했다.
- 합성 입력은 23/16/19바이트(합계58)이며 바이트 가중 BPB는 원래2.2823763406642223 대 count2.293546136437645로 후보가 소폭 나빴다. 16개 ID 생성시간 중앙값은 원래0.22348135383799672초 대 count0.17298005614429712초였다. 각 입력·모드1회/고정 원래→후보 순서/워밍된 페이지·조회 캐시이므로 속도 개선/일반 품질 채택 판단을 하지 않는다.
- peak CUDA allocated는 원래약8.639714GiB/후보약8.639739GiB, 동일 프로세스 peak host RSS 약9.453GiB였다. 원래 neural patcher 가중치는 모델에 계속 상주하므로 제거에 따른 메모리 절감 측정이 아니다. 첫 문장·다중바이트 입력의 생성 ID는 두 모드가 같았으나 반복 입력은 달랐고, 모두 EOS 없이16 ID 상한으로 끝났다. 출력 동등성/종료까지 완성된 생성은 검증되지 않았다.
- docs/INTEGRATION.md에 opt-in 직접 주입 API, 문서 reset, CPU 동기화 비용, 실행기 인자 및 결과 한계를 기록했다. 기존 기본 API/원본 BLT/가중치/LMDB/기존 작업은 보존했다. 사용자 요청의 실제 BLT 연결과 작은 forward·생성 검증은 마쳤다. 다음 연구 단계는 동일한 고정 평가 입력에서 긴 문맥 BPB 및 EOS까지의 생성·반복 시간 측정이며, 현재 결과만으로 확대 실행이나 모델 재학습을 시작하지 않는다.
- 최종 git diff --check가 통과했고 증거 report에 기록된 smoke 실행기/어댑터/LMDB reader/count 모델 네 파일의 SHA256이 현재 로컬 구현과 모두 일치했다. 서버에서 검증한 소스와 현재 구현이 같음을 확인했다. 기본 API를 포함한 전체31개 회귀 통과 및 Python 세 파일 편집기 오류 없음 결과도 유지된다.

## 2026-10-27 / BLT count 확대 검증 / 실행 전 계획

- 사용자 요청: 긴 문맥, EOS까지 생성, 반복 측정을 실제로 검증한다. 기존 smoke 실행기를 확장하고 기본 작은 smoke 옵션은 유지한다. 완료 LMDB/학습 규칙/원본1B/BF16 OSC eager/batch1/no-cache는 고정한다. 기존 모델·DB·작업은 변경하지 않는다.
- 긴 문맥: 기존 학습 선택에 사용한 validation label cache의 계약 및 fit label-report 해시를 확인하고, 첫64개 첫 chunk 안에서 512/1024/2048 ID 길이를 충족하는 문서2개씩 선택해 BPB를 측정한다. 원문/ID는 로컬 증거에 복사하지 않고 소스 해시·길이·측정값만 보존한다. 이는 재사용 validation 진단이며 미사용 heldout 품질 추정은 아니다. 최대 문맥 설정4096을 확인했다.
- 반복: 각 입력/모드를3회, 모드 순서를 교대하고 실제 입력별 warmup 후 forward 및 생성 p50/p95·개별 시간·메모리를 기록한다. 각 문서/반복의 온라인 count를 reset하고 동일 모드 반복의 BPB·생성 ID 재현성을 검사한다. 긴 후보 경계는 fresh rollout과 비교한다.
- 생성: 기존 합성 입력3개에 더해 BOS+source+EOS의 기존 BLT 프롬프트 규약을 작은 합성2개에서 확인한다. 자연 EOS를 포함해 종료하며 강제 EOS/임계값 변경/재학습은 없다. 최대 새 ID512, 전체 timeout1200초를 보호 상한으로 두고 미도달은 max_new_tokens로 별도 실패/미검증 집계한다. EOS 종료·상한 종료 helper를 합성 로짓 테스트로 먼저 검증한다.
- GPU0/CPU8/OpenBLAS8, 모델 로드 제외·CPU 조회/동기화 포함 시간, 생성 길이가 다르면 총 시간만으로 속도 비교하지 않는다. 출력은 별도 runs/en-blt-count-extended-20261027-01에 보존한다. 실패 시 로그를 기록하며 자동 상한 확대나 자원 재시도는 하지 않는다. 서버 착수 관측 GPU 사용1MiB/가용32087MiB이며 진행 중인 학습은 발견하지 않았다.

## 2026-10-27 / BLT count 확대 검증 / 종료 처리·실제 긴 입력 검사 통과

- 집중 테스트4개가 첫 helper 추가 후0.011초, 반복 실행기 연결 후0.006초에 통과했다. 자연 ID2가 나오면 즉시 멈추고 EOS를 출력에 포함하며, 상한 도달과 구분한다. 금지 ID0/1/3 억제, 입력 무변경, p50/p95 계산, 계약 불일치/길이 부족 거부도 검사했다.
- 실제 label report 해시가 fit과 일치했고 첫64개 첫 chunk의 계약 검사를 통과했다. 512 ID는 문서0/1, 1024·2048 ID는 문서44/45를 사용한다. 총6개 길이별 입력이지만 서로 겹치는 접두부가 있으므로6개 독립 문서가 아니다. 원문/ID는 보고서에 저장하지 않는다.
- 계획 정정: 원본 encode_prompt는 BOS+source+SEPARATOR 문자열을 사용한다. 처음 계획의 BOS+source+EOS 추정은 코드 확인으로 폐기했다. 실제 GEC 입력은 원본 함수를 그대로 호출하며 EOS를 프롬프트에 임의 주입하지 않는다.
- 실행기에 실제 입력별 warmup/모드 순서 교대3회/BPB·생성 ID 반복 일치/자연 EOS와 상한 상태/진행 JSON 체크포인트를 연결했다. 생성은 양 모드 동일 logits_to_keep=1을 명시하므로 앞선 logits_to_keep=0 단일 smoke 시간과 직접 비교하지 않는다. 다음은 전체 회귀 및 GPU 확대 검증이다.

## 2026-10-27 / BLT count 확대 검증 / 전체 회귀 통과·실행 진입

- 서버 전체 unittest33개가1.415초에 통과했다. 수정 Python 두 파일의 편집기 오류 없음, git diff --check 정상이다. 기존 기본 API/LMDB 재개/데이터 준비 테스트도 유지됐다.
- 별도 en-blt-count-extended-20261027-01에서 --extended --repeats 3 --max-new-tokens 512, 기존 label_generation.json/labels/validation 경로로 실행한다. 긴 입력6개와 기존 합성3개+원본 encode_prompt 합성2개가 대상이다. timeout1200초, GPU0/BF16/CPU8/OpenBLAS8 및 기존1B/학습규칙/완료 LMDB는 앞선 계획과 같다. stdout과 진행 체크포인트를 보존하며 EOS 미도달이 있으면 completed_with_generation_limits로 표시한다. 아직 GPU 결과가 아니다.

## 2026-10-27 / BLT count 확대 검증 / 실제 실행 완료·EOS 미도달 관측

- 서버 실행 시작 관측2026-10-27T11:03:06+00:00. GPU0 사용1MiB/가용32087MiB 확인 후 기존 loader의510개 가중치 로드 및 긴 입력6개(512/1024/2048 ID 각각2개)가 완료됐다. 이어 합성/GEC 프롬프트5개×모드2개×3회=30개 생성 관측을 출력하고 실행 명령 exit0으로 종료했다. timeout1200초 이내이며 재시도/한도 변경은 없었다.
- stdout의30개 생성은 모두 new_ids512/stop_reason max_new_tokens였고 원래 패처15회·후보15회 모두 자연 EOS를 얻지 못했다. 실행기는 동일 입력/모드의 반복 BPB·생성 ID 불일치 시 예외를 내므로 완료된 항목은 이 재현성 검사를 통과했다. EOS 종료 검증은 미완료/미충족이며 exit0을 전체 기준 통과로 해석하지 않는다.
- 다음은 최종 report와 진행 파일 상태, 긴 입력 BPB/반복 p50·p95/메모리/출력 UTF-8/해시를 대조하고 작은 생성 결과 JSON만 보존한다. 현 체크포인트·프롬프트에서 원래 패처도 EOS 미도달이라는 관측까지만 확정하며 원인(기반 모델 특성/프롬프트 적합성 등)을 단정하지 않는다. EOS를 강제로 생성하거나 모델/생성 상한을 바꾸지 않는다.

## 2026-10-27 / BLT count 확대 검증 / 실측·재현성 검사 완료 및 EOS 기준 미충족

- evidence/english_blt_count_extended_20261027.json(약461KiB), SHA256=027a84b445f082ae24cf5cdd7bd7048dceeeceac2e0af3aee0086b0fd439dcfb를 보존했다. status completed_with_generation_limits, 긴 입력6개/생성 프롬프트5개이며 기준 미충족을 passed와 구분했다. 원본 검증 데이터/모델/DB는 복사하지 않았다.
- JSON 검사에서 총11개 입력·모드별 BPB3회가 각각 정확 일치/유한하고 후보 가상 슬롯 길이 합계가 입력 길이+1이었다. 생성5개×모드2개×3회의 ID가 동일 모드 안에서 정확히 재현됐으며, 모두512 ID/상한 종료/유효 UTF-8였다. 보고서의 실행기/어댑터/LMDB reader/count 모델 네 파일 SHA256이 현재 구현과 일치했다.
- 긴 입력은 총7162개의 평가 바이트(중복 접두부 포함), 원문4개에서 길이별2개이며 독립 heldout가 아니다. 512/1024/2048 ID별 BPB(원래→count)는 0.830686953→0.827806372 / 0.781391458→0.780962920 / 0.762911987→0.763027924다. 짧은 두 길이는 소폭 개선, 2048은 소폭 악화로 일반 품질 개선을 결론 내리지 않는다.
- 같은 길이 입력2개의 반복6개를 합친 prefill 시간 p50(원래→count)은 17.506→54.143ms / 26.719→124.114ms / 68.943→262.307ms였다. 후보의 긴 문맥 초기 처리는 약3~5배 느렸다. CPU count/LMDB 순차 처리·전송 및 loss 계산을 포함하며 병목 분리 프로파일은 아직 하지 않았다.
- 생성15회/모드 전체 시간 중앙값(원래→count)은 7.978473865→6.333843084초, 각512 ID다. 프롬프트별 p50/p95: plain 원래7.469/7.483·후보6.254/6.255초; repeat 7.455/7.457·6.353/6.383초; multibyte 7.978/7.979·6.051/6.052초; gec_short 8.090/8.094·6.373/6.378초; gec_complete 8.037/8.038·6.334/6.335초. 3회뿐인 p95/작은 고정 프롬프트/워밍된 상태/단일GPU 측정이며 일반 속도 개선이나 EOS까지의 생성 시간으로 해석하지 않는다.
- EOS 도달은 원래0/15·후보0/15다. EOS가 나올 때 멈추는 코드 경로는 단위 테스트를 통과했지만 실제 모델의 완성된 자연 종료는 검증되지 않았다. 먼저 원래 체크포인트/프롬프트의 종료 동작을 점검해야 하며 현재 결과로 후보의 EOS 회귀를 단정하지 않는다. 상한을 임의 늘리거나 강제 종료 토큰을 넣지 않았다.
- 긴 입력 peak CUDA allocated는 원래최대9.378334GiB·후보9.377039GiB, 프로세스 peak host RSS9.454525GiB였다. 원래 패처 가중치는 계속 상주한다. docs/INTEGRATION.md에 실행 옵션·표·측정 정의·EOS 제약을 추가했다. 이번 요청의 실행과 결과 검증을 완료했으며 자연 EOS 기준은 명시적 미충족으로 남긴다.

## 2026-10-27 / EOS 상한 확대 / 실행 전 계획

- 사용자가 생성 상한 확대 실험을 제안·승인했다. 이전 실행은 모두512개 새 ID 상한 종료였으며, 이는 상한을 늘리면 EOS가 반드시 나온다는 증거는 아니다. 새 상한1024개, 기존5개 프롬프트/양 모드 각1회로 자연 EOS 진단을 실행한다. 기존1B/학습규칙/완료 LMDB/프롬프트/금지 ID/무캐시/BF16/GPU0/CPU8/OpenBLAS8은 유지한다. 시간 비교·재현성의 추가 반복 검증이 아니라 종료 여부 확인이다.
- 기존 --extended 실행기의 --max-new-tokens 1024 --repeats 1을 사용한다. 부수적으로 동일한 긴 문맥6개 forward 검사도1회 수행한다. 전체 timeout1200초 및 모델 문맥 한도4096은 유지하고 실행기가 prompt+생성 상한을 검사한다. 코드·가중치·원본 데이터·기존 결과를 변경하지 않는다. 1회 p95를 신뢰할 통계로 해석하지 않는다.
- 별도 runs/en-blt-count-eos1024-20261027-01에 report/progress/stdout을 남긴다. 자연 EOS면 즉시 종료하며 강제 EOS는 넣지 않는다. 미도달/상한/시간제한/실패는 구분해 보존하고 자동 상향·재시도하지 않는다. 서버 사전 관측2026-10-27T11:15:06+00:00에 GPU 사용1MiB/가용32087MiB이며 학습 작업은 발견하지 않았다.

## 2026-10-27 / EOS 상한1024 / 실제 실행 완료·자연 EOS 미도달

- 서버 실행 시작 관측2026-10-27T11:15:38+00:00. 기존1B/fit/완료 LMDB/실행기 그대로 --max-new-tokens 1024 --repeats 1로 실행했고 timeout1200초 이내 exit0으로 종료했다. 부수 긴 입력6개 forward 및 생성5개×모드2개=10개가 완료됐다.
- stdout 기준 양 모드 각각0/5 자연 EOS, 모두1024 ID/stop_reason max_new_tokens였다. 상한을 두 배 늘려도 종료 기준을 충족하지 않았고, 단순히512 ID가 부족했던 것이라는 결론은 뒷받침되지 않았다. 더 긴 상한에서 언젠가 EOS가 나올지 또는 원래 모델/프롬프트의 종료 문제가 있는지는 아직 미확정이다. 자동 추가 확대/재시도/강제 EOS는 하지 않았다.
- 다음은 최종 report와 첫512 ID가 이전512 상한 실행과 일치하는지 교차 검사하고 증거를 보존한다. 단일 실행의 시간·p95 또는 실행기 내 반복 재현성 표시를 새 반복 측정 근거로 해석하지 않는다.

## 2026-10-27 / EOS 상한1024 / 결과 교차 검증·증거 보존 완료

- evidence/english_blt_count_eos1024_20261027.json(약428KiB), SHA256=2abf15bdad483e8f3821bd9f8730600dafb74dae85f982dba89107dd221c8420를 보존했다. status completed_with_generation_limits, protocol max_new_tokens1024/repeats1/동일5개 프롬프트를 확인했다. 양 모드 각각EOS0/5·전부1024 ID 상한 종료이며 전체10개 출력 모두 유효 UTF-8다.
- 전부 기존512 상한 보고서와 prompt ID 및 생성 첫512 ID가 정확히 일치했다. 현재 로컬 실행기/어댑터/LMDB reader/count 모델의 SHA256도 보고서와 일치했다. 생성 상한만 늘렸을 때 앞부분이 바뀌거나 기존 EOS가 누락된 경우는 발견하지 않았다.
- 단일 생성 시간은 원래16.98~19.55초·후보13.38~14.98초였으나 반복 성능 측정이나 EOS까지의 시간은 아니다. 새 코드 변경은 없었고 이전33개 회귀 이후 같은 실행기 옵션만 변경했다. 모델/학습규칙/원본/완료 DB/이전 보고서는 보존했다.
- 사용자 요청의 상한 확대 진단은 완료했지만 자연 EOS 기준은 여전히 미충족이다. 512 ID 상한이 실제 종료 사유였던 것은 맞으나 그 뒤 곧 EOS가 나왔을 것이라는 해석은1024 실험으로 지지되지 않는다. 다음은 원래 체크포인트와 프롬프트의 종료 동작을 점검하는 것이며 추가 상향·EOS 강제·재학습을 자동 수행하지 않는다.

## 2026-10-27 / 종료 동작 진단 / 증상·실행 전 계획

- 사용자 요청에 따라 양 모드 공통 종료 경로를 점검한다. 보존 출력에서 plain은 같은 문장 반복, multibyte는 양 모드 모두 ID14(개행)1024회, GEC 입력은 source/구분 문자열 반복을 확인했다. 단순히 정상 장문 생성이 끝나지 않은 경우와 구분한다.
- 원본 greedy helper는 ID0/1/3만 억제하고 ID2를 선택하면 즉시 break한다. 원본 data_adapter의 BOS1/EOS2/byte+4 및 SEPARATOR 문자열을 확인했다. 변환 보고서의 출처는 facebook/blt-1b revision8134b32f0b1d25d1248c30e8c7bdfd442d3bb380/별도facebook/blt-entropy다. 현재 로드 경로는 GEC 미세조정 체크포인트가 아니라 이 변환 모델이다. 오래된 변환 보고서의 converted_unvalidated 표시는 후속 검증 여부와 별개이므로 현재 변환 실패 근거로 사용하지 않는다.
- 별도 generation_config.json 조회는 FileNotFoundError였다. 파일 부재 자체가 문제인지 추정하지 않고 런타임 model.generation_config/토크나이저 특수 ID를 확인한다. 모델/학습규칙/원본/생성 상한은 변경하지 않는다.
- 가설: 종료 helper가 EOS를 놓치는 것보다 기반 모델이 반복 continuation을 선호하고 EOS를 낮게 평가할 가능성이 있다. 판별 체크는 (1)원래 HF model.generate를 같은5개 프롬프트에서128 ID만 실행해 수동 루프의 앞128 ID와 대조 (2)보존1024 ID 출력의 생성 위치0/16/128/512/1024에서 양 모드 EOS 확률·허용 토큰 중 순위·상위 ID·로짓 차이를 측정 (3)EOS가 억제되지 않는 통계 helper 단위 테스트다.
- 별도 scripts/diagnose_blt_termination.py 및 en-blt-termination-20261027-01 출력으로 재현성을 확보한다. GPU0/BF16 OSC eager/CPU8/OpenBLAS8/timeout600초, 캐시 없음. 원래 체크포인트·프롬프트 고정, 강제 EOS/반복 페널티/상한 확대/재학습/모델 교체는 하지 않는다. 결과는 상태·생성 경로·checkpoint 적합성에 대해 측정한 범위만 결론 낸다.

## 2026-10-27 / 종료 동작 진단 / 점수 helper·전체 회귀 통과

- scripts/diagnose_blt_termination.py를 추가했다. 저장1024 ID 보고서의 체크포인트/변환 보고서/원본 BLT 코드/LMDB 출처를 검증하고 런타임 특수 ID·generation defaults를 기록한다. 원래 HF128 ID 생성5건을 수동 경로와 대조하고 양 모드×5프롬프트×5위치의 EOS 점수를 기록한다.
- EOS 통계 helper는 ID0/1/3만 억제하고 EOS2가 허용 상태인지·순위·확률·로짓 차이를 검사한다. EOS가 허용 중 최고 점수일 때 실제 선택이2가 되는 테스트를 포함해 집중5개가0.015초, 전체 회귀34개가1.183초에 통과했다. 생성 루프/모델 동작 자체는 변경하지 않았다.
- 다음은 timeout600초로 GPU 진단을 실행한다. 기존 EOS 미도달/생성 반복 관측의 원인과 조치에 대한 결론은 런타임 대조 결과 확인 뒤 기록한다.

## 2026-10-27 / 종료 동작 진단 / HF 대조 실행 완료

- 서버 실행 시작 관측2026-10-27T11:29:16+00:00. GPU0 사용128MiB 미만 조건에서만 실행했고 기존 가중치510개 로드 후5개 프롬프트의 hf_matches_manual true를 출력, timeout600초 내 exit0으로 종료했다. HF model.generate와 기존 수동 생성의 앞128 ID가5/5 정확히 일치했다.
- 양 모드의 저장 경로에서5개 위치씩 EOS 점수를 기록했다. 아직 수치/설정은 보고서에서 대조하기 전이므로 EOS 억제 여부와 원인 결론은 다음 분석 단계에서 확정한다. 새 Python 두 파일의 편집기 오류 없음, 사전 공백 검사 통과다. 원본 모델·프롬프트·동작은 바꾸지 않았다.

## 2026-10-27 / 종료 동작 진단 / 공통 모델 선택 동작·평가 적합성 확인

- evidence/english_blt_termination_20261027.json(약44KiB), SHA256=afe51fe003cdaa3da47df1c1113d35d620a9d57d5e9280d4f16d499eabfdad9e를 보존했다. status diagnostic_complete, HF 수동 접두부 대조5/5 일치, 저장된 다음 ID40/40 일치(마지막1024 위치10개는 다음 ID가 없어 비교 대상 아님), EOS probe50개를 확인했다. 입력1024 보고서 및 현재 로컬 진단기/어댑터/count/LMDB reader 코드 해시도 일치했다.
- 런타임 tokenizer/model/generation defaults는 모두 BOS1/EOS2/PAD3이며 tokenizer EOS 표기는 </s>다. forced_eos/min_length/min_new_tokens/suppress_tokens/begin_suppress_tokens 기본값은 None이고 실제 제어 생성은 명시적 suppress[0,1,3]/do_sampleFalse/beam1/no-cache였다. 별도 generation_config.json이 없어도 EOS2는 런타임에 정상 설정돼 있었다. 파일 부재를 버그로 볼 근거가 없다.
- EOS는50개 측정 모두 억제되지 않았다. 허용 토큰 중 EOS 순위는 원래2~134위/후보2~137위로 한 번도1위가 아니었다. EOS 확률은 원래4.36e-9~0.0075668(최대약0.757%), 후보9.49e-9~0.0163050(최대약1.631%)였다. 1024 위치의 개행 반복 예시는 EOS 확률 원래7.38e-8/후보5.99e-6으로 ID14가 계속 선택됐다. greedy는 최고 점수만 고르므로 확률이 조금 있어도1위가 아니면 종료하지 않는다.
- 결론 범위: 실제1024 출력에 EOS2가 없고 HF 기본 생성도 같은 접두부를 재현하므로, 확인한 경로에서는 수동 종료 루프가 EOS를 놓치거나 후보만 EOS를 억제하는 오류가 아니라 모델의 continuation/반복 선택으로 설명된다. 상한을 늘려 기다리면 곧 EOS가 나올 것이라는 근거는 없다. HF 대조는 같은 변환 forward를 사용하므로 원래 upstream BLT와 변환 수치의 완전 동등성이나 모든 프롬프트의 종료를 보증하지 않는다.
- 평가 해석 정정: 사용한 경로는 facebook/blt-1b 원본 가중치를 변환한 모델이지 GEC 미세조정 모델이 아니다. 기존 GEC용 SEPARATOR 문자열을 입력했다고 그 구분자·교정 응답·EOS를 학습한 모델로 취급해서는 안 된다. 앞선 추가 GEC 프롬프트는 이 기반 모델의 정상 교정 응답/EOS 검증에 적합한 근거가 아니었으며, 단일 greedy 반복 현상을 패처 오류로 해석하지 않는다. 모든 프롬프트가 반드시 유한 길이 안에 자연 EOS를 낼 것이라는 기준도 이 기반 모델에 보장되지 않는다.
- 기존 긴 문맥 BPB와 동일 길이 생성의 연산시간 측정은 그 명시적 조건의 진단으로 남기되, 정상 종료된 응답의 품질/전체시간으로 주장하지 않는다. 이후 사전학습 BLT 패처 비교는 BPB·고정 바이트 생성 및 반복성으로 분리하고, 태스크 종료 검증은 그 입력/EOS 타깃으로 실제 학습한 checkpoint를 명시해 별도 수행해야 한다. 사용자 승인 없이 모델을 바꾸거나 미세조정/강제 EOS/반복 페널티를 추가하지 않았다.
- 최종 확인: 종료 진단 문서/task/log 반영 뒤 git diff --check 통과, 보존 증거 SHA256 재확인 일치. 앞서 집중5개/전체34개 회귀 및 새 Python 파일 편집기 오류 없음 확인 후 코드는 변경하지 않았다. 진단 작업은 완료했지만 실제 자연 EOS 도달은 여전히 미충족이다.

## 2026-10-27 / 종료 검증 재개 / 사용자 과거 정상 종료 관측과 대조

- 사용자는 예전 가중치 로드 테스트에서 상한 종료가 거의 없었다고 지적하며 종료 검증 우선을 요청했다. 자연 EOS를 재현하지 못한 상태를 기반 모델 특성으로 설명하고 다음 평가로 넘긴 판단은 성급했다. 앞선 HF 대조는 같은 변환 forward를 공유하므로 공통 모델/런타임 문제를 배제하지 못한다. 후속 성능 단계는 보류한다.
- 가까운 증거를 다시 확인했다. p3a_native_full_guarded_11.json은 A100/native val2634건과 checkpoint_hash cc8466be70e67e7164d14a271818bef42a919914cd7737b6471c1f3b7454ab28을 기록한다. 현재 서버에는 해당 outputs/blt_hf_eval/native/val 경로의 보고서가 발견되지 않았다. 이전과 같은 체크포인트라는 가정은 아직 검증되지 않았다.
- 원래 blt_hf/generation.py의 generate_batch는 BOS+source+GEC 구분자를 사용하며 입력 끝 EOS를 넣지 않는다. 현재 진단의 logits_to_keep=1과 달리 기본 생성 호출은 해당 인자를 생략한다. 판별 가설은 체크포인트/프롬프트/런타임 조건 차이 또는 공통 forward 문제다. 간단한 영어·한국어 문장을 raw/GEC 형식으로 원래 HF 전체 로짓 생성과 count 패처에서 측정하고 과거 체크포인트 식별 근거를 대조한다. 가중치·원본 프로젝트·생성 페널티는 변경하지 않는다.

## 2026-10-27 / 종료 검증 재개 / 간단 문장 진단기 회귀 통과

- blt_hf/eval.py에서 resolve_checkpoint 후 mode=train을 요구하고 변환 기반 load_model 다음 학습 model.safetensors를 strict load하는 것을 확인했다. 이번 count 실험에는 이 두 번째 로드가 없었다. 과거 평가의 훈련 가중치와 현재 변환 가중치를 동일 모델로 취급하면 안 된다. 다만 사용자 개인의 예전 테스트가 바로 이 평가였는지는 아직 확정하지 않았다.
- 진단기의 opt-in --simple-controls에 Hello./The weather is nice today./안녕하세요./오늘은 날씨가 좋다.를 raw/GEC 두 형식으로 추가했다. 원래 HF 생성은 logits_to_keep를 생략하고 count는 기존 수동 경로다. 원래 모델/페널티 불변, 별도 run에서 각128 ID(기존1024보다 작은 짧은 진단 상한)로 EOS와 상한을 분리한다. 자연 종료가 없으면 통과로 표시하지 않는다.
- 원문 바이트·BOS·EOS 비주입 테스트 포함 집중6개0.007초, 전체35개1.145초 통과. 다음 GPU 실행은 기존 기록 대조도 유지하며 timeout600초/GPU0/BF16/CPU8/캐시 없음으로 수행한다.
- 실행 전 용어 정정: logits_to_keep 인자를 생략해도 HF가 내부 최적화할 수 있으므로 전체 로짓 계산이라고 단정하지 않는다. 결과 키를 original_hf_default로 정정했다. 판별 대상은 원래 generate_batch와 동일한 명시적 생성 인자 사용이며 내부 연산량 강제 실험이 아니다.
- 키 정정 후 집중6개0.007초 재통과. /home/itcmaster/projects 깊이6 이내 checkpoint.json은 발견되지 않았다(서버 전체 부재를 의미하지 않음). 원래 평가는 Neuron /scratch/r984a02/phdq3의 SLURM 실행을 전제로 하므로 원본 학습 체크포인트가 현재 서버에 있다고 가정하지 않는다. 다음은 현재 가중치의8개 입력×양 모드 실제 실행이다.

## 2026-10-27 / 종료 검증 재개 / 간단 문장 실제 생성 완료

- 서버 실행 시작 관측2026-10-27T11:39:43+00:00, en-blt-simple-termination-20261027-01, timeout600초 내 exit0. Hello./The weather is nice today./안녕하세요./오늘은 날씨가 좋다. 각각 raw/GEC 두 형식의8개 입력 모두 원래 HF 기본 호출 EOS false, count EOS false였다. 이는 각128 ID 상한의 측정이며 무한 생성이나 모든 간단 문장의 실패를 뜻하지 않는다.
- 기존5개 입력의 HF128 접두부 대조도5/5 true로 유지됐다. 편집기 Python 오류 없음, 사전 공백 검사 통과. 자연 EOS 검증은 실패/미완료로 유지하며 다음은 작은 JSON 보존 및 출력/현재-과거 가중치 식별 대조다. 기존 모델/페널티/입력 EOS는 바꾸지 않았다.

## 2026-10-27 / 종료 검증 재개 / 가중치 불일치 확인·원래 체크포인트 필요

- evidence/english_blt_simple_termination_20261027.json(약107KiB), SHA256 a7b8bac1481cd93eeb0672a853c231e0da9fee73dce1797b19ad8895a91bda9c를 보존했다.8개 입력×양 모드16개 모두 새128 ID/stop_reason max_new_tokens이며 보고서·코드 해시와 기존 다음 ID 대조가 통과했다. diagnostic_complete는 진단 실행/대조 완료일 뿐 자연 EOS 검증 통과가 아니다.
- 현재 변환 보고서의 model.safetensors SHA256은4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061이다. load_model은 이 해시를 검증했다. 과거 A100 보고서의 학습 체크포인트 cc8466be70e67e7164d14a271818bef42a919914cd7737b6471c1f3b7454ab28와 명확히 다르다. 당시 eval.py는 변환 기반 로드 후 해당 학습 가중치를 strict load하는 반면 이번 생성은 변환 기반 가중치만 사용했다. 사용자 개인의 예전 테스트까지 같은 체크포인트였다고 확정하지는 않는다.
- 출력 구분: Hello. raw 원래 HF는 " I am a student at the University of Michigan...", 영어 날씨 문장은 해변 이야기를 이어 썼다. 따라서 모든 미종료 출력을 반복 붕괴라고 부르면 부정확하다. 한국어 raw 날씨 문장은 반복했고 GEC 형식은 구분자/문장 반복이 두드러졌다. 짧은 입력이 짧은 생성/EOS를 보장하는 것은 아니지만, 이 관측으로 과거 정상 모델의 실패 원인을 설명했다고 볼 수도 없다.
- 차단 요인: 확인한 서버 프로젝트 깊이6 이내에는 과거 학습 checkpoint.json이 없고 정확한 사용자 이전 테스트의 경로/명령이 없다. Neuron 접속·전송은 사용자 담당이므로 임의 접근하지 않는다. 다음은 사용자에게 이전 정상 종료 가중치 경로 또는 실행 명령을 확인해 동일 체크포인트/프롬프트/생성 설정을 재현하는 것이다. 자연 EOS 검증은 미완료, 후속 최적화·성능 단계는 보류한다. 학습 가중치로 바꿔 실행할 경우 이전 기반 모델 실험과 별도의 조건으로 명시한다.
- 최종 형식 검사 및 진단기 새 파일 공백 검사 통과, 증거 SHA256 재확인 일치. 첫 no-index 검사에서는 새 파일의 정상 diff 종료1 때문에 뒤의 해시 명령이 생략됐으며, 종료1과 공백 오류를 구분해 재실행했다. 마지막 코드 변경 후 집중6개 재통과, 그 직전 전체35개 통과, 실제 GPU 진단 및 편집기 오류 없음 확인 상태다. 이전 정상 종료 테스트 식별 정보를 사용자에게 확인한다.

## 2026-10-27 / 종료 검증 재개 / 사용자 기준 테스트 정정

- 사용자는 이전 테스트가 허깅페이스에서 받은 모델에 간단한 프롬프트를 넣은 일반 생성이며 현재 실험/GEC와 무관했다고 명확히 답했다. 따라서 과거 A100 학습 가중치 차이는 사용자가 말한 정상 동작의 설명이 아니다. 해당 해시 비교 자체는 사실이나 사용자 관측의 원인/해결책으로 연결한 판단을 철회한다. GEC 학습 체크포인트를 요청하거나 그 모델로 바꾸는 것은 현재 목표가 아니다.
- 다음 판별은 원래 HF/업스트림 구현·토크나이저·가중치와 현재 사용자 정의 변환 OSC 구현의 일반 생성 차이다. 서버의 로컬 HF 캐시와 공식 구현 호환성을 먼저 확인하고 같은 일반 프롬프트로 대조한다. 원본 모델/캐시 파일을 수정하거나 종료 게이트를 우회하지 않는다.

## 2026-10-27 / 종료 검증 / 공식 HF 대조 경로

- 사용자 요청에 따라 자연 EOS 관측을 우선해 계속한다. 중단된 앞선 메타 검사는 결과가 남지 않아 재확인했다. 메타 장치의 공식 Transformers5.16.1 BltForCausalLM과 현재 safetensors의510개 키·형상 모두 일치, missing/unexpected/shape mismatch 없음. 직전 진단 프로세스 잔존은 발견되지 않았다(pgrep 자기 명령만 출력).
- 가설: 공식 HF와 사용자 정의 OSC forward의 차이가 공통 반복/미종료 현상에 기여할 수 있다. 판별은 같은 변환 가중치를 공식 클래스에 strict load하고 같은8개 짧은 입력을 no-cache greedy128 ID로 생성하는 것이다. --official-only를 기존 진단기에 추가했으며 자연 EOS 관측 수와 eos_observed/no_eos_observed를 명시한다. 원본 모델 파일과 사용자 정의 구현을 바꾸지 않는다. 공식 구현이 EOS를 내도 그것만으로 사용자 정의 OSC 수정을 승인/동등성 증명했다고 간주하지 않는다.

## 2026-10-27 / 종료 검증 / 공식 대조 완료·보고서 저장 오류

- 2026-10-27T11:47:17+00:00 시작 en-blt-official-termination-20261027-01. 공식 모델510개 로드 및8개 입력128 ID 생성 완료, 모두EOS false였다. 그러나 마지막 json.dump가 HF loading_info의 set 타입으로 TypeError를 내 exit1이었다. report.json은 불완전하므로 정상 JSON 증거로 사용하지 않는다. stdout은 원래 run에 보존한다.
- 저장 결함만 수정해 로딩 진단4개 항목을 정렬된 리스트로 변환한다. 새 run에서 같은 focused GPU 검사를 재실행한다. EOS 미관측은 그대로 미충족이며 모델/생성 설정을 바꾸지 않는다.

## 2026-10-27 / 종료 검증 / 공식 greedy 대조 보존·分布 샘플링 구분

- en-blt-official-termination-20261027-02는同조건 재실행 exit0 및 JSON 파싱 통과, 로딩 진단4개 모두空 리스트, 자연EOS0/8·각128 ID였다. 증거 evidence/english_blt_official_termination_20261027.json을 보존했다. 공식 구현도 이 범위에서 미종료이므로 사용자 정의 OSC만이 원인이라는 가설은 지지되지 않는다. 가중치 변환과 이전 사용자 HF 모델 식별은 여전히 별도 미확인이다.
- 사용자의 우선 목표는 실제 EOS 관측이다. 다음 별도 실험은 --official-only --sample-eos로 raw 간단 문장 최대4개, seed20261027부터 입력별+1, 각1024 ID 상한/전체600초다. 같은 허용 분포에서 do_sample=True/top_k0/top_p1/temperature1로 추출하고 최초 자연 EOS 관측 시 중단한다. ID0/1/3 억제는 유지하고 EOS 강제/입력 주입/반복 페널티는 사용하지 않는다. 공식 대조의 변환 파일 해시 검증도 명시했다.
- 이는 greedy 검증을 대체하지 않는 별도 EOS 발화/종료 진단이며, 샘플링으로 EOS가 나오더라도 기존 greedy 전체 생성·count 패처 검증은 미완료로 남긴다. 자연 EOS가 선택된 바로 직전 접두부의 확률·순위도 재계산해 기록한다.

## 2026-10-27 / 종료 검증 / 공식 HF 자연 EOS 관측

- 2026-10-27T11:50:23+00:00 시작 en-blt-sampled-eos-20261027-01은 첫 raw Hello. 입력에서 seed20261027/원분포 샘플링으로459번째 새 ID에 EOS2를 뽑아1024 상한 전에 종료했다. status eos_observed, 최초 성공 후 계획대로 중단, 강제 EOS/반복 페널티 없음. EOS 직전 확률0.16327539/허용 순위3, greedy 최고는 개행14였다. 같은 지점에서 샘플링과 greedy 선택이 다를 수 있음을 실측했다.
- evidence/english_blt_sampled_eos_20261027.json 약19KiB 보존 및 JSON 파싱 통과. 공식 모델 파라미터510개 strict load와 변환 파일 해시 검증을 통과했다. 이는 공식 클래스·현재 변환 가중치의 실제 자연 EOS 사례이며 이전 greedy 실패가 해소됐다는 주장은 아니다.
- 다음은 같은 Hello./seed/샘플링 설정을 현재 사용자 정의 OSC 원본 및 count 패처에서 각각 검증한다. count는 full-prefix/no-cache HF forward 직전 opt-in patch_lengths 주입 hook을 사용하고 finally에서 제거한다. 원본 모델 파일과 기존 greedy 생성 helper는 변경하지 않는다.

## 2026-10-27 / 종료 검증 / OSC seed20261027은 양 모드 상한 도달

- 2026-10-27T11:52:01+00:00 시작 en-blt-count-sampled-eos-20261027-01은 원래 OSC/count 모두1024 ID·EOS false로 exit0, status eos_incomplete였다. evidence/english_blt_count_sampled_eos_20261027.json 약75KiB 보존/파싱 통과. 공식 모델에서459 ID EOS를 관측했어도 현재 두 경로의 검증은 아직 미완료다.
- 같은 seed라도 서로 다른 forward 분포에서는 선택 경로가 달라질 수 있다. 이것만으로 구현 오류 또는 EOS 불능이라고 단정하지 않는다. 다음은 생성 분포/상한을 바꾸지 않고 seed42로 같은 두 모드를 추가 관측한다. --sampling-seed를 명시적 옵션으로 추가하고 결과에 실제 seed를 기록한다. 실패 run은 보존하고 seed 선택 결과를 일반 종료율로 주장하지 않는다.

## 2026-10-27 / 종료 검증 / seed42 미종료·종료 직전 문맥 대조

- en-blt-count-sampled-eos-20261027-02도 원래OSC/count 모두1024 ID·EOS false, status eos_incomplete다. evidence/english_blt_count_sampled_eos_seed42_20261027.json 보존 및 파싱 통과. 공식 모델의 EOS 관측과 현재 두 경로의 자연 종료를 구분한다.
- 무작정 seed를 늘리지 않고 한 단계 직접 비교한다. --eos-reference로 실제 공식 HF EOS 생성 보고서를 검증해 EOS 바로 이전의 prefix만 재입력한다(EOS ID 자체는 절대 넣지 않음). 같은 문맥에서 현재 원래OSC/count의 초기 EOS 확률·순위를 기록하고 greedy128 ID를 실행한다. 선택된 문맥의 진단이므로 일반 짧은 프롬프트 종료율과 구분한다. 기존 실패와 공식 성공 보고서는 그대로 보존한다.

## 2026-10-27 / 종료 검증 / count greedy 실제 EOS 확인

- en-blt-eos-reference-20261027-01은 공식 모델의 실제 종료 직전 문맥을 입력해 count가 greedy14번째 새 ID에 EOS2를 선택, 원래OSC는128 ID 상한 종료했다. count의 최종 EOS 확률0.51344788/순위1, 다음 후보는 개행14였다. 처음 두 모드의 EOS 확률은 원래0.162939/count0.163310으로 매우 비슷했지만 이후 greedy 경로는 달라졌다.
- evidence/english_blt_eos_reference_20261027.json 약17KiB 보존/파싱 통과, status eos_incomplete(두 모드 중 하나만 EOS). count의 EOS 동작을 실제 모델에서 관측했으나 원래OSC는 아직 실제 EOS 사례가 없다.
- 다음은 새 무작위 seed 대신 count가 자연 종료한 마지막 문맥으로 원래OSC를 한 번 더 대조한다. --eos-reference-mode를 추가해 기존 보고서의 자연 EOS 직전 바이트만 재사용한다. EOS/PAD/기타 특수 ID가 입력에 섞이지 않는지 검증하며 선택 문맥의 진단이라는 범위를 유지한다.

## 2026-10-27 / 종료 검증 / 현재 OSC·count 모두 greedy EOS 관측

- en-blt-eos-reference-20261027-02는 count가 실제 EOS를 낸 직전의 동일 문맥을 두 모드에 입력했다. 원래OSC와 count 모두 새 ID [2] 하나만 생성하고 즉시 EOS 종료, status eos_observed다. 원래 EOS 확률0.63226587/순위1, count0.51344788/순위1. 입력에는 EOS/PAD/추가 특수 ID를 넣지 않았다. 강제 EOS/반복 페널티/상한 도달에 의한 종료가 아니다.
- evidence/english_blt_eos_completed_context_20261027.json 약13KiB 보존/파싱 통과. 공식 모델의 샘플링 문서와 count의 후속 자연 생성으로 얻은 선택 문맥의 검증이다. 따라서 임의 짧은 인사에서 greedy가 잘 끝난다거나 일반 종료율/품질을 검증했다고 주장하지 않는다. 다만 현재 두 경로에 EOS 발화 능력과 HF 종료 동작이 있음을 실제로 확인했다.
- 마지막 의미 있는 경로 확인으로 같은 문맥에서 기존 smoke 스크립트의 greedy_generate 결과가 HF의 [2]와 일치하는지 검사한다. count 온라인 상태를 reset한 뒤 같은 opt-in hook으로 수동 helper를 실행한다. 표준 helper 코드는 바꾸지 않고 실제 자연 EOS가 나오는 입력의 종료 일치만 추가 검증한다.

## 2026-10-27 / 종료 검증 / 실제 EOS 및 수동·HF 일치 확인 완료

- en-blt-eos-reference-20261027-03은 원래OSC/count 모두 HF [2] 및 기존 greedy_generate [2]로 정확히 일치했다. 입력에 EOS 없음, do_sample=False, 자연 EOS 종료, 상한128 중 새1 ID만 생성했다. count 온라인 상태 reset/hook 제거를 유지했으며 실제 [2] 일치를 assert했다. 증거 evidence/english_blt_eos_manual_hf_20261027.json 약13KiB 보존/파싱 통과.
- 최종 코드 상태에서 서버 전체35개 테스트1.141초 통과, 새 Python 진단기 및 테스트 파일 편집기 오류 없음. 가중치/기존 manual greedy helper/원본 BLT 프로젝트 코드는 변경하지 않았다.
- 확인 완료 범위는 공식 HF의 Hello. 원분포 샘플링 자연 EOS459 ID와, 선택된 실제 완결 문맥에서 현재 원래OSC/count의 greedy EOS 발화·정지·수동/HF 일치다. 샘플링 성공을 greedy 성공으로 바꾸어 부르지 않는다. 일반 짧은 입력의 반복·상한 종료 원인과 사용자 예전 모델/버전의 재현은 여전히 미완료이며 성능 실험을 자동 재개하지 않았다.
- 문서/업무 상태에 위 증거와 한계를 반영한다. 다음 최종 확인은 보존 보고서의 원본 해시·EOS 참조 연쇄·코드 해시 및 문서 공백 검사다. 모든 실패 보고서와 로그도 유지한다.

## 2026-10-27 / 종료 검증 / 증거 연쇄 및 최종 기록 확인

- 최종 git diff --check 통과.7개 신규 보고서의 원래1024 보고서 해시 일치와 공식 샘플→count 자연 종료→완결 문맥 재현의 참조 SHA256 연쇄를 확인했다. 최종 진단 코드 해시도 실행 시 기록과 일치했다.
- 최종 입력478 ID=BOS1+477바이트이며 나머지는 전부4~259의 byte ID다. EOS2/PAD3 입력 없음. 원래/count 모두 greedy HF 생성 및 기존 수동 helper가 [2]를 내고 stop_reason eos, EOS 순위1인 것을 assert했다. 최종 증거 SHA256은15985387c3db020a6861a8fc6cecd83c7d68e0f509d33db5103e628af0dba837이다. 공식 Hello. 샘플링 성공 증거 SHA256은d1010c45f546414c95caa1a7760bf820741637f27ad2d037135beb997d99217e다.
- 종료: 실제 EOS 관측과 현재 양 모드의 EOS 발화·정지 경로 확인은 완료했다. 일반 짧은 입력의 greedy 전체 생성 종료는 미해결이며 이번 선택 문맥의 결과로 대체하지 않는다. 후속 성능 실험은 실행하지 않았다. 최종 전체35개 회귀 통과 및 Python 편집기 오류 없음 상태를 유지한다.

## 2026-10-27 / 패처 검증 다음 단계 / 상한2048 승인 및 일반 입력 대조

- 사용자는 생성 상한을 늘려 다음 진단 진행을 요청하고 패처 검증 순서를 물었다. 다음 일반 입력 진단은 --simple-controls --raw-only --max-new-tokens 2048로 명시한다. 이전1024보다 늘리되 모델 문맥4096을 넘지 않으며 EOS 강제/반복 페널티/가중치 변경은 하지 않는다.
- 가까운 코드에서 진단 상한이128/1024로 하드코딩돼 있음을 확인했다. CLI 상한 선택과 문맥 초과 거부 helper, GEC 제외 옵션을 추가한다. 가설은 상한2048에서도 EOS 미도달/반복이 남을 수 있다는 것이며, 판별은 고정된 기존 raw 영어·한국어4개 입력×양 모드 greedy8건의 실제 EOS/생성길이/반복/UTF-8이다. CUDA 동기화한 벽시계 시간도 기록하되 각1회·warmup 없음·원래 먼저 실행하는 진단이므로 일반 속도 향상으로 해석하지 않는다.
- 가장 싼 사전 체크는 새 budget helper가2048을 허용하고 prompt+generation>4096 및0/음수/bool을 거부하는 테스트다. 기존 고정 기록 HF 대조128 ID는 이전 보고서와 비교하는 용도이므로 별도로 유지한다. 후속 패처 핵심 검증은 미사용 문서의 경계 품질·패치 길이 분포 및 teacher-forced BPB이며, 기존6개 겹치는 접두부 BPB는 확증용 heldout이 아니다. 이후 품질 허용 범위가 정해진 조건에서만 속도·메모리를 반복 측정한다.

## 2026-10-27 / 패처 검증 다음 단계 / 상한 보호 회귀 통과

- 집중7개0.007초 및 전체36개1.139초 통과. 요청2048과 모델 문맥 한도 검증을 포함한다. 次단계 actual GPU 실행은 raw4개×2모드 각2048 ID, 전체timeout1800초/GPU0/BF16/eager/no-cache/CPU8이다.
- 실제 결과 해석을 위해 simple_control_generation_count/eos_count와 completed_with_generation_limits 상태를 추가한다. 기존 고정128 ID 경로 대조가 일치하더라도 확대 일반 생성에서 EOS가 없으면 성공으로 포장하지 않는다. 다음 패처 품질 검증은 평가 미사용 문서와 지표/허용 범위 계약부터 고정하도록 task에 기록했다. 새 모델 학습·임계값 변경·캐시 재사용은 이번 진단에 포함하지 않는다.

## 2026-10-27 / 패처 검증 다음 단계 / 상한2048 실제 실행 완료

- 2026-10-27T12:26:13+00:00 시작 en-blt-eos2048-20261027-01은 timeout1800초 내 exit0. raw4개×양 모드8건에서 원래OSC의 Hello.만 EOS true, count의 Hello.와 나머지 양 모드6건은 EOS false였다. 생성 길이·반복·단회 시간은 아직 JSON 수치 대조 전이므로 여기서는 결과 플래그만 기록한다.
- 기존5건의 고정128 ID HF/수동 접두부 대조는 모두 true, Python 편집기 오류 없음. 다음은 작은 보고서 보존 후 EOS 도달률/정확한 길이/UTF-8 및 명시적 반복 지표를 집계한다. 후보의 미종료를 상한 부족만으로 설명하거나 종료율 차이를 보편적 회귀로 확정하지 않는다.

## 2026-10-27 / 패처 검증 다음 단계 / 상한2048 결과 집계

- evidence/english_blt_eos2048_20261027.json 약434KiB, SHA2566149fff02c1e8e8eedf6fd47a9373d14dffd064ef23fa843dd380be8eacde498. status completed_with_generation_limits, EOS1/8、원래1/4/count0/4다. Hello. 원래OSC는514번째 새 ID EOS로 종료(513바이트+EOS), count는2048 상한이었다. 기존에 같은 Hello. greedy를 검사한 것은128 상한이었으며, 이 결과를 이전 다른 프롬프트의1024 실험과 혼동하지 않는다.
- 영어 날씨/한국어 인사/한국어 날씨는 양쪽 모두2048 상한,8개 출력 UTF-8 모두 유효. 모든8건 첫128 ID가 기존 같은 raw 입력 결과와 일치했다. 요청 상한2048·입력+상한<=4096·기존 고정 HF/수동 대조·소스/원본 보고서 해시 검증이 통과했다.
- 반복 지표는 EOS 제외 연속8-ID창의1-(고유 창 수/전체 창 수)로 정의해 사후 기술 통계만 산출했다. Hello. 원래0.1897/count0.7511, 영어 날씨0.9334/0.9569, 한국어 인사0.9476/0.9618, 한국어 날씨0.9863/0.9863이다. 높은 값은 반복 경향을 나타내지만 일반 품질의 보정된 점수는 아니다.
- 단회 시간(초)은 Hello.8.202/41.195, 영어 날씨56.534/44.402, 한국어 인사56.349/37.797, 한국어 날씨54.328/36.033이다. 출력 길이·warmup·순서가 통제된 반복 성능 실험이 아니므로 이 수치를 속도 향상/실용성 입증으로 사용하지 않는다. 선택4개 입력만으로 후보의 보편적 종료율 저하를 확정하지 않는다.
- 다음 패처 핵심 작업은 미사용 영어 문서·평가 계약을 먼저 고정해 같은 teacher-forced 텍스트의 byte 가중 BPB/문서별 차이와 교사 경계 정밀도·재현율/패치 길이 분포를 측정하는 것이다. 이미 적합/임계값 선택에 사용한 검증 자료를 새 heldout이라 부르지 않는다. 주어진 영어 카운트/규칙의 한국어 생성은 별도 분포 진단이다. 문서/task에 이 순서와 생성 품질·속도·메모리 후속 단계를 반영했으며 새 적합/대규모 평가를 임의 실행하지 않았다.
- 최종 git diff --check 및 보존 증거 SHA256 재확인 통과. 집중7개/전체36개 회귀 후 실제 확대 상한 실행과 소스 동일성·EOS 집계가 검증됐고 Python 편집기 오류 없음 상태다. 상한 증가는 명시적 CLI opt-in이며 이전 보고서/기본 진단 조건은 보존한다. 다음 미사용 문서 평가와 품질 허용 범위 확정은 아직 미실행이다.

## 2026-10-28 / 프롬프트 적합성 점검 / 실제 입력 확인

- 사용자는 EOS 미도달이 프롬프트 문제일 가능성을 제기하며 현재 입력을 물었다. 실행 보고서 english_blt_eos2048_20261027.json의 input_ids를 역변환해 Hello./The weather is nice today./안녕하세요./오늘은 날씨가 좋다. 그대로임을 확인했다. raw_only true/상한2048, 실제 구성은 BOS1+문장 UTF-8 byte+4이며 시스템 프롬프트·채팅 템플릿·입력 EOS·GEC 구분자가 없다. 스크립트 정의와 실행 증거가 일치한다.
- 이전1024 실험에는 The cat sat on the mat./abcXabc abcXabc./English with café. 및 두 GEC 구분자 입력도 있었다. 최근 raw4개와 혼동하지 않는다. 종료 문맥 재입력 검사는 별도로 자연 생성 문단을 사용했으며 일반 프롬프트4개에 포함하지 않는다.
- 해석은 가설이다: 기반 언어 모델에 단순 문장을 주는 것은 응답 길이/완결 조건이 정의된 태스크가 아니라 텍스트 continuation일 수 있다. 문장 마침표가 문서 EOS를 의미하지 않으므로 이 입력들의 미종료만으로 패처 오류/실용성 실패를 판정하기 어렵다. 프롬프트 영향의 정량 비교는 아직 수행하지 않았고 모델이 지시문을 따른다고 가정하지 않는다. 이번 확인에서는 코드·가중치·생성 설정을 변경하지 않았다.

## 2026-10-28 / 명확한 과업9개 대조 / 실행 전 고정

- 사용자 승인: 제안한3유형×3소재=9개 프롬프트를 비교한다. --instruction-controls의 instruction9_v1으로 원문을 실행 전에 코드에 고정했다. 이야기: 봉인 편지/도서관 무명 노트와 기차표/빨리 가는 마을 시계. 과정: 비/빵/유리병 재활용. 비교: 신뢰성을 우선한 교통수단/배터리를 우선한 노트북/자동화를 우선한 백업 방식. 앞서 제시한 각유형 첫 프롬프트는 유지한다. 이후 EOS 결과로 입력을 선별하거나 교체하지 않는다.
- 가설은 명확한 지시·완료 조건이 단순 문장보다 과업에 맞는 산출물 관측에 적합할 수 있다는 것이며, EOS 도달이나 지시 수행 개선은 아직 측정 전이다. 같은1B 변환 가중치/원래OSC 대 count/greedy/beam1/no-cache/BF16/eager/GPU0/CPU8/각2048 새 ID를 적용한다. BOS+raw UTF-8 byte+4만 사용하고 채팅 템플릿·입력 EOS·GEC 구분자·강제 종료문자열·반복 페널티는 넣지 않는다.
- 가장 싼 사전 체크는9개 고정/이름 유일/유형별3개/바이트 일치/EOS 비주입/prompt+2048<=4096 단위 테스트다. 기존 진단기에 opt-in 선택만 추가하고 단순4개와 종료 문맥 테스트는 유지한다. 각입력 완료 후 progress JSON을 원자적으로 보존해 긴 실행 중 결과 손실을 줄인다.
- 사전 검토 기준: 지시 수행(충족/부분/미충족/불명확)과 과업 완결(완결/미완결/불명확)을 실제 텍스트에서 별도로 검토한다. 이야기의 상황 해소, 과정의 지정 시작~끝 단계 포함, 비교의 주어진 조건에 근거한 추천을 확인한다. EOS/상한·생성길이·UTF-8·8-ID 중복률은 별도 기술 통계다. 각모드1회·warmup 없음·원래 먼저 실행하는 시간은 속도 개선 지표로 쓰지 않는다. 현재 모델은 기반 모델이며 지시 따르기를 보장하지 않는다.

## 2026-10-28 / 명확한 과업9개 대조 / 사전 회귀 통과

- 서버 집중8개0.007초/전체37개2.179초 통과.9개 고정·유형별3개·BOS/바이트 일치·EOS 비주입 및2048 문맥 보호를 확인했다. 다음 en-blt-instruction9-20261028-01에서 --instruction-controls --max-new-tokens 2048을 실행한다.
- 실행 조건: GPU0 사용128MiB 미만일 때만 시작, BF16/eager/no-cache/CPU8/OpenBLAS8/greedy/beam1, timeout2400초. 최대18건의 새2048 ID 생성과 기존5건의 짧은 HF/수동 경로 제어를 수행한다. 완료한 입력별 progress JSON은 별도 보존하며 모델 로딩/단회 시간은 품질·EOS 분석과 구분한다. 원본 프로젝트·가중치·배경 LMDB는 수정하지 않는다.

## 2026-10-28 / 명확한 과업9개 대조 / 실제18건 실행 완료

- 서버 실행 시작 관측2026-10-27T23:12:45+00:00(한국시간10월28일), en-blt-instruction9-20261028-01. timeout2400초 내 exit0,9개×양 모드18건 생성 완료. 원래OSC는 story_clock만 EOS true, count는 compare_laptop만 EOS true로 각1/9였다. 나머지16건은 EOS false다. 아직 JSON 길이·UTF-8·반복·내용 평가는 대조 전이므로 여기서는 stdout의EOS 플래그만 기록한다.
- 기존5건의128 ID HF/수동 대조도 모두true, 편집기 Python 오류 없음. 다음은 원본 JSON을 보존하고9개 고정 프롬프트·각2048 상한·모델/배경/소스 해시를 대조한 뒤 전체18개 출력의 지시 수행과 과업 완결을 별도로 검토한다. 이번 선택9개만으로 프롬프트 개선 효과나 패처의 보편적 성능을 확정하지 않는다.

## 2026-10-28 / 명확한 과업9개 대조 / 定量 결과 검증

- evidence/english_blt_instruction9_20261028.json 약994KiB, SHA25608dab2512d81096c2ed5ded8522528a448b4923c3faef0115f00b26076234765를 보존했다. status completed_with_generation_limits, EOS2/18=원래1/9/count1/9다. 원래 story_clock1339 ID, count compare_laptop868 ID만 EOS 종료하고16건은2048 상한이었다. 입력 원문/바이트 일치·prompt+2048<=4096·생성 ID 범위·코드/원본 보고서 해시·기존 HF/수동 대조 검증 통과.
- UTF-8은 원래9/9/count9/9 유효, 생성 ID 중앙값은 양쪽2048이다. EOS 제외8-ID창의 중복률은 story_letter0.8065/0.7153, story_notebook0.8893/0.9059, story_clock0.4500/0.9731, process_rain0.9206/0.6561, process_bread0.7854/0.7506, process_glass0.8560/0.5233, compare_travel0.8947/0.8805, compare_laptop0.8893/0.5349, compare_backup0.8814/0.7291(원래/count)이다. 단순 중복 기술 지표이며 의미 품질 점수가 아니다.
- 다음은18개 전체 생성 텍스트를 읽어 실행 전 정의한 지시 수행·완결 기준을 적용한다. 주관적 내용 검토를 객관적 EOS/UTF-8 수치와 혼합하거나 단회 시간을 속도 향상으로 해석하지 않는다.

## 2026-10-28 / 명확한 과업9개 대조 / 전체 출력 내용 검토

-18개 전체 텍스트를 확인했다. 처음 한 번의 전체 출력 표시에서는 대량 빈 줄 때문에 터미널 앞부분이 소실돼 그 화면만으로 평가하지 않았다. 이후 유형별로 모든 비동일 내용을 다시 읽었고 연속 동일 줄/빈 줄만 횟수로 축약 표시했다. 원본 JSON은 변경하지 않았다.
- 개별 기술 검토를 evidence/english_blt_instruction9_review_20261028.json에 보존했다. 실행 전 기준대로 지시 수행과 핵심 내용 완결을 구분하며, 핵심 단계/추천이 있어도 사실 정확성이나 깨끗한 정지까지 통과한 것으로 보지 않는다. 단일 비맹검 보조자 검토로 외부 평가자 합의·통계적 품질 점수·최종 채택 판정은 아니다.
- 주요 관측: 원래 story_clock은1339 ID EOS지만 Resolution/Ending에 같은 단락을 반복하고 무관한 웹 댓글 문구를 덧붙였다. count compare_laptop은868 ID EOS와 배터리 우선에 맞는A 추천이 있으나 A 가격이 더 높다고 잘못 쓰고 무관한 문구로 이어졌다. count 비/빵 설명과 백업 추천은 핵심 끝 단계/선택이 있어도 반복 문단/빈 줄을 계속 생성했다. 비교 여행은 양쪽 모두 상충하는 신뢰성 주장으로 한 가지 추천에 실패했다.
- 반복은 문장/문단뿐 아니라 빈 줄도 포함했다. 여행 원래1635줄/count1359줄, 백업 원래1392줄/count938줄의 연속 빈 줄이 마지막에 있었다. 따라서 EOS와 의미 완결을 동일시하거나 중복률이 낮다는 이유만으로 품질 향상을 주장하지 않는다.9개 고정 프롬프트 결과와 한계를 docs/INTEGRATION 및 task에 반영했다.

## 2026-10-28 / 명확한 과업9개 대조 / 최종 검증 완료

- git diff --check 통과.9개×양 모드18개 정성 검토가 원본 결과와 일대일 대응하고 라벨 범위/메모 존재, EOS2건·상한16건/2048 ID, UTF-8 전부 유효, HF/수동 제어 및 실행 코드 해시 일치를 assert했다. 원본 SHA25608dab2512d81096c2ed5ded8522528a448b4923c3faef0115f00b26076234765, 검토 SHA25676ee497cb46cd6ddcc5b38d27398acfa286529075db9b0429fbfb9ab0d1fcf9f다.
- 최종 Python 코드 변경 후 집중8개/전체37개 회귀 및 실제18건 실행이 통과했고 편집기 오류 없음 상태다. 요청한9개 고정 프롬프트 대조는 완료했다. 지시를 명확히 해도 이번 과업군에서는 반복/상한 문제가 남았으며 기반 모델과 패처의 일반 품질 또는 이전 raw 문장 대비 인과적 개선을 확정하지 않는다. 임계값 재적합·가중치 변경·대규모 품질 평가·추가 최적화는 실행하지 않았다.

## 2026-10-28 / EOS 원인 다각 진단 / 동일 문맥 대조 계획

- 사용자는 다수 상한 종료의 원인을 다각적으로 분석해 실사용 가능성을 판단하도록 요청했다. 성공 문맥을 찾는 방식 대신9개×양모드18개 저장 경로 전부를 대상으로 고정 문맥의 EOS/개행 확률·순위·엔트로피를 비교한다. 가설은 반복 진입 후 개행/반복 바이트 선택이 강해져 EOS가 낮아지는 현상, 구현 차이 및 BF16 경계 민감성이다. 종료 루프는 앞서 실제 EOS [2]를 즉시 멈추는 것으로 검증됐지만 공통 변환 문제는 별개다.
- 새 점수 진단 scripts/diagnose_blt_eos_causes.py에서 생성 위치0/128/512/마지막 선택 직전과 trailing whitespace 시작/16 ID 이후를 자동 선택한다. EOS 자체는 prefix에서 제외한다. 같은 prefix를 공식HF BF16/OSC BF16/count BF16/OSC FP32(tf32 false)에서 재계산하고 기존 자기 경로 next-ID 일치를 제어로 검사한다. FP32는 기존 BF16 로드 가중치를 승격하므로 원본 고정밀 가중치 복원이 아닌 연산 정밀도 대조다.
- 가중치·원본 프로젝트·디코딩 정책은 변경하지 않는다. GPU0/CPU8/timeout1800초, 모델은 하나씩 로드/해제한다. 가장 싼 사전 체크는 점수 위치 선택이 EOS를 입력에 포함하지 않고 개행 반복 시작을 정확히 찾는 단위 테스트다. 공식 구현도 같은 변환 가중치를 공유하므로 이것만으로 upstream 변환 동등성을 증명할 수 없고 기존 가중치 검증 보고서의 실제 범위도 확인한다.

- 사전 집중 테스트9개 중 새 경계 테스트1개 실패: EOS 없는32 ID 기록에서 위치32를 선택해 기록 범위를 한 칸 넘었다. 마지막 위치를len(ids)-1로 제한하는 국소 수정을 적용하고 같은 테스트를 재실행한다. 모델 추론 전에 발견된 진단기 오류이며 기존 결과/가중치/생성 정책은 변경하지 않았다.

## 2026-10-28 / EOS 원인 다각 진단 / 회귀 통과 및 점수 대조 실행

- 수정 후 집중9개0.007초/전체38개1.147초 통과. en-blt-eos-causes-20261028-01에서 저장18개 경로의 위치를4개 모델 조건으로 재계산한다. 입력 EOS 없음/모델 하나씩 로드/GPU0 사용128MiB 미만 사전 조건/timeout1800초/FP32 TF32 비활성으로 수행하며 결과를 구현별 progress에 보존한다.

## 2026-10-28 / EOS 원인 다각 진단 / 320개 점수 실행 완료

- 서버 시작 관측2026-10-27T23:44:17+00:00(한국시간10월28일), timeout1800초 내 exit0. 공식BF16/OSC BF16/count BF16/OSC FP32 각각80개, 합320개 점수를 계산했다. Python 편집기 오류 없음. 다음은 자기 경로 제어와 같은 문맥의 EOS/개행 확률 차이 분석이다.
- 기존 weights_p1_validation_20260915.json은 원본515텐서→변환510텐서의 매핑/형상/자료형/값 torch.equal 검증을 passed로 기록한다. 변환 보고서 해시는 현재와 같다. 다만 forward_parity_passed false/validation pending을 명시하므로 이것만으로 전체 forward 동등성을 주장하지 않는다. 이것은 당시 검증의 범위이며 후속 별도 검증의 부재나 현재 변환 실패를 의미하지 않는다.

## 2026-10-28 / EOS 원인 다각 진단 / 동일 문맥 분석 결과

- evidence/english_blt_eos_causes_20261028.json: diagnostic_complete, 자기 생성 경로80/80 next-ID 재현. 같은80문맥에서 OSC BF16 대비 count BF16/OSC FP32 argmax80/80 일치, 공식HF77/80 일치. 드문 분기 이후 자유생성 경로가 달라질 수 있으므로80개 선택점 일치가 전체모드 동등성을 뜻하지 않는다.
- 장기 공백 꼬리는 여행 양모드1636/1360 ID, 백업 양모드1393/939 ID다(이전 검토의 blank-line 개수와는 단위/개행 시작 포함 여부가 다름). 여행 OSC 경로 위치412에서 EOS0.1916289/개행0.75791, 위치428에서 EOS0.0121841/개행0.85417, 위치2047에서 EOS0.0000069/개행0.99955로 변한다. 백업 OSC도 위치655에서 EOS0.0777376/개행0.86229, 마지막 EOS0.0000029/개행0.99958. count 자기 경로도 같은 방향이며 모든4조건에서 마지막 공백 위치는 개행을 선택한다. 이는 EOS 억제보다 greedy의 개행 선택과 반복 문맥의 분포 집중이 직접 원인임을 지지한다. 모든문맥의 엄밀한 단조성이나 샘플링 성공은 측정하지 않았다.
- 두 자연EOS 문맥에서 OSC/count/OSC FP32는 모두EOS를 선택하지만 공식HF는 둘 다공백을 고른다: story_clock EOS확률 OSC0.7641/count0.8310/공식0.005669, compare_laptop OSC0.6653/count0.7185/공식0.0009504. 공식구현 교체가 해결책이라고 볼 수 없다. FP32 대조는 이번80문맥의 결정 불변이며 전체 free-running FP32 생성 검증은 아니다.
- 과거 공식load smoke는 단64 ID 생성/유한loss/shift를 검증하고 status passed지만 자연종료·의미완료를 통과기준으로 삼지 않았다. 당시 한국어 출력도 끝 UTF-8이 잘렸고 OSC smoke는 GEC 구분자 반복이었다. 이를 사용자 과거 별도HF 실험과 동일시하지 않는다. 다음은 원본 구현 대조 공백/설정 차이를 확인하고 현재 실사용 차단 판정과 후속 개입을 문서화한다.

## 2026-10-28 / EOS 원인 다각 진단 / 원인·한계·실사용 판정 문서화

- docs/INTEGRATION.md에320개 점수/확률표/구현·정밀도·프롬프트·디코딩·변환 검증 범위를 기록하고 task.md 완료/미완료를 구분했다. 현재 greedy 구성은16/18상한 및EOS출력 품질 결함으로 실사용 보류다. 개행 반복의 직접 기제는 관측됐으나 모든 문장 반복의 학습적/구현적 근본 원인은 아직 분리되지 않았다.
- 원본 entropy params는EOS2/BOS/EOS학습 추가/local_block_causal/sliding_window512이고 변환 config는EOS2/threshold1.335442066192627/max_patch_lengthNone, loader는original_spec을 명시적으로 이용한다. 이번 파라미터/loader 읽기는 전체 설정의 upstream 동등성 인증이 아니다. check_patch_parity.py도 same-logits entropy/scalar분할 확인이며 legacy_reference_valid false와 entropy forward pending을 명시한다. 과거 weights checker hash97c8988056486cff1cc9ffc7597ec9d954ee10e56b7f6b769af2d50e4e54fa7d, OSC smoke2e2f2878f6eea84fcfe3f644579d8600c17b0c72077ba4914753c840e01f3864, official load59ca9b0ed64592da845d74cd6edb9e471a54cccba0df6473675f8b7a90d0d27c.
- 점수 증거SHA25656855a609d0334c6fd370e3f83ad15eb60c34b42d8696d7c6e35d85ee9c967ad. 후속 우선순위는 원본 upstream 같은prefix forward/entropy/patch 대조, 그다음 고정prompt×seed 디코딩 품질 대조다. 이번에는 그 둘을 수행하지 않았으며 원본 프로젝트/가중치/임계값/LMDB/생성정책은 수정하지 않았다. 최종으로 증거 구조·source lineage·원격/로컬SHA 일치를 점검한다.

## 2026-10-28 / EOS 원인 다각 진단 / 최종 검증 완료

- 최종 stdlib 구조 검증 통과:18경로/4조건각80개/총320개, 모든EOS·개행 확률 유한·[0,1]범위, 엔트로피 유한, EOS입력 없음, 저장 next-ID 일치, 자기 경로80/80. instruction9/legacy1024 source SHA와 진단기·종료진단·adapter·count·LMDB 현재 로컬코드SHA 모두 일치. 원격/로컬 점수보고서 SHA56855a609d0334c6fd370e3f83ad15eb60c34b42d8696d7c6e35d85ee9c967ad 일치.
- 집중9개/전체38개 회귀 및 실제320개 추론을 완료했다. 측정된 개행 반복 기제와 구현/정밀도 대조는 문서화 완료, 전체 upstream forward 동등성·일반 생성 품질·샘플링 해결 여부는 미검증으로 남긴다. 현재 구성 실사용 보류이며 이후 성능 작업을 자동 재개하지 않는다.

## 2026-10-28 / 원본 BLT 동일 문맥 비교 / 실행 사전검사

- 사용자가1번부터 순차 실행을 지시했다. 보존된 bytelatent__model__blt.py는 원본 ByteLatentTransformer.forward와 직접 patcher 호출을 포함하고 base_transformer는 xformers를 직접import한다. 파일 스냅샷이 있다는 사실만으로 실행가능성을 주장하지 않는다. 가설은 기존환경에 upstream 패키지/의존성이 없다는 것이며 최소 판별은 find_spec 및 실제 bytelatent.model.blt import다.
- scripts/diagnose_blt_upstream.py에 stdlib 사전검사만 추가했다. 기존 BLT 프로젝트에 .venv 디렉터리가 없어 초기 목록 명령이 중단됐고 추측한 model_sources_20260915.json 이름도 실제 없음으로 확인됐다. 소스/기존 가중치/환경은 수정하지 않았다. 다음은 현재 cache .venv에서검사하고 실제 manifest 이름과고정 revision 확인이다. 원본 실행 의존성이 필요하면 별도 격리경로에 준비하며 upstream forward/entropy/patch 비교가 성공하기 전 디코딩 실험을 시작하지 않는다.

## 2026-10-28 / 원본 BLT 동일 문맥 비교 / 현재 환경 import 차단 확인

- en-blt-upstream-preflight-20261028-01/report.json 실행exit0, status blocked: bytelatent.model.blt 실제import ModuleNotFoundError. 현재Torch2.11.0+cu128는있고 bytelatent/xformers/omegaconf/tiktoken/einops는없다. pydantic2.13.5. 진단기편집기오류없음. 사전검사는 차단상태를기록한것이며 원본forward 실행성공이아니다.
- 다음단계는 보존소스manifest의정확한commit을기반으로 별도소스/환경을구성한다. 기존cache .venv나 owning프로젝트소스/가중치는수정하지 않는다.

## 2026-10-28 / 원본 BLT 동일 문맥 비교 / 고정 소스 및 격리 환경 준비

- model_source_review.json의 review_source_commit9774ed4fcc78313f9f218295f3d7e4decdadf2ae를별도 /home/itcmaster/projects/blt-cache/upstream-blt-9774ed4에clone/detachedcheckout했다. 원래학습시실제코드revision은manifest의legacy_actual_commit null이므로 이검사는보존리뷰commit의원본구현대조다. 기존소스/가중치는수정하지않음.
- 별도 .venv-upstream-20261028 생성, 디스크여유349GiB. 기존Torch2.11.0+cu128를읽기전용PYTHONPATH로공유하고추가의존성은새환경에만설치한다. venv의system-site-packages만으로기존다른venv가공유되는것은아니므로명시경로가필요하다. PyPI xformers최신목록0.0.35 확인; wheel요구Torch와실제import/CUDA지원검사가필요하며성공을미리주장하지않는다.

## 2026-10-28 / 원본 BLT 동일 문맥 비교 / 최신 xformers API 차단

- 격리환경에 --no-deps로xformers0.0.35/omegaconf2.3.0/antlr4 4.9.3/tiktoken0.14.0/einops0.8.2/blobfile3.3.0/msgspec0.22.0 설치. 기존Torch2.11.0+cu128 경로/버전불변을preflight02에서확인했다. 원본import는 AttributeError torch.ops.xformers.efficient_attention_forward_cutlass 부재로차단됨. 실제forward는아직실행하지않았다.
- 원본소스를새API로고쳐독립기준을흐리는대신 원본이사용하는연산자가존재하는Torch/xformers조합을또다른격리환경에준비한다. 기존Torch환경은보존하며이환경에서OSC도함께측정해런타임차이를분리한다. GPU Blackwell지원/원본소스해시/strict로드를각각확인한다.

## 2026-10-28 / 사용자 정정 / 기존 HF 환경 사용

- 사용자가 환경은 HF 버전으로 바꾼 것을 이용하면 된다고 정정했다. 직전 구버전 Torch2.7.1/xformers0.0.31.post1 환경 준비 계획은 철회한다. 정정 후 서버 프로세스 확인에서 관련 pip/uv 설치 및 upstream 진단 실행은 없었다. 보존된 별도 환경/소스는 삭제하지 않으며 기존 cache .venv와 HF 변환 가중치를 사용한다.
- 다음 비교는 기존 HF 환경에서 공식HF와 OSC의 동일 문맥 entropy/패치 경계/본체 차이를 분리하는 경로다. 이미 확보한320점수 결과를 재사용하며 단순 반복 실행하지 않는다. HF 변환본끼리의 비교를 원본 upstream 동등성 증명으로 확대하지 않는다. task.md에 사용자 정정을 우선 항목으로 반영했다. 이번 정정에는 모델 코드·가중치·패처·설치 패키지 변경이 없다.
- 정정 기록 검증: git diff --check -- task.md log.md exit0. 관련 설치 실행은 없으므로 중단할 프로세스도 없었다. 구버전 환경 준비 대신 기존 HF 환경을 사용한다는 사용자 제약을 유지한다.

## 2026-10-28 / 사용자 지시 / 불필요한 원본 실행 의존성 삭제 준비

- 사용자가 불필요하게 설치한 의존성을 모두 삭제하도록 지시했다. 직전 별도 환경/소스 보존 방침은 이 지시로 대체한다. 서버의 이번 작업 소유 경로 세 개를 확인했다: .venv-upstream-20261028(22MiB), .venv-upstream-t271(56KiB), upstream-blt-9774ed4(2.3MiB, commit9774ed4fcc78313f9f218295f3d7e4decdadf2ae). 실제 관련 설치/진단 프로세스는 없었다.
- 첫 환경에 추가된 xformers0.0.35/omegaconf2.3.0/antlr4_python3_runtime4.9.3/tiktoken0.14.0/einops0.8.2/blobfile3.3.0/msgspec0.22.0는 환경 디렉터리 제거로 모두 삭제한다. 두 번째 환경은 dist-info가 없는 빈 준비 환경이다. 삭제 전 기존 .venv의 Python prefix와 Torch2.11.0+cu128/Transformers5.16.1 import를 확인했다. 공유 캐시·기존HF환경·모델·데이터·실험증거는 삭제하지 않는다. 다음은 정확한 세 경로만 제거하고 경로 부재/HF import를 검증한다.

## 2026-10-28 / 불필요한 원본 실행 의존성 / 삭제 및 검증 완료

- git diff --check -- task.md log.md exit0 후, 세 경로가 symlink 아닌 디렉터리임을 확인하고 지정한 경로만 rm -rf로 제거했다. .venv-upstream-20261028/.venv-upstream-t271/upstream-blt-9774ed4 모두 부재 검사 통과. 추가 설치7개 패키지는 첫 환경과 함께 제거됐다.
- 기존 /home/itcmaster/projects/blt-cache/.venv에서 Torch2.11.0+cu128/Transformers5.16.1 버전 assert 및 import 통과, find_spec(xformers)는None. 기존 HF 환경은 유지됐고 모델/데이터/진단 증거/공유캐시는 건드리지 않았다. task.md 삭제 항목 완료. 이후에는 기존 HF 환경만 사용한다.

## 2026-10-28 / HF 단계별 동일 문맥 비교 / 참조 정책 및 실험 계획

- 사용자가 다음 작업 재개를 요청했다. 공개 phdq3 commit a1d134362f3982749f8787114e1c3b37a6190397의 P1/NOTES/model/THIRD_PARTY_NOTICES를 참조했다. P1은2026-09-16에 전체 원본 동질성 게이트를 명시적으로 폐기했고 xformers 없는 HF 환경의 가중치 보존 및 실제 mask 검사를 요구한다. 이전 pending을 실행 차단으로 되살리지 않는다. 서버 HEAD734ee03과 미추적 HF 파일을 GitHub 최신본과 동일시하지 않으며 실행 파일 해시를 별도 기록한다.
- 기존 diagnose_blt_eos_causes.py에 --stage-comparison 추가.7개 선정 문맥(짧은 letter prompt, 여행 반복시작412/이후428/마지막2047, 백업655, 자연EOS clock1338/laptop867)을 실행 전 고정한다. 정상 의미품질/종료율의 대표 표본이 아닌 기제 진단이다. OSC/공식HF/lre 자동경계 및OSC동일경계, OSC의 encoder/decoder/both local 마스크를 full-causal로 임시 주입해 경계 산술과 window 영향을 분리한다. hook은 finally에서 제거하고 모델은 하나씩 로드한다.
- 가설: 고정경계에서도 local window 차이가 EOS분포 차이를 설명할 수 있다. 판별은 고정경계+양local full-causal OSC가 공식HF 고정경계의 단계별 출력과 정확히 같은지 검사하는 것이다. 짧은대조군/OSC 외부경계 replay/lre=공식HF를 제어로 둔다. 실제 원본/패처/설치 환경은 변경하지 않는다. 다음은 기존 집중회귀 및 toy tensor/hook 테스트 후GPU 진단이다.

## 2026-10-28 / HF 단계별 동일 문맥 비교 / 사전 검증 통과

- 수정 후 집중9개 테스트0.007초 통과. 저장instruction9에서7개선정/범위/EOS입력 없음 검증 통과, 길이212/734/750/2369/1060/1553/1220 ID. 텐서비교의 동등/값차이/형상불일치 분기 실행검증 통과. 아직 hook정리/단계출력 제어는실제실행전이며 GPU 대조에서 확인한다.
- en-blt-hf-stages-20261028-01에서 기존 .venv, GPU0사용128MiB미만 사전조건, timeout1800초/CPU8/BF16/eager/no-cache/logits_to_keep1로 실행한다. 고정7문맥×OSC5조건/공식2조건/lre2조건=63회 forward이며 자유생성/가중치/패처규칙 변경은 없다.

## 2026-10-28 / HF 단계별 동일 문맥 비교 / GPU 실행 완료

- 서버 시작관측2026-10-28T04:03:28+00:00. en-blt-hf-stages-20261028-01 exit0, OSC35/공식14/lre14 합63회 forward를timeout1800초내 완료했다. 실제 패키지 추가설치 없이 기존Torch2.11.0+cu128/Transformers5.16.1 사용. 진단기 편집기 오류 없음. 다음은보고서를보존하고 제어/단계출력/마스크개입별EOS확률을검증한다. 아직 stdout 실행완료만으로제어통과를주장하지않는다.

## 2026-10-28 / HF 단계별 동일 문맥 비교 / 제어 및 원인 분리 결과

- evidence/english_blt_hf_stages_20261028.json 보존(약608KiB), status diagnostic_complete/제어34개실패0. OSC 외부경계 replay7/7, local 양마스크full-causal→공식HF 고정경계 전체단계 정확일치7/7, lre=공식 자동/고정각7/7, OSC원래자기경로 다음ID6/6(나머지laptop은count경로여서OSC제어에서제외)이다.
- 212ID 짧은입력은 entropy logits/encoder bytes가OSC와공식에서정확히같지만 entropy최대차0.0390625와패치61(S+1=213)/62(S=212) 차이가난다. 같은OSC경계를주면본체전체가정확히같다. 긴6문맥에서는entropy logits부터window에따라달라지고 자동경계차이가크다. OSC/공식 patch수는 여행412:132/187, clock:231/983, laptop:149/617. 이는기존정책의window/entropy산술/S+1차이와일치하며원본동등성·버그판정은아니다.
- 고정OSC경계에서local encoder만full-causal/decoder만full-causal/양쪽full-causal의EOS확률은clock:0.3016405/0.0061460/0.0082215(기본OSC0.7640632), laptop:0.0047447/0.0029331/0.0004512(기본0.6653484). 양local을바꾸면공식동일경계와전단계정확히같아져, 이문맥들의본체차이가local window 개입으로설명된다. 양쪽각각EOS를바꿀수있고상호작용이있으므로decoder만유일원인이라하지않는다.
- 여행마지막2369ID는모든9조건에서개행을선택한다. OSC기본EOS0.0000069/개행0.999549, 양local full-causal EOS0.0030226/개행0.864674, 공식자동EOS0.0031730/개행0.951273. 공식전환·window제거가실사용해결책이라는근거는없다. 다음은진단선택/비교/hook예외복구회귀를추가하고수치·기존320점수재현·source연결을최종검증한다.

## 2026-10-28 / HF 단계별 동일 문맥 비교 / 集中 회귀 통과

- 추가한3개진단회귀를포함한집중12개0.010초통과. 문맥선정의EOS/범위거부, 텐서형상/값차이, 실제마스크주입후의도적forward예외에서모든hook제거를검증했다. 테스트의미사용import만제거하며진단기/실험코드는변경하지않았다.
- task.md에HF단계비교완료와취소된upstream환경/동질성게이트를명시했다. 다음은전체41개회귀와저장증거/코드해시/기존점수대조검증이다. 자유생성및디코딩개선효과는아직측정하지않았으며기존OSC정책을바꾸지않는다.

## 2026-10-28 / HF 단계별 동일 문맥 비교 / 전체 회귀 및 증거 검사 중간 결과

- 전체41개회귀1.193초통과/편집기오류없음. 공개phdq3 commit a1d134362f3982749f8787114e1c3b37a6190397와서버의modeling_blt.py/attention.py/patching.py/model.py가4/4바이트동일함을urllib로읽기전용검증했다. 서버GitHEAD는오래됐지만이4개실행파일은최신공개구현과같다.
- 단계보고서SHA256cf4a5000248d1a423e5d529ad349cfdd6fb2a5fa9ab68d91a60c35f668cb9b93. 최종stdlib검증은패치길이전부양수라는추가가정에서AssertionError로중단됐다. 아직원인확인전이며기존제어34개실패0와구분한다. 다음은실패조건을보고서에대조해HF경계의0길이표현인지sum문제인지확인한뒤동일검증을수정/재실행한다. 모델코드/저장결과는변경하지않는다.

## 2026-10-28 / HF 단계별 동일 문맥 비교 / 최종 증거 검증 및 문서화

- 추가검증실패는公式HF/lre자동경계의말미0길이슬롯하나때문이었다. 모든63회길이합은정확하고음수없음. HF/lre자동14회는끝0하나/나머지양수, OSC기준고정/자동49회는전부양수임을확인했다. 그표현을반영한동일최종검증통과:63회/34제어/7문맥/유한차이·확률/source·진단코드SHA/기존14개점수정확재현. 원격·로컬보고서SHAcf4a5000248d1a423e5d529ad349cfdd6fb2a5fa9ab68d91a60c35f668cb9b93 일치.
- 앞서적은공식자동patch수187/983/617등은0길이슬롯하나를포함한슬롯수다. 양수patch수는각각186/982/616으로구분한다. 212ID대조군OSC61/공식62도공식끝0포함이며이수차만으로entropy개입의독립효과를주장하지않는다. docs/INTEGRATION.md에이구분과고정경계/마스크개입결과를기록했다.
- 공개P1의2026-09-16 전체동질성게이트폐기를반영해, 앞선원본upstream복원우선제안을명시적으로철회했다. 실제HF구현4파일이공개고정커밋과같음을확인했고불필요환경은삭제한상태다. 이번단계에서공식HF와OSC의본체차이는고정경계+양local full-causal개입으로7/7전단계정확재현했다. 종료품질해결·원본parity증명이아니다. 다음단계는기존OSC정책을유지한고정prompt×seed디코딩대조이며이번에는실행하지않았다.

- 최종 git diff --check(진단기/테스트/INTEGRATION/task/log) exit0, 증거SHA불변확인. 집중12개/전체41개회귀, 실제63회forward/제어34개, 원격·로컬결과 및공개4파일식별검증을완료했다. 해당단계는완료이며실사용품질보류는그대로유지한다. 모델수정·새의존성설치·성능최적화는없었다.

## 2026-10-28 / 고정 디코딩 비교 / 실행 전 계획 및 진단 구현

- 사용자가다음작업진행을지시했다. 가설은greedy에서개행/문장반복진입을sampling이피할수있다는것이며 EOS뿐아니라반복·완결·사실성동시관측으로반증한다. instruction9_v1 전체9개/상한2048/기존OSC BF16/eager/no-cache/batch1/beam1/logits_to_keep1을유지한다. 정책은greedy, 원분포T1/top_p1/top_k0, nucleusT0.8/top_p0.9/top_k0이며sampling각seed42/20261027이다. 9×5=45건전부실행하고중간성공으로멈추지않는다. EOS강제/반복페널티/count교체/가중치수정없음.
- 기존종료진단기에 --decoding-controls/--greedy-reference를추가해새greedy9건을기존instruction기록과전체ID대조한다. 매실행후progress원자저장/전체원문·ID보존/시간·GPUpeak·EOS·UTF8·repeat8·공백꼬리·최장동일byte연속길이기록. 반복flag는repeat8>=0.5또는동일byte32개이상으로사전고정하며품질통과문턱이아닌기술지표다. 검토라벨은지시수행·핵심완료·사실성및한계를분리한다.
- GPU0메모리1MiB/RTX5090, 기존Torch2.11.0+cu128/Transformers5.16.1 확인. CPU8/전용run/timeout5400초예정. 가장싼사전검사는고정5조건/seed및EOS제외반복지표/비정상ID거부단위테스트다. 다음은집중14개회귀후전체43개검사및실제45건실행이다. sampling품질·종료개선은아직측정전가설이다.

## 2026-10-28 / 고정 디코딩 비교 / 사전 회귀 통과 및 실제 생성 실행

- 집중14개0.008초/전체43개1.200초통과, Python편집기오류없음. en-blt-decoding9-20261028-01에서9×5조건45건을실행한다. GPU0사전사용128MiB미만확인후기존HF .venv/CPU8/timeout5400초로수행하고매건progress를원자저장한다. greedy전체ID불일치시실험을실패처리하며다른설정과섞지않는다. 시간은생성비용기록이며상이한출력길이의속도향상주장은하지않는다.

## 2026-10-28 / 고정 디코딩 비교 / 실제45건 생성 완료

- 서버시작관측2026-10-28T08:05:26+00:00. en-blt-decoding9-20261028-01가timeout5400초내exit0, 고정9프롬프트×5조건45건모두생성했다. 새greedy9건의전체ID제어가실행중통과했고중간EOS성공뒤에도모든조건을끝까지실행했다. 원분포sampling에서반복지표가낮아지는출력이많았으나일부는여전히2048상한이다.
- 아직최종집계/UTF8/source해시/의미내용검토전이므로이번stdout관측만으로실사용해결을선언하지않는다. 다음은원본JSON보존후정책·seed별검증, 전체45건검토(greedy9건은동일기록의기존검토재사용가능)를수행한다.

## 2026-10-28 / 고정 디코딩 비교 / 결과 무결성·집계 검증 완료

- evidence/english_blt_decoding9_20261028.json 원격·로컬SHA256 5f5dc75c469fc521a457786703613bf3f2f6a1131c2cd8bb06ac3fd27e261673 일치. JSON시각08:05:34.583591–08:46:09.165831 UTC, Torch2.11.0+cu128/Transformers5.16.1/RTX5090/BF16/eager/OSC/threads8. 종료후GPU1MiB로반환됐다. 코드hash전부실행파일과일치.
- 고유45조합/고정정책·seed/9개입력ID·원문/greedy9전체ID/첫EOS위치/2048상한/4096context/UTF8/반복지표/finite생성비용및정책집계재계산검증통과. UTF8 45/45. EOS greedy1/9, 원분포11/18(seed42 7/9,20261027 4/9), nucleus5/18(3/9,2/9). 반복flag8/9·0/18·5/18, repeat8중앙값0.8814307·0.0664074·0.3047526, 새ID중앙값2048·1150.5·2048. 생성시간합606.087·756.419·1071.436초(분모9/18/18상이하고출력길이도달라속도비교불가).
- 원분포sampling은현재표본에서greedy반복을줄였으나7/18상한실패가남는다. nucleus는T와top_p를함께바꾼개입이므로단일변수효과로분해하지않는다. 다음은36개새sampling출력전체를읽고동일greedy9개기존검토와함께45건의의미완료·사실성·꼬리를기록한다. 이단계는아직실사용통과선언이아니다.

## 2026-10-28 / 고정 디코딩 비교 / 전체 출력 내용 검토 및 기록

- 새sampling36건의원문전체를읽었다. 연속동일줄만횟수로표시했고원문은변경하지않았다. 동일greedy9건은 english_blt_instruction9_review_20261028.json의지시수행·완료라벨/notes를재사용하고사실성은기존notes에한정해불확실성을표시했다. 새 evidence/english_blt_decoding9_review_20261028.json에45건모두의policy/seed/지시수행/구조적완료/사실성/구체결함을기록했다. 단일비맹검assistant검토이며외부사실감사·품질인증아님.
- 구체실패: 원분포유리seed42는PET로주제변경후EOS, 노트북seed42는16시간battery→둘다8시간/700달러라는입력수치왜곡후EOS, 백업seed20261027은5달러월비를360달러로바꾸고선택없이EOS. nucleus교통seed42는초기A선택뒤새학생여행문제와replyform, 백업seed20261027은적절한cloud선택뒤에도A자동/수동모순과coupon꼬리가남는다. 이야기미해결·강수물리오류·과정생략도관측했다.
- INTEGRATION에정책·seed별EOS/상한/UTF8/반복/길이/비용및실패사례·한계를추가하고task45건항목완료표시. 현재표본의반복감소는측정됐지만실사용품질은보류다. 다음은새검토JSON의45개조건완전성·라벨·sourceSHA·greedy재사용일치와문서diff검증후이단계를종료한다. 새가중치/패키지/환경/강제중단/성능작업없음.

## 2026-10-28 / 고정 디코딩 비교 / 최종 검증 완료

- 새검토JSON의45고유조건·9×5완전성·허용라벨·비어있지않은notes·원본SHA·기존검토SHA및greedy9건의기존지시수행/완료/notes동일성검증통과. 검토SHA256 113cb5a145eff0f51f76feb7e4d769194d507f9f740237b8ebc59eb325320bad. 로컬실행코드hash도원격결과에기록된값과일치, 관련파일 git diff --check exit0.
- 기술검토집계: 지시수행met는greedy0/9·원분포0/18·nucleus0/18, 구조적완료2/9·2/18·9/18. 이완료라벨은잘못된선택도명시적선택이있으면포함하므로정답률/실사용성으로읽지않는다. 사실성has_error는각3/9·10/18·11/18, fiction/not_applicable및unclear는통과가아니다. 단일비맹검기술관찰의집계이지일반품질추정치가아니다.
- 실제45건/greedy9전체ID제어/UTF8 45/45/집중14개·전체43개회귀/결과·검토무결성검증을완료했다. 이디코딩비교단계는종료하며실사용품질보류는유지한다. 다음단계의새프롬프트·모델실험은이번에실행하지않았고count최적화/BPB/성능작업으로진행하지않았다.

## 2026-10-28 / 사용자 지시 반영 / 신경망·count 패처 비교 재개

- 사용자가 기존 진단을 여기서 중단하고 원래 패처 비교를 진행하도록 지시했다. 과거 보류 조건은 이번 비교의 선행 게이트로 사용하지 않는다. 과거 증거는 보존하며 이후 원인 분석은 진행하지 않는다.
- 기존 측정에 근거해 생성 공통 조건은 원분포 sampling(T1/top_p1/top_k0), seed42/20261027, 상한2048로 고정한다. 모델/OSC/BF16/eager/no-cache/batch1/beam1 및 count threshold0.375/계수/LMDB를 유지한다. 최종 품질 주평가는 같은 바이트열의 teacher-forced BPB이고 경계 지표/패치 길이/비용을 함께 기록한다. 사전 허용 폭이 없으므로 채택 게이트를 임의로 만들지 않는다.
- 기존 smoke 실행기의 argmax 경로가 공통 sampling 비교를 지원하지 않는 것이 국소 제약이다. 기존 greedy API는 보존하고 명시적 seed를 받는 torch.multinomial 기반 sample_generate를 추가했다. 가장 싼 검사는 두 seed의 분리/동일 seed 재현/특수 ID 억제/기존 greedy 보존 테스트다. 다음은 집중 회귀 후 보존된 평가용 문서 계약과 실제 비교 경로를 연결한다. 새 의존성 설치나 재적합은 없다.

## 2026-10-28 / 패처 비교 / 공통 샘플링 집중 검사 통과

- 기존 서버 HF 환경에서 집중16개0.017초 통과. seed42의 독립 호출 전체ID 재현, seed20261027과 경로 분리, 필터 없는 두 바이트 추출, 억제 ID 배제 및 기존 greedy 동작 보존을 검증했다. 다음은 기존 적합/평가 분할 계약을 확인한 뒤 teacher-forced·생성 비교를 연결한다.

## 2026-10-28 / 패처 비교 / 평가 계약 확인 및 조회 경로 정정

- 기존 english_patcher_pilot.json에 BPB 차이의 문서 bootstrap95% 상단<=0.01, bootstrap2000회, 고정 입력 warmup3회/반복10회 기준이 있음을 확인했다. 앞선 '사전 허용 폭 없음' 기록은 이 보존 규약을 확인하기 전 판단이며 정정한다. 현재 고정 후보의 관측 차이와 이 기준을 보고하되 재적합하지 않는다.
- 초기 실험 폴더에 후속 실험의 data_preparation.json 이름을 가정한 읽기 전용 조회가 FileNotFoundError로 종료됐다. 실제 초기 폴더에는 dataset_sources.json/label_generation.json/teacher_contract.json이 있다. 데이터·작업·환경 변경 없음. 실제 파일명으로 heldout 경로와 기존 중복 제외 기록을 확인한다.

## 2026-10-28 / 패처 비교 / 평가 입력 고정 및 단계별 실행기 구현

- datasets/en-patcher-20261019-01의 test/Wikipedia test/train/validation 파일 SHA가 10GB data_preparation.json의 original_split_hashes와 전부 일치했다. 평가원문 해시 test=d6f7b14ef862a1c076f4cce7f2d0028f8c08913f8c9abc6c3ed54f3c216d4eec, wikipedia_test=fb9832076db21acbc17aaa1b4b96259a5ad06b09d9a6765e12db8c45f53d77f7. 기존 exact/URL/MinHash128 근사 중복 제외 및 보호 기록을 사용하며 완전한 유사문서 배제나 본체 사전학습 비중복을 주장하지 않는다.
- 비교 실행기 scripts/compare_blt_patchers.py를 추가했다. quality는 두 평가 분할 전체/문서 단위/2047바이트 비중첩+BOS/청크 reset으로 동일 실제바이트의 NLL·BPB를 구한다. 문서 paired bootstrap2000회/seed20261019/기존차이기준0.01을 유지한다. 경계는 기존 라벨 계약의 위치2..n(가상 next-slot 포함), F1/F0.5 동시 보고하되 기존 F1 선택 후보를 재적합하지 않는다.
- timing은 분할별 길이256/512/1024/2048의 첫 적격 문서 첫청크, warmup3/교대10회. 패처prefill·모델prefill·동일 접두부32회증분 패처를 별도 측정한다. 실제 신경망 패처 호출 인자를 캡처하고 단독 호출 경계 일치를 검사한다. generation은 기존9프롬프트×2seed×2패처=36회, 공통 원분포sampling/상한2048, seed별 순서교대, 원래패처의 기록된 HF sampling 전체ID를 제어로 대조한다.
- 단계별 별도 JSON/원자 progress/실패보존/출처·코드SHA를 남기며 원문 데이터나 모델을 저장소에 복사하지 않는다. 다음은 청크 바이트 보존/가상 경계/F지표/byte 가중 bootstrap 집중 검사 후 실제 quality부터 실행한다.

## 2026-10-28 / 패처 비교 / 실행기 회귀 통과 및 quality 시작

- 집중19개0.018초/전체48개1.153초 통과, 변경 Python3파일 편집기 오류 없음. 사전 GPU0 사용1MiB, 디스크 가용365,481,292KiB 확인. 기존 HF .venv/CPU8/RTX5090에서 전용 runs/en-blt-patcher-compare-20261028-01을 사용한다.
- quality.json을 먼저 생성한다. 두 평가 분할 전체, 원문 파일·문서별SHA 및 기존 보호 분할 대조, 적합/변환/배경 식별자 검증 후 각 문서의 모든2047바이트 청크를 양 패처에 넣는다. 시간 상한5400초 내 실패 시 부분 progress와 실패 보고서를 보존하며 데이터를 자동 축소하지 않는다. 다음 단계로 넘어가기 전 실제 품질 결과를 기록한다.

## 2026-10-28 / 패처 비교 / 전체 평가 실행 완료

- 서버 시작 관측2026-10-28T09:46:35+00:00. quality 단계 exit0, FineWeb test113문서/Wikipedia test220문서 총333문서 전체를 처리했다. 적합·배경·분할·원문SHA 및 경계 길이 계약 검사도 실행중 통과했다. 데이터를 축소하거나 규칙을 재적합하지 않았다. 다음은 quality.json을 로컬 증거로 보존하고 문서별 NLL·byte 가중 BPB·paired bootstrap·경계 집계를 재검증한 뒤 고정 입력 타이밍으로 이동한다.

## 2026-10-28 / 패처 비교 / 전체 품질 결과 검증 및 고정 입력 타이밍 시작

- evidence/english_blt_patcher_quality_20261028.json 원격·로컬SHA b93a15bf3d2f2d57e96bba9457b1668d1a68b95682dbd8007f76add2b8b37427 일치. JSON 실행09:46:37.248624–09:51:40.549194 UTC, host peak29,705,908,224바이트. 전체333문서/1,497,578바이트의청크·손실·경계·길이히스토그램독립재집계, 출처·코드SHA, bootstrap재계산검증통과.
- FineWeb BPB0.7709047522→0.7737696030(차이+0.0028648508,95%[+0.0012703058,+0.0046950582]); Wikipedia0.8303014877→0.8323763702(+0.0020748825,[+0.0011416466,+0.0030207773]); 합산0.8106483993→0.8129846651(+0.0023362658,[+0.0015224279,+0.0032011347]). 각기존BPB상단<=0.01기준통과. 손실은측정상증가했으며'동일품질'주장은아니다.
- 경계TP275426/FP128558/FN63472,precision0.6817745/recall0.8127106/F1 0.7415067/F0.5 0.7044741. 패치수340754→405840, 평균길이4.4003416→3.6946432. 이는고정F1선택규칙의새평가이며재적합·F0.5선택결과가아니다. 기존F1 0.90화면기준을통과했다고주장하지않고BPB기준만분리보고한다.
- 다음timing.json은각분할·길이별첫적격문서8개, 패처prefill/모델prefill/동일접두부32회증분각warmup3·교대10회로수행한다. 원문과같은입력작업량의비교이고DB는warm상태다. 기존모델·규칙·환경을유지하며개선코드는추가하지않는다.

## 2026-10-28 / 패처 비교 / 고정 입력 타이밍 실행 완료

- 서버시작관측2026-10-28T09:53:05+00:00. timing 단계 exit0, FineWeb/Wikipedia×256/512/1024/2048 ID의8입력 모두 완료했다. 실제모델호출에서캡처한인자에따른신경망패처단독경계제어8건도실행중통과했다. 각측정종류/패처 warmup3·교대10회이며32회증분의priming은시간에서제외했다. 다음은원시480표본과p50/p95·메모리·출처를검증하고생성36조건으로이동한다.

## 2026-10-28 / 패처 비교 / 타이밍 검증 및 공통 샘플링 생성 시작

- evidence/english_blt_patcher_timing_20261028.json 원격·로컬SHA ddd6dcfc51c71eb1a1cdf0720371a0324d4873a4fa4ef50bd1be8de6c54ae485 일치. JSON09:53:08.132379–09:54:23.237857 UTC,host peak10,153,635,840바이트. 8입력×3종류×2패처×10=480개양수·유한표본, 고유분할/길이,입력길이,p50/p95 독립검증통과.
- 모델prefill p50 신경망/count ms(FineWeb):256=15.2637/31.6965,512=19.0457/55.7117,1024=24.4031/120.3932,2048=59.4393/246.0497. Wikipedia:15.3633/32.3456,19.8141/55.8282,26.6670/122.2843,67.6934/264.6022. count모델prefill은현재고정8입력에서약2.08–4.93배느렸다.
- 패처증분32회 p50 신경망/count ms(FineWeb):108.8400/6.4985,137.7373/7.3901,201.5957/9.7769,714.5127/12.4192. Wikipedia:108.8492/6.3471,137.7355/6.8447,201.8903/10.0085,714.6290/13.0600. warm prefix에서후보약16.75–57.53배빠름. priming/원래패처의재계산정책/CPU조회·전송을포함한현재조건이며일반모델전체속도가아니다. 패처cold prefill은반대로느리다.
- 다음 generation.json은사전고정9프롬프트×2seed×2패처36건, 공통원분포sampling/상한2048/no-cache로실행한다. 각프롬프트양패처16ID warmup후seed마다순서교대, 원래패처18건은기록된HF sampling전체ID와대조한다. 원문·ID·시간·GPUpeak보존, 다른생성경로의총시간은동일작업량가속으로해석하지않는다.

## 2026-10-28 / 패처 비교 / 공통 샘플링 생성36건 완료

- 서버시작관측2026-10-28T09:55:19+00:00. generation 단계 exit0, 사전고정9프롬프트×seed42/20261027×양패처36건을전부처리했다. 신경망기준18건은기존HF 원분포sampling의전체생성ID와모두일치했다. count규칙/threshold/본체/환경변경없음.
- 양쪽생성경로와길이가달라진사례가다수관측됐다. 다음은원문·ID증거보존, 고유36조건/입력·seed/출력범위·UTF8·finite비용·메모리·출처SHA 검증과대표출력내용확인이다. 생성총시간을동일작업가속으로요약하지않는다.

## 2026-10-28 / 패처 비교 / 생성 증거 검증 완료

- evidence/english_blt_patcher_generation_20261028.json 원격·로컬SHA bd88edc92e5c46fb385b5a8fea12e61476840993bfc13b8fc21be209db7f1216 일치. JSON09:55:22.144898–10:15:20.729857 UTC,host peak10,153,140,224바이트. quality/timing/generation 세단계의출처·코드SHA도모두실제파일과일치했다. 완료후GPU1MiB.
- 고유36조합/입력ID·문맥/동일seed·공통설정/출력ID범위·원문복원/UTF8/유한시간·메모리 검증통과. 신경망기준18건은기록된HF출력전체ID와일치. UTF8양쪽18/18. 양패처의서로동일한생성은0/18이며이는출력동일성을요구하지않는대체패처비교다.
- 생성ID합계신경망23554/count18279, 중앙길이1150.5/673. 시간합753.8013/434.6476초, 실행당시간중앙28.0602/10.7716초. GPUpeak10,257,550,336/10,427,063,808바이트. 서로다른경로·길이·동일조건한번씩측정이므로전체생성의일반가속률이나paired속도신뢰구간으로해석하지않는다. 다음은새후보출력내용확인과문서/작업상태정리다.

## 2026-10-28 / 패처 비교 / 내용 확인·반복 변동 구간·문서화 완료

- count후보18개생성원문전체를읽었다(연속동일줄만횟수로표시, 원문변경없음). 노트북seed20261027은A를고르지만700/850=.94등계산오류, 유리seed20261027은삼각형절단/구멍뚫기로재활용을왜곡, 백업seed20261027은수동드라이브를자동으로바꾸고essay문구로이탈했다. BPB허용충족과생성의정확성/출력동일성은분리한다. 단일비맹검기술관찰이며새품질점수나일반개선주장은없다.
- 같은반복블록10개를paired재표집하는2000회/seed20261019 bootstrap으로입력별모델prefill·패처증분비율95%구간을계산했다. 모델비율0.2027–0.4816, 증분16.7485–57.5331이고모든고정입력에서방향이동일하다. 세부구간을INTEGRATION에기록했다. 단일실행내기술적변동구간이며다른GPU/말뭉치전체성능신뢰구간은아니다.
- 앞서'cold prefill'이라적은것은어댑터prefix상태를처음부터만드는경우를뜻하며DB의cold-storage측정이아니다. 이번모든타이밍은warm DB, 원래패처가중치GPU상주, CPU조회·전송포함이다. 기존prefix전체모델1.05배속도기준은미달이고패처증분1.2배기준은현재8입력에서충족한다. BPB기준만으로전체채택을선언하지않는다.
- INTEGRATION에333문서품질/경계/분포/480타이밍표본/36생성원본및한계를통합하고task의새비교항목3개를완료표시했다. 보존평가333문서는이제열람됐으므로규칙의미변경·재튜닝은새heldout이필요하다. 다음개선후보는count prefill이나이번비교에서새최적화를구현하지않았다. 다음은관련변경의최종회귀·문서/증거식별자검사다.

## 2026-10-28 / 패처 비교 / 최종 검증 및 단계 완료

- 최종전체48개회귀1.156초통과(사전집중19개/전체48개도통과). 품질/타이밍/생성원본3개SHA가문서기록과일치하고runtime/규칙/count config/보호분할/실행코드식별자가세단계에서동일함을검증했다. 새문서의모든로컬링크존재,task최신비교3항목완료,관련 git diff --check exit0 확인.
- 사용자지시에따른원래패처비교를끝냈다. 측정결론은고정후보의BPB소폭증가가보존허용기준내이고,동일접두부증분패칭은빠르나초기입력처리는느리다는것이다. 생성원본/실행비용은다른길이·경로라는한계와함께보존했다. 환경/모델/데이터/기존작업은유지했고재적합·배경확대·새최적화·자동채택·커밋/푸시는하지않았다. 후속구현이진행된다면동결후보의규칙·경계를보존하는count prefill 비용개선이우선대상이다.

## 2026-10-29 / 사용자 요청 / 프로젝트 문서 한글화 시작

- 사용자가 docs/INTEGRATION.md, docs/HANDOFF.md, docs/EVIDENCE.md를 한글로 바꾸도록 요청했다. 제목·본문·표의 설명을 번역하며 기존 실험 기록의 의미와 한계는 유지한다. 실행 코드·명령어·API·파일 경로·링크 대상·해시·수치는 변경하지 않는다. 원본 JSON 근거와 생성 원문은 번역 대상이 아니다.
- 수정 전 세 문서의 코드 블록·인라인 식별자, 링크 대상, 수치 목록을 추출해 정렬 목록의 SHA256을 기록했다. 인수인계31개/근거색인11개/통합94개 코드 구간이 기준이다. 인수인계와 근거 색인을 먼저 번역했으며 다음은 식별자 보존 검사 후 통합 문서의 구간별 번역이다.

## 2026-10-29 / 문서 한글화 / 인수인계·근거 색인 검증 및 통합 문서 번역

- 인수인계와 근거 색인의 코드 구간·링크 대상·수치 목록 해시가 수정 전과 모두 일치했다. 통합 문서는 설치·패키지 연동·count 어댑터 사용법·확장 검증의 설명과 표부터 번역했다. 실행 코드 블록은 변경하지 않았다. 다음은 통합 문서 보존 검사 후 남은 과거 기록과 최신 비교 결과를 번역한다.

## 2026-10-29 / 문서 한글화 / 통합 문서 앞부분 보존 검사 통과

- 통합 문서 앞부분 번역 후 코드94개·링크20개·수치723개의 목록 해시가 원문 기준과 모두 같았다. 이어서 과거 검증 기록과 지시형 프롬프트 표를 번역했다. 당시 결론과 이후 수정된 판단은 원래 순서대로 보존한다. 다음은 같은 보존 검사 후 남은 비교 기록 번역이다.

## 2026-10-29 / 문서 한글화 / 통합 문서 중간 구간 보존 검사 통과

- 기존 검증 기록과 프롬프트 표 번역 뒤에도 통합 문서의 코드·링크·수치 목록 해시가 모두 기준과 같았다. 이어서 인과 진단과 단계별 개입 기록의 설명·표·범위 수정 내용을 번역했다. 새 진단이나 실험은 수행하지 않았다. 다음은 보존 검사 후 고정 시드 비교와 최신 패처 비교 기록의 번역이다.

## 2026-10-29 / 문서 한글화 / 통합 문서 마지막 구간 번역

- 단계별 기록 번역 후 코드94개·링크20개·수치723개의 목록 해시가 모두 원문 기준과 일치했다. 고정 시드 비교와 최신 신경망/count 패처 비교의 제목·설명·표·검증 결과까지 번역했다. 출력 길이가 다른 생성 비용을 가속으로 주장하지 않는 주의와 패처만의 증분 비용·전체 모델 초기 처리의 구분을 보존했다. 다음은 세 문서 전체의 보존 검사, 남은 영문 서술·링크·공백 확인과 완료 기록이다.

## 2026-10-29 / 문서 한글화 완료 / 전체 보존·형식 검사 통과

- docs/HANDOFF.md, docs/EVIDENCE.md, docs/INTEGRATION.md의 제목·본문·표를 한글로 번역했다. 명령·Python 예제·API·파일 경로·해시·수치와 과거 실험의 해석 한계는 유지했다. task.md의 번역 및 검증 항목을 완료로 표시했다.
- Python 표준라이브러리로 코드 블록·인라인 코드의 공백 정규화 목록, 링크 대상 목록, 수치 목록을 추출·정렬해 JSON의 SHA256을 대조했다. 원문과 최종본 모두 일치했다. 문서별 코드/링크/수치 개수는 HANDOFF 31/0/31, EVIDENCE 11/0/26, INTEGRATION 94/20/723이다.
- 코드 밖 영문만 있는 서술 행·일본어/한자 혼입을 검사했고 미검출이었다. 코드 펜스 짝과 로컬 링크 대상 존재 검사를 통과했으며 원격 링크는 대상 문자열만 보존 확인했다. `git diff --check -- docs/INTEGRATION.md docs/HANDOFF.md docs/EVIDENCE.md task.md log.md`를 통과했고 다섯 문서의 편집기 진단도 오류가 없었다.
- 문서만 수정했으므로 모델·서버 실행이나 Python 패키지 테스트는 추가로 수행하지 않았다. 원본 JSON 근거·실행 코드·환경은 변경하지 않았다. 번역 요청은 완료했으며 추가 실험이나 최적화는 이번 범위에 포함하지 않는다.

## 2026-10-29 / 사용자 승인 / 동일 바이트 전체 모델 증분 비교 구현

- 사용자가 다음 단계 진행을 승인했다. 현재 작업은 기존 타이밍 8입력의 동일 바이트 32단계 전체 모델 측정이며 규칙·임계값·가중치·환경을 고정한다. 초기 처리 최적화나 재튜닝은 이번 측정과 분리한다.
- 기존 실행기의 실제 제어 경로를 확인했다. 기존 timing 단계는 모델 초기 처리와 패처만의 증분 처리를 측정하므로, 명시적인 incremental 단계와 필수 timing-reference를 추가했다. 참조의 환경·규칙·설정·분할·의존 코드·배경·입력을 대조한다. 기존 단계의 측정 유형은 유지한다.
- 가설: 같은 접두부와 동일 32개 바이트를 두 모드의 전체 순전파에 재생하면 출력 길이에 좌우되지 않는 전체 모델 증분 비용을 비교할 수 있다. 확인 방법은 32개 접두부의 정확한 길이·바이트 및 준비 구간 제외 단위 테스트, 실제 모델에서 count 상태 재사용과 새 접두부 계산의 단계별 경계·로짓 일치 검사다. 다음은 집중 검사와 서버 자원 확인 후 실행이다.

## 2026-10-29 / 전체 모델 증분 비교 / 집중 검사 통과

- SSH BatchMode로 itcerdo 접속 및 GPU 실행 프로세스 부재를 확인했다. 기존 환경은 Torch2.11.0+cu128/RTX5090으로 유지됐고 새 의존성은 설치하지 않았다. 변경한 비교 실행기와 테스트만 서버 source에 동기화했다.
- `OPENBLAS_NUM_THREADS=8 PYTHONPATH="$PWD/src" ../.venv/bin/python -m unittest discover -s tests -p test_blt_patcher.py`: 집중21개가 0.018초에 통과했다. 새 검사는 준비 접두부 제외, 정확히 같은 32개 확장, 최종 입력 보존, 잘못된 길이·배치·단계 수 거부를 확인했다.
- 다음은 전체 회귀, 참조 보고서의 원래 인자·코드 식별 정보 확인 후 새 실행 디렉터리에서 측정이다. 실제 전체 모델 속도는 아직 측정 전이다.

## 2026-10-29 / 전체 모델 증분 비교 / 전체 회귀 통과 및 실행 준비

- 기존 itcerdo 환경에서 `OPENBLAS_NUM_THREADS=8 PYTHONPATH="$PWD/src" ../.venv/bin/python -m unittest discover -s tests`를 실행해 전체50개가 1.167초에 통과했다. 비교 실행기·테스트·작업 기록의 편집기 진단도 오류가 없었다.
- 이전 타이밍 근거의 상태 completed, 모델 경로, 적합/데이터 준비/라벨/변환/예비설정 보고서 경로와 환경을 확인했다. 입력은 test/wikipedia_test 각각256/512/1024/2048 ID인 기존8개다. 계획한 새 출력은 `../runs/en-blt-patcher-incremental-20261029-01/incremental.json`이며 기존 보고서는 유지한다.
- 다음은 기존 데이터 디렉터리 확인 후 증분 측정 실행이다. 준비 접두부는 측정에서 제외하며, 기록 시간은 같은32회 전체 순전파의 합계다. 자유 생성·샘플링 시간이나 단일 바이트 지연의 분위수로 해석하지 않는다.

## 2026-10-29 / 전체 모델 증분 비교 / 실행 완료·원본 검증 대기

- 기존 runs 내부에서는 분할 파일을 찾지 못했고 프로젝트의 datasets 영역에서 `../datasets/en-patcher-20261019-01`을 확인했다. 이 경로의 보호된 다섯 분할과 원래 보고서·코드·환경 대조를 실행기가 통과했다. 초기 후보를 추정해 새 데이터를 만들거나 분할을 바꾸지는 않았다.
- GPU가 비어 있음을 재확인하고 기존 `model.safetensors` SHA256 `4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061`을 확인했다. `OPENBLAS_NUM_THREADS=8 PYTHONPATH="$PWD/src" ../.venv/bin/python -m scripts.compare_blt_patchers --stage incremental --timing-reference ../runs/en-blt-patcher-compare-20261028-01/timing.json`에 기존 fit/배경/모델/라벨/설정 인자를 적용했다.
- 실행은 exit0으로 종료했고 입력8개 완료가 출력됐다. 새 원본은 `../runs/en-blt-patcher-incremental-20261029-01/incremental.json`, 실행 출력은 같은 디렉터리의 execution.log에 보존했다. 다음은 원본 수집·해시 대조,160개 시간 표본·상태 대조 검증과 속도비·변동 구간 계산이다. 아직 수치 결론을 확정하지 않았다.

## 2026-10-29 / 전체 모델 증분 비교 / 원본 수집 및 상태 대조 확인

- 새 보고서를 `evidence/english_blt_patcher_incremental_20261029.json`으로 수집했다. 로컬 SHA256은 `ea290b23cb21348c16191402ccb0b7070b3f2fd70c6317af78ea0f8e62c808da`이며 상태 completed/stage incremental을 확인했다. 실제 실행 시각은 원본의 UTC 필드로 보존했다.
- 입력8개 모두 기존 타이밍 입력 일치, 준비 길이224/480/992/2016, 측정 끝 길이256/512/1024/2048, 정확히32개 확장을 기록했다. 단계별 count 증분 상태와 새 접두부 계산의 경계·로짓 일치가 총256단계에서 통과했다. 실패를 무시하거나 불리한 입력을 제외하지 않았다.
- 다음은 전체160개 원시 표본의 유한성·표본 수·p50/p95/최솟값/최댓값 재계산, 로컬·원격 및 실행 코드·입력 출처 해시 확인, 같은 반복 블록을 재표집한 속도비 구간 계산이다.

## 2026-10-29 / 전체 모델 증분 비교 / 독립 검증 통과·측정 결론 문서화

- 기존 서버 NumPy로8입력·160원시표본의 양수/유한성·반복 수·p50/p95·최솟값·최댓값을 독립 재계산했고 모두 일치했다. 준비 길이/첫·마지막 측정 길이·같은 입력 ID·count 상태 대조256단계도 검증했다. 새 원본의 로컬/원격 SHA256은 `ea290b23cb21348c16191402ccb0b7070b3f2fd70c6317af78ea0f8e62c808da`로 같고 이전 참조 SHA256 `ddd6dcfc51c71eb1a1cdf0720371a0324d4873a4fa4ef50bd1be8de6c54ae485`도 유지됐다. 원격 실행 코드9개·출처6개의 실제 파일 해시를 확인했다.
- 측정 결과: 같은32개 바이트 확장의 전체 모델 신경망/count 중앙값 비율은1.1033332659-1.5260951384로8개 입력 모두 count가 빨랐다. 같은 반복 블록10개를 함께 재표집한2000회/seed20261019 부트스트랩95%구간도 모두1보다 컸다. 구간은 단일 실행 안의 기술적 변동이며 전체 환경의 성능 신뢰구간으로 일반화하지 않는다. 세부8행은 통합 문서에 기록했다.
- 최대 GPU 할당은 신경망10076264448/count10099477504바이트, 전체 프로세스 최대 호스트 RSS10154020864바이트였다. 원래 패처 가중치가 두 모드 모두 상주했고 호스트 최대치는 로드·정확성 검사까지 포함한다. 메모리 절감이나 모드별 호스트 메모리 우위를 주장하지 않는다. 보고서 기록 구간은240.518383초이며 이 값은 모델 로드·대조·준비 실행도 포함해 측정 표본의 생성 시간과 별개다.
- 통합 문서에 조건·32단계 합계 밀리초·입력별 표·구간 계산법·재현 명령·원본 해시·한계를 한글로 추가하고 task의 측정·검증·기록 항목을 완료로 표시했다. 준비 접두부 비용은 제외됐고 기존 초기 처리2.08-4.93배 지연은 미해결이므로 전체 실행 가속/자동 채택은 주장하지 않는다. 다음은 문서 수치·로컬 실행 코드·링크·공백 최종 검사이며, 후속 구현 후보는 count 초기 처리 병목 개선이다.

## 2026-10-29 / 전체 모델 증분 비교 / 최종 문서 검사에서 표기 수정

- 최종 검사에서 원본 SHA·로컬 실행 코드5개 해시·Python AST·표8행의 p50/p95/속도비·로컬 링크·펜스는 통과했으나 새 절의 한자 혼입과 셸 출력 경로의 꺾쇠 표기를 검출했다. 한글 표기로 수정하고 실행 이름을 NEW_RUN_ID로 제시하며 새 이름으로 바꾸라는 설명을 추가했다. 측정 코드와 원본 수치는 변경하지 않았다. 다음은 같은 문서 검사의 재실행이다.

## 2026-10-29 / 전체 모델 증분 비교 완료 / 최종 검증 통과

- 같은 최종 검사를 재실행해 원본 SHA·로컬 실행 코드5개 해시·Python AST·표8행 수치·로컬 링크·펜스·한글 서술 검사가 모두 통과했다. 관련 코드·테스트·문서·작업 기록의 편집기 진단은 오류가 없었고 `git diff --check -- scripts/compare_blt_patchers.py tests/test_blt_patcher.py docs/INTEGRATION.md task.md log.md`도 통과했다.
- 동일 바이트32단계의 전체 모델 증분 비교를 완료했다. 기존48개에 접두부 검사2개를 더한 전체50개 회귀가 통과했으며 실제 모델 대조·원시160표본·출처/코드/원본 해시와 통계 검증을 완료했다. 결과와 한계는 원본 근거와 통합 문서에 보존했다.
- 후속 구현 대상은 경계·규칙을 유지하는 count 초기 처리 비용 개선이다. 이번에는 이 최적화를 구현하지 않았고 기존 모델·규칙·환경·데이터·작업을 보존했다. 측정한 증분 이득을 초기 처리 포함 전체 실행의 가속이나 다른 GPU/말뭉치의 보장으로 일반화하지 않는다. 커밋·푸시·새 패키지 설치는 하지 않았다.

## 2026-10-29 / 사용자 정정 / 초기 처리 최적화 보류·비교 평가 우선

- 사용자는 초기 병목 개선을 나중으로 미루고 현재 비교·평가를 먼저 마무리하라고 지시했다. 직전의 '다음은 초기 처리 최적화' 안내를 현재 우선순위에서 철회한다. 현재 task.md를 다시 읽고 사용자의 다른 변경은 유지한 채 이 우선순위와 미완료 평가 항목만 반영했다.
- 확인한 공백은 초기 처리 포함 동일 작업량의 전체 비용이다. 현재1.1033-1.5261배는 준비 접두부 비용을 제외한32단계 전체 모델 증분 비율이며 초기 처리 포함 전체 비용이 아니다. 기존 초기 처리 측정과 증분 측정은 시작 접두부·실행이 다르므로 단순 합산으로 보완하지 않는다.
- 다음 평가 순서는 같은8입력에서 초기 처리와 동일32바이트 확장을 한 실행에 포함해 초기/증분/합계를 측정한 뒤, 기존 BPB·경계·속도·메모리 근거와 함께 기준별 종합 판정을 정리하는 것이다. 규칙·임계값·모델·환경을 고정하고 최적화·재튜닝은 수행하지 않는다. 이 항목은 계획이며 새 측정을 실행하거나 결과를 주장한 것은 아니다.

## 2026-10-29 / 사용자 승인 / 초기 처리 포함 전체 비용 측정 구현

- 사용자가 다음 비교·평가 실행을 승인했다. 현재 task와 최신 로그를 읽고 별도 total 단계를 추가했다. 기존 timing/incremental 결과와 경로는 유지하며 참조8입력·준비3회/반복10회·교대 실행·count 상태 대조를 재사용한다. 후보 최적화·규칙 변경은 하지 않는다.
- 가설은 초기 접두부 처리와 동일32바이트 확장을 한 실행의 타이머 경계로 나누면 각 반복의 초기/증분/합계 비용을 직접 비교할 수 있다는 것이다. 새 timed_replay는 시작·초기 완료·증분 완료에서 GPU를 동기화하고 동일 시계 차이를 기록한다. 싸고 구분력 있는 검사는 순서가 초기1회+확장32회인지, 초기와 증분의 합이 총시간인지 가짜 시계와 실제 입력 슬라이스로 검사하는 단위 테스트다.
- 초기 처리에는 count 상태 구축과 전체 모델의 첫 순전파를 포함한다. 모델 로드·어댑터 reset·준비 실행·정확성 대조·샘플링은 제외한다. 다음은 집중 테스트 후 실제 새 실행과 기존 기준별 종합 평가다.

## 2026-10-29 / 초기 포함 전체 비용 / 집중 테스트 통과

- itcerdo GPU 실행 프로세스 부재를 확인하고 변경한 실행기·테스트만 동기화했다. 기존 환경에서 `OPENBLAS_NUM_THREADS=8 PYTHONPATH="$PWD/src" ../.venv/bin/python -m unittest discover -s tests -p test_blt_patcher.py`를 실행해 집중22개가0.018초에 통과했다.
- 새 검사는 시작 동기화→초기 접두부1회→동기화→정확히32개 확장→동기화 순서와 초기+증분=합계를 확인했다. 다음은 전체 회귀·기존 적합 지표 확인 후 `en-blt-patcher-total-20261029-01` 새 실행이다. 아직 전체 비용 수치 결과는 없다.

## 2026-10-29 / 초기 포함 전체 비용 / 전체 회귀·기존 검증 지표 확인

- 기존 환경의 전체 테스트51개가1.146초에 통과했고 관련 편집기 진단도 오류가 없었다. 고정 적합 보고서의 status는 validation_gate_failed이며 validation F1은0.7853676082457853이다. 원래 예비설정의 minimum_validation_f1=0.90에 미달한 결과를 보존하며 heldout F1과 혼동하거나 통과로 재분류하지 않는다.
- 사용자가 승인한 것은 고정 후보의 비교·평가이므로 이 미달을 숨기거나 규칙을 재적합하지 않고 전체 비용 측정을 진행한다. 새 출력은 `../runs/en-blt-patcher-total-20261029-01/total.json`, 단계는 total이다. 다음은 유휴 GPU 재확인 후 실행과 원시 표본 검증이다.

## 2026-10-29 / 초기 포함 전체 비용 / 측정 실행 완료

- 유휴 GPU와 새 실행 디렉터리 비중복을 확인한 뒤 `--stage total --timing-reference ../runs/en-blt-patcher-compare-20261028-01/timing.json`으로 실행했다. 기존 fit/배경/모델/라벨/설정/데이터 경로를 그대로 전달했다. 모델 가중치 SHA256은 `4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061`로 유지됐다.
- 실행은 exit0으로 종료하고8개 입력 완료를 출력했다. 새 원본과 실행 출력은 `../runs/en-blt-patcher-total-20261029-01/total.json`, 같은 디렉터리 execution.log에 보존했다. 다음은 원본 수집·해시 확인과 같은 반복의 초기/증분/합계 검증이며 아직 통계 결론은 확정하지 않았다.

## 2026-10-29 / 초기 포함 전체 비용 / 독립 검증 통과 및 종합 평가 문서화

- 새 원본을 `evidence/english_blt_patcher_total_20261029.json`으로 수집했다. 로컬·원격 SHA256은 `73c43ce944240243f88079e4947b3e6a880dd1bb1c6cbd5c40c4248747d9971e`로 일치한다. 상태 completed/stage total이며 실제 UTC 실행 시각은 원본에 보존했다. 원격 코드9개·출처6개 해시와 기존 보고서의 모델/규칙/설정/배경/분할/환경 일치를 검증했다.
- NumPy로160실행블록(80대응쌍)의480시간값을 독립 검증했다. 표본 수·양수/유한성·p50/p95/최솟값/최댓값이 모두 맞았고 각 표본의 초기+증분=합계를 확인했다. 입력8개·준비/확장길이·count 상태256단계 대조도 통과했다. 기록한 순전파는 초기1회+확장32회씩 총5280회다.
- 초기 포함 전체 비용의 신경망/count 중앙값 비율은1.0371007933-1.3122871137이다.8입력 모두 count가 빨랐고1.05이상은7개다. 대응 블록10개를 함께 재표집한2000회/seed20261019 부트스트랩95%구간의 최저 하한은1.0364618259였다. 단일 실행의 변동 구간이며 다른GPU/말뭉치·자유 생성·임의 길이로 일반화하지 않는다.
- 최대 GPU 할당은 신경망10076264448/count10099477504바이트, 전체 프로세스 최대 호스트 RSS10153779200바이트였다. 모델 로드와 정확성 대조를 포함한 호스트 최대치이고 양쪽 모두 원래 패처 가중치가 상주하므로 모드별 호스트 우위나 패처 제거 메모리 절감은 주장하지 않는다.
- 통합 문서에 초기/증분/합계 p50과 합계p95·입력별 비율/구간을 기록했다. 기존 기준별 판정은 BPB허용과 패처증분속도는 검사 범위에서 통과, 검증F1 0.7853676082<0.90 및 초기처리속도는 미달이다. 추가 전체 비용은 사전 별도 합격 기준이 없었으므로 초기처리 기준을 대신 통과한 것으로 취급하지 않는다. 절제실험은 미검증으로 명시했다. fit.remaining은 당시 기록이며 이후 BPB·타이밍·평가는 완료됐다는 점도 구분했다.
- task의 현재 고정 후보 비교·평가 두 항목을 완료로 표시했다. 다음은 문서 수치·로컬 코드·링크·공백 최종 검사다. 초기 병목 최적화·규칙 재튜닝·새 패키지 설치·자동 채택은 하지 않았다.

## 2026-10-29 / 고정 후보 비교·평가 완료 / 최종 검증 통과

- 최종 검사에서 새 원본 SHA256, 실행한 로컬 코드5개 해시, Python AST, 문서 표8행의 초기/증분/합계p50·합계p95·속도비, 표본별 초기+증분=합계, 로컬 링크·펜스·한글 서술과 현재 task 완료 상태가 모두 통과했다. 관련 편집기 진단은 오류가 없고 `git diff --check -- scripts/compare_blt_patchers.py tests/test_blt_patcher.py docs/INTEGRATION.md task.md log.md`도 통과했다.
- 현재 고정 후보의 비교·평가는 완료했다. 실제 전체51개 테스트 통과와 모델 측정 원본·단계별 시간·종합 판정을 보존했다. 초기 포함 같은32단계 재생의 이득은 확인했지만 검증F1·초기처리속도 기준 미달, 절제실험·패처제거 메모리절감 미검증을 남긴다. 이 결과를 모든 채택 기준 통과로 표현하지 않는다.
- 사용자의 현재 범위대로 초기 병목 개선은 수행하지 않았다. 원본 모델·규칙·환경·데이터·기존 작업은 보존했고 재튜닝·새 의존성 설치·커밋·푸시는 하지 않았다. 다음 구현이나 추가 실험을 자동으로 시작하지 않고 이번 비교·평가 결과로 마무리한다.

## 2026-10-29 / 사용자 요청 / 조회·계산·전송 비용 계측 착수

- 기존 HANDOFF/PLAN/워크플로와 최신 로그를 확인했다. itcerdo 기존 Torch2.11.0+cu128/RTX5090 환경과 유휴 GPU를 확인했다. 초기 병목 개선이 아니라 비용 분해만 요청받았으며 규칙·환경·후보는 변경하지 않는다.
- 가설: 초기 처리의 순차 CPU 계산·상태 관리가 큰 비중일 수 있으나 LMDB 조회·전송의 실제 비율은 미측정이다. 독립 계측 스크립트를 추가해 원래 어댑터를 호출하면서 배경/온라인 lookup, Tensor.tolist, 결과 텐서 생성·GPU 완료 시간을 분리하고 나머지를 계산·기타로 남긴다.
- 같은8입력의 초기 접두부와 동일32확장, 준비3회/반복10회, baseline/계측 순서 교대와 경계 동일성 검사를 사용할 계획이다. lookup에는 캐시 접근과 행 해석이 포함된다. 나머지에는 계측 오버헤드도 포함되며 모델 전체 비율이나 순수 저장장치 I/O로 해석하지 않는다. 다음은 집중 검증 후 실행이다.

## 2026-10-29 / 비용 계측 / 집중 검증 통과

- itcerdo 기존 환경에서 결정론적 가짜 시계로 비중복 항목 합계·잔여 시간 산술을 검증했다. 실제 CUDA 합성 입력으로 기존 어댑터와 계측 어댑터의 패치 경계 일치, 입력/출력 전송 호출 각1회, 배경/온라인 조회 횟수 일치, 정상·예외 경로의 함수 복구를 확인했다.
- 참조 total 보고서의 배경 메타데이터와 입력 구조를 확인했다. 다음은 `en-count-cost-profile-20261029-01/profile.json` 새 경로에서 8입력·초기/증분 계측을 실행하고 baseline 대비 오버헤드와 원시 표본을 검증한다. 아직 비용 비율 결과는 없다.

## 2026-10-29 / 비용 계측 / 8입력 실행 완료

- 유휴 GPU와 새 경로를 확인한 뒤 `python -m scripts.profile_count_patcher --reference ../runs/en-blt-patcher-total-20261029-01/total.json --background ../runs/en-count-lmdb-full-20261025-01/counts.lmdb --output ../runs/en-count-cost-profile-20261029-01/profile.json`을 기존 환경에서 실행했다. 종료0, 8입력의 초기/증분32 단계16개가 완료됐다.
- 계측/baseline 중앙값 비율은 초기1.0338-1.0520, 증분1.0465-1.0861이었다. 계측 오버헤드가 있으므로 계측 시간의 구성비를 전체 모델의 원래 구성비로 단정하지 않는다. 다음은 결과 수집·해시·시간 합계·구성비·캐시 카운터·원시 표본 검증이다.

## 2026-10-29 / 비용 계측 / 원시 표본 검증 및 결과 확보

- 새 원본을 `evidence/english_count_patcher_costs_20261029.json`으로 수집했다. SHA256은 `68124f7f559b7a7b8b841c0daffa83b3917d82f414bcf252d99891e576ea1b1f`다. 320개 측정 블록의 중앙값, 계측160개 블록의 항목 합계·비음수성·호출 수·캐시 카운터·비율을 독립 재계산했다. 초기80회/증분2560회의 입력/출력 전송 쌍과 배경/온라인 조회 횟수가 모두 맞았다.
- 계측 시간 합계 가중 비중: 초기 배경조회16.2172%+온라인조회1.2163%, 계산·기타82.5062%, 입력전송0.0123%+출력전송0.0478%. 증분32는 조회4.8443%, 계산·기타85.7433%, 전송9.4124%였다. 초기 입력별 조회3.06-20.86%, 계산·기타79.09-96.85%, 전송0.05-0.16%였다.
- 이는 패처 단독·준비된DB 조건의 계측 결과다. 계산·기타에는 Python/확률·엔트로피/상태갱신/검사/할당/계측 비용이 포함돼 순수 산술 비율이 아니다. 실제 CUDA 합성 검사를 영구 회귀 테스트의 CPU/동기화 대역 검사와 가짜 시계 산술 검사로 보완했다. 다음은 집중/전체 테스트와 소스·원본 해시 확인 후 문서화다.

## 2026-10-29 / 비용 계측 / 회귀 테스트 통과

- 기존 itcerdo 환경에서 `unittest discover -s tests -p test_blt_patcher.py` 집중24개가0.019초, 전체 `unittest discover -s tests` 53개가1.155초에 통과했다. 새 테스트는 가짜 시계 산술·합계 가중 비율·겹친 시간 거부, 경계 동일성·전송/조회 횟수·정상/예외 복구를 확인한다.
- 초기 짧은 입력은 배경 조회 캐시100% 적중이었고 긴 입력은44.53-50.41%였다. 이 차이로 조회 비중이 커지지만 계산·기타가 여전히79% 이상이다. 다음은 문서/업무 상태 갱신과 원본·소스 해시 및 표 최종 검사다. 런타임·규칙·알고리즘 최적화는 하지 않았다.

## 2026-10-29 / 비용 계측 / 문서화·최종 검증 완료

- 통합 문서에 초기/증분 합산 구성비, 입력8개의 초기 시간·비율, 캐시 적중률과 계측 오버헤드·분모/분류 한계를 기록하고 task의 현재2항목을 완료 표시했다. 패처 단독 계측이며 전체 모델 가중치가 상주하지 않는 조건임을 명시했다.
- 최종 검사에서 로컬/원격 원본 SHA256 `68124f7f559b7a7b8b841c0daffa83b3917d82f414bcf252d99891e576ea1b1f`, 실행 프로파일러 SHA256 `8120ca19b260f0163170c7bc0d30fec934689384be009595df9da8866f490b65`, 참조 total SHA와 패키지3개 소스 해시가 맞았다. Python AST·표8행 수치·로컬 링크·펜스·한글 서술·task 상태·git diff --check·관련 편집기 진단도 통과했다. 집중24개/전체53개 테스트 통과 결과를 보존했다.
- 결론은 현재 준비된8입력 초기 처리에서 조회17.43%/계산·기타82.51%/입출력·전송0.06%라는 계측값이다. 계산·기타에는3.4-5.2% 계측 오버헤드 및 비산술 비용이 포함돼 순수 Python 비용이나 C++/Rust의 예상 가속 배수로 해석하지 않는다. 최적화·재튜닝·새 환경 설치·커밋 없이 요청한 비용 분해를 마쳤다.

## 2026-10-29 / 사용자 요청 / C++ 전환 절감 비용 실측 착수

- 최신 로그·현재 순차 계산과 기존 native_minhash의 명시적 빌드 관례를 확인했다. itcerdo에 /usr/bin/c++와 기존 Python3.11 확장 헤더가 있고 GPU가 유휴 상태임을 확인했다. 로컬 최초 glob 검색은 불일치로 실패해 기존 명시 경로를 읽었다. 기존 작업·환경은 보존했다.
- 가설: Python 바이트 반복·확률/엔트로피/경계 계산·온라인 상태 관리의 네이티브 전환으로 초기 비용이 줄어들 수 있다. 이를 검증할 독립 C++ 확장과 실험 어댑터를 scripts 아래 추가했다. 배경 LMDB lookup은 기존 Python 콜백을 유지하고 입출력 전송도 유지한다. 빠른 수학 옵션 없이 -O3/-ffp-contract=off로 빌드할 계획이다.
- 순수 Python 오버헤드 추정이 아니라 동일 규칙의 실제 구현 교체 비교다. 우선 합성 입력의 경계·엔트로피/점수·증분/리셋을 대조하고 통과한 뒤 기존8입력을 측정한다. 아직 C++ 가속 결과는 없다. 운영 패키지 기본 동작은 변경하지 않았다.

## 2026-10-29 / C++ 비교 / 첫 집중 검사 실패 및 국소 수정

- 기존 서버에서 C++ 컴파일은 성공했으나 진단 튜플 반환의 Py_BuildValue에 지원되지 않는 p 지정자를 써 SystemError가 발생했다. 측정이나 동등성 통과로 기록하지 않는다. 반환 형식을 정수 지정자 i로 수정했다. 다음은 동일 합성 대조 재실행이다.

## 2026-10-29 / C++ 비교 / 수치 대조 실패 및 원인 수정

- 반환 수정 후 합성 검사에서 위치1의 엔트로피2.1199588869 대비 기준1.6551086464 차이를 검출했다. C++ 초안이 최종 가중 평균을 반환했지만 Python CountModel.probabilities는 마지막 문맥의 probability를 반환하는 경로였다. 원래 계산 규칙을 바꾸지 않고 C++의 마지막 평균 대입을 제거했다. 아직 성능 측정을 수행하지 않았으며 다음은 동일 합성 대조 재검증이다.

## 2026-10-29 / C++ 비교 / 합성 대조 통과 및 실제 입력 측정 준비

- 수정 후 동일 합성 대조가 통과했다. 전체/증분/리셋과 특수 ID가 포함된5입력에서 패치 길이·반복길이·거리·경계가 같고 엔트로피/점수 절대차가2e-13 이하였으며 이 대조를 명시적 BLT_TEST_NATIVE_CPP=1 회귀 테스트로 추가했다.
- 실제8입력의33접두부마다 Python/C++ 경계·수치와 C++ fresh/누적 경계를 검증하고, 초기/증분32를 준비3회/반복10회로 교대 측정하는 CLI를 추가했다. 배경 캐시 hit/miss가 양쪽에서 같은지도 검사한다. 빌드/로드/리셋/대조 비용은 제외하고 GPU 입력/출력은 포함한다. 다음은 집중/전체 테스트 후 새 실행 경로에서 실측이다.

## 2026-10-29 / C++ 비교 / 네이티브 포함 회귀 테스트 통과

- 기존 환경에서 BLT_TEST_NATIVE_CPP=1로 C++ 빌드·합성 대조를 활성화했다. 집중25개가0.398초, 전체54개가1.539초에 모두 통과했다. 새 의존성이나 환경 설치 없이 기존 c++/Python 헤더를 사용했다.
- 다음 실행 경로는 `../runs/en-count-cpp-compare-20261029-01/result.json`이며 기존 total·cost 보고서와 배경을 참조한다. 실제8입력의 경계·수치·cache 작업량이 다르면 중단하고 성능 결론을 내리지 않는다. 아직 성능 수치는 없다.

## 2026-10-29 / C++ 비교 / 실제 측정의 캐시 이력 불일치 중단

- 첫 실행은 FineWeb256/512의 진단·측정 뒤 긴 입력에서 `Timed background cache workload differs`를 검출하고 중단했다. 01 경로의 빌드 산출물은 보존하고 완성 결과로 취급하지 않는다. 부분 출력의 속도비는 최종 결론에 사용하지 않는다.
- 원인은 양쪽이 하나의 LRU를 공유하고 사전 진단에서 접근한 이력이 남아, 첫 실행이 다음 실행의 캐시를 바꾸는 통제 문제였다. 동일 읽기 전용 LMDB 트랜잭션 위에 동일4096행 LRU를 구현별로 분리하고 각 단계 시작에서 양쪽 캐시를 비운 뒤 같은 준비 실행을 수행하도록 수정했다. Python LMDB lookup/read 구현은 그대로다. 다음은 캐시 통제 집중 검사와 새02경로 재실행이다.

## 2026-10-29 / C++ 비교 / 긴 입력 캐시 통제 재검증 통과

- 실패했던 실제 FineWeb 초기992 ID를 독립 LRU 두 개로4회 재실행했다. 양쪽 hit/miss는 첫3805/5096, 이후 각4487/4414로 정확히 같고 패치 길이도 일치했다. 준비 실행 후 같은 안정 캐시 상태가 만들어짐을 확인했다.
- 다음은 `../runs/en-count-cpp-compare-20261029-02/result.json` 새 경로에서8입력 전체 재실행이다. 01의 실패 기록·빌드는 보존하며 최종 결과로 사용하지 않는다.

## 2026-10-29 / C++ 비교 / 통제된8입력 측정 완료

- 02 새 경로에서 실제8입력 전체 측정이 종료0으로 완료됐다. 원본은 `../runs/en-count-cpp-compare-20261029-02/result.json`이다. 모든 입력의33접두부 수치/경계·fresh/누적 대조와 계측 cache hit/miss 일치 검사를 통과했다.
- 실행 출력 기준 초기 Python/C++ 중앙값 속도비3.3105-6.3055, 증분4.0388-5.1027였다. 아직 문서의 확정 통계로 옮기지 않았으며 다음은 원본 수집,320시간값·대응160블록·절감률/구간·출처 해시와 최대 수치 차이의 독립 검증이다. 전체 모델 가속 결과는 아니다.

## 2026-10-29 / C++ 비교 / 원시 표본·동등성·절감률 검증

- 성공한02 원본을 `evidence/english_count_cpp_comparison_20261029.json`으로 수집했다. SHA256은 `99a518f9a6842ccf0040167a8f03dbf8775aaf4cff85c34ba7a2eaff1dab33ce`다. 참조 total/cost와 실제 runner/C++/패키지 소스 해시가 맞았다. 같은 실행의320시간값·160대응블록에서 양수/유한성·중앙값·속도비·절감률과 각 쌍의 cache hit/miss 일치를 재집계했다.
- 초기 중앙값 절감률69.7932-84.1409%, 속도비3.3105-6.3055였다. 초기80표본 합계는 Python7.3707664353초/C++2.0396608366초로72.3277% 절감이다. 증분은 입력별75.2399-80.4026% 절감/4.0388-5.1027배,80표본 합계 기준78.4293% 절감이다. 이는 초기 접두부224/480/992/2016 ID의 패처 단독 결과다.
- 실제8입력×33접두부=264개 대조에서 재검사 포함249480위치의 경계·반복길이·거리가 같았다. 엔트로피 최대절대차7.5495165675e-15, 점수4.1078251911e-15, 최소 Python 임계값 여유3.8530205947e-05였다. C++ 누적/새 상태 경계도 모두 같았다. 중간 수치는 비트 단위 동일하지 않으며 다른 입력·일반 모델 출력 동등성은 미검증이다.
- 다음은 부트스트랩 구간·p95·원격 바이너리/소스 해시 독립 검사와 캐시 통제 수정 후 전체 회귀 재검증, 문서·task 완료 기록이다. 기존 Python LMDB/LRU와 전송은 유지했고 변경된 자료구조·수치 축약까지 포함한 실제 네이티브 구현 이득이지 순수 인터프리터 비용 추정은 아니다.

## 2026-10-29 / C++ 비교 / 실행 해시·통계·최종 회귀 검증

- 원격 패키지/runner/C++/실제 .so 해시가 실행 원본과 같았다. NumPy로 독립 재구성한16개 대응 부트스트랩95%구간(2000회/seed20261019)과 p95가 모두 일치했다. 캐시 통제 수정 후 BLT_TEST_NATIVE_CPP=1 전체54개 테스트가1.541초에 다시 통과했다.
- 문서8행의 반올림·속도비·절감률은 원본과 일치했다. 한국어 검사에서 문서 끝에 잘못 작성한 일본어 문장1개가 발견돼 한국어로 수정했다. 다음은 수정된 문서 서술·링크/공백·편집기 진단 최종 확인이며 측정 수치나 코드는 변경하지 않는다.

## 2026-10-29 / C++ 비교 / 문서 검증 통과 및 작업 완료

- 최종 검사에서 원본·runner·C++ 해시, 초기 수치 표8행, 한글 서술·링크·펜스·Python AST·task 현재2항목 완료 상태와 git diff --check가 통과했다. 관련6파일의 편집기 진단에도 오류가 없었다. 전체54개 네이티브 포함 테스트와 실행 바이너리/통계 독립 검증 결과를 보존했다.
- 사용자가 요청한 C++ 전환 실제 절감 비용 측정을 완료했다. 초기 패처 시간 입력별69.8-84.1%/합산72.3277%, 증분 입력별75.2-80.4%/합산78.4293% 절감이다. 동일8입력의 경계·캐시 작업량 일치와 작은 비트 비동일 수치 차이를 확인했다. 이 결과는 모델 전체 가속·다른 입력의 출력 동등성·순수 인터프리터 제거율이나 이론적 최대 절감률을 뜻하지 않는다.
- 실험용 확장과 실행기는 scripts 아래에만 두고 명시적으로 빌드/실행한다. 운영 패키지 기본 백엔드·규칙·모델·데이터·환경은 변경하지 않았다. 실패01 기록과 기존 산출물도 보존했다. 새 환경 설치·재튜닝·커밋·푸시 없이 마쳤다.

## 2026-10-29 / 사용자 요청 / 실제 C++ 백엔드와 품질·시간 비교 착수

- 사용자가 실험 C++를 실제 패처에 적용하고 품질/시간을 비교하도록 요청했다. 현재 어댑터·비교 실행기·생성 함수와 최신 로그를 확인했다. 가설은 검증된 C++ 상태를 기존 어댑터 안에서 선택하면 같은 경계를 유지하며 실제 모델 비용을 줄일 수 있다는 것이다.
- CountPatcherAdapter에 backend=cpp/native_library 명시 선택을 추가했다. 기본 Python 경로, 공통 입력 검증/리셋/패치 길이 제한과 GPU 입출력은 유지한다. 별도 로더만 패키지에 추가해 phDQ 소스나 자동 빌드에 의존하지 않는다. 다음은 실제 어댑터의 합성/리셋/제한 대조 테스트 후 전체 품질·생성·동일 작업 모델 시간 비교다. 새 측정 결과는 아직 없다.

## 2026-10-29 / 실제 C++ 적용 / 어댑터 집중 검사 통과 및 모델 비교 준비

- itcerdo 기존 환경에서 BLT_TEST_NATIVE_CPP=1 집중26개 테스트가0.404초에 통과했다. 실제 CountPatcherAdapter의 C++ 선택·입력 계약·리셋·경계와 패치 길이 제한을 검증했다. Python 기본값은 유지됐다.
- 별도 실행기 evaluate_cpp_blt_patcher를 추가했다. 기존333평가 문서의 전체 청크에서 신경망/Python/C++ BPB와 Python/C++ 전체 로짓·경계 일치, 실제 모델 초기+동일32단계의3방식 교대 시간, 기존18개 Python 생성 결과의 C++ 재생을 측정할 계획이다. 동일 LMDB 트랜잭션의 독립 LRU와 실제 패키지 백엔드를 사용한다. 이전 측정 경로는 보존한다. 다음은 실행기 집중 검사·전체 회귀 후 새 실행이다.

## 2026-10-29 / 실제 C++ 적용 / 실행기 집중·전체 회귀 통과

- 실행기에서 패치/로짓 불일치 탐지와 진행/완성 JSON의 원자적 저장을 합성 검사했다. 기존 환경의 네이티브 포함 전체55개 테스트가1.544초에 통과했다. 어댑터 C++ 경로에도 frozen/vocabulary/context capacity 배경 호환성 검사를 보완하고 거부 사례를 추가했다.
- 다음은 보완 검사의 집중 재실행 후 `../runs/en-cpp-blt-evaluation-20261029-01` 새 경로에서 실제 품질·시간·생성 비교다. 비교 전 모델 가중치·기존 출처/보호분할·환경·고정 C++ 커널 해시를 확인하고 운영 기본값은 Python으로 유지한다.

## 2026-10-29 / 실제 C++ 적용 / 배경 계약 회귀·wheel 빌드 통과

- 배경 frozen/context/vocabulary 계약을 보완한 전체55개 네이티브 포함 테스트가1.528초에 통과했다. `pip wheel --no-build-isolation --no-deps . --wheel-dir ../runs/en-cpp-package-20261029-01`도 성공했다. wheel SHA256은 `5c64ea47cb90deb6e47813ff5f0344f12db1f957097339f56629f18eb9a4cfb5`다. 새 의존성이나 환경 설치는 하지 않았다.
- 다음 단계는 유휴 GPU 재확인 후 01 새 실행에서 전체333문서 품질·8입력 전체 모델3방식 시간·18개 C++ 생성 재생이다. 기존 결과와 사용자 데이터는 덮어쓰지 않는다. wheel의 저장소 밖 독립 import/네이티브 로드도 실제 빌드 산출물을 사용해 후속 확인한다.

## 2026-10-29 / 실제 C++ 적용 / 메타데이터 수집 오류 수정

- 01 실행은 고정 출처/모델/커널 검사와 네이티브 빌드 뒤, lru_cache 래퍼인 load_count_native에 inspect.getfile을 직접 호출해 TypeError로 중단됐다. 모델 로딩·품질 측정 전이며 결과가 나온 것으로 취급하지 않는다. 01 빌드와 실행 로그는 보존한다.
- 소스 경로 수집에 inspect.unwrap을 적용했다. 실제 패처 계산은 변경하지 않았다. 다음은 래퍼의 실제 소스 해시 집중 검사 후 새02경로 재실행이다.

## 2026-10-29 / 실제 C++ 적용 / 메타데이터 수정 집중 검사 통과

- 기존 환경에서 inspect.unwrap으로 native_patcher.py의 실제 경로와 SHA256을 얻는 집중 검사가 통과했다. 다음 실행은 `../runs/en-cpp-blt-evaluation-20261029-02` 새 경로이며 동일 품질/시간/생성 설정을 유지한다. 측정 계산 코드나 고정 후보는 변경하지 않았다.

## 2026-10-29 / 실제 C++ 적용 / 전체 품질·시간·생성 실행 완료

- 02 실행이 종료0으로 완료됐다. FineWeb113/Wikipedia220문서 전체 품질, 기존8입력의 신경망/Python count/C++ count 전체 모델 초기+32단계 시간, 고정18개 생성 재생이 모두 완료됐다. Python/C++ 경계·전체 로짓 불일치와 시간 측정의 캐시 작업량 불일치는 검출되지 않았고 생성18개 모두 기존 Python의 전체 ID·문자열을 재현했다.
- 새 원본은 `../runs/en-cpp-blt-evaluation-20261029-02/{quality,timing,generation}.json`, 실행 출력은 상위 runs의 같은 실행명.execution.log에 보존했다. 다음은 원본 수집·해시, 문서/청크 손실·경계/BPB,3방식 대응 시간·구간·메모리 독립 검증과 wheel의 저장소 밖 네이티브 로드다. 아직 확정 속도비는 보고하지 않는다.

## 2026-10-29 / 실제 C++ 적용 / 원본 수집·품질/시간 집계·wheel 로드 검증

- 로컬 새 근거 `english_blt_cpp_{quality,timing,generation}_20261029.json`을 수집했다. SHA256은 각각 `2cfe1c2b695e249272fa098ce11b0b5115da411e552376b5ab6a16bc6491feba`, `f8958eb1bf6706f71431fcdc201c24039596932044b00767f063679e04b06354`, `521057edfac8fe5cfa346c5164dd77011a618666fd911976edac84a60aacc635`다. 로컬 코드 해시와 문서/청크 손실 합계·대응 시간 합계/캐시 작업량·메모리를 검증했다.
- 전체333문서/928청크/1497578바이트에서 Python/C++ 패치 길이·모델 로짓·NLL이 같고 기존 결과와도 손실/경계 차이가0이었다. 합산BPB는 신경망0.8106483993/count0.8129846651, 차이+0.0023362658로 기존 허용치 안이다. 경계F1 0.7415067265/F0.5 0.7044741395는 그대로다. 생성18개/18279 ID·문자열도 기존Python과 같았다.
- 같은 실행의 전체 모델 속도비: 초기 C++는Python대비1.9523-2.4436배이나 신경망대비0.4766-1.0045로 초기 속도기준1.05에 여전히 미달이다. 증분은Python대비1.0053-1.0174/신경망대비1.1133-1.5344, 초기+동일32 합계는Python대비1.0531-1.1219/신경망대비1.0993-1.4582였다. 패처 단독 가속을 모델 전체에 그대로 적용하지 않는다.
- 최대Torch할당은 신경망10075999232/Python count10099330048/C++ count10099330048바이트, 프로세스 high-water RSS27708678144바이트였다. RSS는 해시/로드/전체평가까지 포함한 과정 전체 값이며 모드별 메모리 비교가 아니다. C++ 생성18회 합계431.0332초는 기존Python과 다른 실행이므로 대응3방식 시간 비교를 대신하지 않는다.
- 별도 경로에서 wheel을 풀고 저장소/BLT 소스 없이 import한 CountPatcherAdapter의 Python/C++·패치 제한·리셋이 일치했다. 기존 환경 설치는 바꾸지 않았다. 다음은 BPB/경계·48개 대응 시간 구간과 원격코드/라이브러리 해시 독립 재검증 후 사용법·결과 문서화다.

## 2026-10-29 / 실제 C++ 적용 / 통계 독립 검증 및 문서화

- 원격3원본·실행 소스·출처·실제.so 해시가 맞았다. 전체 청크에서 경계를 독립 재집계했고3개 BPB 대응 문서 부트스트랩과48개 대응 시간 부트스트랩/p95를 독립 계산해 모두 일치했다. 합계속도비95%구간의 최저하한은 신경망기준1.0989715434/Python count기준1.0524123389였다.
- README에 명시적 빌드·backend=cpp/native_library 사용법과 ABI/지원 계약을 추가하고 이전 Python 전용 설명을 현재 기본값/선택형 동작으로 바로잡았다. 통합 문서에 전체 품질·8입력3방식 시간 표·메모리·출력 재생·실패01 기록·wheel 검증과 한계를 정리했다. task 현재3항목은 완료 표시했다.
- 현재 실제 C++ 적용은 끝났고 기본 Python 선택은 유지한다. 신경망 대비 품질 향상이나 초기 속도기준 통과로 표현하지 않는다. 다음은 원본·코드 해시/문서 수치·링크/한국어·공백과 편집기 진단 최종 확인이다. 새 환경 설치·재튜닝·커밋은 하지 않았다.

## 2026-10-29 / 실제 C++ 적용 / 최종 검증 통과·작업 완료

- 최종 검사에서3개 원본/실행 코드 해시,4개 Python AST,품질3행·시간8행3방식 수치,링크·펜스·한글 서술·task 현재3항목 완료 상태와 git diff --check가 통과했다. 관련8파일의 편집기 진단에도 오류가 없었다. 전체55개 네이티브 포함 테스트·wheel 빌드/저장소 밖 로드와 독립 통계 검증 결과를 보존했다.
- 실제 CountPatcherAdapter의 명시적 C++ 적용, 전체333문서 품질/경계/로짓 대조,18개 생성 전체 ID/문자열 재현,같은 실행의3방식 전체 모델 시간·메모리 비교를 완료했다. 검사 범위의 품질·출력은 Python count와 같고 초기+동일32 합계는Python대비1.05-1.12배/신경망대비1.10-1.46배 빨랐다.
- 생성18회 C++431.0332초와 과거Python434.6476초는 유사한 관측치이나 서로 다른 실행의 합계이며 대응 반복 통계가 아니다. 자유 생성 가속·품질 향상·기존 경계/초기속도 채택기준 통과로 일반화하지 않는다. 기본 Python과 과거 실패/성공 산출물·사용자 데이터/환경을 보존했다. 새 환경 설치·재튜닝·커밋·푸시 없이 사용자 요청을 마쳤다.

## 2026-10-29 / 사용자 요청 / 문서 하단3방식 종합 평가표 작성

- 사용자가 엔트로피/확률/확률+C++의 BPB·생성 바이트·EOS 비율·단계/전체 시간·재현 점수를 맨 하단에서 종합 비교하도록 요청했다. 새 실험 없이 기존4개 원본을 집계했다. 실제 바이트는 특수 ID를 제외해23543/18266/18266, EOS는11/18·13/18·13/18이었다. 이는 요청한 지표 집계이며 별도 종료 원인 진단을 재개한 것이 아니다.
- 통합 문서 마지막에 종합표를 추가했다. 동일3방식8입력의 단계 시간은10반복 평균의 입력합계를 사용해 초기+증분=합계를 유지하고, 서로 다른 시점/출력 길이의 자유 생성 총시간과 분리했다. 모듈별 시간과 자유 생성 내부 단계 분해는 미측정으로 명시했다.
- 경계 재현은 엔트로피 기준 Precision/Recall/F1/F0.5, 생성 재현은 같은 프롬프트/시드의 전체 ID 일치로 구분했다. 자기 비교100%를 품질 정답률로 해석하지 않는다. 다음은 원본 기반 표 수치·정의·링크/한국어·공백 검증이다.

## 2026-10-29 / 후속 사용자 요청 / 입력·생성 바이트당 속도 추가

- 사용자가 총시간 외에 입력 바이트당 초기 속도·생성 바이트당 속도를 요청했다. 실제 입력7416바이트/동일 증분256바이트와 자유 생성23543/18266/18266바이트를 원본 ID에서 확인해 바이트당 시간 및 B/s를 집계했다. 초기 us/B는32.8886/130.7550/54.9404,자유 생성 실효 ms/B는32.0181/23.7954/23.5976이다.
- 표에 초기/동일 증분/자유 생성의 정규화 시간·처리량6행과 분모 정의를 추가했다. 자유 생성은 초기 처리·샘플링을 포함한 실효 비용이고 동일 증분은 모델 순전파 비용이다. 순수 자유 생성 단계만의 시간은 기록돼 있지 않아 수치로 꾸미지 않았다. 한국어 표의 잘못된 외국어 표기도 수정했다.
- 앞선 종합표 검증 호출은 tool 결과가 outcome_unknown으로 반환돼 성공 여부가 미확정이다. 이번 수정 후 전체 표 수치·바이트 분모·합계·링크·한국어 검증을 재실행한다. 새로운 모델 실행이나 원본 변경은 하지 않았다.

## 2026-10-29 / 종합 평가표·바이트당 속도 / 원본 대조 검증 완료

- 로컬 표 검증에서 원본4개의3방식 BPB·생성 ID/실제 바이트·UTF-8 길이·EOS·총시간·6개 바이트당 시간/처리량 행·모든 원시 블록의 단계 합계·경계/생성 재현·GPU 메모리가 일치했다. 입력7416/동일 증분256바이트 분모와 문서 링크·펜스·한국어 검사도 통과했다. git diff --check와 수정3문서의 편집기 진단에 오류가 없었다.
- 초기 처리량은 엔트로피30405.70/Python7647.89/C++18201.55 B/s,자유 생성 실효 처리량은31.23/42.02/42.38 B/s다. 이는 총바이트/총시간으로 집계한 관측치다. 자유 생성의 prefill/이후 단계는 미분리이며 동일 증분 모델 속도와 혼동하지 않는다. 진행 항목을 완료 처리했다. 추가 모델 실행·튜닝·코드/원본 변경 없이 요청한 문서 비교를 완료했다.

## 2026-10-29 / 전체 태스크 감사 / 원래 단계와 누적 실적 통합

- 사용자 요청에 따라 task 전체·BLT-PATCHER 원안·HANDOFF/PLAN·프로젝트 절차·최근 log와 실제 비교 실행기의 분할/저장 범위,로컬 Git 상태를 대조했다. 원래3절의 T09~T11 전부 미완료 표기는 이후 실적과 맞지 않았으며, 검증 분할 BPB/위치별 손실·평가 교사 접두부·정식 F0.5 선택·ablation/비열등성은 실제 완료 증거가 없었다. 최신 C++ 구현/근거는 미커밋 상태로, 과거 게시와 구분했다.
- task3절을 현재 상태의 기준으로 지정하고 기존 날짜별 기록은 당시 이력으로 보존했다. T00~T14 요약과 단계별 완료/미완료 체크박스를 갱신하고, 영어 구현·고정 후보 비교는1차 완료지만 F1/초기 속도 게이트는 미달임을 명시했다. T10 검증 BPB와 T11 test/Wikipedia BPB를 혼동하지 않고 후보 간 접두부 일치와 교사 접두부 라벨 진단을 분리했다.
- 다음 순서를 계약/새 평가 보호·자원 확인→20GB 확대 회차→한국어 데이터/엔트로피 교사 적합 준비로 정리했다. 기존10GB는 배경 원문이고 계수용 라벨 학습 약4.04MB는 고정이므로20GB 확대 대상부터 확정해야 한다. 미실시 절제실험 등을 정식 채택 전 남은 연구와 구분하고 과거 종료 진단을 선행 조건으로 재개하지 않았다. 다음은 단계/체크박스·근거 링크/수치·시간순 기록·한국어/공백 검증이다. 실제 데이터 수집·재적합·원격 실행·환경 변경·커밋은 하지 않았다.

## 2026-10-29 / 전체 태스크 감사 / 상태·근거 검증 및 정합성 보완

- 집중 검사에서 T00~T14 헤더의 유일성·완료/부분/미착수 체크박스, T03/T06/T08의 낡은 미실행 문구 제거,20GB/평가 보호/한국어 준비의 선행 항목을 확인했다.333문서/928청크/1497578바이트·BPB/경계 수치/임계값·Python/C++ 품질 대조를 원본과 재대조했고 모든 문서 링크·펜스·한국어 및 git diff --check와 편집기 진단이 통과했다.
- 추가 정합성 검토에서 이미 수행한 초기 W=1024/무제한 비교와 미실시 추가 W/배경·온라인 가중치 탐색을 체크박스로 분리했다. T09의 정식 선별 조건은 유지하되 사용자 지시에 따라 먼저 수행한 T10~T11 연구 비교를 게이트 통과와 혼동하지 않도록 문구를 맞췄다. 다음은 해당 보완과 최종 진행 기록 확인이다.

## 2026-10-29 / 전체 태스크 감사 / 완료·다음 순서 확정 범위 기록

- T09 보완 집중 검사에서 초기 W비교 완료/추가 탐색 미완료와 정식 선별/연구 비교 구분이 맞았다. 진행 기록 제목의 비한국어 혼입1건을 한국어로 수정한 뒤 동일 집중 검사를 재실행해 통과했다. 앞선 전체 단계·근거/수치·링크 검증 결과와 함께 현재 상태를 확정했다.
- 영어 구현·고정 후보 비교의1차 수행은 완료다. 다만 T06 평가 교사 접두부, T08 정식 F0.5 선택/계층·추가 탐색, T09 절제/비열등성, T10 검증 분할 BPB/경계별 손실·정식 채택/버전 고정, T11 나머지 평가 진단은 미완료로 남겼다. 게이트 미달도 보존했다.
- 다음 실행 전에 F1/F0.5 선택 계약·이미 열람한 평가의 역할/새 보류 평가 보호·20GB의 배경/라벨 대상·부모10GB 재현과 자원 예산을 정해야 한다. 이후20GB 확대 회차→한국어 데이터/엔트로피 교사 적합 준비 순서다. 한국어 실제 학습은 T12의 기준 패처·H200 파일럿/예산 해결 뒤이며 사용자 제출 계약을 유지한다. 새 현재 태스크를 추가하지 않고 기존3절/5절을 갱신했다. 이번 요청 범위인 문서 감사·상태 정리를 완료했으며 실험 실행·환경/데이터 변경·커밋/푸시는 하지 않았다.

## 2026-10-29 / T06 평가 교사 접두부 진단 / 즉시 실행 준비

- 사용자가 T06 미완료 진단을 지금 수행하도록 요청했다. 기존 학습/검증 전용 라벨 생성기를 보존하고 명시적 평가 진단 실행기를 추가했다. 부분집합은 결과 열람 전 test/wikipedia_test 각각 첫3문서의 첫 청크,각 청크 길이2..n의 모든 접두부로 고정했다. 기존 같은 모델/BF16/OSC/eager·배치1·캐시 없음·임계값을 유지하며 재적합이나 자유 생성은 하지 않는다.
- 가설은 전체 입력과 실제 접두부 호출의 BF16 형상 차이가 엔트로피뿐 아니라 일부 경계 라벨에도 차이를 만들 수 있다는 것이다. 가상 다음 위치의 불일치율과 과거 위치의 불일치율을 따로 산출한다. 합성 교사로 두 종류의 변화와 강제 위치 제외·가상 슬롯 정렬·동일 입력 재실행·packed 라벨 복원을 검사하는 테스트를 추가했다. 다음은 집중 테스트 후 실제 고정6문서 실행이다.
- itcerdo 관측 GPU는RTX5090/할당1MiB/이용률0%,기존Python3.11.16이었다. 원시 라벨/엔트로피 배열은 새 서버 run에만 보존하고 저장소에는 집계 근거만 수집한다. 자원 상한은 기존 RAM48GiB/GPU28GiB를 유지한다.

## 2026-10-29 / T06 평가 교사 접두부 진단 / 집중 검사 통과

- 새 실행기와 기존 테스트 파일만 itcerdo에 전송했다. 기존 환경에서 CountPatcherTests.test_teacher_prefix_diagnostic_separates_virtual_and_past_labels가1개/0.033초로 통과했다. 합성4개 접두부의 endpoint2/4·과거1/6·전체3/10 불일치와 packed 라벨 복원·동일 입력 재실행·잘못된 입력 거부를 확인했다. Pylance 실행기 구문 검사도 통과했다.
- 다음은 로컬 순수 패키지 검사와 서버 전체 회귀 후 실제 교사6문서 진단이다. 원본 라벨 생성기·후보 규칙·환경은 수정하지 않았다.

## 2026-10-29 / T06 평가 교사 접두부 진단 / 회귀 통과·실측 착수

- 로컬 test_api는1개 통과/1개 Torch 의존 skip이었다. itcerdo 기존 환경의 OPENBLAS_NUM_THREADS=8/BLT_TEST_NATIVE_CPP=1 전체56개 회귀가1.582초로 모두 통과했다. 새 의존성 설치나 환경 변경은 없었다.
- 다음 명시적 실행은 scripts.diagnose_teacher_prefix_labels,기존 english_patcher_pilot 설정과 en-blt-patcher-compare-20261028-01/quality.json 참조,원본 en-patcher-20261019-01 평가 분할이다. 출력은 새 runs/en-teacher-eval-prefix-20261029-01에 두고 원본 모델/교사·분할·임계값을 보호한다. GPU 점유 재확인 후 실행하며 완료 전 수치는 결과로 간주하지 않는다.

## 2026-10-29 / T06 평가 교사 접두부 진단 / 고정6청크 실측 완료

- 새 run이 completed로 끝났다. FineWeb 첫3문서의 첫 청크는 입력904/854/604 ID,위키피디아는906/2048/2048 ID였으며 총7358접두부를 평가했다. 모든 청크에서 전체 입력의 같은 길이 재실행 엔트로피/라벨은 정확히 같았다.
- 가상 다음 위치 불일치는 FineWeb2/2359,위키피디아3/4999,합산5/7358(약0.067953%)였다. 과거 위치 반복 비교는8562/5549356(약0.154288%),전체 가시 위치는8567/5556714였다.4418개 접두부에서 가상/과거 중 적어도 한 경계가 전체 입력과 달랐다. 과거 분모는 같은 위치의 반복 비교를 포함하므로 독립7358바이트 불일치율과 구분한다.
- 원시 엔트로피/packed 라벨6개 npz와 집계 JSON은 서버 run에 저장됐다. 다음은 원시 배열의 위치/임계값/불일치 수 독립 재계산 및 모델/코드/분할·산출물 해시 확인 후 작은 집계 근거 회수와 T06 상태/문서 갱신이다. 이 결과를 최종 평가 전체·다른 장치/모델의 불일치율이나 자유 생성 품질로 일반화하지 않는다.

## 2026-10-29 / T06 평가 교사 접두부 진단 / 독립 검증 통과·문서 반영

- 서버6개 원시 npz의 엔트로피·packed 라벨을 독립 복원해 강제 위치 제외·가상/과거/전체 가시 분모와 불일치 수·임계값 판정·같은 입력 재실행을 재계산했고 보고서와 일치했다. 저장된 모델 SHA는 기존4b6115bd01f6793b4a3afb6734f16b7204e841cb9248e23cd79b67ef01fff061과 같았다. 실행기/설정/참조·owner 소스·평가 분할·archive 해시도 통과했다.
- 작은 집계 evidence/english_teacher_eval_prefix_20261029.json만 회수했으며 로컬/서버 SHA256은dc48b72e5fca5731b06cb0e9de2075981c484fbc8150b5db8efd992ba6dff321로 일치했다. 원시 라벨·입력 문서는 저장소에 복사하지 않았다. 실행 보고 UTC 시작01:15:21.264840/종료01:16:24.506051,내부 경과59.537416초(로드/추론/저장 포함),GPU reserved970981376바이트/RSS2094112768바이트로 기존 예산 안이었다.
- task3절의 T06을 고정 부분집합 범위 완료로 갱신하고 T11/후속 우선순위의 T06 미완료 표현을 제거했다. 통합 문서에 분할별 수치·분모/한계·임계값 사례·재현 명령을 추가했다. 다음은 문서/태스크 상태와 원본 수치·코드 해시·링크/한국어·공백·편집기 진단 최종 확인이다. 원본 학습 라벨·교사/후보·임계값·환경은 변경하지 않았다.

## 2026-10-29 / T06 평가 교사 접두부 진단 / 최종 확인·완료

- 최종 검사에서 집계/실행기 SHA,이전 평가와 첫3문서·첫 청크 식별자,문서 표의 모든 분모/불일치 수·비율,T06의7개 완료 체크박스와 미완료 표기 제거,링크·펜스·한국어가 통과했다. 관련 코드/테스트/문서5파일의 편집기 진단과 git diff --check에도 오류가 없었다. 전체56개 회귀 및 서버 원시 배열 독립 검증 결과를 보존했다.
- T06 요청은 고정6청크/7358접두부 범위에서 완료했다. 가상 다음 위치5/7358·과거 반복 비교8562/5549356 불일치와4418개 접두부의 가시 경계 차이를 측정했다. 전체 입력 라벨과 접두부 라벨의 동일성을 가정하지 않으며 전체 평가/다른 모델·장치/자유 생성 품질로 확대하지 않는다. 후속20GB 확대·한국어 학습/준비는 자동 착수하지 않았다. 원문/원시 라벨은 서버에 보존하고 새 의존성 설치·가중치/임계값 변경·커밋/푸시 없이 마쳤다.

## 2026-10-29 / 사용자 순서 확정 / 10GB T08·T09 우선 착수

- 사용자가 현재10GB 결과의 T08·T09를 먼저 수행하고,완료 뒤20GB 배경 빈도 적합과 Neuron 한국어 후속 준비를 병행하도록 지시했다. task3절/5절을 이 순서로 갱신했다.20GB/한국어 실행은 지금 시작하지 않는다.
- 고정 분석 계획 english_count_analysis_10gb.json을 추가했다. 기존10GB 배경과 train/validation만 사용하며 독립 F1/F0.5 격자·동률 규칙,8개 전체/길이/반복/온라인 제거·W1024/eta0.5 설정,원문 문서 대응 bootstrap2000/seed20261019를 사전 고정했다. F1 비열등성0.005만 판정하고 F0.5 구간에 새 통과 기준을 만들지 않는다. 기존 F1 후보·라벨·평가 원본은 보존한다.
- 로컬 적합 코드의 RMS/L2/양수 제약을 그대로 재사용한다. 제거 특징 열을 복사본에서0으로 둬 재적합하고,새 임계값마다 후보 경계를 새로 갱신하는 캐시 순차 실행을 합성 원래 rollout과 대조하는 집중 테스트를 추가했다. 다음은 집중 검사 후 실제 특징/순차 평가·절제 실행기 완성이다.
- 서버 관측은 RAM60GiB 중 available58GiB,디스크349GiB 가용,GPU1MiB/이용률0%였다. 기존10GB 특징161665888바이트/라벨32333280바이트가 있어 동일 설정 절제에 재사용 가능하다. 기존 RAM48GiB/GPU28GiB/디스크 보호와24설정/33임계값 예산은 유지한다.

## 2026-10-29 / T08·T09 실행기 / 집중 검사 통과

- 기존 서버 venv에서 OPENBLAS_NUM_THREADS=8,PYTHONPATH=src:tests로 test_analysis_ablation_refits_and_cached_rollout_uses_own_boundaries를2회 실행해 각1테스트 통과했다(0.280초/0.276초). 제거 열 계수의 정확0·입력 비변경·원래 rollout의 경계/점수/거리 일치·F0.5 산식·동일 문서 paired구간0을 확인했다. 아직 실제 절제 결과는 없다.
- 실행기는 부모 특징 해시·라벨/청크 해시·10GB LMDB 원본 보고서 일치·부모 계수/기존F1 문서별 결과의 정확 재현을 요구한다. 설정별 H/R 캐시만 공유하고 각 임계값마다 거리·경계를 재계산한다. 선택된 후보는 검증 전체를 실제 count rollout으로 다시 대조한다.
-8설정의 각 F1/F0.5 독립 임계값 집합 합집합은33개 예산 이내다. 문서별 상대 위치·길이·반복·후보 거리·교사/후보 임계값 근방 진단,문서 대응 구간 및 절대 구간,검증 전용8입력의 patcher 단독 평균/표준편차/p50/p95/대응 속도 구간/전후 온도·전력·클록을 보고하도록 구현했다. 시간은 전체 BLT 추론 속도가 아니며 전후 전력 측정은 연속 열안정성 증명이 아니다. 다음은 확대 집중 검사와 실제8설정 실행이다.

## 2026-10-29 / T08·T09 실행 전 검사 / 로컬 결함 수정

- 확대 집중 검사에서 패치 개수 진단 블록의 IndentationError를 발견했다. 해당3행 들여쓰기만 바로잡고 동일 테스트를 다시 실행해1테스트 통과(0.279초)했다. 임계값1.0으로 경계 이력을 바꿔도 원래 rollout의 경계/점수/거리를 정확히 재현하는 추가 검사가 포함된다.
- 실제 결과가 생기기 전 오류를 수정했다. 새 수치나 성능 결과로 간주하지 않는다. 다음은 고정8설정 train/validation 실행이며 서버 실행기는 의미 있는 진행·실패를 원격 root log.md와 run progress.md에 즉시 기록한다. 로컬 로그에도 주요 단계·결과를 이어서 반영한다.

## 2026-10-29 / T08·T09 원격 실행 시작 / 회귀 검사

- 서버 tmux en-count-analysis-10gb-20261029-01은 실제 서버 표기 Thu Oct29 01:28:18 2026에 시작했다. OPENBLAS_NUM_THREADS=8,PYTHONPATH=src로 scripts.analyze_count_patcher의 고정 계획을 실행 중이다. 상세 단계는 runs/en-count-analysis-10gb-20261029-01/result.json,progress.md와 원격 root log.md에 보존한다.
- 전체 회귀57테스트를1.170초에 실행해 통과했다. 명시적 C++ opt-in 테스트1개만 건너뛰었으며 일반 NumPy/Torch/LMDB 테스트는 실행했다. 새 Python/JSON3파일의 편집기 진단도 모두 없음이었다.
- 실행 초기 원래 학습 특징 해시·계수 재현이 통과했고,전체 후보의 임계값0.375에서 TP84063/FP25370/FN20577,F1 0.7853676082457853,F0.5 0.7749570405551909로 기존 수치를 재현했다. 아직 독립 F0.5 선택·절제·최종 통계/시간이 끝나지 않았으므로 완료가 아니다. 다음은 실행 완료 후 원시 문서 수치와 근거 해시를 검증하는 단계다.

## 2026-10-29 / 추가 C++ 회귀 / 종료 대기 보조 기능 한계

- BLT_TEST_NATIVE_CPP=1로 기존 C++/Python 수치·경계·리셋1테스트를 따로 실행해0.403초에 통과했다. 앞선57테스트에서 건너뛴 선택 검사도 실제 확인했으며 진행 중인 CPU 분석의 최종 시간 측정과 겹치지 않는다.
- 종료 대기 보조 명령은 서버 Python에 os.pidfd_open 속성이 없어 실패했다. 실험 자체는 중단되지 않았다. 같은 운영체제의 libc.pidfd_open과 select를 이용한 이벤트 대기로 전환했다. 작업 완료를 추정하거나 주기적 대기 명령을 실행하지 않는다. 다음은 실제 종료 이벤트와 보고서 검증이다.

## 2026-10-29 / T0810GB 선택·계층 완료 / T09 중간6설정

- 새 특징 정렬·모든6계층의 위치 수 보존·patch 수 집계를 추가 검사해1테스트0.275초 통과했다. 자체 count_features는 기존 교사 특징과 정확히 일치했다.
- 실제 보고서에서 전체 모형의 원래 계수·F1 임계값·111원문 문서별 confusion 재현 통제가 통과했다. 각 설정의 고유 임계값은21개로33개 예산 이내다. train/validation 첫 청크의 C++/Python H/R 허용오차/정확반복 일치와 선택 결과 전체 fresh count 경계 일치 검사를 통과했다.
- 전체와 길이 제거는 각각 재적합해 같은 경계 결과를 얻었다. F1 선택0.375에서 F1=0.7853676082457853,F0.5=0.7749570405551909;독립 F0.5 선택0.625에서는 F0.5=0.806566035228912,F1=0.7396218615377921이다. 단순 계수0 재해석이 아닌 별도 적합 결과다.
- 반복 제거/길이·반복 제거의 F1 선택은0.34375,F1=0.7783429085880289;F0.5 선택0.625,F0.5=0.8074140787547199였다. eta0·반복 유지의 F1=0.7842667288412217,F0.5 선택값0.8049841959887236;eta0·반복 제거의 F1=0.7764930508890876,F0.5 선택값0.8043565051756647였다. 이 값들은 새 검증 측정이며 문서 대응 비열등성 판정·성능 선별·최종 채택은 아직 아니다.
- 현재10GB W1024의 새 H/R 특징 생성 중이다. 이후 eta0.5,8설정 대응 통계,검증 전용 patcher 단독 시간이 남았다.20GB/Neuron 작업은 시작하지 않았다.

## 2026-10-29 / T08 선택 기준 간 독립 대응 검사 / T09 중간 통계

- 완료된111검증 원문 문서의 confusion으로 별도2000회/seed20261019 paired bootstrap을 실행했다. 전체 모형의 F0.5 선택 minus 기존 F1 선택은 F1 차이95%[-0.0521289704,-0.0387901115],F0.5 차이95%[0.0259063449,0.0378476101]였다. F0.5 증가를 F1 기준 개선이나 정식 채택으로 해석하지 않는다.
- F1 선택끼리 전체 모형 대비 차이95%는 길이 제거[0,0],반복 제거 및 둘 다 제거[-0.0085336300,-0.0056653021],eta0·반복 유지[-0.0016998357,-0.0005731902],eta0·반복 제거[-0.0107292833,-0.0070512512]였다. 기존 F1 비열등성0.005로는 길이 제거/eta0·반복 유지가 통과하고 반복 제거 두 설정/eta0·반복 제거는 실패한다. 이는 재사용 검증의 선택 후 기술 구간이며 독립 새 평가의 보장이나 다중 비교 보정 결과가 아니다.
- W1024/eta0.5와 격리 시간 결과는 아직 남아 있다. 원격 진행은 계속 유지한다. 완료 전20GB를 시작하지 않는다.

## 2026-10-29 / 다음 단계 자원 예비 점검 / 아직20GB 미착수

- T09 실행과 별개로 기존 확대 실행기·10GB 저장 크기만 읽었다. 디스크 가용349GiB,기존10GB 확대 run52GiB/LMDB38GiB/원래 라벨 데이터17MiB/현재 분석275MiB였다.10GB 준비의 측정 SQLite 완료 크기는22040432640바이트,블록 카운트 합계43565515047바이트였다. 현재20GB 처리나 한국어 준비를 시작한 것은 아니다.
- 단순 전체 재구축은 배경 JSONL 포함 저장이 약104GiB로 추정돼 기존 새 산출물100GiB 한도를 넘길 위험이 있다.20GB LMDB까지 동시에 만들면 더 커진다. 추정이며 새20GB 실측값이 아니다. 기존 한도를 자동 확대하거나 기존 데이터/실패 자료를 지우지 않는다.
- 기존 준비기는 부모 원문을 그대로 선두에 보존한다. 후속의 작은 명시적 선택 구현으로 부모의 검증된400블록을 참조하고 새10GB만 빈도로 구축하면 동일 문서별 가산 빈도를 중복 저장하지 않을 수 있다. 이는 아직 제안이며 실제 사용 전 소형 원문/전체 재구축 대조·부모 접두부/해시 변조 실패 검사가 필요하다. 그 방식이면 새20GB LMDB 없이 기존 순차 투영 적합 경로를 사용할 수 있다. T09 완료 후 예산 안의 경로를 확정한다.

## 2026-10-29 / T08·T09 최종 완료 / 독립 검증 통과·20GB로 전환

- 실제 UTC01:28:18.536881~01:53:15.950753,1497.412412초에 completed로 종료했다. 최대 RSS32350359552바이트(30.128620GiB),8설정×21고유 임계값/16선택을 검증했다. 모든463770위치의 fresh count 경계,111문서 합계,6계층의 위치/TP/FP/FN 보존,제거 계수0·최적화 조건,2000회 대응 구간,코드/설정/부모·라벨/특징/시간 해시가 독립 재계산과 같았다.
- W1024는 F1=0.7852947086559715,차이95%[-0.0004158908485,0.0002785038913];eta0.5는0.7854195066385314,차이95%[-0.0001551327848,0.0002734623442]로 F1 비열등성 통과였다. 기존 전체/길이 제거/eta0 반복 유지와 포함해도 최고 F1은0.90 미달이다. R 제거3설정은 허용폭0.005 비열등성 실패다. F0.5 최고0.807414도 새 통과 기준이나 F1 개선으로 해석하지 않는다.
- 단독 시간은 검증8입력/16개 Python 후보 선택/교사,warmup3/repeat10·교대·독립 LRU·GPU 동기화였다. 모든 평균/표본 표준편차/p50·비율을 원시 표본에서 재계산했다. 전체/F1의 교사 대비 초기0.064896~0.223090배,동일32증분16.54188~53.42584배,초기 포함1.82598~4.56617배다. 전체 모형은 아니며 초기 단독 비용은 느렸다. GPU 전후35~43도/64.07~136.29W/2407~2887MHz 관측은 연속 열안정성·CPU 열/전력 증명이 아니다.
- 집계만 evidence/english_count_analysis_10gb_20261029.json(SHA3e74b81ef6c8fc704a58936a0b98f3be043cdfef3bf0114d82a06804d582f247) 및 english_count_analysis_timing_20261029.json(SHA8f14359ad3432529639b8b10531861a259fede03775a6cb594083c5e68896300)으로 회수했다. 로컬 해시도 같았다. 원문/학습 특징/LMDB/가중치는 복사하지 않았다.
- task T08/T09와 통합·인수인계를 완료 상태/실패 게이트/미측정 한계로 갱신했다. 다음 단계는 명시적 부모 블록 재사용의 소형 전체 재구축 대조 후20GB 파이프라인을 시작하고,그동안 한국어 Neuron 준비물과 미확정 입력을 정리하는 것이다. 아직20GB/Neuron을 실행했다고 주장하지 않는다.

## 2026-10-29 /20GB 명시적 부모 블록 재사용 / 집중 검사 통과

- run_background_expansion.build_blocks에 reuse_parent_blocks=true를 명시한 새 계획만 활성화하는 경로를 추가했다. 부모 보고서 SHA·카운트 규약/manifest·모든 블록 SHA/크기·원문 SHA/문서·바이트 합계·전체 부모 원문 접두부를 검증한 뒤 부모 블록을 참조하고 새 문서만 구축한다. 부모 파일은 수정하지 않는다. 새 실제 run 저장량과100GiB 여유를 매 블록 검사하며 한도를 늘리지 않는다.
- 소형 전체 재구축 대조와 기존 기본/압축 경로2테스트를0.453초에 통과했다. 조합 빈도의 모든 행·문서/입력 ID/바이트 합계가 같았고,접두부 변경·고정 보고서 SHA 변경·블록 변조·비불리언 선택은 거부했다. 실제20GB 결과를 측정한 검사는 아니다.
- 새 계획 english_background_20gb_nested.json을 고정했다. 누적 배경 원문20000000000바이트,기존10GB400블록 재사용,새10GB 블록만 저장·새 LMDB 미생성으로 예상 최종/준비 공간 각각약64GiB를 목표로 한다. 기존48GiB/100GiB 새 산출물/최소100GiB 여유/BLAS8을 유지하고 원문 포함·중복 제거·원래 F1 적합·10GB 대응 비교를 수행한다.20GB의 새 학습 라벨이나 한국어 자료를 뜻하지 않는다.
- 기존 T08/T09에서 부모 계수/검증111문서가 정확 재현됐으므로 준비 전 중복400블록 투영 스캔만 생략한다. 실제 적합과 부모 대응 비교의 해시/순차 재생은 유지한다. 최종 독립 평가·F0.5 후보 채택은 하지 않는다. 다음은 확대 회귀·예산/계획 해시 점검 후 원격 장기 파이프라인 착수다.

## 2026-10-29 /20GB 시작 전 최종 검사 /59회귀 통과

- 부모 적합 보고서의 고정 SHA를 착수/비교에서 강제하고,T08/T09 완료 보고서 SHA·status=completed를 시작 조건으로 추가했다. 변조 거부/부모 블록 재사용2집중 검사는0.415초에 통과했다.
- OPENBLAS_NUM_THREADS=8,BLT_TEST_NATIVE_CPP=1에서 전체59테스트를1.678초에 실행해 건너뛰기 없이 통과했다. 새20GB JSON 구문과 Python/JSON3파일 편집기 진단도 통과했다. 실제 가용 디스크349GiB로 기존100GiB 여유 조건을 충족했다.
- 다음 명령은 서버 source의 기존 venv로 고정20GB 계획을 원격 tmux blt-bg20gb-nested-20261029-01에서 실행하는 것이다. 완료된10GB 실험과 겹쳐 새 성능을 측정하지 않는다. 준비·새 빈도 구축·기존 F1 적합·10GB 대응 비교의 장기 파이프라인이며 성공/실패는 원격 root log와 run progress/run_report에 기록한다. 실패 시 원본/중간 산출물을 보존하고 자동 재시도하지 않는다.

## 2026-10-29 /20GB 파이프라인 실제 착수 / 한국어 T12 준비 시작

- 서버 tmux blt-bg20gb-nested-20261029-01은 실제2026-10-29 UTC01:58:50에 시작했고 고정 게이트 통과 뒤 prepare started를 기록했다. 원격 PID925467의 주 실행기가 유지되는 것을 확인했다. 아직 자료 준비 단계이며20GB 적합·수치 결과 완료가 아니다. 사용자 요청 순서대로10GB T08/T09 종료·검증 뒤 시작했다.
- 한국어 후보의 공식 FineWeb2 카드와 HfApi 메타데이터를 확인했다. 실제 관측 UTC01:59:40.530202,repository HuggingFaceFW/fineweb-2,revision af9c13333eb981300149d5ca60a8e9d659b276b9,kor_Hang의 train25개/test1개,선언 odc-by였다. 공식 카드는 ODC-By1.0·CommonCrawl 조건과 이메일/IP 익명화의 한계·남을 수 있는 개인정보를 명시한다. 원문/가중치를 다운로드하지 않았으며 데이터 사용 승인을 대신하지 않는다.
- 한국어 준비 JSON/문서와 사용자용 읽기 전용 환경 수집기를 추가했다. 공식 test 보류·문서/중복 군집 분할·학습 역할 중첩 계약·원문 UTF-8 보존,선행 한국어 교사 추가 학습 권고안,실제 학습 step/Adam 상태/저장·재개·학습 bytes/s 예산 게이트를 정리했다. 할당·바이트/모델 규모·기간·소유 프로젝트 entrypoint가 미정이므로 학습 승인은 false이고 가짜 Slurm 학습 명령은 만들지 않았다.
- Neuron 접속·전송·제출은 계속 사용자 담당이다. 다음은 수집기 구문·로컬 비GPU 실행/인자 오류·JSON/링크 검증,20GB 파이프라인의 초기 준비·보호 예산 상태 확인이다. T12 전체를 완료로 표시하지 않는다.

## 2026-10-29 / 준비물 최종 검사 /20GB 초기 진행 확인·인수인계

- 한국어 환경 수집기는 bash -n,Mac의 실제 비GPU 실행,존재하지 않는 경로의 exit2 거부를 통과했다. 새 의존성 설치·GPU 실행·Slurm 제출은 없었다. JSON의 training_authorized=false,태스크/한국어 준비 문서의 로컬 링크,변경 공백,Python/JSON/Shell/문서 편집기 진단을 확인했다. 실제 Neuron 할당에서의 실행은 미검증이다.
-20GB 파이프라인은 실제 UTC02:02:17의 Disk preparation heartbeat170,임시 저장1470442587바이트,최대 RSS202051584바이트로 진행 중이었다. 원격 tmux가 유지되고 디스크347GiB 가용/RAM57GiB available이었다. 초기 준비 실측일 뿐20GB 최종 용량·속도·계수/성능 결과가 아니다. 종료 보고서는 run_report.json,상세 진행/실패는 progress.md와 원격 root log.md에 남긴다.
-10GB T08/T09는 완료·독립 검증 통과,20GB는 prepare→build→fit→compare 장기 실행 중,T12는 후보 출처/계약/수집기 준비·학습 미승인으로 task와 HANDOFF를 정리했다. 실제 한국어 할당/작업 경로·모델/데이터/기간 예산·소유 학습 진입점 확인이 남았다.59회귀 통과를 보존하고 현재 장기 실행 소스는 더 변경하지 않는다. 커밋/푸시·기존 작업 중단·자료/환경 삭제는 하지 않았다.

## 2026-10-29 / 외부 한국어 CPT 계획 병합 / 설계 반영

- 사용자 제공 T13.plan.md(원문 작성 기준2026-10-20)를 읽고 기존 한국어 준비 문서/JSON에 연구 설계를 병합했다. 원문은 수정하지 않았다. 공개 가중치 CPT,B0/E1/L0/조건부 G1/F1,동일 공개 본체 독립 출발·동일 노출 통제,고정 글로벌을 통한 encoder gradient·실제 파라미터 목록 검사,영어 망각·checkpoint 복원·비용 분리를 반영했다. 실험 F1은 JSON에서 body_full로 구별했다.
-75/15/10 혼합,1GB/5GB와30/100/300GB 단계,4/6/8 bytes/patch,5090 우선 파일럿은 제안으로만 반영했다. 기존 H200 목표·원문 UTF-8 보존·Neuron 사용자 접속/제출 계약을 유지하며 자원 배치 변경은 미승인이다. 학습 승인 false·실제 예산 null을 보존했다. 원본의 외부 환경 파일/노드 정책/모델 규모·메모리·기간·선행 그래프 값은 검증된 근거로 승계하지 않았고 비밀 파일을 읽지 않았다.
- T06의 전체 입력/접두부 경계 차이를 패치 캐시 계약에 반영해 동일 문맥 online/offline 대조와 가변 접두부 한계를 구분했다. 캐시 출력 보존 연구와 CPT·count 대체를 분리하고 소유 프로젝트의 학습 구현 책임을 유지한다. 이번 요청은 문서/계약 병합이며 원격20GB 실행 소스나 학습/데이터를 변경하지 않는다. 다음은 JSON 게이트/참조 검증 후 task T12~T14와 인수인계 동기화다.

## 2026-10-29 / CPT 계획 병합 검사 / 태스크 동기화

- 첫 집중 검사에서 JSON 파싱,training_authorized=false,실제 byte/자원 예산 null,제안 혼합/노출 approved=false,5개 실험 ID·조건부 G1/body_full,준비 문서 링크/펜스를 확인해 통과했다. 새 실험 수치나 학습 결과를 만든 검사는 아니다.
- task의 기존 T12~T14에 교사 CPT·B0/E1·L0 우선/조건부 G1/F1·독립 출발 통제·정량 확대 게이트·저장/복원·T14 고정 본체 count 비교를 통합했다. 본체 후 교사 신규 학습이 필수로 읽히던 순서를 바로잡았다. 설계 병합만 완료 표시하고 실제 준비/학습 체크박스는 미완료로 유지했다. 인수인계에 원본과 병합본/미승인 범위를 연결했다.
- 다음은 전체 변경 문서의 링크/펜스·구문·계약 일치·공백 검사다. 런타임 코드는 바꾸지 않았으므로59개 Python 회귀나 원격 실험을 재실행하지 않는다.20GB의 현재 원격 상태를 이번 병합에서 재측정했다고 주장하지 않는다.

## 2026-10-29 / CPT 병합 문서 검증 통과

- JSON·미승인 실행/예산/품질 게이트·독립 출발 문구·Neuron 사용자 권한·3개 문서의 로컬 링크/펜스/원본 참조 검사와 git diff --check가 통과했다. 준비 문서/JSON/task/HANDOFF의 편집기 진단도 오류가 없었다. 런타임 회귀나 한국어 학습을 실행한 결과는 아니다.
- JSON의 차단 상태를 특정 Neuron 할당이 아닌 학습 계약/하드웨어 선택 미확정으로 명확히 하고,저장·평가가 포함된 처리량에 비용을 중복 가산하지 않도록 정리했다. 마지막 패치에서 log 문맥 오타로 적용이 거부되어 정확한 문맥으로 재적용했다. 다음은 최종 JSON/공백 재검사 뒤 사용자에게 병합 범위와 미승인 항목을 보고하는 것이다.
- 최종 재검사도 통과했다: JSON 구문·정확한 차단 상태·training_authorized=false·자원 예산 null·비용 중복 방지 문구,git diff --check,JSON/log 편집기 진단 오류 없음. 원본 T13.plan.md와 원격 실행을 보존했다. 다음 결정은 실제 데이터/노출·품질/망각/기간 한도와5090 우선 대안의 승인 여부이며 이번에는 계획 병합까지만 완료했다.

## 2026-10-29 / 사용자 지정 한국어 단계 ID 동기화

- 사용자가 준비 문서 표에서 변경한 BLT/PATCHER/ENCODER/GLOBAL/BODY_FULL을 확인했다. 해당 문서의 잔여 참조·task T12/T13·HANDOFF·준비 JSON을 같은 대문자 ID로 통일하고 옛 display_id를 제거했다. ENCODER는 로컬 decoder/byte 임베딩/cross-attention/projection도 포함한다는 기존 학습 범위를 명시했다.
- 명칭 변경만 수행하며 글로벌/해시 동결 범위·독립 공개 본체 출발·조건부 승인·학습 미승인 상태를 보존한다. 경계 지표 F1·영어 근거·과거 로그는 바꾸지 않는다. 다음은 표/JSON ID 일치·옛 참조 부재·계약 보존 집중 검사 후 가져온 원본의 명칭 대응 안내다.
- 집중 검사 통과: 표와 JSON의5개 ID/순서 일치,활성4파일의 B0/E1/L0/G1/body_full 부재,업데이트 범위·조건부 상위 단계·학습 미승인/예산 null 보존을 확인했다. 원본 T13.plan.md에는 옛 ID와 현 ID 대응 안내 및 정식 문서 링크만 추가해 가져온 본문을 보존했다. 새 학습·원격 실행은 없으며 다음은 문서 참조/구문·공백 최종 검사다.
- 최종 링크 검사는 원본의 기존 외부 프로젝트 경로 paper/blt.pdf에서 실패했다. 원문 보존 범위의 기존 링크로 구분해 활성3문서 전체 링크/펜스/옛 ID 부재와 원본에 새로 추가한 참조를 재검사했고 통과했다. JSON의5개 ID/미승인 유지·git diff --check도 통과,변경5파일 편집기 진단 오류 없음이다. 원본의 기존 외부 링크를 유효하다고 주장하지 않는다. 다음 작업부터 새 ID를 사용하며 이번 변경은 명칭 동기화까지만 완료했다.

## 2026-10-29 / 모두의 말뭉치 신청 대상 선정안

- 사용자 요청으로 공식 목록 https://kli.korean.go.kr/corpus/main/requestMain.do 및 신청 도움말/이용 정책/세종 DVD 공지를 확인했다. 일반 한국어 CPT에서 FineWeb2의 장르를 보완하기 위한 우선 신청안은 문어 말뭉치 2025(v1.0),문어 말뭉치(v1.2),구어 말뭉치(v1.2),일상 대화 말뭉치 2025(v1.0),온라인 대화 말뭉치 2021(v1.1)이다. 첫 항목은 공식 소개상 문학·정보 도서10,293종이며,기존 문어는 책·잡지·보고서,구어는 방송·강연·대본을 포함한다.
- 온라인 게시 자료 2025와 신문 2025는 추가 후보로 두고,음성/형태·구문 주석/병렬·요약·지시문 파생 자료는 이번 원문 CPT의 우선 신청에서 제외하는 제안이다. 이는 장르 기반 판단이며 효과·UTF-8 실용량·최적 혼합률을 측정한 결과가 아니다. 연도/버전 간 누적·대체·중복 여부와 FineWeb2 중복을 수령 후 확인해야 한다.
- 공식 도움말상 신청 사유/이용 기간 기재,관리자 승인,약정 동의·서명이 필요하다. 자료별 학습/모델 가중치 공개 허용 범위는 아직 확인하지 않았으며 승인된 범위·기간 및 결과물 공개 절차를 확인해야 한다. 세종계획은 별도 DVD 신청 안내(2021-07-01,기존 웹 배포 종료)가 연결되어 있어 위 온라인 목록과 동일 자료로 간주하지 않는다. 신청·다운로드·학습·계약 변경은 하지 않았다. 다음은 사용자 신청 및 자료별 약정/설명서 확인이다.

## 2026-10-29 / 사용자 신청 완료 보고와 세종 다운로드 도구 검토

- 사용자가 모두의 말뭉치의 필요한 자료를 신청했으며 직접 내려받아 itcerdo로 전송할 예정이라고 보고했다. 신청 대상의 정확한 목록·승인·다운로드·전송 완료는 확인하지 않았다. 준비 문서에 사용자 보고와 이후 파일/약정/SHA 확인 필요를 반영했다.
- https://github.com/coolengineer/sejong-corpus 의 README,sejongrc,10.list.sh,LICENSE.txt를 웹으로 확인했다. 데이터 미러가 아닌 과거 ithub.korean.go.kr 게시판용 스크립트이며 기본 변환에 수작업 패치가 포함된다. 별도 형태소/자모 가공도 있으므로 원문 CPT에 무심코 적용하지 않는다. 약정 사본에는 비상업적 연구 용도 및 결과물의 출처 명시 조건이 있다. README의 약2GB는 당시 설명이지 현재 확보량 측정이 아니다.
- 다운로드 가능성은 미검증이며 공식 웹 배포 종료 안내와 충돌할 수 있는 옛 엔드포인트라는 한계가 있다. 도구 실행·자료 다운로드·원격 접속/전송·학습은 하지 않았다. 현재 취득/결과물 공개 약정 확인과 사용자 전송 후 원본 목록/문서 단위 중복 검사가 다음 단계다.

## 2026-10-29 / 한국어 PATCHER 학습 준비 착수

- 사용자 승인 범위: 모두의 말뭉치와 FineWeb2를 기본 자료로 하고 세종 확보는 필수 조건에서 제외한다. itcerdo 수신 디렉터리와 자료 도착 후 entropy CPT를 수행할 코드를 준비한다. 실제 한국어 학습/대규모 다운로드/Neuron 접속은 시작하지 않는다. 기존 본체 학습기는 교사를 동결하므로 소유 프로젝트 phdq3에 별도 교사 진입점을 추가하고 합성 자료로 정렬·저장/재개를 검사할 계획이다.
- 읽기 전용 원격 확인: RTX5090 사용1MiB/0%,디스크329GiB 여유,호스트 RAM58GiB available이었다. 이는 조회 순간 값이지 학습 처리량/상시 공존 검증이 아니다. 공개 entropy revision f2aae511e44e2086b1204bc4ddec6ac6c9651332의 기존 다운로드·변환 자료가 소유 프로젝트에 있다. 기존 환경/가중치/사용자 변경은 보존한다.
- 정정: 영어20GB는 더 이상 실행 중이 아니다. runs/en-patcher-bg20gb-nested-20261029-01/run_report.json은 status=failed,prepare 하위 명령 exit1,elapsed4368.500978s를 기록한다. 실패 원인은 이번 범위에서 추가 진단하지 않았고 재시작/산출물 수정도 하지 않았다. 기존 문서의 prepare 진행 중 표시는 이 조회보다 이전 상태다. 다음은 패처 모델 호출 규약 확인과 코드·합성 검증,수신 경로 생성이다.
- 소유 프로젝트에 entropy_data.py와 tests/test_hf_entropy.py를 추가했다. 합성3검사 통과(0.003s): UTF-8 바이트 보존/단일 shift/BOS·최종 EOS/문서 비연결/자료 hash 및 최종 test 입력 거부. 실제 말뭉치 학습은 아니다. 별도 entropy_train.py와 미승인 설정을 추가해 패처 로더·CE·예산 게이트·저장/재개 검증을 준비한다. 최초 복합 패치는 소유 로그 문맥 차이로 거부되어 정확한 범위로 재적용했다.
- entropy_train 기본 preflight는 학습 승인/5개 자원 상한/자료 manifest 부재를 차단 사유로 보고했고 구문 검사도 통과했다. 명시적 NIKL paragraph/utterance 또는 id/source/text JSONL 변환을 추가한 후 합성 검사4개 통과,로컬 Torch 부재로 optimizer/RNG 재개1개는 skip이다(전체5개,0.005s). 실제 수령 schema와 근접 중복/개인정보/권리 검토는 미완료이며 생성 manifest의 승인3종은 false로 유지한다. 다음은 원격 수신 디렉터리 생성과 신규 파일만 배치 후 기존 Torch 환경의 CPU 검증이다.
- itcerdo 소유 프로젝트에 data/korean_cpt/{incoming/nikl,incoming/fineweb2,licenses,manifests,prepared},outputs/korean_entropy,artifacts/korean_entropy를 신규 생성(새 디렉터리0700)하고 신규4파일만 배치했다. 첫 원격 합성 검사는 독립 CE 합산의 비트 동일성 요구에서 실패했다. 합산 비교만 rtol/atol1e-6으로 수정했고 optimizer/RNG 복원 후 다음 손실·모수 exact 비교는 유지했다. 재실행5검사 모두 통과(1.663s)했다.
- 기존 phdq_blt_hf 환경에서 CPU --check-model 성공: 패처99,512,064모수,BF16,strict loading. preflight는 학습 미승인/5예산 null/미수령 manifest로 training_ready=false이며 CUDA 학습은 실행하지 않았다. 패키지 설치나 기존 환경·가중치 수정도 없었다. 다음은 실행 안내/태스크·기계 계약 반영과 자원/재개 보호의 마무리 검사다.
- 체크포인트 SHA 검증/저장 전 여유·산출물 예산/GPU allocator 상한/검증 기한을 보완한 뒤 원격 합성5검사 재통과(1.668s),CPU strict load/preflight 보고서를 artifacts/korean_entropy/preparation-20261029.json에 신규 생성했다. 실제 패처 합성 CPU CE42.64093017578125/14 targets 및 backward에서129모수 텐서의 기울기 finite를 확인했다. optimizer0회/체크포인트 미생성이며 이 손실은 한국어 품질 지표가 아니다. 다음은 안내·태스크·기계 계약의 최종 일치 및 원격 파일 hash 검사다.
- 최종 실패 경로 보강: 승인/자료/예산 미확정 차단,저장 전 디스크 reserve 및 손상 checkpoint hash 거부를 검증했다. 원격 새 준비7개+기존 학습 스케줄3개 총10검사 통과(1.665s). 준비 JSON의 승인 false/5예산 null/세종 비필수와 안내 펜스 검사도 통과했다. 문서 패치1회가 잘못된 끝 문맥으로 거부되어 해당 문맥을 제거해 재적용했다. 다음은 원격 안내 배치·파일 hash 대조·최종 문서/구문 검사다.
- 최종 배치 확인 통과: itcerdo의 entropy_data.py/entropy_train.py/test_hf_entropy.py/korean_entropy_preparation.json/KOREAN_ENTROPY.md 총5파일 SHA256이 로컬 검증본과 모두 일치한다. Pylance entropy_train 구문 오류 없음,새 Python3파일 py_compile 및 두 저장소 git diff --check 통과,준비 문서/task/JSON/HANDOFF/소유 안내 편집기 진단 오류 없음이다. 기존 환경·원본 가중치·제공 split·20GB 실패 산출물을 보존했고 Neuron 접속/제출은 없었다.
- 이번 요청의 수신 디렉터리/소유 학습 코드 준비는 완료했다. 실제 말뭉치가 도착하면 schema/약정/PII/문서·근접중복 분할과 자료 manifest를 확정하고 예산 승인 후 실제 GPU Adam/VRAM/처리량·재개 파일럿을 수행해야 한다. FineWeb2 Parquet 수집/정제와 품질·망각·threshold 검증은 아직 남았으며 지금 상태를 즉시 대규모 CPT 가능 또는 한국어 적응 성공으로 주장하지 않는다. 사용자 전송 위치는 phdq3/data/korean_cpt/incoming/nikl,설명서/약정은 data/korean_cpt/licenses다.

## 2026-10-29 / 20GB 실패 직접 원인과 재시도 준비

- 사용자 요청으로 실패 launch.log를 확인했다. prepare_disk_background.py의 candidates에서 ValueError: Insufficient candidate bytes in pinned shard가 발생했다. 실패 직전 RSS304,881,664B이며 메모리 부족으로 단정할 근거는 없다. 각 고정 shard에 같은 후보 바이트를 요구하고 작은 shard가 소진되면 전체 자료를 보기 전에 실패하는 조건을 확인했다.
- 새 실행 전용 opt-in candidate_quota_policy=redistribute_remaining_v2를 추가한다. 전체 후보 예산·고정 source revision/order는 보존하며 부족분을 남은 shard로 재배분하고 전체 후보 부족은 실패한다. 기존 equal_v1 동작과 실패 run/SQLite/로그는 보존한다. 다음은 작은 shard/전체 부족/구정책 보존 합성 회귀 후 새 run ID로 실행하는 것이다.
- Neuron 배포는 사용자 요청에 따라 별도 디렉터리에 모으고 phdq3/scripts 및 ssh.md의 정책만 참고한다. ssh.md에는 평문 자격증명이 있어 배포/사용하지 않으며 사용자에게 폐기·재발급을 권고했다. Neuron 접속/전송/제출은 하지 않는다.
- opt-in 후보 재배분 단독 검사 통과 후 itcerdo에서 `OPENBLAS_NUM_THREADS=8 ../.venv/bin/python -m unittest tests.test_data_preparation -v` 12검사 모두 통과(0.821s). 기존 sampling parity/부모 블록 재사용/native dedup 회귀 포함이다. 디스크329GiB/RAM58GiB available은 조회 순간 값이다.
- 추가 진단: 기존4개 Parquet text 컬럼의 비압축 크기는 각각3428022433/3425382377/3428191002/3431348647B(합계 약13.71GB). 이는 실제 적격 UTF-8 합계가 아닌 컬럼 메타데이터이며, 전체20GB 확보를 재배분만으로 보장하지 못한다. 실패 SQLite 읽기 전용 집계는 보호2753721/신규260279문서다. 실패 파일은 수정하지 않았다.
- 사용자의 추가 shard 수집 취지에 따라 같은 FineWeb revision/prefix의296개 신규 후보를 정렬·seed20261029 shuffle해12개를 고정했다. `evidence/english_background_sources_20261029.json`과 새 `experiments/english_background_20gb_retry.json`을 추가했다. 부모10GB/평가 보호는 중첩 규모 비교·누출 방지 조건,48GiB RAM/100GiB 산출물은 이번 실행의 안전 상한이며 프로젝트 전체 제한이 아님을 설명했다. 아직 재실행/실제20GB 확보는 미완료다. 다음은 계획 검사와 새 run02 시작이다.
- 로컬 stdlib 검사 통과: 신규12shard 유일성/기존4개와 비중복/동일revision·prefix/source-config SHA/부모·T08·F1 비교 identity/run·tmux 분리. 다음은 새 계획2파일만 배치 후 run02를 tmux에서 시작하고 초기 상태를 확인하는 것이다.
- itcerdo 새 tmux `blt-bg20gb-nested-20261029-02`에서 run02 시작. 서버 progress 시작2026-10-29T08:33:53+00:00,08:34:25 heartbeat checks10/scratch72199145B/RSS200581120B를 확인했다. prepare 진행 중이며 완료/20GB 실수율은 아직 미확정이다. 기존01은 보존한다. 다음은 Neuron 전용 사용자 실행 bundle 준비다.
- Neuron 기존 GEC common의 데이터 전수 감사/신호 전달을 그대로 사용하지 않는다. 소유 entropy 실행기에 SIGUSR1/SIGTERM step-boundary 중단·저장 후 exit75를 추가하고 validation 중단 시 미완료를 분리한다. attention/patching 등 실제 의존 코드 hash도 resume identity에 포함한다. 다음은 신호 합성·기존 optimizer/RNG 검사 후 고정 배포 사본 생성이다.
- 로컬 신호 집중1검사 통과,소유2파일 itcerdo 배치 후 entropy8+기존학습3 총11검사 통과(1.812s). 실제 GPU signal/optimizer 검증은 아직 아니다. 별도 `neuron/`에 allowlist/hash 기반 소유 런타임 export·검증,단일GPU SLURM/경로/종료여유 검사,기본 preflight wrapper·미승인 template·합성 guard 검사를 추가했다. 다음은 집중 검사와 고정 snapshot 생성이다.
- Neuron guard3검사 통과(0.007s): 기본 preflight/승인/15분여유,허용 partition·단일GPU·CPU비율·root·comment,파일hash/allowlist 변조 거부. bash -n 통과. 다운로드·자료/예산 승인·파일럿·재개·실패 보존을 `neuron/README.md`에 정리했다. 다음은16파일 고정 export와 배포 사본 자체 검사,비밀정보 없는 범위만 GitHub 게시다.
- 첫 export 사전 검사에서 소유 tests/__init__.py 부재를 발견해 배포 생성 전에 중단했다. namespace tests에 불필요한 항목을 allowlist에서 제거해 실제15파일로 정정했다. 소유 테스트·실행 산출물은 변경하지 않는다. 같은 export/guard 검사를 재실행한다.
-15파일 export/hash 검증과 guard3/b​​ash -n 재검사 통과. itcerdo의 독립 `neuron-check-20261029`에서 guard3(0.003s)/entropy8(2.068s) 및 실제99512064모수 BF16 strict load 통과. 승인 false/예산·manifest 부재 차단을 확인했고 학습은 하지 않았다. 편집기 새4파일 오류 없음/git diff --check/비밀정보 패턴 검사 통과. 다음은 기존 H200 목표에 맞춘 기본 partition 확인과 `neuron/`만 게시하는 것이다.
- UTC08:39:52 run02 heartbeat checks340/scratch2875878433B/RSS201170944B,tmux 유지. prepare 진행 중이며 실수율/20GB 완료·적합 성능은 아직 미확정이다. 한국어 본 학습은 Neuron 사용자 실행 경로로 분리하고 데이터·학습 예산 승인 조건은 유지한다.
- H200 기본값 반영 후 허용3partition 포함 guard3(0.008s),bash -n,준비 JSON/git diff --check 통과. 스테이징은 신규 neuron21파일만이며 다른 기존 변경·20GB 소스 수정은 포함하지 않았다. 다음은 이 범위만 커밋·GitHub push 후 원격 SHA 확인이다. 기존 안전한 Git 인증만 사용하고 문서에 노출된 자격증명은 사용하지 않는다.
- 용량 표현 보완: 약13.71GB는4개 Parquet text 컬럼의 비압축 저장 메타데이터 합계이지 실제 UTF-8 적격 문서 합계의 실측이나 엄밀한 상한이 아니다(encoding 영향). 직접 확인한 실패 원인은 실제 shard 소진 시 후보 quota 미달이다. 추가12shard로 source 범위 부족을 해소하도록 계획을 수정했으며,최종 중복 제거 후20GB 확보 여부는 진행 중 실행으로 판정한다.
- 게시 완료: 신규 `neuron/`21파일만 commit `a0cfa521a272ac61f19d60bde17674cb2e86fa56`로 GitHub `esoterikosQ/26-14_CACHE` main에 일반 push했고 ls-remote SHA 일치를 확인했다. 다른 기존 미커밋 변경/20GB 소스/비밀 파일은 포함하지 않았다. 가중치·원문·checkpoint·인증 파일 없이 소유15파일 고정 사본/검증·스크립트·미승인 설정·설명만 배포했다.
- 최종20GB 관측: 서버2026-10-29T08:42:45+00:00 조회 시08:42:36 heartbeat checks480/scratch4192909863B/RSS201170944B,tmux 유지/run_report 아직 없음. prepare 진행 중이며20GB 완료/fit/compare·품질 개선을 주장하지 않는다. 다음은 사용자의 Neuron preflight 보고서·실제 자료/예산 승인 확인과20GB 단계 완료/실패 보고서 수집이다. Neuron 접속/전송/제출·실제 pretrained optimizer는 수행하지 않았다.
- 최종 기록 검사 통과: 준비 JSON 파싱/두 저장소 git diff --check/인계·task·JSON·Neuron shell 편집기 진단 오류 없음. 게시된 neuron 경로의 미커밋 변경은 없으며 나머지 기존 작업 변경은 보존한다. 현 상태와 미검증 GPU·20GB 완료 조건을 사용자에게 인계한다.

## 2026-10-29 / Neuron 작업별 명령 문서

- 사용자 요청으로 `neuron/command.md`에 원문/약정/정제 자료/manifest/가중치/설정/산출물 저장 경로와 다운로드·환경·데이터 준비·preflight·2step 파일럿·재개·본 학습·상태/중단 명령을 추가했다. 배포 README에서 연결한다. 실제 entropy_data의 명시적 split/schema·파일 크기 제한과 미구현 FineWeb2 Parquet 수집·본체 학습을 구분했다.
- 기본승인 false/예산 null,동일 CONFIG 재개,원본/실패 보존,사용자만 Neuron 실행 원칙을 유지했다. 자료 준비는 미확인 CPU partition을 만들지 않고 기존 확인된 H2001GPU 할당 안에서 CPU 작업으로 안내했다. 이번 변경은 문서뿐이며 Neuron 접속·제출/추가 데이터 수집/학습/커밋·push는 수행하지 않았다. 다음은 모든 shell 블록·내장 Python의 구문과 배포 경로/CLI 일치 검사다.
- 로컬 검사 통과: bash18블록 전체 `bash -n`,내장 Python2블록 AST,고정 runtime 파일 경로와 데이터 CLI --plan/--output 확인. 실제 원문 파일명/예산은 의도적으로 미확정으로 두었고 자동 승인 명령은 넣지 않았다. task에 명령 문서 위치·로컬 변경 상태를 기록했다. Neuron에서의 실제 실행 검증은 사용자 수행 대기다.
- 최종 git diff --check와 명령표/README/task 편집기 진단 통과,README 링크 대상 존재 확인. 신규 command.md와 README 변경은 미커밋·미게시 상태로 남겼다. 명령 문서 작성 요청은 완료했으며 실제 cluster 명령은 실행하지 않았다.

## 2026-10-29 / 사용자 Neuron 실행 로그 수신 경로

- 사용자가 Neuron 작업을 전부 직접 실행하고 결과를 전달하는 방식으로 재확인했다. 저장소 루트에 `runtimelog/README.md`를 만들고 작업명/Job ID별 결과 보존과 공유할 작은 보고서 목록을 안내했다. 기존 Neuron 출력 경로·실행기는 변경하지 않았다.
- `.gitignore`에 runtimelog 내용 제외/README 예외를 추가하고 명령표·task에 수신 경로를 반영했다. 토큰/전체 환경변수/원문/가중치/checkpoint는 제외한다. Neuron 접속·실행·제출이나 commit/push는 하지 않았다. 다음은 디렉터리 존재와 Git 제외 규칙 확인이다.
- 검증 통과: runtimelog 디렉터리 존재,샘플 metrics/SLURM 로그의 git check-ignore 제외,README 추적 예외,git diff --check 및 안내/명령표/task 편집기 진단 오류 없음. 실제 결과 로그는 아직 수령하지 않았으며 사용자가 전달하면 해당 실행 결과를 분석한다.

## 2026-10-29 / GitHub 로그 전달 방식 정정

- 사용자 지시를 잘못 이해해 추가했던 runtimelog 제외 규칙을 제거했다. 정본은 Neuron 사용자 실행/결과 수집→runtimelog commit/push→로컬 pull→분석이다. 이전 제외 기록은 당시 작업 이력이며 현재 정책이 아니다. 가중치·원문·비밀정보 제외는 유지한다.
- runtimelog 안내·작업 명령표·task를 수정했다. 실행용 detached commit을 변경하지 않도록 별도 로그용 main clone에서 검토한 작업별 파일만 게시하고,로컬 수신 시 기존 변경을 보존한다. 다음은 Git 추적 가능성·셸 구문 검사와 관련 안내만의 게시다. Neuron에는 접속하지 않는다.
- 검사 통과: runtimelog의 README/metrics.jsonl/SLURM out/environment.json은 추적 가능하며 .env/pt/safetensors의 기존 제외는 유지된다. 명령표 bash23블록 및 내장 Python 구문 통과. 게시 대상은 runtimelog/README.md,neuron/command.md,neuron/README.md3개뿐이다. runtimelog 제외 규칙은 원래 미커밋 변경이었으므로 제거 후 GitHub에도 별도 제외 규칙이 없는 상태를 유지한다. 기타 기존 .gitignore 변경은 게시하지 않는다.
- 최종 게시 전 검사: 안내/명령표/task 편집기 오류 없음,staged diff --check 통과,문서3파일만 스테이징됨을 확인했다. .gitignore의 기존 chat.json 변경은 유지하되 스테이징하지 않았다. 다음은 문서 commit/push 및 원격 SHA 확인이다.
- 게시 완료: commit39ab9e73df1d4dc111dd847ad7a523b73099ad9c로 문서3파일을 GitHub main에 push했고 ls-remote SHA 일치를 확인했다. 실제 결과 로그는 아직 수령하지 않았다. 정본 전달 경로는 Neuron 사용자 push→GitHub→로컬 pull이며,에이전트의 Neuron 접속·제출은 수행하지 않았다. 다음은 사용자 업로드 후 해당 결과 수신·분석이다.

## 2026-10-29 / 참조 프로젝트 오기록 회수

- 사용자 정정: phdq3는 참조 전용이며 이번 작업의 코드/설정/문서/로그는 모두 blt-cache에 둔다. 이전의 '소유 프로젝트에 구현하고 export' 해석은 잘못이었다. 앞으로 참조 프로젝트에는 기록하지 않는다. 기존 사용자 command.md 수정19줄은 건드리지 않는다.
- 잘못 추가한 entropy_data.py/entropy_train.py/test_hf_entropy.py/korean_entropy_preparation.json4개가 neuron/runtime 보존본과 바이트 단위로 같음을 cmp로 확인했다. KOREAN_ENTROPY.md는 docs/archive/KOREAN_ENTROPY_20261029.md로 원문 보존한다. 이 archive는 과거 잘못 배치한 경로의 기록이며 현재 실행 안내가 아니다. 다음은 archive 동일성 확인 후 로컬 phdq3의 제가 만든5파일과 덧붙인 로그만 회수하는 것이다.

### 참조 프로젝트에 잘못 기록했던 내용의 이관본

아래는 당시의 기록을 보존한 것이며 '소유 프로젝트' 표기는 위 정정으로 폐기한다.

- blt-cache 사용자 요청으로 모두의 말뭉치+FineWeb2 기반 한국어 교사 CPT 준비를 소유 프로젝트에 추가한다. 기존 GEC train.py와 제공 split/가중치/환경은 변경하지 않는다. itcerdo 작업 허용 범위는 2026-10-19 사용자 결정으로 확대됐으며 과거 추론 전용 제한보다 우선한다. 이번 요청은 준비이며 실제 pretrained CPT를 시작하지 않는다.
- entropy_data.py와 합성3검사가 바이트 보존·단일 label shift·문서별 chunk reset·해시/최종평가 보호를 통과했다. 별도 entropy_train.py 및 plan/korean_entropy_preparation.json을 추가했고 training_authorized=false/실행 예산 null이다. 다음은 합성 optimizer/체크포인트 재개,원격 strict load/preflight와 수신 경로 설치 검증이다.
- itcerdo에 한국어 원문 수신/약정/manifest/prepared 및 별도 출력 경로를 생성하고 신규4파일을 배치했다. CPU 합성5검사가 모두 통과했고(1.663s),optimizer/RNG 저장·복원 후 다음 손실과 가중치는 exact 일치했다. 독립 CE reduction 합산 비교만1e-6 허용오차로 수정했다. 공개 변환본의 패처99,512,064모수를 BF16 strict load했고 실제 학습은 미실행이다. 다음은 안내 문서와 자원·동시실행 게이트 보완이다.
- 저장 전 예산 검사/GPU allocator 상한/checkpoint SHA 검증/기한 확인을 추가했다. 실제 패처의 합성 CPU forward/backward에서129모수 텐서 gradient finite,optimizer0회/저장 없음이다. 최종 준비7개+기존 스케줄3개 총10검사 통과(1.665s). 신규5파일(두 모듈·테스트·설정·KOREAN_ENTROPY.md)의 원격/로컬 SHA256 일치,Python 구문 및 git diff --check 통과다. 준비 보고서는 artifacts/korean_entropy/preparation-20261029.json,수신 경로는 data/korean_cpt/incoming/nikl이다. 실제 데이터/약정·PII/근접 중복·예산 승인 및 GPU Adam/재개·처리량 검사는 미완료이며 실제 CPT는 시작하지 않았다.
- Neuron 사용자 실행 배포 준비: entropy 실행기에 SIGUSR1/SIGTERM 수신 후 step 경계 체크포인트/exit75,validation 미완료 분리를 추가했다. resume identity에 attention/patching/manifest/data_adapter hash 포함. 로컬 신호1검사와 itcerdo entropy8+학습3 총11검사 통과(1.812s),실제 GPU 신호/재개는 미검증이다. blt-cache/neuron/runtime은 이 소유 코드의 파일hash 고정 배포 사본이며 별도 학습 구현/소유권 이전이 아니다. Neuron 접속·제출은 사용자만 수행한다.
- 소유15파일 배포 사본을 itcerdo 독립경로에서 hash/entropy8검사 및 실제 패처99512064모수 BF16 strict load로 검증했다. Neuron guard3/shell 검사도 통과했다. 배포전용 디렉터리는 GitHub esoterikosQ/26-14_CACHE commit a0cfa521a272ac61f19d60bde17674cb2e86fa56에 게시됐고 main SHA 확인 완료다. 소유 프로젝트의 나머지 변경은 커밋/게시하지 않았다. 실제 학습은 미승인·미실행이며 사용자 Neuron preflight와 데이터/예산 확정을 기다린다.

### 회수 실행

-5개 보존본 동일성 확인 후 로컬 phdq3의 제가 만든5파일과 log.md 추가9줄만 제거했다. 기존 command.md의 Git blob hash96a2f6166656881e7b44446cd9e36dd75cb1e5aa를 보존 기준으로 기록했다. 원격 itcerdo의 이전 배치본·자료 경로와 실행 중20GB 작업은 아직 건드리지 않았다. 다음은 로컬 회수 검증 및 blt-cache 내부 실행 경로·유지보수 경계 정정이다.
- 로컬 회수 검증 통과: phdq3/log.md는 HEAD와 동일,기존 command.md hash 불변,제5파일 제거,blt-cache 런타임15파일 hash 검증 통과. 유지보수 위치를 neuron/runtime으로 정정하고 외부 export를 없앴다. Neuron ROOT/출력/미승인 설정은 /scratch/r984a02/blt-cache로 변경했으며 옛 참조 root 제출·출력을 거부하는 회귀를 추가했다. AGENTS에도 참조 전용 경계를 기록했다. 다음은 guard 검사와 런타임 manifest 갱신이다.
- 새 경계 검사 통과: guard4(0.008s),manifest15파일 refresh/verify,bash -n,독립 runtime entropy7통과/optimizer1개 Torch 부재 skip(0.013s). 계산 코드는 변경하지 않았다. Neuron README/command의 옛 쓰기 root 일괄 치환 후 양쪽 shell 구문과 옛 root 부재도 확인했다.
- 루트 command.md에 올바른 문서/코드 위치를 모으고 현재 인계·준비 계약·task를 참조 전용으로 정정했다. 예전 runtime commit의 잘못된 root를 새 실행에서 사용하지 않도록 안내했고 새 데이터/가중치 경로가 자동 준비됐다고 주장하지 않는다. 다음은 문서/CLI/manifest 일치와 새 runtime의 편집기 진단 확인이다. 원격 기존 배치본과 실제 데이터는 변경하지 않는다.
- 최종 경계 검사 통과: 양쪽 명령 안내의 shell/내장 Python 구문,옛 Neuron 쓰기 root 부재,설정2개의 blt-cache 경로/승인 false,readiness의 참조 전용 계약,manifest15파일 및 git diff --check. 참조 log.md 복원과 기존 사용자 command.md 보존도 재확인했다. 새 guard/실행 shell/AGENTS/루트 안내 편집기 오류 없음. archive에는 현재 실행 안내가 아니라는 머리말을 붙여 원문 본문과 구분했다. 다음은 새 안내·배포 수정 파일만의 GitHub 게시다.
- 게시 전 확인: 이번 정리 관련11파일만 staged,staged diff --check 통과,GitHub fetch 후 HEAD...origin/main ahead0/behind0. 다른 기존 실험 변경·참조 프로젝트는 커밋하지 않는다. 다음은 일반 commit/push와 원격 SHA 확인이다.
- 게시 완료: 정리본 commit0dd953189005c524847fda2f879bfcd8af376132를26-14_CACHE main에 push하고 ls-remote 일치를 확인했다. 로컬 phdq3 확인 대상에는 기존 사용자 command.md 수정만 남고 제5파일/추가 로그는 없다. 이제 루트 command.md가 시작 안내이고 참조 프로젝트 export 기능은 제거됐다. guard4/로컬 entropy7통과·Torch1skip이며 실제 Neuron/GPU 실행은 하지 않았다. 원격 기존 배치본·자료 경로와 실행 중20GB는 그대로 보존했다.
- 최종 기록 검증 통과: readiness JSON 파싱,git diff --check,게시한 AGENTS/루트 안내/neuron/archive의 미커밋 변경 없음,참조 log.md HEAD 일치와 기존 사용자 command.md hash 불변,상태 JSON/task/HANDOFF 편집기 오류 없음. 이번 로컬 회수와 향후 기록 경계 정리는 완료했으며 원격 기존 파일 이동·GPU 재검증은 수행하지 않았다.

## 2026-10-29 / Neuron 제출 위치와 프로젝트 위치 분리

- 사용자 확인 조건: sbatch는 /scratch/r984a02에서 제출한다. 스크립트가 하위 프로젝트 디렉터리에 있다는 사실과 제출 cwd는 별개다. 로컬 참조 common의 프로젝트-root 제출 검사를 실제 운영 조건으로 가정한 것은 에이전트의 오류다. Neuron에서 확인한 사실로 주장하지 않는다.
- blt-cache의 Python/shell guard에 SUBMIT_ROOT=/scratch/r984a02를 분리하고 ROOT=/scratch/r984a02/blt-cache는 데이터·출력 위치로 유지했다. stdout/stderr를 프로젝트 절대경로로 지정해 제출 폴더로 흩어지지 않게 했다. 부모에서 제출 시 환경 준비 단계로 진행하고 두 프로젝트 하위 폴더 제출은 거부하는 로컬 shell/Python 회귀를 추가했다. 참조 프로젝트·첨부 자격증명은 변경/사용/복사하지 않는다. 다음은 집중 검사와 사용자 명령표 정정이다.
- 집중 검사 결과: macOS Python3.11 unittest discover -s neuron -p test_bundle.py의5개 통과(0.023s), bash -n 통과. 부모 제출은 conda 준비 단계에 도달하고 프로젝트/참조 하위 폴더는 그 전에 거부됨을 로컬에서 검사했다. Neuron 접속·제출·실제 conda/GPU 실행은 하지 않았다.
- 명령표 정정: 코드 clone 위치를 /scratch/r984a02/blt-cache로 명시하고 제출 cwd와 runtime cwd를 구분했다. 로그 전송용 clone은 별도 /scratch/r984a02/blt-cache-logs로 명시했다. 기존 홈 clone/실행 중 job의 자동 이동은 하지 않으며 자료·가중치는 Git 제외 경로로만 관리한다. 반복 경로 치환 후 문서 bash 구문 검사를 통과했으며 다음은 완성 명령의 cwd/로그 경로 대조와 게시다.
- 완성 명령 검사 통과: 문서25개 bash 블록,내장 Python 구문,9개 sbatch의 부모 cwd/절대 스크립트,stdout/stderr 절대경로 일치 및 git diff --check. staged 변경 없음과 기존 다수 미커밋 실험 변경을 확인했다. 게시 대상은 루트 command.md와 neuron의 이번 wrapper/guard/test/명령 안내6파일로 한정하고 기존 미커밋 실험·runtime-manifest는 포함하지 않는다. 다음은 편집기 진단과 선별 commit/push다.
- 게시 완료: 편집기8파일 오류 없음,6파일만 commit3fb7eab6af59773fcf72f99be31338cd50b9084e로 push했고 ls-remote origin refs/heads/main의 같은 SHA를 확인했다. 기존 미커밋 실험과 runtime-manifest는 포함하지 않았다. task/HANDOFF/readiness와 이 진행 로그는 로컬 최신 상태로 갱신했다. 남은 작업은 사용자의 Neuron 실제 preflight 및 검토한 runtimelog 전달이다. 에이전트의 Neuron 접속·전송·제출·GPU 실행은 없었다.

## 2026-10-29 / Neuron 명령표 상대경로 정리

- 사용자 요청에 따라 neuron/command.md 전체를 blt-cache cwd 기준 상대경로로 정리했다. ROOT/SUBMIT_ROOT/LOG_REPO 고정 변수를 없애고 제출은 pushd .. / 상대 스크립트 / popd로 원래 위치를 복원한다. 실행기에서 요구하는 BUNDLE/CONFIG/RESUME만 pwd에서 절대경로로 만들고 JSON 내부 자료·출력 경로는 resolve한다. srun 할당 셸도 blt-cache에서 자료를 준비하게 맞췄다.
- 사용자가 전달한 파일 목록에는 phdq3/artifacts/converted/blt-1b-hf-own의 config/model 파일이 있었다. 그 원본을 변경하지 않는 최초 상대경로 복사 절차와 읽기 검사도 추가했다. 파일 목록은 가중치 출처/hash 또는 실제 모델 로딩 검증이 아니며 복사/Neuron 실행을 에이전트가 수행하지 않았다. 다음은 문서 구문과 모의 제출 cwd·설정 경로 검사다.
- 첫 집중 검사 통과:26개 bash 블록 및 내장 Python 구문,명령 블록 내 고정 scratch 경로/ROOT·SUBMIT_ROOT·LOG_REPO 변수 부재,5개 sbatch 모의 실행의 부모 cwd/스크립트 접근/절대 실행 인자/프로젝트 복귀를 검증했다. 명령표와 로그 편집기 오류 없음. 변환기의 plan/output resolve 처리를 확인했으며 다음은 설정 JSON 경로와 srun 모의 이동 검사다.
- 추가 검사 첫 시도는 테스트용 mock 핸들을 조회한 뒤 마지막 호출 인자를 검사해 AssertionError로 중단됐다. 문서 동작 실패가 아닌 검사 코드 오류로 확인했으며 전체 호출 목록에서 배타적 생성 모드를 확인하도록 수정해 같은 검사를 재실행한다. 이 시점의 JSON/srun 추가 검사는 완료로 기록하지 않는다.
- 추가 검사 재실행 통과: 실제 수정은 mock 핸들 조회 전에 호출 인자를 확인하는 순서 변경이었다. 자료/학습 JSON2개를 메모리에서 생성해 배타적 생성·절대경로·승인 false 보존을 검사했고 모의 srun의 부모 cwd/할당 셸 blt-cache 진입/상대 PLAN·PREPARED/PYTHONPATH/종료 후 복귀 및 git diff --check를 통과했다. 파일·가중치 생성과 실제 Slurm 실행은 없었다. 다음은 neuron/command.md만 선별 게시하며 다른 기존 변경은 포함하지 않는다.
- 게시 완료: neuron/command.md 한 파일만 commita5e08daca7b7f43c6f91ca4b0cd0c504e84a75ee로 push하고 원격 main SHA 일치를 확인했다. 편집기 명령표/task/log3파일 오류 없음,staged diff --check 통과. 이번 검증은 로컬 모의 실행이며 실제 Neuron 제출/자료 준비/모델 복사를 확인한 결과가 아니다. 사용자 실행은 새 명령표 기준으로 진행하며 코드·manifest·참조 프로젝트·기존 실험 변경은 게시에 포함하지 않았다.

## 2026-10-29 / 사용자 Neuron 환경 검사 로그 수신

- GitHub main ea3b013을 pull --ff-only로 수신했다. 변경은 runtimelog/entropy-953179.out(58줄)과 빈 .err 두 파일뿐이며 기존 로컬 미커밋 변경은 보존했다. 사용자 로그 커밋은 d64b6e4다. 에이전트의 Neuron 접속·제출은 없었다.
- 사용자 실행 Job953179/gpu56,로그 내부 보고 시각2026-10-29T10:47:46.634605+00:00: runtime15파일 무결성 및 SLURM preflight 계약 통과. Python3.11.16,Torch2.11.0+cu128,Transformers5.16.1,CUDA12.8,xformers 없음,H2001GPU capability9.0. 환경 status=pass/errors=[]이며 BLT import/CUDA 가용성/작은 BF16 행렬곱 검사 모두 true다. 실제 pretrained BLT 모델 forward나 optimizer 검증으로 확대하지 않는다.
- preflight의 training_ready=false, dataset=null은 미승인 template의 예상 결과다. blocker7개는 training_authorized와 양의 예산5개(max_steps/max_train_bytes/max_seconds/max_run_bytes/max_gpu_memory_bytes),dataset_manifest 누락이다. stderr는 비었지만 sacct State/ExitCode는 전달되지 않아 스케줄러 최종 상태는 별도 미확인이다. 다음은 수신 JSON 필드 대조 후 사용자 자료/권리/분할·예산 준비이며 현재 학습 제출은 승인되지 않았다.
- 수신 결과 검증 완료: stdout의 환경/preflight JSON2개를 표준 JSON decoder로 파싱해 버전·장치1개·CUDA/BF16/import·status/errors·blocker7개·dataset null과 대조했고 stderr0바이트 및 git diff --check도 통과했다. 원본 로그는 변경하지 않았다. 환경 점검 통과만 채택하며 학습 준비 게이트와 모델 로딩·실제 optimizer 검사는 미완료로 유지한다.

## 2026-10-29 / itcerdo 영어20GB 재시도 진행 확인

- 사용자 요청으로 ssh BatchMode 읽기 전용 상태 점검을 수행했다. 원격 date 관측12:30:30 UTC,run en-patcher-bg20gb-nested-20261029-02/tmux blt-bg20gb-nested-20261029-02 및 부모PID954687/prepare PID954705가 살아 있었다. 시작 후 약3시간57분이며 아직 prepare(자료 준비·중복 제거) 단계다. 계수 적합 fit 단계에 도달했다고 보고하지 않는다.
- 최신 heartbeat12:30:34 UTC: checks10360,scratch_bytes45683705114(약42.55GiB),peak_host_rss_bytes315695104(약301MiB). 12:30:03/18/34의 checks10340/10350/10360 및 scratch 증가로 진척을 확인했다. launch.log tail에는 출력/오류가 없었다. 프로세스 현재 RSS291692KiB,평균 CPU26.3%이며 디스크 여유286GiB(df -h),주소공간 hard/soft48GiB 유지다. 누적 write_bytes 약857GB는 SQLite journal 등을 포함한 I/O 누적치이며 현재 저장량으로 해석하지 않는다.
- 실행 plan의 redistribute_remaining_v2/추가 shard manifest/parent block 재사용/신규 LMDB 없음/100GiB 신규 산출물 및 최소100GiB 여유 한도는 유지됐다. 관측 시점 오류·중단 징후는 없으나 전체20GB 확보·build/fit/비교 완료 및 완료율/종료 예상 시각은 아직 확인할 수 없다. 기존 실패01/실행 중02/환경·설정은 변경하거나 재시작하지 않았다. 다음은 현재 실행 유지 후 prepare 완료와 후속 단계 보고서 확인이다.

## 2026-10-30 / itcerdo 영어20GB 재시도 재확인

- 읽기 전용 SSH 관측의 원격 시각은2026-10-29 21:19:19 UTC(한국시간10월30일06:19)다. run02/tmux와 부모PID954687,build PID956025가 살아 있고 전체 경과12시간45분/build약7시간,build CPU99.6%/현재 RSS5025488KiB다. 이전 prepare 관측에서 build 단계로 진행했다. 프로세스·계획·기존 파일을 변경/재시작하지 않았다.
- data_preparation.json의 status=prepared,finished_at=2026-10-29T14:19:05+00:00,elapsed20712.16초. 문서4891146개/UTF8바이트20000001834,원래 background 문서2752379개 보존,candidate5669458개,redistribute_remaining_v2 적용이다. 준비 단계 최대 RSS526000128바이트,완료 당시 SQLite scratch58569035776바이트이며 현재 디렉터리에 dedup.sqlite는 없다. 이는 준비 완료 보고서의 수치이며 이번 점검에서 원문/hash 전체를 재검증하지 않았다.
- 최신 완료 블록은 index609(총610개,기존400개 재사용 포함),21:17:39 UTC/누적문서3613153개/UTF8바이트15251601186/최대 RSS5205266432바이트(약4.85GiB). 전체20GB 대비76.26%,추가분 약10GB 대비52.5% 구축이다. 21:11~21:17 사이 약119초마다 블록이 증가했으며 멈춤·오류 징후는 없다. du -sh 실행 전체42GiB/신규 background_blocks22GiB,df 여유287GiB로 관측상100GiB 신규 산출물·최소100GiB 여유 한도 안이다.
- fit 및 최종 비교는 아직 미착수다. 최근 블록 속도가 유지된다면 남은 구축만 대략6시간대지만 문서 분포/I/O에 따라 달라지며 적합·비교 시간은 포함하지 않는다. 다음은 build 완료 및 fit 시작/보고서 확인이며 결과 채택·규칙 변경은 하지 않는다.

## 2026-10-30 / Neuron 직접 입력 명령과 ZIP 준비 안내

- 사용자는 국어원 ZIP 전송 완료 및 이용 처리는 교환 시스템에서 완료했다고 보고했다. 별도 관련 파일 수집/검토 명령은 요청대로 neuron/command.md에서 제거했다. 원본 ZIP별 새 추출 폴더와 unzip -l/-n 명령,큰 해제의 할당 셸 실행,기존 split 보존·형식 확인 절차를 추가했다. 실제 ZIP 파일명/schema/압축 크기는 아직 전달받지 않았으므로 CORPUS/REPLACE 경로는 명시적 예시다.
- Git/sbatch/squeue/sacct/파일 조회/복사·변환·설정 생성에서 사전 shell 변수를 없앴다. sbatch 필수 BUNDLE/CONFIG/MODE/RESUME는 인자에 직접 적고 job 번호도 직접 적는다. Git은 neuron+runtimelog sparse와 현재 clone의 선별 commit/fetch/merge/HEAD:main push로 통일해 기존 sparse 제외·detached HEAD 로컬 main 혼동을 줄였다. 실행 중 clone 갱신 금지는 유지했다. 실행 코드/승인 게이트는 이번 명령표 요청에서 변경하지 않았다.
- 첫 수정 후31개 bash/내장 Python 구문은 통과했으나 설명 문장에 비한국어 문자 혼입을 검사에서 발견했다. 같은 문장을 한국어로 수정하고 동일31개 구문/문자 검사를 통과했다. 이어 로그 전달 부분까지 직접 명령으로 정리했으며 다음은 완성 문서의 무변수/요청 항목 부재/제출 cwd·ZIP 비덮어쓰기 검증이다. 에이전트의 Neuron 접속·제출·실제 압축 해제는 없다.

- 완성 문서31개 bash 블록/내장 Python 구문,사전 shell 변수·별도 이용 절차 부재,5개 sbatch의 부모 cwd/직접 경로를 확인했다. 임시 합성 ZIP으로 문서의 unzip 명령을 실행해 추출 성공·기존 목적지 재실행 거부·기존 파일 보존을 확인했다. 실제 자료·Neuron 검사가 아니다.
- 추가 점검에서 명령표만 수정하면 entropy_data의 license_approved=false 생성 및 entropy_train preflight 게이트가 그대로 남아 실행을 막는 것을 확인했다. 이용 처리는 교환 시스템에서 완료했다는 사용자 지시에 맞춰 해당 생성/검사만 제거하고 개인정보·분할·예산 검사를 유지하는 최소 수정으로 연결했다. 먼저 기존 테스트에 필드 부재/나머지2개 검토 필수 회귀검사를 추가했고9개 중 해당2개가 예상 실패,optimizer1개는 Torch 부재 skip였다. 이어 생산자·소비자를 수정했으며 다음은 동일 검사 재실행과 고정 runtime hash 갱신이다. 앞의 실행 코드 미변경 기록은 이 추가 발견 전 상태다.

- 동일 entropy9개 재실행 결과8개 통과,optimizer1개는 로컬 Torch 부재 skip였다. 데이터 hash·교차 split 중복/변조·개인정보/분할·미승인 예산 차단은 유지됐다. 할당 bash에서 conda 함수가 상속된다고 가정하지 않도록 conda info의 설치 위치에서 활성화 스크립트를 직접 source하게 보완했다. 이것은 저장 변수가 아닌 필요한 경로 조회다. task.md의 T12 최신 상태도 함께 갱신했다. 다음은 문서 재검증·runtime hash 갱신/guard와 선별 게시다.

- 최종 문서31개 bash/내장 Python 구문 및 저장 shell 변수·제거 요청 절차 부재 재검증을 통과했다. bundle.py refresh로 변경한 runtime3파일 hash만 갱신했고15파일 무결성·배포 guard5개·train_entropy.sh의 bash -n·변경5파일 git diff --check를 통과했다. editor diagnostics4파일 오류없음 및 Pylance Python3파일 syntax 오류없음이다(Pylance 첫 호출은 workspaceRoot 누락으로 거부됐고 명시 후 통과). staged 변경이 없고 참조 프로젝트/기존 실험 변경은 게시 대상에서 제외함을 확인했다. 다음은 neuron/command.md,entropy_data.py,entropy_train.py,test_hf_entropy.py,runtime-manifest.json의5파일만 선별 commit/push다. optimizer/GPU·실제 원문 추출은 미검증이다.

- 관련5파일을 commit272de3eff4278647e50aeae2d8cbe7b920d24d76으로 GitHub main에 게시했고 git ls-remote로 원격 SHA 일치를 확인했다. 기존 다른 실험 변경과 앞선 미게시 이력이 많은 root log.md/task.md는 선별 commit에 포함하지 않고 로컬 기록을 유지했다. 다음은 사용자가 실행 중 job이 없는 상태에서 갱신하고 할당 셸에서 실제 ZIP별 새 폴더에 압축 해제하는 것이다. 실제 파일명·JSON schema·분할·자원 예산 확인 전 학습 승인/실행은 하지 않는다.

## 2026-10-30 / 사용자 제공 국어원 디렉터리 목록과 구조 인계 준비

- 사용자가 Neuron의 data/korean_cpt/incoming/nikl 위치와 ls -lh를 제공했다. 목록에 DIALOGUE2020~2025/DIALOGUE_json/OM_json/SPOKEN_JSON/WRITTEN2025/WRITTEN_json ZIP11개와 대응하는 NIKL 접두사 디렉터리11개가 있다. ZIP 표시 합계4.1G는 추출 원문의 크기나 학습 바이트 수가 아니다. 폴더 존재만 확인했으며 전체 추출 성공·완전성·본문 schema는 아직 미확인이다.
- 소유 entropy_data.py의 입력 계약은 document[].id 및 paragraph[].form 또는 utterance[].form이다. 문서별 첫 대표 JSON의 키/자료형을 받으면 이 계약과 구별할 수 있다는 가설로,사용자가 현재 nikl cwd에서 실행할 읽기 전용 Python 명령을 준비한다. 폴더별 JSON 수·대표 파일명/크기·키/자료형만 출력하며 실제 문자열/본문/화자 값은 출력하지 않는다. 대표 JSON 읽기는32MiB 이하1파일로 제한하고 ZIP 해제·전체 hash·학습·split 변경은 하지 않는다. 다음은 합성 자료에서 본문 비출력 및 두 입력 구조 검증 후 명령을 사용자에게 전달하는 것이다. Neuron 접속은 하지 않았다.

- 안내 명령을 실제 파일 쓰기 없이6개 합성 폴더의 mock 경로/JSON으로 실행했다. paragraph/utterance/sentence 키·자료형 출력,본문/문서 ID/화자 값 비출력,32MiB 초과 파일 및 빈 폴더 건너뛰기,JSON 오류의 종류만 출력하는 동작을 통과했다. 실제 말뭉치 전수 구조 검사나 Neuron 실행 결과가 아니다. 다음은 사용자가 현재 nikl 위치에서 실행한 구조 출력 및 제공 split 구분 유무를 전달하면 변환기 호환 여부를 판단하는 것이다. runtime-manifest.json과 실행 코드/원문은 변경하지 않았다.

## 2026-10-30 / 국어원 대표 JSON 구조 및 미분할 확인

- 사용자가 제공 분할 없음과11폴더별 JSON 개수·대표 파일 구조를 전달했다. JSON 합계136307개(구어9폴더/문어2폴더)이며 대표들의 document[].id 및 utterance[].form/paragraph[].form은 현재 변환기 형식과 맞는다. OM 대표는 JSON1개 안에 문서4개,다른 대표는1개다. 전체 문서 수·전체 schema 일관성·텍스트 바이트 수는 아직 미측정이다. 원문/화자 실제 값은 전달받지 않았다.
- DIALOGUE_v1.2와 SPOKEN_v1.2는 각각25696파일 및 같은 대표명 SARW1800000001.json/24154bytes를 보였다. 중복 가능성의 근거이나 전체 동일성 또는 제거 가능한 수량으로 확정하지 않는다. 기존 entropy_data는 모든 split의 exact 본문 중복을 거부하며 자동 분할·중복 제거는 하지 않으므로 source 이름만 바꿔 해결할 수 없다.
- neuron/command.md에 실제11폴더·개수·대표 형식,원본 직접 경로/재해제 불필요,미분할 원본에서 기존 계획 생성/변환 예시 실행 금지를 반영했다. task.md도 갱신했다. 다음은 문서의 개수 합계·형식 집계·shell 구문 검증이며,실제 자료에서는 문서/중복 관계를 확인한 뒤 비율·시드·보류 평가·중복 처리 규약을 확정해야 한다. 규약/분할·학습을 임의 승인하거나 Neuron에 접속하지 않았다. 실행 코드와 runtime-manifest.json은 변경하지 않았다.

- 로컬 검사에서 표11행/파일 합계136307/utterance9·paragraph2,미분할 원본 변환 금지·중복 미확정 경고,기존31개 bash 및 내장 Python 구문,저장 shell 변수·제거 요청 항목 부재를 통과했다. 새 실제 데이터 검사가 아니라 문서의 수신 정보 일치 확인이다. 이번 변경은 로컬 문서/진행 기록이며 새 GitHub commit/push나 Neuron 동작은 하지 않았다. 다음 단계는 원본 보존 상태의 문서/중복 관계 전수 확인과 분할 규약 확정이다.

## 2026-10-30 / 명시적 국어원 audit·그룹 분할 구현

- 사용자가 DIALOGUE_v1.2는 SPOKEN_v1.2를 착각해 중복 배치한 것이라고 확정하고 직접 제거하기로 했다. 새 입력 목록은 SPOKEN만 포함하는10출처/사용자 보고 JSON110611개로 준비한다. 에이전트가 원격 파일을 삭제하지 않는다.
- 기존 변환기만으로는 자동 그룹 분할이 없으므로 소유 runtime의 별도 opt-in entropy_corpus 모듈을 추가한다. 먼저 기존 테스트 파일에 audit/그룹 연결/정확 중복 대표화/원문 보존/test 격리/재현성/동일 ID 충돌/schema/심볼릭 링크/스냅샷 변조 검사를 추가했다. 첫12개 실행에서 새3개만 모듈 부재로 예상 실패,기존8개 통과·optimizer1개 Torch 부재 skip였다.
- 이어 SQLite 기반 원문·출처 스냅샷 audit와 별도 split 진입점을 구현했다. 동일 문서 ID 또는 NFC+공백 비교용 본문의 연결 성분을 만들고 raw exact 본문만 대표1개로 줄이며 정규화는 출력에 적용하지 않는다. 모든 별칭/원본 위치는 private index에 남긴다. seed/비율은 실행 시 명시하며 test는 학습 manifest의 splits에서 제외한다. 퍼지/부분중복 전수 탐지는 구현 범위가 아니며 검토 승인2개는 false로 유지한다. 다음은 동일 검사 재실행이다. 실제 Neuron 스캔/분할·학습은 미실행이다.

- 동일 entropy12개 재실행에서11개 통과·optimizer1개 Torch 부재 skip였다. 새 기능은125개 합성 문서의 exact 대표123개/연결 그룹121개/최대 그룹3개,재실행 파일 SHA 일치,변조·잘못된 비율·같은 source/ID의 다른 본문·연결 입력 차단을 확인했다. 이어10출처/예상 JSON110611개 카탈로그와 DIALOGUE_v1.2 명시적 제외를 추가하고 예상 파일 수 불일치 중단을 보완했다. runtime allowlist는 새 모듈·카탈로그를 포함한17개로 확장했으며 다음은 동일 slice 검사 후 manifest hash 갱신·배포 검증이다. 실제 입력 데이터 크기·시간/저장 예산 충족 여부는 아직 미측정이다.

- 최종 entropy13개 중12개 통과·optimizer1개 Torch 부재 skip,17파일 runtime hash 갱신/검증 및 배포 guard5개를 통과했다. 명령표는 실제10출처110611JSON/CPU 할당/기본 최소 여유100GiB/audit 검토 후 명시적 비율 split/작은 보고서만 Git 전달로 교체했다. 기존 문맥 불일치로 첫 문서 패치가 거부돼 해당 구간만 읽고 재적용했으며,설명에 섞인 비한국어 단어는 문자 검사에서 발견해 수정했다. 최종33개 bash/내장 Python 구문·카탈로그 집계·저장 shell 변수/별도 제거 요청 절차 부재를 통과했다.
- 별도 Python 프로세스로 CLI audit/split을 공백 포함 임시 경로에서 실행해125개 합성 입력→123개 고유 본문과3개 nonempty split,읽기 전용 SQLite URI,보고서 생성을 확인했다.6대상 editor diagnostics 오류없음 및 Pylance3Python파일 구문 오류없음이다. task.md의 T12도 갱신했다. 다음은 관련6파일의 선별 diff/공백 확인과 GitHub 게시다. 원문과 SQLite는 private이며 Git에 넣지 않는다. 실제 Neuron scan/split/학습이나 자원 측정은 하지 않았다.

- 관련6파일의 diff/공백·기존 staged 변경 부재를 확인하고 commit b2dc5730ce09741531e772d7333e19dbfd030bdc으로 GitHub main에 게시했다. git ls-remote로 원격 SHA 일치를 확인했다. 기존 다른 실험 변경과 앞선 미게시 이력이 많은 task.md/log.md는 선별 commit에서 제외해 로컬 기록을 유지했다. 다음은 사용자가 CPU 할당에서10출처 audit를 실행하고 작은 audit.json만 검토·전달하는 것이다.98/1/1 seed42는 예시이며 audit 검토 후 사용자가 명시적으로 선택할 때만 split한다. 실제 말뭉치의 중복 수/문서·바이트 수/그룹 크기/시간·디스크 사용량은 미측정이고 퍼지·부분중복/PII 검토 승인과 학습 실행은 남았다.

## 2026-10-30 / 자료 준비의 불필요한 CPU 할당 안내 정정

- 사용자가 자료 준비는 별도 CPU 할당 없이 직접 실행하면 된다고 정정했다. 이전 CPU partition/srun/2시간 제한 안내는 코드나 확인된 운영 요구에서 나온 것이 아니라 에이전트의 불필요한 가정이었다. entropy_corpus에는 SLURM/CUDA 의존이나 할당 검사가 없고 이전 합성 CLI 검사도 일반 로컬 프로세스에서 통과했다.
- neuron/command.md의 ZIP 및6절에서 할당 필수 안내·srun·할당 셸 초기화/exit/복귀·할당2시간 언급을 제거했다. 현재 셸의 blt-cache에서 직접 실행하며 이미 활성화된 환경은 재활성화할 필요가 없다. audit/split 인자와 원본 보존/디스크 여유/출력 불변 조건은 유지하고 GPU 학습 job 제출 계약은 변경하지 않았다. 다음은 문서 구문·자료 준비 절의 할당 제거·기존 명령 불변 검사다. 실제 Neuron 명령을 실행하지 않았다.

- 수정 후30개 bash 블록 및 내장 Python 구문,6절의 srun/sbatch/할당 종료/시간 제한 부재,HEAD 대비 audit/split CLI 명령 및7절 이후 GPU 제출 안내 불변을 확인했다. 저장 shell 변수·별도 제거 요청 절차·비한국어 문자 혼입도 없다. 다음은 명령표1파일의 선별 게시이며 실행 코드/runtime hash는 변경하지 않는다.

- 명령표1파일만 commit1fb1de5fd80c1109fed314bb07ba8902d9dd1837로 GitHub main에 게시하고 원격 SHA 일치를 확인했다. 문서/로그/작업 기록 editor diagnostics 오류없음 및 선별 diff 공백 검사를 통과했다. 사용자 정정을 메모리에도 반영했다. 다음은 현재 셸의 blt-cache에서 기존 audit 명령을 직접 실행한 사용자 보고서 수신이다. 에이전트의 Neuron 접속·제출·자료 준비 실행은 없으며 task.md/log.md의 기존 미게시 이력은 선별 commit에 포함하지 않았다.

## 2026-10-30 / 사용자 audit 실패와 form 검사 수정

- 사용자의 현재 셸 audit가 NIKL_DIALOGUE_2020_v1.4/SDRW2000000031.json 문서 위치0에서 Expected nonempty form strings로 중단됐다. 이 compound 검사는 빈 문자열과 누락/비문자열/잘못된 parts를 함께 거부하므로 전달된 traceback만으로 실제 값의 종류는 확정할 수 없다. 기존 entropy_data는 문자열 form을 LF로 연결하며 내부 빈 문자열을 허용한다. 새 audit의 모든 form 비어있음 금지가 과도하다는 가설로 국소 수정한다.
- 먼저 구어·문어 모두 앞뒤 빈 form을 가진125문서 합성 입력의 구분 LF·원본 hash 보존,보고서의 빈 form 개수,split 출력까지 확인하는 회귀검사를 추가했다. 다음은 이 검사로 기존 실패를 재현한 뒤 빈 문자열만 허용하고 누락·비문자열은 위치/자료형만 표시하며 계속 차단하는 것이다. 실제 실패 파일의 원문은 받지 않았고 Neuron 접속·실행·파일 제외는 하지 않았다.

- 새 focused1검사는 기존 line114에서 같은 Expected nonempty form strings로 예상 실패했다. 빈 문자열을 허용하되 삭제·대체하지 않고 원래 LF 연결을 유지하도록 수정했다. 출처별 empty_form_parts 개수를 추가하고,누락/비문자열은 발화/문단 위치와 자료형만,문서 전체가 비거나 공백뿐이면 부분 수·빈 form 수만 표시하며 중단한다. 오류를 피하기 위한 원문 제외/None의 빈 문자열 대체/original_form fallback은 하지 않는다. 잘못된 자료형5종/누락/문서 전체 비어있음·공백 검사도 유지·확장했으며 다음은 동일 focused 검사와 entropy slice 재실행이다.

- 동일 focused1개 통과 및 전체 entropy14개 중13개 통과·optimizer1개 Torch 부재 skip였다. 구어·문어 모두 빈 form 앞뒤 LF와 원본 hash 및 split 출력이 보존됐고,None/int/bool/list/dict/누락 form과 문서 전체 빈 값·공백은 구체적 오류로 계속 차단됐다. 명령표의 audit/split/보고서 복사를 새 nikl-v002에 맞추고 실패 v001 보존·자동 재개 없음·형식별 집계/오류 정책을 기록했다. task.md도 갱신했다. 다음은 문서 구문·경로 연결,17파일 runtime hash 갱신/배포 guard 검증과 선별 게시다. 실제 실패 자료에서 빈 form이 원인이었는지는 재실행 결과로 확인해야 한다.

- 문서30개 bash/내장 Python 구문,직접 실행 유지,audit/split/보고서의 v002 경로 연결을 통과했다.17파일 manifest의 변경2파일 hash만 갱신했고 배포 guard5개·선별 diff 공백·대상5파일 editor diagnostics 및 Pylance Python2파일 구문 검사도 통과했다. 기존 staged 변경은 없고 현재 게시 대상은 코드·테스트·manifest·명령표4파일이다. 다음은 선별 GitHub 게시 후 사용자의 v002 재실행 결과 수신이며 실제 실패 파일의 form 값은 미확인이다.

- 관련4파일을 commit afe260ccf63159243a6c0793fae3c4f9eb740b4b으로 GitHub main에 게시하고 git ls-remote로 원격 SHA 일치를 확인했다. 다른 실험 변경 및 task.md/log.md의 기존 미게시 이력은 선별 commit에 포함하지 않았다. 다음은 사용자가 blt-cache 현재 셸에서 갱신·bundle verify 후 새 nikl-v002 audit를 실행하는 것이다. 실패 v001을 삭제하거나 일부 행/발화를 건너뛰지 않는다. 실제 실패 파일의 값과 전체 audit 성공 여부는 사용자 후속 결과로 확인해야 한다.

## 2026-10-30 / 본문 없는 문서의 명시적 격리 정책

- 사용자의 후속 audit는 마지막 heartbeat87000파일/114244문서 이후 NIKL_SPOKEN_v1.2/SERW1900028016.json 문서0에서 중단됐다. utterance_parts=4/empty_form_parts=4로 이번에는 발화4개가 모두 빈 문자열임이 오류에서 확인됐다. 앞선 내부 빈 form 허용 후 대부분 스캔이 진행됐지만 문서 전체 내용 없음 검사는 여전히 오류로 중단하는 상태다.
- 내용 없는 문서를 원본에서 지우거나 조용히 누락하지 않도록 기본 error는 유지하고,사용자가 명시하는 empty_document_policy=quarantine에서만 원래 LF 본문·출처/ID·위치·사유를 private SQLite에 보존/집계하고 학습 파생 JSONL에서 제외하는 정책을 준비한다. 기본 strict 유지/내용 없는3문서 격리 및 바이트9개 보존/그룹 불변/manifest·report 고지/동일 ID 충돌을 합성 회귀검사로 먼저 추가했다. 다음은 기존 코드에서의 실패 재현이다.
- 기존 audit는 파일별 DB commit은 있지만 검증 가능한 재개 체크포인트나 재개 인터페이스가 없다. 최초 업데이트에서 재개 가능 범위를 확인하겠다고 했으나,이번 국소 수정에서 기존 v002를 임의 이어쓰기/부분 복사하지 않는다. 실패 산출물을 보존하고 새 v003 재스캔이 필요함을 사용자에게 명시한다. 실제 Neuron 원문·DB를 읽거나 변경하지 않았다.

- 새 focused 검사는 기존 API에 empty_document_policy가 없어 예상 TypeError로 실패했다. 이어 기본 error를 유지하는 keyword-only 정책과 CLI 선택 인자를 추가했다. quarantine 모드에서는 내용 없는 본문·원본 위치/hash·사유·부분 수를 별도 SQLite 원장에 저장하고 source별 전체/사용 가능/격리 문서·바이트 수를 분리한다. 빈 본문은 중복 연결/대표 선정에 넣지 않아 무관한 문서를 묶지 않으며 동일 source/ID의 다른 본문은 원장과 기존 records를 함께 검사해 계속 차단한다. split manifest/report에도 정책·격리 개수를 기록한다. 다음은 동일 focused 검사와 기존 entropy slice 재실행이다.

- PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=neuron/runtime /opt/local/bin/python3 -m unittest discover -s neuron/runtime/tests -p test_hf_entropy.py -v에서15개 중14개 통과·optimizer1개 Torch 부재 skip였다. 합성128문서 중3개를 격리 원장에 원본 LF 본문9bytes 그대로 보존하고125개 사용 가능/123개 raw-unique/121그룹 유지·원본 hash 불변·동일 ID 충돌 및 학습 JSONL 비어 있지 않음을 확인했다. 이는 합성 결과이며 실제 NIKL 격리 개수/총량은 미확인이다.
- 명령표의 audit/split/보고서 경로를 v003으로 연결하고 명시적 quarantine 플래그·원장/집계 검토·v001/v002 보존·전체 재스캔 필요를 기록했다. opt-in에서도 누락/None/정수 form과 알 수 없는 정책을 거부하는 회귀를 추가했다. 다음은 같은 entropy slice 재검증 후 runtime hash·배포 guard 및 문서 명령 검증이다.

- 강화 후 같은 entropy15개 중14개 통과·optimizer1개 Torch 부재 skip,neuron/test_bundle.py의 guard5개 통과 및 runtime17파일 hash 검증을 완료했다. bundle refresh는 기존 manifest의 소유/참조 provenance는 유지하고 corpus 모듈과 테스트 hash만 갱신했다. 공백이 있는 임시 경로에서 실제 CLI audit(quarantine)→split도 성공했고,내용 없는4발화의 LF3bytes·격리1문서·manifest 정책/개수 및 train/validation만 학습 split에 포함됨을 확인했다.
- neuron/command.md의 bash30블록·내장 Python1블록 구문,v003 audit/split/보고서 연결 및 편집 한국어의 비의도 CJK 검사 통과. 편집 Python2파일·명령표/task의 editor 진단도 없었다. 전체 실제 NIKL의 scan 완료/격리 총량·실행 시간·저장 사용량은 미검증이고 Neuron 실행/접속/전송은 하지 않았다. 다음은 관련4파일만 diff 확인 후 선별 GitHub 게시이며 기존 log/task의 미게시 이력과 다른 실험 변경은 그대로 보존한다.

- 관련4파일130삽입/22삭제를 commit d2e7a23ceaf7f4821f4432220b1064c72e75b6f0으로 GitHub main에 게시하고 git ls-remote로 원격 SHA 일치를 확인했다. 다른 실험 변경과 log/task의 기존 미게시 이력은 선별 commit에 포함하지 않았다. 다음은 사용자가 blt-cache 현재 셸에서 갱신·bundle verify 후 새 nikl-v003 audit를 quarantine 정책으로 실행하고,집계가 든 audit.json을 검토하는 것이다. v001/v002나 원본은 삭제/변경하지 않으며 실제 전체 완료 및 이후 split·학습은 아직 미실행이다.

## 2026-11-01 / itcerdo 영어20GB 적합 결과 확인 / 완료 보고서 수신

- 사용자 요청으로 ssh -o BatchMode=yes -o ConnectTimeout=15 itcerdo의 읽기 전용 조회를 수행했다. 최초 접속 관측 시각은2026-11-01T08:30:52Z다. /home/itcmaster/projects/blt-cache/runs/en-patcher-bg20gb-nested-20261029-02/run_report.json은 status=completed,prepare/build/fit/compare4단계 artifact/hash,전체 elapsed88913.995334581초를 기록했다. 마지막 조회의 build 진행 중 표시는 과거 상태이며 이번 결과로 정정한다.
- 원격 progress.md는 build 완료2026-10-30T03:40:48Z,fit 완료07:46:44Z,compare/전체 완료09:15:47Z를 기록한다. 배경4891146문서/20000001834UTF8bytes 구축 완료,fit status=validation_gate_failed,compare의 F1 차이+0.0024683645255075826/111문서/quality_gate_passed=false를 확인했다. 이는 보고서 조회이며 아직 세부 지표·대응 통계·고정 artifact 해시를 독립 대조하지 않았다.
- 실행·계수·임계값·환경·원문·산출물을 변경/재실행/삭제하지 않았다. 다음은 run_report에 고정된4개 stage hash 및 부모/계획 identity를 검증하고,fit/report.json과 comparison.json의 실제 수치를 분석해 task 상태에 반영하는 것이다. 파이프라인 완료와 후보 품질 게이트 실패를 구분하고 후보를 자동 채택하지 않는다.

- 최초 해시 검사에서는4개 stage SHA가 통과한 뒤 저장 plan.json의 바이트 hash를 run_report.plan_sha256과 비교해 AssertionError가 났다. 이는 실행 실패가 아니라 확인 코드가 해시 대상을 잘못 가정한 것이다. 소유 run_background_expansion.py가 입력 args.plan의 hash를 기록하고 plan.json은 JSON 재직렬화한다는 구현을 확인했다. 동일 검사를 입력 source/experiments/english_background_20gb_retry.json으로 바로잡아 원본 hash·저장본 JSON 값 동등성·baseline config·4개 stage·고정10GB 부모 build/fit hash 및 비교의 참조 SHA를 모두 통과했다.
- fit은 L-BFGS-B14iteration/스케일된 projected gradient4.38159e-09로 수렴했고 임계값15개 중0.375를 선택했다.10GB→20GB의 F1 0.7853676082457853→0.7878359727712929,precision0.7681686511381394→0.7717153201044865,recall0.8033543577981651→0.804644495412844,entropy MAE0.4511278819663696→0.44609577717204196다. 대응 F1 차이+0.0024683645255075826/95%구간[0.0016393433386237472,0.003274021716170755]/111문서/baseline_replay_matches=true다. F1 0.90 품질 게이트는 false다.
- 적합 단계14753.965초 중 배경 빈도 투영/로딩13545.425초,특징397.814초,계수 최적화 자체1.349초다. 전체88913.995초/24.70시간,build48091.128초/13.36시간이며 최대 RSS는build5485826048bytes/fit4751736832bytes였다. 준비/빈도/적합 보고서 해시를 검증했지만 원문이나 모든 count block을 다시 해싱하거나 적합을 재실행하지 않았다.
- 본문/문서 ID 없이 요약 수치·고정 report SHA·한계를 evidence/english_background_20gb_result_20261101.json에 기록하고 task의20GB 상태/T00·T07·T08 및 우선순위,HANDOFF의 현재20GB 진행 문구를 완료·게이트 미달로 정정했다. 과거 시작/실패 이력은 보존한다. 같은 validation의 임계값 선택 후 대응 기술통계이며 새 heldout/20GB 절제/전체BLT BPB·속도는 미측정이다. 다음은 요약 JSON을 원격 보고서와 값/해시별 대조하고 링크·현재 상태·문자/공백·editor 진단을 검증하는 것이다. 커밋/푸시나 후속 실험은 요청하지 않아 수행하지 않는다.

- 요약 JSON의 모든 지표·계수/수렴·실행시간·RSS·입력 규모·9개 report SHA 및 완료 시각이 실제 원격 원본과 일치하는 검사를 통과했다. 이어 F1/차이 산술과 현재 문서 링크도 통과했으나 편집 한국어의 문자 검사에서 task T07 표에 잘못 들어간 U+3002 문장부호를 발견했다. ASCII 마침표로 바로잡았으며 다음은 같은 문자/산술/링크 검사 재실행이다. 원격 값 검사는 문장부호 수정과 무관하며 결과/실행 파일은 바꾸지 않았다.
- 후속 문자 검사에는 기존 미커밋 이력의 문자도 함께 포함됐다. 이번 새 로그 문장의 비의도 단어도 한국어로 바로잡고,검사 범위를 이번20GB 상태/추가 로그/인계 문단으로 제한한다. 기존 사용자 변경·과거 실행 이력은 수정하지 않는다. 최종 산술·링크·문자/공백·진단 확인 후 결과를 보고하며 후속 실행이나 후보 채택은 하지 않는다.

- 최종 집중 검사에서 요약 JSON의 F1/차이 산술·현재 task/HANDOFF의 결과 링크·이번 편집 문자·파이프라인 완료/품질 게이트 실패 구분과 git diff --check를 통과했다. 근거 JSON/task/HANDOFF/log의 editor 진단도 없었다. 앞서 원격 모든 요약 값과9개 report SHA 대조를 통과한 결과를 그대로 유지했다. 결과는20GB의 소폭 개선/기존0.90 미달이며 새 독립 평가·전체BLT 품질/속도를 주장하지 않는다. 기록만 로컬 갱신했고 원격 원본/실행/환경·기존 변경은 보존했다. 커밋/푸시·추가 실험·후보 채택은 수행하지 않았다. 다음은 사용자에게 결과를 보고하고 후속 결정 전까지 새 실험을 시작하지 않는 것이다.

## 2026-11-01 / 사용자 승인:20GB BLT 비교 및30GB 확대·재적합

- 사용자가20GB 적합 요약을 INTEGRATION에 추가하고,실제 패처 연결 후 다음 바이트 품질·자유 생성·경계/출력 재현 비교 및 문서 반영,이후30GB 확대·재적합을 지시했다. 앞선 추가 실험 미실행 방침은 이 후속 승인으로 변경됐다. 기존 후보/모델/분할·원본·실패 실행을 보존하고 신규 run만 사용한다. phdq3는 읽기 전용이며 Neuron 접근/제출은 하지 않는다.
- 기존 compare_blt_patchers/evaluate_cpp_blt_patcher는 LMDB metadata.source_report_sha256과 적합 background_report_sha256의 일치를 요구한다.20GB 계수에10GB LMDB를 그대로 연결하면 정확한20GB 실험이 아니므로 이 검사를 우회하지 않는다. 먼저 정확한20GB 빈도 조회 저장소를 준비하고 기존 고정333문서/9프롬프트×2시드/모델·환경을 재사용할 계획이다. 표본/시드/임계값 재선택은 하지 않는다.
- 원격 읽기 전용 관측2026-11-01T08:43:25Z에서 디스크268GiB 가용/RAM58GiB available,tmux 서버 없음으로 확인했다. tmux list-sessions의 종료1 때문에 뒤의 LMDB 위치 조회는 실행되지 않았으며 없는 인덱스라고 단정하지 않는다.20GB count block 전체를 조회 가능한 인덱스 준비·30GB 피크 저장 여유를 다음에 확인한다. 아직 원격 실행/소스/환경은 변경하지 않았다.
- INTEGRATION 끝에 검증된20GB 적합 표·대응 차이/한계·수렴·시간/RSS·근거 링크를 추가했다.20GB 전체 모델 비교는 준비 중으로 명시해 기존10GB BPB·생성 표를 새 측정으로 오인하지 않도록 했다. 다음은 이 문서 수치/링크 검증 후 정확한20GB 인덱스·실험 연결과30GB 새 실행 계획의 국소 구현/검증이다.

- INTEGRATION의20GB 표9개 지표·RSS 반올림·근거 링크·신규 한국어 문장 및 git diff --check를 통과했다. 기존 전체10GB LMDB는 runs/en-count-lmdb-full-20261025-01/counts.lmdb이며20GB 전체 인덱스는 목록에 없었다. 기존 빌더·LMDB 조회자 호출18곳을 언어 서버로 확인했고 선택형 keyword 인자로만 부모 완료 인덱스를 신규 출력에 복사해 정확한 prefix 뒤의 블록만 누적하는 경로를 준비한다.
- 기존 count 테스트의 합성3블록 fixture를 재사용해 부모1블록 인덱스에서 확대한 결과의 전체 재구축/메모리 빈도·rollout 일치,부모 data.mdb hash 불변·행/블록 합계와 잘못된 보고서/부분 부모/인자 누락/seed+resume/블록 순서 변경 거부 검사를 추가했다. 다음은 현재 API에서 expected failure 확인 후 최소 opt-in 구현이다. 실측 대규모 변환 시간이나20GB BLT 결과는 아직 없다.

- 로컬 focused 검사는 NumPy 부재로 skip됐다. 기존 itcerdo 환경을 변경하지 않고 신규 runs/en-blt20gb-compare-20261101-01/source/tests에 테스트만 전달해 기존 소스로 재실행했으며 parent_background 미지원 TypeError를 재현했다. 기존 서버 source/부모 DB/실험 산출물은 덮어쓰지 않았다.
- build_lmdb_background에 optional parent_background/parent_report와 CLI 선택 인자를 추가했다. 완료·전체 부모 DB의 source report/manifest·config·정확한 block prefix·행/바이트·변환 중 부모 파일 불변을 확인하고,LMDB read-only copy를 신규 출력에만 만든 뒤 부모 완료 블록 이후부터 누적한다. 복사 전에 기존 디스크 여유/출력 한도를 확인하며 부모 environment는 child mapping 전에 닫는다. 기존 default 변환/재개 동작은 유지하고 seed+resume은 거부한다. 다음은 새 실행 source에 검증본을 배치해 동일 focused 및 기존 LMDB 회귀를 재실행하는 것이다.

- 신규 독립 source에서 LMDB 부모 재사용/기존 재개2검사 통과(0.375s),OPENBLAS8·native C++ 포함 전체60회귀 통과(2.374s)였다. Pylance syntax·관련3파일 editor 진단 오류 없음,변경 API 호출22곳의 signature 호환성도 통과했다. tar 전달의 macOS xattr 경고는 코드 검사의 실패가 아니었으며 다음 전달에는 xattr를 제외한다. 기존 환경/원본 source를 바꾸거나 패키지를 설치하지 않았다.
- 실제 보고서에서20GB 블록800개 중 첫400개가 기존10GB block list와 정확히 같음을 확인했다. 추가 LMDB 입력은5,051,713,997행(전체10,197,855,299행)이므로 단기 모델 검사처럼 취급하지 않는다. canonical 평가 위치는 datasets/en-patcher-20261019-01이며20GB preparation의 original_split_hashes가 기존5split과 일치한다. GPU는5090/32607MiB 중1MiB 사용,모델 Python은 기존 phdq_blt_hf다.
- 30GB 준비의 SQLite documents.payload가 부모 본문 JSON까지 무압축 저장됨을 확인했다.100GiB 새 산출물 한도를 자동 확대하지 않고 새 계획에서만 compress_dedup_payload=true를 쓰는 선택형 zlib payload 저장을 준비한다. 중복 digest/URL/MinHash/bucket·문서 ID/선택 순서는 그대로이며 출력 시 원래 JSON을 복원한다. 기존3표본 dedup fixture에 압축/무압축 JSONL byte/hash·중복·바이트/순서 일치,BLOB 저장/실제 payload 감소·비불리언 거부 회귀를 추가했다. 다음은 기존 API에서 실패 재현 후 생산자/소비자를 함께 수정하는 것이다.

- 새 compressed 회귀는 기존 API에 compress_payload가 없어 expected TypeError로 실패했다. 이어 DiskDeduplicator/expand_to_disk에 explicit boolean opt-in을 추가해 JSON payload만 zlib level1 BLOB으로 저장하고,보호 문서 및 신규 선택 문서의 두 출력 경로에서 UTF-8 JSON을 정확히 복원하도록 연결했다. 새 prepare 계획의 compress_dedup_payload를 전달하고 보고서에 payload_storage 규약을 기록한다. 기본은 기존 무압축이며 중복/서명/순서·원본/출력은 바꾸지 않는다. 다음은 동일 compressed 및 기존 prepare 회귀/전체 검사다.

- 새 압축 경로를 포함해 기존 data 준비12검사 모두 통과(0.904s)했다. 합성3개 타깃의 JSONL bytes/순서·중복·바이트 합계 일치 및 압축 BLOB payload 감소를 확인했다. 실측30GB 전체 저장량이 줄었다고 주장하지 않으며 런타임100GiB 보호는 그대로다.
- 30GB 계획을 en-patcher-bg30gb-nested-20261101-01로 고정했다. 기존20GB800블록/보고서·적합 SHA를 부모로 보존해 새10GB만 구축하고,F1·라벨·격자·BLAS8/기존자원·평가 보호를 유지한다. 기존 고정16shard를 먼저 사용하며 적격/고유 용량 부족 시 원본/실패를 보존하고 새 shard를 명시적으로 고정한 별도 재시도로 처리한다. 추가 수집·자동 한도 확대는 하지 않았다.
- 20GB 비교는 신규 source snapshot의 실행 shell에서 입력/가중치 SHA 확인→선택형 LMDB 확장→전체 next-byte/경계 비교→고정18개 자유 생성 쌍/원래 HF sampling 대조→동일 작업 timing→단계별 완료 SHA 보고서로 고정했다. 기존10GB 생성/품질 수치를20GB 측정으로 재사용하지 않는다. task의 후속 체크박스/계획 링크를 추가했으며 다음은 shell/Python/계획·부모·입력 경로 및 전체 회귀 검증 후20GB 비교와30GB 파이프라인을 별도 tmux에서 시작하는 것이다.

- 30GB 부모/비교 SHA와 target30000000000·명시적 압축/재사용·seed/BLAS8,20GB shell 구문/내장 Python2개 및 quality/generation/timing3단계 인자 검증을 통과했다. 신규 source에 계획·고정 shard catalogue·실행 shell을 전달했고 첫20GB 입력/실제 모델 가중치 preflight도 통과했다. 아직 장기 변환·모델 비교·30GB 실행은 시작하지 않았다.
- 장기 변환의 실패 복구 위험에 맞춰 부모 seed 복사 후 중단/기존 --resume 경로의 전체 빈도·행 합계 일치 및 부모 복사 전 출력 한도 거부 검사도 추가했다. 다음은 동일 LMDB 집중 검사와 최종 전체 회귀·진단 후 소스 snapshot 고정/실행이다. 기존 부모/실패 산출물과 기존 env는 보존한다.

- 부모 seed 중단·재개/출력 한도 포함 LMDB 집중2개(0.358s), 압축 변경 포함 네이티브 전체60개(1.909s)가 통과했다. 변경 Python5파일 편집기 진단도 없다. 30GB 실행기가 새 snapshot을 source로, 고정 work_root를 자료 경로로 사용하며 부모/분석/설정/catalog SHA·48GiB/100GiB 게이트를 통과했다.
- 모델 환경 사전 import는 lmdb 부재로 실패했다. 기존 Torch2.11.0+cu128/Transformers5.16.1은 유지되고 count 환경 lmdb는2.3.0이다. 기존 환경을 수정하지 않고 신규 run의 system-site-packages venv에 lmdb2.3.0만 추가해 모델 단계를 연결한다. 아직 실행 전이며 다음은 해당 환경 import/명령 검증이다.
- 현재 가용268GiB·RAM 약58GiB, 기존 부모 DB37GiB이다. 두 최대100GiB 산출물/48GiB RAM 작업의 동시 peak와 timing 오염을 피하기 위해30GB prepare/build/fit/compare를 먼저 실행하고 종료 후20GB 인덱스/BLT 비교를 순차 실행하도록 결정했다. 기존 작업/자료/환경을 보존하며 최소 가용100GiB와 각 출력100GiB 한도를 늘리지 않는다.

- 신규 run의 model-venv(system-site-packages)에 lmdb2.3.0만 설치하고 실제 비교 runner import와 Torch2.11.0+cu128/Transformers5.16.1/lmdb2.3.0 버전 검사가 통과했다. 수정 shell 구문도 통과했다. 기존 conda/count 환경은 수정하지 않았다. 다음은 snapshot 코드/계획 SHA 기록 후30GB 실행,20GB tmux 사건 대기 등록 및 초기 상태 확인이다.

- UTC09:14:40.158368 source_manifest.json에 신규 snapshot94파일 SHA/환경/순서를 기록하고 tmux blt-bg30gb-nested-20261101-01 및 blt-blt20gb-compare-20261101-01을 생성했다. 서버 progress의 UTC09:14:41에30GB Started/prepare started가 기록됐으며09:15:11 조회에서 runner PID1078327/prepare PID1078343(각 RSS 약149/153MiB),20GB tmux wait PID1078324,가용268GiB를 확인했다. 모델 비교나30GB 적합 완료를 뜻하지 않는다.
- 초기 상태 조회의 rg는 서버 명령 부재로 실패했으나 grep으로 동일 검사를 재실행해 통과했다. 작업 실패가 아니라 조회 도구 문제다.30GB 출력은 runs/en-patcher-bg30gb-nested-20261101-01/progress.md/run_report.json,launch 출력은 runs/en-blt20gb-compare-20261101-01/background30-launch.log이며20GB는30GB 종료 사건 후 launch.log/quality.json/generation.json/timing.json으로 진행한다.
- INTEGRATION·HANDOFF·task에 실제30GB prepare/20GB 대기 상태와 순차 자원 한도·환경·산출물·미측정 한계를 반영했다. 기존10GB 수치를20GB로 바꾸지 않았고20GB Python/C++ 재현은 미측정이다. 다음은 장기 단계의 실제 완료/실패 보고서와 해시를 확인하고20GB 전체 모델/30GB 적합의 측정 수치를 통합 문서에 추가하는 것이다. Git commit/push 및 Neuron 접속/실행은 하지 않았다.

- 새 INTEGRATION/HANDOFF/task/log 구간의 로컬 링크·Korean text·20GB3단계 대기/30GB prepare/미완료 표시·환경/자원 선언과 최종 shell 구문 검사가 통과했다. 현재 요청의 결과 요약/실행 등록은 완료했으나 장기20GB 측정 수치와30GB fit/compare 완료는 남아 있다. 이 한계를 완료 결과와 혼동하지 않도록 문서/응답에 명시한다.

## 2026-11-01 / 사용자 NIKL nikl-v003 audit 완료 보고서 수신

- 사용자가 Neuron 현재 셸에서 출력한 audit.json을 전달했다. 실행 완료 시각은 보고서에 없으므로 임의로 기록하지 않는다. status=complete,10출처110611파일/137855입력 문서/137853사용 가능 문서이며 SPOKEN에서만2문서/5UTF-8bytes를 명시적 quarantine 원장으로 격리했다. 일부 form의 빈 문자열은 오류로 처리하거나 원문에서 제거하지 않았다.
- 고유 정확 본문137716문서,정확 중복137건,137712그룹/그룹 최대 고유2문서,identity_links0/normalized_links141이다. 제외 폴더는 NIKL_DIALOGUE_v1.2이고 code_sha256=b101a696c84b01570da1c61cf5bd340c840162a28de9154e616ef9e1d5c2aa13,catalog_sha256=2cd8cb49225779165174e929a51d0fe1c274882284ad21b945cc237f1ef4ae72,index_sha256=c7f891b47ed2c7db5b5a51237e9c0d35ea220606cb051350213bfe265ed164e4가 보고됐다. 본문/실제 ID/원장/원문은 저장하거나 전송하지 않았다.
- task에 audit 완료/격리 집계 수신을 반영하고 이전 v003 대기/실패 기록은 이력으로 보존했다. 다음은 출처별 합계·보고서 산술과 로컬 code/catalog SHA를 대조한 뒤,사용자가 채택한 그룹 split 비율/seed로 실행하도록 안내하는 것이다. 실제 Neuron DB/index SHA 재계산·split·GPU 학습·PII/퍼지 중복 검토는 수행하지 않았다. 기존98/1/1·seed42는 예시이며 자동 채택하지 않는다.

- 집중 검증에서 출처10개 파일/입력·사용 가능 문서/격리 합계와 각 출처 documents=usable+quarantined,137853-137716=137정확 중복 및137853-137712=141그룹 연결 산술을 통과했다. 입력 본문 합계8348441371UTF-8bytes/7.775GiB이며 원문 audit 규모이지 정확 중복 제거 후 split 바이트나 학습량이 아니다. 로컬 audit 코드와 catalog SHA가 사용자 보고값에 정확히 일치했다. Neuron index SHA는 재계산하지 않았으며 실행 시간/디스크 사용량은 보고서에 없어 미측정이다.
- 다음 단계는 동일 코드/SQLite를 유지하고 사용자가 채택한 비율/seed로 현재 셸에서 split을 실행한 뒤 report.json/manifest의 출처·분할·실제 바이트·quarantine/held_out_test 규약을 확인하는 것이다. 별도 CPU/Slurm 할당을 요구하지 않으며 학습이나 PII/퍼지 중복 검토가 완료됐다고 판단하지 않는다. Git commit/push 및 Neuron 접속/실행은 하지 않았다.
- task/log 두 기록 파일의 최종 편집기 진단 오류가 없음을 확인했다. 사용자에게 audit 완료와 split 미완료를 구분하고 기존 비율 예시를 채택하는 경우의 직접 실행 명령을 안내한다.

## 2026-11-01 / 사용자 NIKL korean-entropy-v001 split 완료 보고서 수신

- 사용자가 nikl-v003 audit에서 validation/test 각1%·seed42로 split을 실행한 출력과 이어진 json.tool 출력을 전달했다. 두 JSON은 CLI 반환 보고서/같은 report.json 표시이며 별도2회 처리의 근거가 아니다. status=complete,전체137716문서/명시적 quarantine2문서가 보고됐다. 완료 시각/실행 시간은 보고서에 없어 임의로 기록하지 않는다.
- train134981문서/8142668796UTF-8bytes/134977그룹,validation1379문서/94232879bytes/1379그룹,test1356문서/80898953bytes/1356그룹이다. 정책은 SHA256(seed:group-min-exact-sha)의 대략적 그룹 비율이며 바이트98/1/1 할당을 의미하지 않는다. manifest_sha256=13ae32044cd30335989c0e6e35b0d7155b3a8cb73a972dd4ad1dcb85f2773f22는 사용자 보고값이고 실제 manifest/JSONL을 재해싱하지 않았다.
- task의 그룹 split을 사용자 실행/완료 보고서 수신으로 갱신했다. 다음은 분할별 출처 합계·전체 문서/그룹과 앞선 audit 고유137716문서/137712그룹의 산술 대조다. 검토 후 작은 report/manifest 기록을 보존하고 개인정보·근접 중복 검토/학습 설정·예산 승인으로 진행한다. Neuron 접속/전송/실행·학습·Git commit/push는 하지 않았고 원문/SQLite/JSONL은 저장하지 않았다.

- 집중 검증에서 각 split의10출처 합계·137716전체 문서·137712전체 그룹이 audit와 일치했다. 출처별 유지 문서는 audit의 usable 이하이며 정확 중복137문서 감소와도 일치한다. 파생 본문 전체8317800628UTF-8bytes,train7.5835GiB/문서98.0140%,validation0.0878GiB/1.0013%,test0.0753GiB/0.9846%다. 보고서 산술은 확인했지만 실제 JSONL 간 그룹 분리/manifest SHA를 독립 재검증한 것은 아니다. audit 본문과 파생 본문 차이30640743bytes에는 정확 중복 및 격리 본문이 포함되며 바이트 목표를 새로 설정하지 않는다.
- 보고서 전달 안내 정정: 기존 neuron/command.md대로 Git runtimelog에는 검토된 audit.json/report.json만 전달하며 manifest는 Neuron에서 검토한다. 위의 report/manifest 기록 문구를 manifest 자동 Git 추가 지시로 사용하지 않는다. task에도 이 범위를 반영했다. 다음은 최종 기록 진단 후 audit/split 완료와 학습·PII/근접 중복 검토 미완료를 구분해 보고하는 것이다.
- 최종 task/log 두 파일의 편집기 진단 오류가 없음을 확인했다. 사용자 보고서와 산술에 따라 NIKL audit/split 완료를 확인하며,실제 데이터 재해싱·품질 검토·학습이 완료됐다는 주장은 하지 않는다.

## 2026-11-01 / 사용자 정정: NIKL과 FineWeb2 통합 준비 구현

- 사용자가 NIKL-only 완료를 전체 자료 준비로 다루지 말고 약속한 FineWeb 확보 코드를 구현하라고 지시했다. 기존 bundle에는 FineWeb2 Parquet 수집 코드가 없음을 확인했다. 고정 FineWeb2 kor_Hang revision/train25/test1 메타데이터 계약은 있지만 실제 다운로드/통합 준비는 누락됐다. NIKL audit/split 원본과 기존 분할·held-out을 보존하고 이 누락을 구현한다.
- 로컬 urllib의 고정 train tree 메타데이터 조회는 TLS 인증서 검증 실패로 중단됐다. 인증서 검증을 끄지 않으며 다른 검증된 HTTP 경로로 메타데이터를 확인한다. 원문 다운로드나 Neuron 접속은 하지 않았다.
- 기존 runtime 테스트에 고정 revision/train shard SHA·공식 test 제외·불완전 hash 거부 검사를 먼저 추가했다. 다음은 미구현 실패를 확인하고 별도 entropy_fineweb 모듈에 다운로드 및 NIKL 분할 보존 통합을 구현하는 것이다. 기존 entropy_corpus 파일은 바꾸지 않아 nikl-v003 code SHA와 원장 재사용을 유지한다. 자료량/저장 한도/혼합 비율을 자동 확정하거나 학습 승인을 변경하지 않는다.

- 첫 FineWeb 검사는 기존 Torch skip 데코레이터의 배치에 걸려 skip됐다. 데코레이터를 원래 optimizer 클래스에 복구해 같은 검사를 다시 실행했고 entropy_fineweb 미구현 ModuleNotFoundError를 재현했다. 사용자 질문에서 FineWeb2 한국어 train 전체를 선택했다. curl의 TLS 검증을 유지한 같은 고정 API 조회에서25shard/105767105257압축bytes와 LFS SHA 메타데이터를 확인했다. 원문은 내려받지 않았다.
- 별도 entropy_fineweb에25개의 고정 train 경로·크기/LFS SHA256/공식 test 제외를 검증하고 catalog JSON을 새 경로에 생성하는 CLI를 추가했다. 다음은 동일 집중 검사 통과 뒤 명시적 디스크 예산의 다운로드/재개·통합 구현이다. 전체 train 선택은 학습 노출량/혼합 비율/학습 승인을 확정하지 않는다.

- catalog 집중 검사가 통과했다. 사용자가 새 산출물 상한10TB를 승인했으며10000000000000decimal bytes로 명시하고 최소 가용100GiB를 별도로 유지한다. 기존 영어 작업 예산/원본/환경은 바꾸지 않는다.
- 전체25shard의 검증된 다운로드/Range 재개·SHA/크기 검사·원본 Parquet 보존·32행 PyArrow batch의 무정규화 UTF-8 gzip JSONL 변환·shard별 완료 SHA/progress/resume identity 및 출력/가용 예산 검사를 추가했다. 빈 본문은 삭제하지 않고 통합 quarantine 입력으로 보존한다. 공식 test는 경로 검사로 거부한다. 다음은 synthetic Range/원본 보존/예산 검사 후 NIKL 분할을 보존하는 통합 준비다. 실제 전체 다운로드·저장/RAM/시간은 아직 측정하지 않았다.

- 다운로드 회귀는 hashlib import 누락으로 처음 실패했으며 import 보완 후 같은 catalog/Range/SHA/원본 보존/예산2검사를 통과했다. 실제 원문 다운로드는 아니다.
- NIKL audit을 read-only backup한 새 SQLite에 FineWeb 본문을 통합하는 경로를 추가했다. 기존 manifest/3split SHA/대표 ID와 원래 그룹 할당을 검증하고 연결된 FineWeb 그룹은 NIKL 역할을 따른다. 서로 다른 보호 split을 연결하면 재배정 없이 실패한다. UTF-8 불변·정확 중복의 NIKL 우선·빈 본문 격리·test 분리·검토 false 및48GiB AS/10TB 산출물/최소 가용100GiB를 유지한다. 다음은 합성25shard에서 NIKL 역할/본문 보존과 test 연결 문서의 누출 방지를 검사하는 것이다.
- 첫 통합 검사는 fixture 최대 산출물100MB가 사전 예약512MiB보다 작아 예산 보호로 실패했다. fixture만1GB로 수정하고 실제 보호 한도는 완화하지 않는다. 새 로그의 비의도 언어 표기도 한국어로 바로잡았다. 다음은 같은 통합 집중 검사 재실행이다.

- NIKL 보호 통합/catalog/Range3집중 검사가 통과했다(0.076s). 원래 NIKL의 모든 대표 문서/역할·원장 SHA,정확/NFC·공백 중복의 test 보호와 빈 문서 격리·held_out_test/검토 false·cross-role bridge 거부를 확인했다. 기존 itcerdo 준비 환경의 PyArrow26.0.0을 확인했다. 새 설치나 기존 장기 작업 source 수정은 하지 않았다.
- 실제 synthetic Parquet의 UTF-8/빈 본문 변환·25shard 중단 후 나머지24shard 재개·완료 gzip SHA 불변/예산 identity 변경 거부 회귀를 추가했다. 다음은 별도 신규 검증 디렉터리에서 기존 PyArrow 환경으로 같은 FineWeb 검사를 실행한 뒤 배포/문서 연결이다. 원문 데이터가 아니라 생성한 합성 Parquet다.

- 독립 runs/ko-fineweb-prep-check-20261101-01에서 기존 PyArrow26.0.0 환경으로 FineWeb4검사를 모두 통과했다(1.554s). 실제 합성 Parquet를32행 reader로 변환했고2번째 다운로드 중단 후 완료 첫 shard SHA를 보존하면서 나머지24개만 재개했다. 기존 장기 source/환경/자료는 수정하지 않았다. 새 모듈/테스트 편집기 진단도 없다.
- bundle allowlist에 새 모듈을 추가하고 명령표6-4·README·준비 문서/HANDOFF/task/준비 JSON에 전체25shard/10TB 및 최소 가용100GiB·AS48GiB,독립 통합 manifest·NIKL 역할 보존·미실행/미승인 한계를 반영했다. 학습 설정 생성 예시는 NIKL-only 대신 통합 manifest를 가리킨다. 다음은 runtime-manifest refresh/guard 및 전체 entropy 회귀·문서 구문/계약/링크 검증이다. 아직 GitHub 게시·Neuron 실제 다운로드/통합은 하지 않았다.

- runtime-manifest를 기계적으로 refresh해18파일 verify를 통과했고 bundle guard5개를 통과했다(0.037s). 로컬 entropy19개는17통과/2환경 skip(0.208s)이었다. 독립 서버의 실제 catalog CLI가 고정25shard/105767105257압축bytes를 조회했으며 원문 다운로드는 하지 않았다. 기존 Torch 환경의 전체 entropy19개는18통과/실제 Parquet1환경 skip(9.577s)였다. 해당 Parquet 회귀는 기존 PyArrow 환경의4집중 검사에서 이미 통과했다.
- 새 직접 shell4블록 구문·링크·신규 Korean text·10TB/다운로드 승인·원문 미수신/학습 false 계약·기존 NIKL entropy_corpus SHA 불변 검사를 통과했다. 변경 Python/JSON4파일 편집기 진단도 없다. 기존 NIKL audit/split은 재실행하지 않고 보존했으며 전체 FineWeb 실제 다운로드/통합 및 저장/RAM/시간 측정은 사용자 실행 대기다.
- Neuron이 받을 실행 코드 전달을 위해 필요한6파일(neuron/bundle.py,runtime-manifest.json,README.md,command.md,runtime/blt_hf/entropy_fineweb.py,runtime/tests/test_hf_entropy.py)의 선별 GitHub 게시 승인 여부를 사용자에게 묻는다. 승인 전 commit/push는 하지 않았고 기존 영어/한국어 미커밋 기록은 이력 그대로 보존한다.

- 사용자가 실행6파일 선별 게시를 승인했다. 기존 staging은 비어 있고 해당5수정+1신규 파일만 게시 대상으로 확인했다. 공백 검사를 통과했으며 현재 HEAD/원격 main은 d2e7a23ceaf7f4821f4432220b1064c72e75b6f0로 같았다. 기존 영어 실험/로그/task/추가 준비 문서·JSON은 게시에 포함하지 않는다.
- 기존 모델 환경에 PyArrow를 설치하지 않도록 명령표에 사용자 실행용 별도 .venv-korean-prep 생성/PyArrow26.0.0 설치와 해당 interpreter를 명시했다. 다음은 수정 shell 구문/venv Git 제외·bundle 검증 후 승인6파일만 commit/push하는 것이다. 환경 설치/Neuron 실행은 여기서 하지 않았다.

- 별도 환경의4shell 블록 검사는 통과했지만 git check-ignore에서 .venv-korean-prep가 제외되지 않아 뒤의 bundle 검증은 실행되지 않았다. 환경을 기존 data/ 제외 경로인 data/korean_cpt/environments/fineweb-pyarrow로 정정했다. 원문/환경의 Git 혼입을 피하며 .gitignore나 기존 환경을 수정하지 않는다. 다음은 동일 shell/환경 제외/bundle 검증 재실행이다.

- 정정된 준비 interpreter의4shell 블록·PyArrow26.0.0/10TB 인자,환경 Git 제외,18파일 bundle verify와 승인 경로 공백 검사를 통과했다. 다음은 사용자 승인6파일만 commit/push하고 게시 commit/원격 main 및 bundle SHA를 확인하는 것이다. 이 log/task·준비 JSON/추가 문서·기존 영어 실험 변경은 게시 대상이 아니다.

- 승인된6파일만 commit28ca0f0381592e1faca30d8a5ca30147b726270a로 게시했다(721추가/7삭제,신규 entropy_fineweb482줄). git push origin HEAD:main이 성공했고 ls-remote의 main이 같은 SHA이며 게시 후 bundle18파일 verify를 통과했다. 기존 index staging은 비어 있었고 --only 경로 제한으로 나머지 미커밋 실험/문서/로그를 포함하지 않았다. 원문·weights·환경·Neuro 작업은 게시/실행하지 않았다.
- task/로컬 준비 JSON에 현재 게시 runtime commit을 갱신했다. 이 상태 갱신과 root log는 이번6파일 게시에 포함되지 않는다. 다음은 사용자가 현재 Neuron blt-cache에서 ff-only 갱신/bundle verify 후 별도 data 준비 환경/PyArrow26.0.0/catalog→전체 download→NIKL 보호 combine을 실행하고 작은 완료 보고서를 전달하는 것이다. 실제105.77GB 압축 원문 다운로드/통합·저장/RAM/시간·혼합 학습 노출량/품질은 아직 미측정이며 학습 승인은 false다.
- 게시 상태를 반영한 로컬 준비 JSON/task/log의 최종 편집기 진단 오류가 없음을 확인했다. 수집/통합 구현과 선별 게시·검증은 완료했고 실제 Neuron 자료 확보·통합은 사용자 실행 대기다. 기존 NIKL 결과와 미완료 FineWeb 단계를 혼동하지 않는다.

## 2026-11-01 / 사용자 Neuron detached HEAD 갱신 실패

- 사용자가 git pull --ff-only && bundle verify를 실행했으며 origin/main d2e7a23→28ca0f0 fetch는 성공했지만 detached HEAD에서 branch/upstream을 결정하지 못해 pull이 중단됐다. && 뒤의 bundle verify는 실행되지 않았다. 실제 HEAD/작업 트리는 이 출력만으로 확인하지 않았다.
- 직전 응답에서 실행 clone의 detached HEAD를 고려하지 않고 인자 없는 pull을 안내한 오류다. 명령표 갱신을 fetch origin→merge --ff-only origin/main→bundle verify로 정정하고 fast-forward 불가/로컬 변경 충돌 시 이력을 보존하며 중단하도록 명시했다. 강제 checkout/reset·임의 merge commit·Neuron 접속/실행은 하지 않는다.
- 다음은 로컬 임시 Git 저장소에서 detached HEAD fast-forward와 기존 변경 보존/분기 이력 거부를 검증한 뒤 사용자에게 이미 fetch된 origin/main의 직접 merge/verify 명령을 안내하는 것이다. 이번 문서/로그 수정은 로컬이며 추가 commit/push는 수행하지 않았다.

- 임시 Git fixture의 detached HEAD에서 merge --ff-only origin/main이 새 커밋으로 갱신하면서 detached 상태와 tracked 로컬 수정 내용을 보존했다. 별도 local commit으로 분기된 이력에서는 실패하고 HEAD/수정 내용을 그대로 유지하는 검사를 통과했다. 실제 사용자 Neuron 작업 트리는 접근하지 않았다. 다음은 현재 프로젝트 폴더에서 이미 fetch된 origin/main을 ff-only merge하고 Runtime verified:18 files를 확인하는 사용자 실행이다.
- 정정한 명령표/task/log 세 파일의 편집기 진단 오류가 없음을 확인했다. 추가 게시나 Neuron 실행 없이 사용자에게 명시적 merge/verify를 안내한다. 실제 갱신 성공 여부는 다음 사용자 출력으로 확인한다.

## 2026-11-01 / 사용자 정정: phdq_blt_hf conda 환경 강제

- 사용자는 프로젝트 환경이 이미 conda phdq_blt_hf로 준비돼 있으며, 별도 환경이 꼭 필요한 경우에도 conda로 통일하도록 명시했다. 이전 FineWeb 준비용 venv 및 영어 비교용 model-venv 안내/생성은 이 환경 정책을 지키지 않은 에이전트 오류다. 과거 실행 기록은 보존하고 이번 정정으로 대체한다.
- AGENTS.md 상단에 모든 Python 자료 준비/다운로드/검사/실험/학습의 기존 phdq_blt_hf 사용, 실행 전 interpreter/환경 확인, venv/virtualenv/uv venv 및 model-venv 금지, 환경 부재 시 임의 Python 우회 금지, 별도 환경의 사전 승인 및 conda 한정 규칙을 추가했다. 기존 환경/작업은 삭제·변경·재시작하지 않는다.
- 다음은 지침 계약을 집중 검증한 뒤 Neuron FineWeb 명령표의 venv 생성/전용 interpreter 안내를 기존 conda 환경 사용으로 정정하는 것이다. Neuron 실행이나 의존성 설치, 기존 작업의 환경 변경, commit/push는 수행하지 않는다.
- 셸 awk 계약 검사에서 기존 phdq_blt_hf 강제, interpreter 확인, venv 금지, 환경 부재 시 중단, 별도 환경 사전 승인, conda 한정의 여섯 규칙을 확인했다. AGENTS.md/log.md 편집기 진단 오류도 없다. 다음은 해당 지침과 충돌하는 FineWeb 실행 안내만 정정한다.
- Neuron 명령표6-4절의 venv 생성, fineweb-pyarrow/bin/python 경로 및 자동 pip install을 제거했다. 기존 phdq_blt_hf 활성화/interpreter·PyArrow 버전 확인 뒤 plain python으로 catalog/download/resume/combine을 실행한다.26.0.0은 합성 검사 버전으로 기록하며 미확인 의존성을 자동 교체하지 않는다. task의 환경 정정 상태도 갱신했다. 다음은 네 bash 블록의 구문 및 conda/경로/예산 계약 검증이다.
- 네 FineWeb bash 블록의 bash -n 구문 검사와 conda 활성화/interpreter 확인, venv·자동 설치 부재, catalog1/download2/combine1,10TB·100GiB·48GiB 예산3곳 및 resume1곳 계약 검사를 통과했다. 수정한 AGENTS.md/명령표/task/log 네 파일의 편집기 진단 오류가 없다. Python/의존성 설치/환경 생성/원격 실행/기존 작업 변경은 없으며 수정은 로컬에만 남겼다. 다음 자료 실행은 사용자가 기존 phdq_blt_hf에서 수행한다.

## 2026-11-01 / 사용자 승인: conda 지침과 Neuron 명령표 게시

- 사용자는 로컬 수정에 그치지 말고 GitHub를 통해 Neuron에서 받을 수 있도록 게시하라고 명시했다. 게시 대상은 이번 환경 정책 AGENTS.md와 Neuron 명령표 neuron/command.md 두 파일로 한정한다. 명령표의 detached HEAD fetch/ff-only 정정도 포함한다.
- 두 파일의 실제 diff가 해당 지침/명령 정정만 포함함을 확인했다. 기존 실험·자료 준비 문서·root task/log 등 다른 미커밋 변경은 보존하고 커밋에 포함하지 않는다. 앞 단계의 지침 계약 및 FineWeb 네 bash 블록 검사는 통과했다. 다음은 선택 경로 공백/런타임 불변 검증, 두 파일 한정 commit/push, 게시 커밋과 원격 main 일치 확인이다. Neuron 접속/전송/실행은 사용자 담당이다.
- 선택 두 파일의 git diff --check를 통과했고 기존 staging이 비어 있음을 확인했다. neuron/runtime·runtime-manifest.json·bundle.py는 HEAD 대비 변경이 없으며 AGENTS.md/명령표/log 편집기 진단 오류도 없다. 다음은 git commit --only 경로 제한과 실제 커밋 파일 목록 두 개 확인 후 force 없이 origin HEAD:main을 push하는 것이다.
- 게시 완료: commit3308e133f853c82120ca5ffd9322236df2a6f07b에 AGENTS.md와 neuron/command.md 두 파일만 포함됐다(42추가/12삭제). git diff-tree 파일 목록이 정확히 두 경로임을 확인한 뒤 git push origin HEAD:main을 수행했고 GitHub main이 동일 SHA임을 ls-remote로 확인했다. 런타임 코드/18파일 manifest·기존 실험·root task/log는 이 커밋에 포함하지 않았다.
- 다음은 사용자가 Neuron의 기존 phdq_blt_hf/project 폴더에서 git fetch origin && git merge --ff-only origin/main && python neuron/bundle.py verify로 갱신하고 정정된 명령표6-4절을 실행하는 것이다. 에이전트는 Neuron 접속/전송/실행·환경 생성/변경을 하지 않았다. 실제 Neuron 갱신/자료 실행 결과는 사용자 확인 대기다.

## 2026-11-01 / 사용자 Neuron FineWeb 초기 준비 확인 성공

- 사용자가 기존 conda phdq_blt_hf에서 command -v python,PyArrow import/버전 출력,bundle verify,catalog CLI를 연속 실행한 출력을 전달했다. interpreter는 /home01/r984a02/.conda/envs/phdq_blt_hf/bin/python,PyArrow26.0.0,Runtime verified:18 files다. 환경·의존성 import 및 bundle 파일 무결성 확인은 성공했다. Git HEAD/merge 출력은 없으므로 특정 문서 게시 commit으로의 갱신을 별도로 확정하지 않는다.
- catalog는 repository HuggingFaceFW/fineweb-2,revision af9c13333eb981300149d5ca60a8e9d659b276b9,kor_Hang/train25개,압축105767105257bytes이며 각 파일 경로/크기/SHA256이 출력됐다. 공식 test는 reserved_official_test로 보류되고 pii_review_approved=false다. 고정 메타데이터 확보 단계의 성공으로 기록하며 실제 원본 파일 SHA 검사 완료라고 해석하지 않는다.
- 제공 명령/출력에는 Parquet 다운로드·JSONL 변환·NIKL 통합이나 단위 테스트/모델 GPU 연산 검사가 없다. 따라서 초기 준비 확인만 완료로 task를 갱신했다. 다음은 사용자가 같은 환경/프로젝트 폴더에서 명령표6-4절의 download를 실행하고 report.json의 complete/25shard 및 실제 자원 결과를 확인하는 것이다. 에이전트의 Neuron 실행·환경 변경·신규 게시는 없다.

## 2026-11-02 / itcerdo 30GB 확대 실패 및 20GB 비교 진행 조회

- 사용자 요청에 따라 ssh itcerdo에서 UTC00:11:34~00:11:46의 tmux/프로세스/보고서/최근 로그/자원을 읽기 전용 조회했다. Neuron 접속·Python 실행·작업 중단/재시작·환경 또는 frozen source 수정은 하지 않았다.
- runs/en-patcher-bg30gb-nested-20261101-01/run_report.json은 status=failed,stages=[],elapsed_seconds=18887.15618485678이다. 보고서 mtime은2026-11-01 UTC14:29:28이며 background30-launch.log의 직접 오류는 ValueError: Not enough deduplicated text:29999746734bytes,need30000000000이다. 목표보다253266bytes 부족해 prepare가 실패했고 build/fit/compare 결과는 없다. 이는 OOM 증거가 아니며 실패 자료는 보존했다. 구체적인 후보 부족 원인/수정 방법은 이번 상태 조회에서 진단하지 않았다.
- 30GB 종료 후 en-blt20gb-compare-20261101-01의 build_lmdb_background가 자동 시작돼 PID1079410/경과09:41:30으로 실행 중이었다. 최신 building 로그는481/800블록 완료(부모400재사용,신규81/400완료),source_utf8_bytes=12025582322,output_bytes=43893882880,session_elapsed_seconds=33671.47868656041이다. data.mdb mtime도 현재 조회 시각으로 갱신됐으며 완료 표식은 확인되지 않았다. 전체 블록60.125%와 신규 블록20.25%는 구분하며 블록 크기/처리 시간이 달라 종료 시각을 단순 비례 추정하지 않는다.
- GPU는 RTX5090 사용률0%/1MiB로 quality/generation/timing 전 단계다. 프로세스 RSS41340116KiB(약39.4GiB),디스크 여유157GiB,시스템 available58GiB이며 LMDB의 file-backed RSS와 가용 메모리를 구분한다. 품질/생성/속도 측정 결과는 아직 없다.
- 과거 시작한20GB 프로세스가 기존 .venv/bin/python을 사용하고 frozen 후속 스크립트에 model-venv 경로가 남아 있음을 확인했다. 사용자 conda 정정 이전 설정이며 이번 요청은 상태 조회이므로 기존 작업을 중단/이동/의존성 변경하지 않았다. 새 실행은 AGENTS.md의 기존 conda phdq_blt_hf 정책을 따라야 한다. task의 오래된 prepare 실행 중/비교 대기 상태를 정정했다. 다음은20GB 인덱스 완료와 후속 결과 확인,30GB 부족 원인의 별도 진단/승인된 재시도 검토다.
- 부족량253266bytes,전체481/800=60.125%,신규81/400=20.25%,출력40.88GiB/RSS39.43GiB를 awk로 검산했고 task/log 편집기 진단 오류가 없음을 확인했다. 이번 조회는2026-11-02 KST09:11시점의 관측이며 이후 완료 여부/남은 시간은 확정하지 않는다. 상태 기록은 로컬에 보존했고 추가 commit/push나 원격 변경은 하지 않았다.

## 2026-11-02 / 30GB 후보량 부족 원인 분석 및 수정 준비

- 실제 progress.md의 Shard sampled12건 모두 shortfall_bytes=0이고 후보 합계19999997728bytes다. 고정 후보 범위가 소진됐다는 증거가 아니라 중복 제거 전 약20GB quota를 채워 멈춘 뒤,고유 추가량이 목표보다253266bytes 부족한 것이다. 이전 상태 설명의16shard는 기존 전체 목록과 이번 선택12개를 혼동한 표현이므로 정정한다. 원문 자체의 전체 고유 용량 부족은 확인하지 않았다.
- prepare_disk의 quota=ceil(2*remaining/shards)와 sample_shards가 보호 부모/다른 split 중복도 원문 quota로 세는 반면 expand_to_disk는 나중에 이를 제외한다는 경로를 확인했다. 수정 가설은 기존 기본 정책을 보존하면서 opt-in retained_unique_v3에서 실제 중복 제거 후 고유 추가 bytes를 읽기 중 피드백해 quota를 채우는 것이다. 고정 shard 실제 소진 시에는 여전히 실패해야 하며 목표/중복 기준/분할·자원 예산을 완화하지 않는다.
- conda env list 및 interpreter 경로를 확인한 뒤 기존 phdq_blt_hf로 의존성 존재 여부만 검사했다. numpy는 있지만 datasketch/pyarrow/lmdb는 없다. 설치·venv 우회는 하지 않는다. 순수 샘플러 검사를 위해 데이터 의존성 import를 prepare_disk 내부로 옮기고 기존 테스트 파일에 고유량 기반/보호 중복/진짜 소진 회귀를 추가했다. 다음은 별도 소형 검증 사본에서 기존 conda로 실패 재현이다. 실행 중20GB snapshot/환경과 실패30GB 자료는 변경하지 않는다.
- 별도 runs/en-bg30gb-fix-validation-20261102-01 사본에서 conda phdq_blt_hf로 CandidateSamplingTests3개를 실행했다. 기존 재분배 검사는 통과했고 신규2개는 retained_bytes 인자 부재로 예상대로 실패했다. Pylance는 sample_shards9호출 중 신규2곳만 비호환,expand_to_disk11호출은 기존 시그니처 호환으로 확인했다.
- 선택형 retained_unique_v3 및 채택된 후보 bytes 피드백을 연결했다. 부모/보호 split/후보 간 중복은 고유 quota로 세지 않고,전체 고정 shard 소진 시 명시적 부족 오류를 유지한다. 기존 정책과 중복 판정/출력 선택/예산/실패 자료 보존 규칙은 유지하며 원문2배 제한은 새 정책에만 적용하지 않는다. 다음은 같은 conda/별도 사본에서 세 샘플러 회귀를 재실행하는 것이다.
- 첫 수정 후 검사에서 legacy 예시의 고유 추가량 예상값이 실제0bytes와 달랐고,소진 fixture가 close 없는 list_iterator여서 contextlib.closing 계약을 지키지 못했다. 테스트의 기대값/reader generator만 정정했다. 이는 데이터 경로 결함 증거가 아니며 동일3검사를 즉시 재실행한다.
- 정정 후 CandidateSamplingTests3개를 기존 conda에서 재실행해 모두 통과했다. Pylance 변경 후 sample_shards10호출/expand_to_disk11호출이 모두 호환되고 수정 Python3파일 편집기 진단 오류가 없다. 실제 고정 목록이12개임도 로컬 source catalog와 대조했다.
- 결정성/UTF-8 바이트·부족분 재분배 회귀와 실제 SQLite/Parquet 경로의 반복 출력/보호 split/목표량 회귀를 기존 테스트에 추가했다. fresh run02용 english_background_30gb_retry.json을 별도로 준비하고 실패 run01/30GB 목표/부모/라벨/자원 예산은 유지했다. INTEGRATION/task에 원인·수정·통합검사 차단과20GB 완료 후 재실행 조건을 기록했다. 다음은 순수4회귀/계획 identity/문법 검증이며 전체 데이터 의존성 검사는 승인 없이는 실행하지 않는다.
- 동일 검증 사본/기존 conda phdq_blt_hf에서 샘플러4개 모두 통과했다. 실제 streaming_prepare 통합1개는 명시적으로 skip됐으며 성공으로 세지 않는다. ast.parse의 Python3파일 문법과 JSON 계획의 목표/부모/report hashes/source/샘플링 seed/기존 제한·새 실행 identity·고정12shard 계약 검사가 통과했다. 수정7파일 편집기 진단 및 추적 파일 공백 검사도 오류가 없다.
- INTEGRATION/task의 최종 검증 상태를 갱신했다. 원인 분석과 선택형 수정/독립 재시도 계획 준비는 완료했으나 SQLite·Parquet 연결 및 실제30GB 수율/자원은 미검증이다. 다음 게이트는 기존 conda에 필요한 데이터 의존성의 승인된 준비 후 통합 회귀,20GB quality/generation/timing 완료 확인이다. 이후 별도로 재실행을 판단한다. 새 환경/의존성 설치·실행 중20GB 수정·30GB 재시작·commit/push는 하지 않았으며 원격에는 소형 검증 사본만 추가했다.

## 2026-11-02 / itcerdo 20GB 비교 후속 진행 조회

- 사용자 요청에 따라 UTC07:02:56(KST16:02:56)에 SSH로 기존20GB 프로세스/최근 로그/보고서 유무/GPU/디스크만 읽기 전용 조회했다. PID1079410의 LMDB 구축이 실행 중이며 경과16:32:52,RSS42776632KiB다. 작업·소스·환경·의존성을 변경하거나 재시작하지 않았다.
- 최신 building 로그는 completed_blocks=548/800,부모400재사용이므로 신규148/400=37%다. 전체68.5%는 부모 재사용을 포함한 수치이며 비교 전체의 진행률이 아니다. 이전 UTC00:11의481블록에서67개 늘었다. source_utf8_bytes=13701081896,output_bytes=47441428480,session_elapsed_seconds=58340.31059794407이고 연속 로그의 input_rows가 증가했다.
- quality.json/generation.json/timing.json/run_report.json은 실행 루트에 아직 없다. GPU0%/1MiB,디스크 여유154GiB이며 모델 품질·생성·속도 단계에 진입한 증거는 없다. 상태를 task에 갱신했고 다음은 인덱스 완료 및 후속 단계 보고서 확인이다. 완료 시각이나 품질 수치를 추정·확정하지 않는다.

## 2026-11-02 / 사용자 FineWeb 재개 Killed 출력 분석

- 사용자가 Neuron glogin01의 기존 conda phdq_blt_hf에서 고정 catalog/full-v001/10TB/최소100GiB/주소공간48GiB와 --resume으로 실행한 로그를 전달했다. shards=24,documents=59940077 뒤 traceback 없이 Killed다. 실행·종료 시각,exit status,실제 RSS,커널/cgroup 기록은 전달되지 않았다. 전체25shard 완료·통합 성공으로 세지 않는다.
- entropy_fineweb.download_corpus의 출력은 완료된 Parquet/변환본 SHA 검증과 shard 보고서 반영 뒤 발생한다. resume에서도 기존 완료 파일마다 같은 출력을 내므로 짧은 시간에24shard를 새로 받은 뜻이 아니며,관측 종료 구간은 다음25번째 shard의 다운로드/검증/변환이다. SHA는1MiB씩 읽고 Parquet는32행 batch지만 행 수 제한이 디코딩 바이트/RSS 상한을 보장하지는 않는다.
- CLI memory-limit-gib는 resource.RLIMIT_AS 주소공간 상한이며 RAM 예약이나 호스트/cgroup 제한 변경이 아니다. 일반적인 할당 실패/디스크 예산 오류와 달리 Killed는 외부 SIGKILL과 부합한다. 메모리/OOM 또는 cgroup 제한은 실행시간과 무관하게 발생할 수 있으나 현재 증거만으로 OOM·공유노드 정책·정확한 native 메모리 피크를 확정하지 않는다.
- 다음 확인은 사용자가 종료 직후 exit status와 /proc/self/cgroup 및 가능한 커널/cgroup OOM 카운터를 전달하는 것이다. 반복 재개/상한 증대/소스 hash 변경/환경 교체를 처방하지 않았다. Neuron에 접속하거나 자료/런타임/bundle/의존성을 변경하지 않았고 task의 미완료 상태만 갱신했다.

## 2026-11-02 / 사용자 FineWeb 전체 다운로드 완료 보고서 확인

- 후속 사용자 출력은 같은 conda/고정 catalog/full-v001/예산/--resume 명령에서25번째 shard까지 처리하고 최종 status=complete를 출력했다. 실행·완료 시각과 실제 RSS/디스크 사용량은 제공되지 않아 추정하지 않는다. 이전 Killed 원인은 여전히 미확정이며 이번 성공이 OOM/정책 가설을 입증하거나 배제하지는 않는다.
- 전달된25개 shard 수치만 Node로 독립 합산해60874355문서/229164863492본문UTF-8 bytes(약229.165GB,213.426GiB)/105767105257원본 Parquet bytes를 확인했다. 마지막 shard는934278문서,각 shard의 contentless_documents는0이다. 이는 정확 중복 제거 후 고유량이나 통합 train 노출량이 아니다. gzip JSONL·보존 중단본을 포함한 총 디스크 사용량은 보고서에 없어 별도다.
- repository/revision/configuration/공식 test 보류가 기존 선택과 일치하며 original_parquet_preserved=true,pii_review_approved=false다. 보고서 code_sha256=2001d15104f8e08846514f1a0b5b4b5a79e5ec2c20ba9c9028c3f884c379b8a3은 로컬 shasum 결과와 정확 일치했다. catalog_sha256=bee8ca492987a5c0a01e26544337e251b6f46f57430d9ce5467559eee3340724 및 Neuron 실파일 hash는 사용자 보고값이며 독립 재검증하지 않았다.
- task에서 다운로드/변환 완료와 통합 대기를 분리했다. 다음은 기존 코드/원본/NIKL 분할을 보존한 새 korean-entropy-nikl-fineweb-v001 출력의 combine과 보고서 검토다. 통합 완료·PII/근접 중복 승인·학습 준비 완료를 주장하지 않는다. Neuron 접속/실행·코드/bundle/환경 변경·commit/push는 하지 않았다.

## 2026-11-03 KST / itcerdo 20GB 비교 후속 진행 조회

- 사용자 요청에 따라2026-11-02 UTC21:59:15(KST11-03 06:59:15)에 SSH로 기존20GB 프로세스/최근 로그/후속 보고서/GPU/디스크를 읽기 전용 조회했다. PID1079410은 계속 LMDB 구축 중이며 경과31:29:10,CPU25.5%,RSS44458780KiB다. 기존 실행의 .venv interpreter는 이전 환경 정정 전 시작한 작업으로 보존하며 새 Python 실행·환경/소스 변경·재시작은 하지 않았다.
- building 로그의 completed_blocks=689/800이며 부모400재사용을 제외한 신규289/400=72.25%,남은111블록이다. 이전 UTC07:02의548블록보다141개 진행했다. 전체86.125%는 부모 재사용을 포함한 인덱스 블록 비율이지 비교 전체 진행률이 아니다. source_utf8_bytes=17227256097,output_bytes=54359846912,session_elapsed_seconds=112120.09141692426이고 최근 연속 로그에서 input_rows가 증가한다.
- 실행 루트의 quality.json/generation.json/timing.json/run_report.json은 아직 없으며 GPU0%/1MiB,디스크 여유147GiB다. 실제 품질·생성·속도 비교 완료나 진입을 주장하지 않는다. task 상태를 갱신했고 다음은 인덱스 완료와 후속 단계 보고서 확인이다. 완료 시각은 추정하지 않았다.

## 2026-11-04 / itcerdo 20GB 비교 실행 완료 확인

- 사용자 상태 확인 요청으로2026-11-04 UTC02:07:39(KST11:07:39)에 SSH 읽기 전용 조회했다. 기존20GB build_lmdb_background/compare_blt_patchers 프로세스는 검색되지 않았고 launch.log 말미는 completed_timing_cases=8 뒤20GB BLT comparison completed다. GPU0%/1MiB,디스크 여유142GiB이며 작업/소스/환경/의존성을 변경하거나 재시작하지 않았다.
- 실행 루트의 quality.json(14909757bytes),generation.json(827183bytes),timing.json(141873bytes),run_report.json(926bytes)이 모두 생성돼 있다. 작은 최종 run_report를 직접 읽어 run_id=en-blt20gb-compare-20261101-01,status=completed,finished_at_utc=2026-11-03T11:41:38.639289+00:00(KST11-03 20:41:38)을 확인했다. 따라서 직전689/800 인덱스 진행 상태는 과거 이력이며 실제 실행은 이미 완료됐다.
- 최종 보고서는 quality/generation/timing 세 단계 artifact와 SHA를 기록하고 범위를 Frozen20GB count versus OSC neural; compare to frozen10GB evidence separately로 명시한다. 상세 보고서의 실제 문서/프롬프트 커버리지·BPB/경계/생성 동등성/시간 수치 및 artifact SHA는 이번 상태 조회에서 독립 재검증하지 않았다. 완료 표식을 출력 동등성이나 속도 개선 증거로 확대하지 않는다.
- task에서 실행 완료와 결과 검토/INTEGRATION 수치 반영 대기를 분리했다. 다음은 세 보고서의 identity/커버리지/hash와 측정 수치를 검토하고 고정10GB 근거와 조건을 대조하는 것이다. 이번 요청에서는 진행 확인만 수행했고 결과 artifact 전송·새 Python 실행·commit/push는 하지 않았다.

## 2026-11-04 / 20GB 비교 결과 분석 착수와 원본 검증

- 사용자 요청으로 실제20GB 품질·생성·속도 결과 분석에 착수했다. itcerdo 원본의 sha256sum은 quality=5092a5a1bf8d6250dfac0f028e82d8577b72c1dfcaf275ec5615980b3118bf7e,generation=6d061e2dbbc8a3fd4a55ddb55a4359e99b290a13f82f75ef675ceb0158d90a4a,timing=f20e3835e23008bddc6813cdf5c3e70e45a8f759638e220fd535a68fc3ce58ab이며 최종 run_report 기록과 모두 일치한다.
- jq로 원격 JSON을 읽고 quality_summary/boundary_summary/generations/timing_cases 구조를 확인했다. 기존 고정10GB 표는333문서/18생성/8입력이며,20GB timing의 종류는 patcher_prefill/model_prefill/patcher_incremental32다. 이 패처 단독 증분 시간을 기존 전체 모델 초기+증분 시간과 섞지 않는다. 다음은 집계/실제 커버리지·출력 재현 및 정확한 동일 작업 조건 대조다.
- 원격에 jq와 기존 conda phdq_blt_hf가 존재함을 확인했지만 새 Python/모델 작업은 실행하지 않았다. 데이터/모델/환경을 변경하지 않고 공개 집계와 hash만 읽었다. 이 단계에서는 성능 개선·후보 채택을 아직 결론내리지 않는다.
- quality333문서/928청크/1497578바이트와20GB 배경800블록/20000001834bytes 완료를 확인했다. 합산BPB는 신경망0.810648399298247/count0.8129000206372378,차이+0.0022516213389908667와 문서 대응95%구간[+0.0014776165842499416,+0.0031102422356310694]다. 기존0.01 허용은 통과하지만 신경망보다 나쁘다. 전체 경계TP275761/FP125193/FN63137,F1=0.7454490898179635다.
- 생성36기록을 이름/시드별18쌍으로 비교해 ID/문자열 완전일치 모두0을 확인했다. 신경망23543바이트/754.4062840626575초/EOS11/count26211바이트/696.3994387765415초/EOS9,UTF-8은 둘 다18/18이다. 신경망18개는 기존 sampling ID와 정확 일치한다. 10GB count EOS13/18 대조는 과거 별도 출력의 관측치이며 내용 품질 검정이 아니다.
- timing8입력의 각10반복 평균 합계는 전체 모델 초기 neural0.24873058786615732/count0.9956672342494131초,패처 단독 초기0.07346042469143868/0.8088548284955323초,패처 단독32바이트 증분2.332086761575192/0.0747043889015913초다. 전체 모델 초기 약4배 느림/패처 증분 약31.22배 빠름을 구분한다. 새 model_incremental32/model_total32는 미측정이며 당초 비교 범위에서 이 부분을 완료 처리하지 않는다.
- INTEGRATION에 과거10GB 품질 대조·생성·정확한 시간 범위와 후보 미채택 판정을 추가하고 작은 집계 evidence 및 task를 갱신했다. 전체 원문/생성 텍스트/ID/모델을 로컬에 복사하지 않았다. 다음은 집계 JSON의 산술·커버리지·기존10GB identity 대조와 문서 진단이다. 새 실험·환경 변경·commit/push는 하지 않는다.
- Node의 집계 JSON 검사에서333문서/바이트 합계,가중 BPB,신경망 대비 차이,TP/FP/FN의 precision/recall/F1,hash 형식·생성 횟수가 모두 통과했다.10GB 실제 품질 근거 대비 BPB 차이는-0.00008464447845468737,F1 차이는+0.003942363312273489다. 시간비는 전체 모델 초기4.002994737배 느림/패처 초기11.010756225배 느림/패처 증분31.217533479배 빠름이다. 관측 자유 생성 처리량은 neural31.207322231/count37.637882141bytes/s이며 동일 작업 speedup으로 해석하지 않는다.
- 원격20GB metadata와 로컬10GB 원본 JSON의 model_checkpoint 경로/runtime/count_config/split_sha256이 구조적으로 정확 일치했다. 실제 모델 가중치 재해싱은 하지 않았다. jq 검사는18개 이름/시드 그룹에 original/count_lmdb가 각각1개씩 존재하고 신경망18개 모두 기존 sampling ID와 일치함을 확인했다. 수정4파일의 편집기 진단도 오류가 없다.
- 분석·기록을 완료했다. 기존BPB 허용치는 통과하지만20GB count는 신경망보다 BPB가 높고 출력 동등성/초기 속도 기준을 충족하지 않는다. 기본 후보는 채택하지 않는다. 남은 전체 모델32바이트 증분/전체 시간과20GB C++ 재생은 명시적 미측정이며 새 실험을 자동 시작하지 않았다.

## 2026-11-04 / 사용자 승인 20GB 전체 모델32바이트 증분 측정 준비

- 사용자가 확률 패처의 핵심인 전체 모델32바이트 증분 시간의 실제 측정을 요청했다. 기존 compare_blt_patchers --stage total/timed_replay 경로는 고정 timing8입력에서 초기/증분/합계를 동일 실행으로 기록하고 count 재사용 대 fresh-prefix logits/경계를32단계 모두 정확 비교한다. 기존 quality/generation/timing/LMDB/source는 보존하고 새 결과로 실행한다.
- itcerdo 기존 conda env list와 conda run -n phdq_blt_hf의 sys.executable/CONDA_DEFAULT_ENV를 확인했다. 실행기는 /home/itcmaster/miniconda3/envs/phdq_blt_hf/bin/python이며 torch2.11.0+cu128/transformers5.16.1/numpy2.4.6, lmdb는 MISSING이다. GPU0%/1MiB,디스크 여유142GiB,기존 프로젝트 Python 작업은 검색되지 않았다.
- 새 venv/기존 model-venv 우회는 하지 않는다. 다음은 기존 conda에 lmdb2.3.0만 의존성 변경 없이 설치할 사용자 승인과 기존 증분/분해 테스트 확인이다. 의존성 설치·GPU 측정은 아직 실행하지 않았다.
- 사용자 확인 도구에서 기존 conda에 lmdb==2.3.0만 --no-deps로 설치하고 측정 진행을 명시 승인받았다. 설치는 해당 환경의 python -m pip로 제한하고 Torch/Transformers/NumPy·기존 환경·원본/이전 산출물을 변경하지 않는다. 다음은 승인된 설치와 기존 시간 분해/증분 회귀다.
- 기존 conda phdq_blt_hf의 python -m pip install --no-deps lmdb==2.3.0을 실행해 캐시된 cp311 wheel 설치에 성공했다. 실제 import/sys.executable/CONDA_DEFAULT_ENV와 lmdb2.3.0/torch2.11.0+cu128/transformers5.16.1/numpy2.4.6을 확인했다. 다른 환경·패키지 버전은 변경하지 않았다. 다음은 frozen source의 기존3개 replay/시간 분해 검사다.
- frozen source의 test_total_replay_includes_initial_forward_and_pairs_component_times/test_incremental_replay_uses_identical_bytes_and_excludes_priming/test_incremental_replay_rejects_invalid_steps_and_prefix_shapes를 기존 conda로 실행해3개 모두 통과했다(0.002초). PYTHONDONTWRITEBYTECODE=1로 원본/참조 코드에 새 pycache를 쓰지 않았다. 문서 진단도 오류가 없다.
- 다음 GPU 실행은 새 runs/en-blt20gb-total-20261104-01/total.json에 --stage total --timing-reference runs/en-blt20gb-compare-20261101-01/timing.json을 기록한다. 기존 frozen source/모델/20GB fit·LMDB/보호 분할/8입력/no-cache/3warmup·10repeat/교대순서를 유지한다. 모델 가중치·기준 timing·fit/background hash를 먼저 검증하고 초기+32번의 동일 byte teacher-forced 순전파 시간을 한 실행에서 분리한다. 실제 실행 결과는 아직 없으며 실패 산출물은 보존한다.
- 승인된 전체 모델 실측을 기존 conda/frozen source에서 실행했다. 사전검사에서 모델 가중치/fit/background/기준 timing/replay 소스의 고정hash가 모두 일치했고 GPU 실행은 completed_timing_cases=8까지 처리해exit0으로 끝났다. 새 total.json/preflight.log/launch.log만 en-blt20gb-total-20261104-01에 생성했다. 주소공간160GiB 상한을 적용했으며 원문·기존source/결과/LMDB는 수정하지 않았다. 다음은 보고서status/초기·증분·합계/paired times 및 정확성controls/RSS 검증이다.
- 새 total.json은 stage=total/status=completed,UTC02:30:00.126280~02:34:02.367616이며 실제SHA49c55639ac264d2fc2313335d6da325ba30dbc6ba63738c4178c52529634db07을 확인했다.8입력/각10반복/count32단계 fresh 경계·logits 일치와 기준ID 일치가 모두true,paired초기+증분=전체 잔차는0이다.
- 8입력 반복평균 합계는 초기 neural0.24340699864551424/count0.9803054124582559초,32바이트 전체모델증분7.8343434590846295/6.120595667604357초,전체8.077750457730144/7.100901080062613초다.8개 입력 모두 count 증분이 빨랐다. 최대hostRSS10118696960bytes/실제디스크여유142GiB를 확인했고 GPU는 종료후0%다.
- 전체 모델 증분 이점 약1.28배/초기 포함 전체 약1.14배를 측정 결과로 기록했다. 이전 초기 느림만으로 전체 효용을 부정하는 판정은 보완한다. count warm/fresh 동등성은 신경망 출력 동등성을 뜻하지 않으며 자유 생성 처리량과도 구분한다. 기존 evidence의followup_total32/INTEGRATION/task를 갱신했고 다음은 집계 산술·원본paired/control·고정조건 검증과문서진단이다.20GB C++/채택/새실험/commit/push는 하지 않았다.
- Node의followup 집계검사는8입력합계/초기+증분=전체/반복·controls/hash·실제RSS를 모두 통과했다. 정확한증분속도비1.279996896470543배/시간감소21.874810575135385%,전체속도비1.137566960397499배/시간감소12.093086841185062%,초기시간비4.027433138378751배다. 최대hostRSS9.4237709045GiB다. 사용자가 요청한전체모델32바이트증분실측은 완료했으며 결과는고정입력teacher-forced replay 범위다.

## 2026-11-04 / 사용자 요청 30GB 중단 점검 및 재시도 준비

- 사용자가 중단된30GB 점검과 재진행을 요청했다. itcerdo 첫 조회 UTC02:49:28에서 기존 conda phdq_blt_hf의 interpreter/환경을 확인했다. datasketch/pyarrow는 없고 lmdb/numpy/torch/transformers는 있으며 scipy도 없다. 다른 환경이나 기존 .venv로 대체 실행하지 않았다.
- 실패01의 run_report/progress.md를 재확인했다. prepare 실패/stages=[]이며 기존 background.jsonl 약32GiB와 dedup.sqlite 약39GiB는 보존 중이다. 기존 기록의 고유29999746734bytes/목표30000000000bytes/253266bytes 부족을 원인으로 유지한다. OOM이나 고정12shard 전체 고갈을 새로 주장하지 않는다. launch.log는 실패 실행 디렉터리에 없으므로 실제 progress.md를 사용했다.
- 관련 실행 프로세스는 없고 기존 종료된 tmux2개는 보존했다. 디스크 여유142GiB/사용 가능RAM약58GiB/GPU0%이며 새 en-patcher-bg30gb-nested-20261102-02 디렉터리는 아직 없다.20GB 본 비교와 전체모델증분은 완료했으므로 이전 순차 실행 게이트는 충족됐다.
- 로컬 retained_unique_v3는 실제 deduplicator의 채택바이트 피드백으로 읽기를 계속하며 기존 정책을 바꾸지 않는다. 재시도 가설은 원문 quota 대신 채택고유량 quota로 이번 부족을 방지할 수 있다는 것이다. 가장 가까운 반증 검사는 기존 sampler4회귀와 실제 SQLite/Parquet streaming_prepare 통합 회귀다. 부모가 기록한 datasketch2.0.0/pyarrow26.0.0 및 필요한 의존성을 확인하고 설치 승인을 받은 뒤 통합검사/고정 사본/새 실행으로 진행한다. 기존 실패본/source/부모/환경/자원 상한은 변경하지 않았다.
- 부모 환경의 읽기 전용 metadata와 fit/count 코드로 scipy1.17.1도 필수임을 확인했다(datasketch의 요구사항 및 적합의 expit/spearmanr/minimize). 설치 요청은 기존 conda에 datasketch2.0.0/pyarrow26.0.0/scipy1.17.1 세 개만 --no-deps이며 기존 numpy2.4.6 등은 변경하지 않는다. huggingface_hub/xxhash는 이미 있다.
- 디스크의 추가 게이트를 확인했다. 기준 config의 minimum_free_disk_gib=100/maximum_new_artifact_storage_gib=100은 유지 중이고 실제 여유142GiB이므로 현재 약42GiB만 새로 쓸 수 있다. 실패01 prepare의 약70GiB 파일 피크보다 작아 그대로 재시작하면 공간 guard로 다시 중단될 위험이 있다. 다른 작업용 mount는 없다. 패키지 설치와 실패01 background.jsonl/dedup.sqlite의 무손실 압축 보관(압축전 해시/압축본 복원 해시 검증 후 원래 두 파일 제거)에 대한 명시 승인을 요청한다. 승인 전 설치/압축/삭제/재실행은 하지 않았다.
- 사용자가 질문 도구에서 '세 패키지만 설치하고 진행'과 '검증 후 무손실 압축본으로 보관'을 명시 선택했다. 승인 범위는 기존 conda의 datasketch2.0.0/pyarrow26.0.0/scipy1.17.1 --no-deps 설치와 실패01 두 대형 파일의 검증된 압축본 보관뿐이다. 환경 교체/다른 의존성 변경/부모 삭제/예산 완화는 승인하지 않았다. 다음은 설치·버전/import 확인,압축본 복원 SHA 및 실제 회수 공간 확인,기존 통합회귀 통과 후 fresh run02 시작이다.
- UTC03:49:16 설치 전 ps/grep 안전 점검이 명령 문자열 안의 conda interpreter 경로 때문에 자신의 bash를 활성 작업으로 오인해exit1했다. pip는 실행되지 않았고 실제 Python 작업 충돌을 의미하지 않는다. 실제 Python PID의 /proc/exe 경로로 점검을 좁혀 같은 승인된 설치를 다시 검증한다.
- UTC03:49:52~03:49:57 실제 Python PID/exe 충돌 점검 후 승인된3패키지를 --no-deps로 설치했다. datasketch2.0.0/pyarrow26.0.0/scipy1.17.1 실제 import와 interpreter/CONDA_DEFAULT_ENV 및 기존 numpy2.4.6/torch2.11.0+cu128/transformers5.16.1/lmdb2.3.0 불변 assertion이 모두 통과했다. 다른 패키지나 환경은 변경하지 않았다. 다음은 두 실패 파일의 순차 압축/복원 SHA 검증 및 새 소스 사본의 통합 회귀다.
- 새 독립 runtime runs/en-bg30gb-retry-runtime-20261104-01/source를 전송하고 source_manifest.sha256=b6bb9b8441ba1c21dab8f279efe5b1b76b895c2274ab61033b582e1619daa19b로 고정했다. 기존 conda/BLAS8/PYTHONDONTWRITEBYTECODE에서 tests.test_data_preparation 전체15회귀가1.975초에 통과했고 skip은 없다(검사 종료 UTC03:58:27). sampler4개·실제 SQLite/Parquet retained quota·UTF-8/보호 split·반복 출력·압축payload·부모블록/재구축/적합 비교 재현/자원 guard를 포함한다. 검사 전후 전체 사본 SHA 검증도 통과했다. 기존 source/부모/실패 코드에는 덮어쓰지 않았다.
- 승인된 실패01 압축은 UTC03:52:19부터 순차 실행 중이며 JSONL 원본33745582859bytes/SHA61cffa4b55cd9b61757b475fa4ea5eb62202d4e14b79435c601a451311d914ce를 먼저 확보했다. 완료된 복원 SHA/실제 회수 공간을 확인하기 전 재시도는 시작하지 않는다. 다음은 부모/라벨/고정 소스 identity 사전검사와 압축 완료 후 디스크 게이트다.
- 부모 사전검사는 UTC04:07:45.762854에 status=verified로 완료됐다.20GB 부모800블록의 크기/SHA와20000001834bytes 원문,원래5split SHA,고정fit/분석/라벨 및 기존 핵심6소스의 frozen20GB 사본 일치가 모두 통과했다. 계획SHA678df03b547ad35496d23d3902088cbf52941e73a20f9ff92e73f63e5a62bffe/configSHA6043b4e375cabca5744d91a948add168cf4a90bd4365d6df3129c98c6c4eba64/라벨SHA0f79afdb7a1f7957fac83d1dd517d9beec1e5dd0abb6d82264191d4fb0fea201를 preflight.json에 기록했다. 압축 진행 중 당시 여유163963408384bytes는 최종 가용량이 아니다. 직전 읽기 전용 상태 조회는 출력이 기록되지 않아 outcome_unknown였으며 변경이나 재실행 명령은 포함하지 않았다. 다음은 압축 완료 증거와 최종 여유 확인이다.
- UTC04:09:44 증거 조회에서 JSONL 보관은 UTC04:01:20에 검증 완료됐음을 확인했다. 원본33745582859bytes→gzip14655422484bytes로19090160375bytes(약17.8GiB) 회수했으며 원본/복원SHA61cffa4b55cd9b61757b475fa4ea5eb62202d4e14b79435c601a451311d914ce가 일치했다. gzipSHAf3dd2fa36e9dcc919311e931654fddf7abf53d7e9737a5c43186fd21bfc58699와 복원 manifest를 실패01에 보존했다. SQLite는 원본과 압축 진행본이 함께 남아 있어 아직 검증 완료로 세지 않았다. 다음은 압축 프로세스 종료 이벤트 후 두 보관 증거/원본 제거/실제 여유를 검증해 fresh run02를 시작하는 게이트다. 주기적 sleep/poll이나 보호 기준 완화는 하지 않는다.
- UTC04:12:36.200917에 기존 conda의 단발 게이트가 실제 압축bash PID1089395의 pidfd 종료 이벤트 대기를 등록했다. 두 파일의 verified_lossless_archive/원본·복원SHA 일치/원본 제거/고정 소스·계획 SHA/새 run·tmux 부재와 디스크 최소100GiB+이전 준비피크74776387139bytes를 모두 통과한 경우에만 새 tmux blt-bg30gb-nested-20261102-02에서 기존 conda/BLAS8/prepare→build→fit→compare를 시작한다. 종료 이벤트 후에도 실패하면 실행하지 않는다. 현재는 게이트 대기이며 실제30GB 시작/완료로 세지 않는다.
- SQLite 압축 검증은 UTC04:18:43에 완료됐고 명령은04:18:45에 정상 종료했다. 원본41058263040bytes→gzip31865540918bytes로9192722122bytes를 회수했다. 원본/복원SHA6a4058df0eec94ce8b768b8493ab6a041183f596d62b460d0e5c5446ce354b4d가 일치하고 gzipSHA3d967c5cf5f49ef988def44d11116aa6311ce73f5fc2d65edd4531d9cb96e56d다. 두 파일 총28282882497bytes를 회수했으며 실패 로그/계획/native는 보존했다.
- 종료 이벤트 게이트는 압축 검증을 통과했지만 실제 여유179703967744bytes가 최소100GiB+이전준비피크182150569539bytes보다2446601795bytes(약2.28GiB) 부족해exit1했다. 새30GB run/tmux는 시작하지 않았다. 이는 새 준비 실패가 아니라 재시작 사전 공간 게이트다. 같은 승인된 실패 JSONL의 무손실 보관 압축률을 높여 추가 공간을 확보하고 복원SHA를 다시 확인한다. 다른 자료 삭제/기준 완화/패키지 추가는 하지 않는다. 첫 보관 manifest와 실패 게이트 출력은 이력으로 유지한다.
- UTC04:20:38에 기존 /usr/bin/xz5.4.5를 확인했고 첫 실패 게이트 출력은 launch_gate-failed-20261104-01.log로 보존했다.04:21:29부터 같은 JSONL gzip 보관본을 xz preset1/4스레드/압축메모리2GiB로 변환 중이다. 전체 복원SHA가 원본과 일치하고 xz가 더 작은 경우에만 gzip 보관본을 대체하며 첫 gzip manifest는 남긴다. 새 의존성 설치·원문 변경·부모 삭제는 없다. 다음은 이 변환 종료 이벤트와 같은 디스크/소스/중복 방지 게이트를 통과한 fresh 실행이다.
- 회고 보완: UTC04:27:24.598450에 xz 변환의 실제bash 종료 이벤트2개를 기다리는 단발 게이트를 등록했다. 당시 문서/로그 패치는 tool outcome_unknown로 적용되지 않았음을 이후 최근 기록과 대조했으며 이 줄로 보완한다. 변환은04:26:59 압축 종료/04:32:36 전체 복원SHA 검증 완료로 끝났다. JSONL xz는11988104668bytes/SHAa04945a485d1b7b6717aaf82e351e633f0894be166b662eec81bd1282600ec83이며 원본/복원SHA는 기존값과 정확 일치했다. gzip보다2667317816bytes를 추가 회수하고 첫 gzip manifest를 남겼다. SQLite와 총 회수량은30950200313bytes다.
- 두 번째 시작 게이트는 보관/공간/고정계획·소스/새run·tmux 부재를 통과해 UTC04:32:36 새 세션을 생성했으나 뒤의 remain-on-exit 설정에서 잘못된 window target으로exit1했다. 실제 실행 실패로 가정하거나 중복 재시작하지 않았다.04:33:46에 세션/conda 드라이버/prepare PID1090105와04:32:37 Started/prepare started 기록을 직접 확인했다. 이는 실제 fresh run02 시작이다.
- UTC04:34:44에 올바른 tmux window target blt-bg30gb-nested-20261102-02:0으로 remain-on-exit=on을 검증했다. 실제 prepare exe는 기존 conda의 python3.11,CONDA_DEFAULT_ENV=phdq_blt_hf/BLAS3변수8/PYTHONDONTWRITEBYTECODE=1/주소공간상한51539607552bytes(48GiB)다. 당시CPU71.5%/RSS199116KiB로 실행 중이며 디스크 약170GiB다. 기존 실패/부모/source를 보존했고 새 의존성 추가/예산 완화/commit/push/Neuron 작업은 없다.
- task/INTEGRATION에서 승인된 새 실행 시작과 미완료 prepare/build/fit/compare를 구분해 갱신했다. 원인 수정·의존성·통합15회귀·부모800블록/원문·보관/실제 재시작 확인은 완료했다. 다음은 시작검증 JSON/문서진단 및 실제 단계별 진행·완료 보고서 확인이며 아직30GB 고유량/적합F1/paired 결과를 발표하지 않는다.
- UTC04:36:32.256662 최종 launch_verification.json은 status=prepare_running이다. 실행 계획의 JSON값 동일성/원래 입력계획SHA/전체 소스SHA/실제 prepare PID·exe·환경·48GiB prlimit/세션/복원SHA·회수량 검사가 모두 통과했다. 보고서SHA09a0a3c89fd94269a4b229007aa185f58c3f69d8c37df6095acd77f37156f70a이며 실패한 빈 window-option 게이트 파일은 별도 .log 이름으로 보존했다.04:36:27 heartbeat는 checks140/scratch782870911bytes/peakRSS202809344bytes다. 최종 당시 여유181549883392bytes는 진행 중 파일 생성을 반영한 값이다. 수정 문서/계획4파일 편집기 진단도 오류가 없다. 사용자 요청의 점검·안전한 재시작은 완료했고 다음은 실행 중 단계별 완료·실패와 결과 보고서 확인이다. 완료 예상시각/새 F1/후보채택을 추정하지 않는다.

## 2026-11-04 / 사용자 승인 실패01 대형 압축본 삭제

- 사용자가 '압축한 파일도 지워'라고 명시 승인했다. 이번 승인으로 실패01 대형 산출물의 보존 의무를 해당 두 파일에 한해 해제한다. 삭제 대상은 runs/en-patcher-bg30gb-nested-20261101-01/background.jsonl.xz(11988104668bytes)와 dedup.sqlite.gz(31865540918bytes)뿐이며 총43853645586bytes다. 로그/계획/원본·복원·보관SHA manifest/native 및 정상20GB 부모/실행 중30GB 자료는 삭제하지 않는다.
- UTC07:47:58 읽기 전용 점검에서 두 대상이 일반 파일이고 보관 manifest의 크기/검증 상태와 일치함을 확인했다. 새30GB prepare는07:47:49 heartbeat checks10270/scratch34501125795bytes/peakRSS314621952bytes를 기록 중이다. 당시 디스크 여유147849576448bytes다. 다음은 실패 상태·새 부모 경로·파일 사용 여부를 좁게 확인하고 명시된 두 파일만 삭제한 뒤 실제 부재/남은 증거/새 작업·여유 공간을 검증하는 것이다.
- UTC07:49:08 사용자가 승인한 두 압축본만 rm의 명시된 경로로 삭제했고 실제 부재를 확인했다. 삭제량43853645586bytes,디스크 여유147804774400→191658434560bytes(약179GiB)다. 실패01 로그/계획/보고서/보관manifest 및 정상20GB 부모 보고서의 삭제 전후 SHA가 모두 동일하다. cleanup_authorized_20261104.json을 실패01에 남겼으며 원문 복원이 가능한 압축본은 이제 없고 남은 SHA는 검증 이력일 뿐임을 명시했다.
- 사전 파일사용 검사에서 이 호스트의 fuser가 -- 인자를 지원하지 않아 usage 오류를 반환했지만 조건문이 이를 미사용으로 오인했다. 이 검사는 통과로 세지 않는다. 삭제 자체는 명시 승인 범위에서 완료됐으며 두 파일 크기에 대응하는 공간 회수와 새30GB 세션/prepare PID1090105 유지·07:48:58 heartbeat(checks10300/scratch34563699585bytes/peakRSS314621952bytes)를 확인했다. 다음은 삭제감사 JSON과 새 작업의 열린 descriptor를 좁게 확인하고 문서 상태를 마무리하는 것이다. 삭제 명령 재실행이나 다른 자료 정리는 하지 않는다.
- UTC07:50:19 최종 검증에서 삭제감사 status/정확히2파일/43853645586bytes·보호SHA 불변과 실제 파일 부재를 모두 확인했다. 새driver1090089/prepare1090105는 살아 있고 두 프로세스의 /proc/fd에도 삭제된 압축본이 없다. 감사JSON SHA5af83bb3a8cad40fb27204e80b11b0d91150cb169824221a5717849316a2d478이며 디스크 여유는 약179GiB다. log/task/INTEGRATION 진단 오류가 없고 사용자 승인 범위의 정리를 완료했다. 다른 실패 자료/부모/source/환경/실행 중 작업은 정리하지 않았고 commit/push도 하지 않았다.

## 2026-11-04 / 사용자 지시 C++ 빈도 구축·로딩 가속과 30GB 중단

- 사용자가30GB 작업을 중단하고 (1)C++ 빈도 구축·로딩 코드 (2)20GB 블록 테스트 (3)동일성·시간 절감 확인 (4)블록 병렬 (5)부모 투영 재사용을 먼저 진행한 뒤30GB를 재개하라고 지시했다. task에 작업 목록을 추가했다.
- 근거: 20GB 실행 시간은 prepare20712s/build48091s/fit14754s(빈도 로딩13545s,특징398s,최적화1.35s)였다. 20GB 블록은 블록당 약1236만 문맥/2022만 간선/압축 해제592MB이고 적합 필요 문맥은4055232개다. itcerdo에 zlib 헤더와 GCC13.3이 있다. CountModel 확률은 토큰별 배열 원소 합과 정수 합계를 쓰므로 행 순서가 수치에 영향을 주지 않지만, 구현은 Python dict 삽입 순서와 출력 바이트까지 동일하게 맞춘다.
- 다음은30GB run02 중단·기록 보존,C++ 구현과 로컬 회귀다. 원본20GB 산출물은 읽기 전용으로 사용한다.
- UTC08:45:46 사용자 지시로 run02 prepare PID1090105(기존 conda exe/계획 인자 확인)에 SIGTERM을 보냈고 prepare/driver 종료 이벤트를 확인했다. run_report는 status=failed,CalledProcessError(SIGTERM),elapsed15188.96s,stages[]이며 직전 heartbeat는 checks12650/scratch38796433900bytes다. progress/plan/native와 부분 dedup.sqlite(38788698112bytes)/journal을 보존했다. prepare는 재개 기능이 없어 C++ 작업 후 새 run으로 다시 시작한다. 당시 디스크 여유는 약175GiB다.
- (1) 구현: scripts/native/count_blocks.cpp에 CountTable.add_document/save와 같은 문맥 삽입·간선 순서·JSONL 바이트를 만드는 블록 구축기, 필요 문맥만 거르는 gzip 블록 파서와 블록 순서 병합기를 추가했다. scripts/native_counts.py는 명시 빌드/ctypes 래퍼·병렬 투영·투영 저장/고정hash 로드를 맡는다. run_background_expansion은 plan의 count_backend=cpp_v1/count_workers일 때만 블록 병렬 구축을, load_workers/parent_projection_report가 있을 때 fit/compare C++ 투영·부모 투영 재사용을 쓴다. 기본 Python 경로와 보고서 스키마는 유지했다. Python은 16바이트 초과·홀수 길이 문맥을 매칭하지 않으므로 래퍼에서 제외해 같은 결과를 낸다.
- 새 검증 사본 runs/en-native-counts-validation-20261104-01(source_manifest SHA df83f5456ab3d7f4d52de512ccccc872f89413092a1f48b49fc92323b0c63a55)에서 기존 conda로 tests.test_native_counts 4개+test_data_preparation+test_count_patcher 총37개가3.831초에 통과했다(skip 없음). K=0/1/3/8 무작위 문서의 평문 블록 바이트·문맥/간선/크기와 gzip 해제 내용,1/3작업자 투영의 행·순서·합계,3블록 부모 투영+나머지=직접 투영과 부분집합 필터,병렬 build_blocks의 블록명·메타데이터·평문 SHA·gzip 해제 내용 일치,기존 출력 덮어쓰기·범위 초과·prefix 불일치·hash 변경 거부를 확인했다. 다음은 20GB 실데이터 측정 스크립트다.
- scripts/benchmark_native_counts.py를 추가했다. build는 원본20GB 블록을 읽기만 하고 같은 문서로 Python/C++ 블록을 새 출력에 만들어 원본 gzip 해제 내용SHA·크기·문맥/간선과 대조한 뒤 새 블록만 지운다. project는 Python 부분집합 대조,전체 C++ 투영,20GB 학습특징 전체·검증F1 재현,부모 투영+나머지=직접 투영을 확인한다. 측정 사본 runs/en-native-counts-bench-20261104-01(source_manifest SHA e43e16fcce03ffdb41a7cda9d0a7d9f860e3c8cf5fec83ceda54a2d62cc71e21)을 고정했다.
- 예비 build(블록400~401,2작업자)는 verified다. 블록400에서 Python 116.117초(집계97.857초+저장·gzip),C++ 단일15.768초(gzip 포함)로 약7.36배 빨랐고 Python 재생/C++ 모두 원본 해제 내용과 같았다. 문맥12362022/간선20218298/해제592437825bytes가 원본 메타데이터와 일치했다. 2블록 2작업자 병렬은24.758초(부모 문서 건너뛰기 포함 읽기7.351초)였고 두 블록 모두 일치했다. Python 기준 블록 최대RSS 약5.05GB다. 다음은 신규400블록 전체의8작업자 측정이다.
- (2)(3)(4) 전체 build 측정 UTC09:04:11~09:29:46 full-build/result.json status=verified. 블록400/401 Python 115.699/115.814초 대 C++ 단일15.643/15.549초(약7.4배)였고 Python 재생·C++ 모두 원본과 같았다. 신규400블록(400~799) C++8작업자 병렬 구축은1082.766초(문서 읽기47.292초 포함),최대RSS15601246208bytes(약14.5GiB)다. 400블록 전부 원본 gzip 해제 내용SHA/크기와 문맥·간선·해제바이트 메타데이터가 일치했다(불일치0). 기존20GB 실행 build48091.128초 대비 약44.4배 짧다. 단 과거 build는 부모 블록 검증·원문 대조를 포함한 다른 실행이므로 같은 실행의 대응 측정은 블록당 7.4배 값이다. 새 블록은 검증 후 지웠고 디스크 여유는 약175GiB다.
- 사용자가 질문 도구에서 중단된 run02의 부분 dedup.sqlite·journal 삭제를 승인했다. 진행 기록·계획·run_report·native는 보존한다. 다음은 삭제 후 project(로딩·부모 투영) 측정이다.
- 첫 삭제 시도는 pgrep -f가 같은 문자열을 담은 검사 셸 자신을 실행 중 작업으로 잡아 삭제 전 중단했다. 실제 Python cmdline과 열린 fd만 검사하도록 고쳐 UTC10:31:37에 run02의 dedup.sqlite(38788698112)/journal(55934688) 두 파일만 삭제했다. 합계38844632800bytes,여유187375026176→226219679744bytes다. cleanup_authorized_20261104.json을 남겼고 진행기록·계획·run_report·native는 보존했다.
- (3)(5) project 측정 UTC10:32:18~10:54:21 project/result.json status=verified(필요 문맥4055232,8작업자). 첫8블록 Python 투영122.218초 대 C++ 1작업자29.935초/8작업자12.227초이며 행·삽입순서·합계가 모두 같았다. 전체800블록 C++ 투영은350.200초(문맥3929157/간선66457052)로 기존 Python 로딩13545.425초 대비 약38.7배 짧다. 이 투영으로 재계산한 학습특징4041644위치가 20GB fit의 train_features.npy와 전부 같았고(352.795초),검증 지표·문서별 집계·F1 0.7878359727712929가 원본 fit과 정확히 같았다. 부모400블록 투영(187.253초)을 저장·로드해 나머지400블록과 병합(188.815초)한 결과가 전체 직접 투영 배열과 완전히 같았고 필터된 시드 문맥은0이다. 최대RSS7956725760bytes다. 20GB800블록 투영 report SHA59a32aea2259b34ab459e0b4e4d70c02ed7b64f67de2d5a36ee7d9cb163816c1/arrays SHAfb238346d3c77341e3c3044a4b6ae417a00298eb35a59e9252d2ed1c00f7179a를 30GB 부모 투영으로 고정한다.
- 새 계획 experiments/english_background_30gb_cpp.json(run03, tmux blt-bg30gb-nested-20261104-03)은 기존 재시도의 목표/부모/라벨/seed/quota/자원 제한을 유지하고 count_backend=cpp_v1,count_workers=8,load_workers=8,부모 투영 고정 hash만 추가했다. 다음은 새 실행 사본 회귀·사전검사 후 run03 시작이다.
- Node 계획 계약 검사(기존 재시도와 목표/부모/seed/quota/자원 필드 동일)가 통과했다. 새 실행 사본 runs/en-bg30gb-cpp-runtime-20261104-01(source_manifest SHA9f56d8fb973f70d4609f3a76ee4ad1763979435f1cca089fccb61e18e55ca4a2)의 핵심5파일이 측정 사본과 바이트 동일하고 회귀37개가 4.023초에 통과했다. 부모 투영 load_projection이 고정 hash로 800블록/3929157문맥/66457052간선/필요문맥4055232를 검증했다. 새 run/tmux 부재와 여유224673447936bytes를 확인한 뒤 UTC10:56:03 tmux blt-bg30gb-nested-20261104-03을 만들고 remain-on-exit를 켰다.
- UTC10:56:04 run03 Started/prepare started를 확인했다. prepare PID1119538은 기존 conda python3.11/CONDA_DEFAULT_ENV=phdq_blt_hf/BLAS8/주소공간 48GiB이며 plan.json의 cpp_v1/8/8/부모 투영 hash도 일치한다. prepare는 변경 없는 기존 경로이고 build/fit/compare가 C++ 경로를 쓴다. task의 (1)~(5) 완료와 run03 진행을 갱신했다. commit/push는 하지 않았다.

## 2026-11-04 / 사용자 지시 prepare 가속과 50GB 확장

- 사용자가 run03을 중단하고 준비 단계의 (a)부모 중복 색인 재사용 (b)서명 C++ 이전 (c)병렬 서명·순서 판정 (d)로컬 shard를 모두 완료한 뒤 50GB로 확장하라고 지시했다. 근거는 run02 기록의 부모 재색인 약1.5시간, shard당 약13분, 단일 Python 스레드 처리다. task에 목록을 추가했다. 다음은 run03 중단과 구간별 실측 프로파일이다.


## 2026-11-04 / 확률 패처 적합 결과

지금까지 측정한 모든 영어 패처 결과를 기존 근거 파일에서 모아 표로 정리했습니다. 새로 실험한 것은 없습니다. 한 행 안에서는 같은 조건의 수치만 비교했습니다.

**용어**
- **엔트로피 패처**: BLT의 기존 신경망 패처
- **확률 패처**: count 패처
- **속도비**: 엔트로피 시간 ÷ 확률 패처 시간. 1보다 크면 확률 패처가 빠릅니다.

## 1. 실제 BLT에 연결한 비교

| 항목 | 엔트로피 | 10GB 확률 (Python) | 10GB 확률 (C++) | 20GB 확률 (Python) |
|---|---:|---:|---:|---:|
| FineWeb BPB | 0.770905 | 0.773770 | 0.773770 | 0.773656 |
| Wikipedia BPB | 0.830301 | 0.832376 | 0.832376 | 0.832306 |
| **합산 BPB** (낮을수록 좋음) | **0.810648** | 0.812985 | 0.812985 | **0.812900** |
| 엔트로피 대비 BPB 증가 [95%] | — | +0.00234 [+0.00152, +0.00320] | 같음 | **+0.00225** [+0.00148, +0.00311] |
| 경계 Precision / Recall | 기준 | 0.6818 / 0.8127 | 같음 | 0.6878 / 0.8137 |
| 경계 F1 (평가 333문서) | 기준 | 0.7415 | 0.7415 | **0.7454** |
| 적합 검증 F1 (111문서, 기준 0.90) | — | 0.7854 (미달) | 같음 | 0.7878 (미달) |
| **초기 처리** (8입력 합계, 초) | 0.2439 / 0.2434 | 0.9697 | 0.4074 | 0.9803 |
| 초기 처리 속도비 | 1 | 0.25 (약 4배 느림) | **0.60** | 0.25 |
| **동일 32바이트 증분** (초) | 7.8548 / 7.8343 | 6.1631 | 6.1022 | 6.1206 |
| 증분 속도비 | 1 | 1.27배 | **1.29배** | 1.28배 |
| 증분 바이트당 시간 | 30.6 ms/B | 24.1 ms/B | 23.8 ms/B | 23.9 ms/B |
| **초기 + 증분 합계** (초) | 8.0987 / 8.0778 | 7.1328 | **6.5097** | 7.1009 |
| 합계 속도비 | 1 | 1.14배 | **1.24배** | 1.14배 |
| 자유 생성 바이트 (18회) | 23,543 | 18,266 | 18,266 | 26,211 |
| EOS 도달 | 11/18 | 13/18 | 13/18 | 9/18 |
| 자유 생성 시간 (초) | 753.8 / 754.4 | 434.6 | 431.0 | 696.4 |
| 실효 생성 처리량 | 31.2 B/s | 42.0 B/s | 42.4 B/s | 37.6 B/s |
| 엔트로피와 생성 ID 완전일치 | 기준 | 0/18 | 0/18 | 0/18 |

- 엔트로피 열에 두 값이 있는 행은 왼쪽이 10GB 측정, 오른쪽이 20GB 측정과 같은 실행의 기준값입니다. 각 속도비는 같은 실행의 엔트로피 값으로 계산했습니다.
- 10GB C++는 Python과 경계·로짓·BPB·생성 출력 18개가 모두 같았습니다. 바뀐 것은 속도뿐입니다.
- 자유 생성은 출력 길이와 경로가 서로 달라, 같은 작업량의 속도 비교로 볼 수 없습니다.

## 2. 패처만 따로 측정한 시간

| 측정 | 10GB 확률 (Python) | 10GB 확률 (C++) | 20GB 확률 (Python) |
|---|---|---|---|
| 패처 초기 처리 | 입력별 19.9–207.4ms (엔트로피 3.5–22.3ms) | Python 대비 **3.3–6.3배 빠름** (시간 72% 감소) | 합계 0.809초 (엔트로피 0.073초, 약 11배 느림) |
| 패처 32바이트 증분 | 엔트로피 대비 **16.7–57.5배 빠름** | Python 대비 4.0–5.1배 빠름 | 엔트로피 대비 **31.2배 빠름** |

패처만 보면 증분 처리가 수십 배 빠릅니다. 하지만 전체 모델에서는 인코더·전역 트랜스포머·디코더 비용이 그대로 남아 약 1.28배 수준으로 줄어듭니다.

## 3. 배경 빈도 크기별 적합

모두 같은 검증 111문서 기준이며, 이후 비교에 사용한 기본 설정은 K=8, 창 무제한입니다.

| 배경 빈도 | 검증 F1 | 이전 단계 대비 | 선택 임계값 |
|---|---:|---:|---:|
| 10MB (창 1024) | 0.6251 | — | — |
| 10MB | 0.6258 | — | — |
| 100MB | 0.7145 | +0.0887 | — |
| 1GB | 0.7641 | +0.0496 | — |
| 5GB | 0.7804 | +0.0163 | 0.34375 |
| 10GB | 0.7854 | +0.0049 | 0.375 |
| 20GB | **0.7878** | +0.0025 | 0.375 |
| 30GB | 진행 중 | — | — |

빈도 자료를 늘릴수록 F1 증가폭이 빠르게 줄고 있습니다. 모든 크기가 기준 F1 0.90에 미달했습니다.

## 4. 10GB 설정별 절제 실험

| 설정 | F1 | F0.5 | F1 비열등성 (허용 −0.005) |
|---|---:|---:|---|
| 전체 모형 | 0.7854 | 0.8066 | 기준 |
| 길이 제거 | 0.7854 | 0.8066 | 통과 |
| eta 0.5 | 0.7854 | 0.8065 | 통과 |
| 창 1024 | 0.7853 | 0.8064 | 통과 |
| eta 0, 반복 유지 | 0.7843 | 0.8050 | 통과 |
| 반복 제거 | 0.7783 | 0.8074 | 실패 |
| 길이·반복 제거 | 0.7783 | 0.8074 | 실패 |
| eta 0, 반복 제거 | 0.7765 | 0.8044 | 실패 |

이 설정들은 패처 단독 시간만 측정했습니다(증분 16.5–53.4배 빠름). 전체 BLT의 BPB와 생성 결과는 측정하지 않았습니다.

## 요약

| 기준 | 판정 |
|---|---|
| BPB 증가 허용치 (0.01 이하) | 10GB·20GB 모두 통과. 다만 엔트로피보다 약 0.002 나쁩니다. |
| 적합 검증 F1 0.90 이상 | 모든 확률 패처가 미달. 최고는 20GB의 0.788입니다. |
| 전체 모델 초기 처리 속도 1.05배 이상 | 미달. C++도 0.60배로 엔트로피보다 느립니다. |
| 전체 모델 증분 속도 | 약 1.27–1.29배 빠름 |
| 초기 처리 포함 합계 | Python 1.14배, **C++ 1.24배** 빠름 |

현재 가장 좋은 조합은 **20GB 빈도와 C++ 백엔드**로 예상되지만, 이 조합은 아직 측정하지 않았습니다. 20GB C++ 재생은 미측정 상태입니다. 모든 시간은 RTX 5090, 배치 1, 같은 8개 입력에서 측정한 값입니다.

## 2026-11-04 / prepare 프로파일 결과와 작업 재개

- run03은 사용자 지시로 SIGTERM 중단됐다(run_report status=failed/CalledProcessError SIGTERM, elapsed523.52s, stages[]). 진행 기록·계획은 보존했다.
- runs/en-prepare-profile-20261104-01에서 scripts/profile_disk_preparation.py로 20GB 부모 앞10만 문서(580428655 UTF-8 bytes)를 기존 DiskDeduplicator 경로와 같은 순서로 처리했다. UTC11:08:50 결과: 총97.813초(0.978ms/문서, 5.93MB/s). 구간 비율은 Python shingle+SHA1 48.0%, SQLite 삽입·커밋20.4%, C++ MinHash 호출(ctypes 변환 포함)10.8%, JSON+zlib 8.4%, 정규화+SHA256 5.2%, band 조회2.5%, 정확 조회1.0%다. 고정 shard data/CC-MAIN-2025-05/004_00011.parquet 다운로드는2153246710bytes/81.922초(26.3MB/s), 로컬 전체 읽기(949 row group/949000행/텍스트3423939929bytes)는6.383초다. 최대RSS약360MB다.
- 측정 직후 이전 응답이 결과 처리 전에 끝나 기록·다음 단계가 지연됐다. 서버 작업 실패는 아니다. 다음은 (b)(c) C++ 일괄 서명·병렬화와 SQLite 기록 개선 구현이다.
- 구현: (b) scripts/native/minhash.cpp에 SHA1 포함 shingle·MinHash 일괄 커널 blt_minhash128_batch(문서 단위 원자 카운터 다중 스레드)를 추가하고 native_minhash.signatures로 연결했다. (c) disk_dedup에 Signer/SignedDocument를 두고, 보호 문서는 4096개 묶음, 후보는 prepare의 row group 단위로 사전 서명한다. 후보 생성기는 문서마다 채택량을 보고 멈추므로 생성기에서 미리 꺼내지 않는다. 채택 판정·SQLite 기록은 순서대로다. (a) build_protected_index/scripts/build_protected_index.py가 보호 색인을 만들고, expand_to_disk는 고정 hash 색인을 읽기 전용 ATTACH해 후보만 main에 넣는다. 정확·유사 조회는 base/main 모두 확인하고 보호 출력은 base 순서로 쓴다. 후보 ID가 1부터 시작해도 band별 정렬 목록 길이와 상대 순서가 같아 섞기·출력 순서는 같다. (d) scripts/download_fineweb_shards.py가 LFS SHA256·크기를 검증하고 prepare는 로컬 고정 hash를 확인한다. 가속 경로의 임시 DB는 journal/synchronous를 끈다. 모두 계획 키를 줄 때만 쓰며 기본 경로는 그대로다.
- 검증 사본 runs/en-fast-prepare-validation-20261104-01에서 기존 conda로 회귀39개가 통과했다(tests.test_fast_preparation 2개 신규). 첫 실행의 실패1개는 합성 목표가 부모보다 작았던 테스트 설정, 두 번째 실패는 목표가 작아 중복 거절 경로를 거치지 않은 설정이었고 목표만 키워 통과했다(구현 변경 없음). C++ 서명은 빈/공백/1~6단어/유니코드 공백·문자/긴 반복 문서와 seed42·20261019, 1·4스레드에서 datasketch·기존 경로와 일치했다. prepare의 기본·병렬 서명·로컬 shard·색인 재사용·전부 조합이 압축/무압축 모두 background.jsonl 바이트와 file_sha256/문서·바이트·band·후보·중복·row group·shard 표집이 같았다. shard/색인 hash 변경은 거부됐다.
- 20GB 실제 재현을 tmux blt-fast-prepare-verify로 시작했다. 첫 실행은 즉석 다운로드 스크립트의 f-string 역슬래시 SyntaxError로 다운로드 전에 끝났고(로그 verify_20gb-failed-syntax.log 보존), 저장소 정식 scripts/download_fineweb_shards.py로 교체해 UTC11:42:04 재시작했다(source_manifest SHA c2d5420bf09d7cc5751dd05dff457407e89c352375c60713df955165c27ea1d6). 순서는 고정 shard12개 다운로드→10GB 부모 보호 색인(16스레드)→기존 20GB 재시도 계획에 가속 키만 더한 prepare 재현→원본 data_preparation.json 대조다. 여유 약207GiB에서 시작했다.

## 2026-11-05 확인 / 20GB prepare 새 경로 재현 결과

- UTC 2026-11-04T21:26:55 조회에서 tmux blt-fast-prepare-verify는 exit0으로 끝나 있었다. 다운로드 11:42:04~11:56:37(12 shard, 24849298130bytes, 872.315초, 모두 LFS SHA256·크기 일치), 10GB 부모 보호 색인 11:56:37~12:03:48(2753721문서/10000002264bytes, 429.333초, 16스레드, DB 19431919616bytes, 최대RSS약369MB), 20GB prepare 재현 12:03:48~12:37:36이다.
- 재현 data_preparation.json은 status=prepared, file_sha256=ac9aed77c41490aa2c2dae3fa151d9cb3f7e4b711de4c0fde3a7e35255ced6a4로 원본20GB와 같다. file_sha256/문서/바이트/length_bands/후보문서/중복제거/row_groups_read/shard_sampling/원래 배경 보존 9개 항목이 원본과 모두 일치했다. prepare 시간은 2024.979초로 원본 20712.165초 대비 약10.2배 짧다. 일회성 다운로드·색인을 더해도 3326.6초로 약6.2배다. 최대RSS약532MB, scratch 39090552832bytes다.
- 재현 산출물 background.jsonl(22182942710bytes)은 원본20GB와 hash가 같은 중복본이다. 남은 여유는 약146GiB이며 로컬 shard 24.8GB와 10GB 부모 색인 19.4GB가 남아 있다. 다음은 50GB 계획 전 디스크 정리 범위 확인, 20GB 부모 보호 색인 구축, 50GB용 shard 수 확인이다.
- 사용자가 두 항목 삭제를 승인했다. UTC2026-11-04T21:28:40에 재현 출력 runs/en-patcher-bg20gb-fast-repro-20261104-01/background.jsonl(22182942710bytes, 삭제 직전 재계산 SHA256 ac9aed77…ed6a4가 원본20GB report와 같고 크기도 같음)과 10GB 부모 검증 색인 protected.sqlite(19431919616bytes, SHA256 fd15cda4b068adb35d8d84995c376c25c7e475c9059b8efafa2185343b285835)만 삭제했다. 열린 fd는 없었다. 여유 155977281536→197592150016bytes(약185GiB)다. 두 run의 data_preparation/progress/protected_index.json/native와 감사 cleanup_authorized_20261105.json은 보존했다. 로컬 shard는 50GB용으로 유지한다.

## 2026-11-05 / 50GB 확장 사전 점검과 20GB 부모 보호 색인

- 50GB 용량·예산을 점검했다. 고정 shard12개 원문은 약39GB(profile shard 기준 3.42GB/shard, 005_00040은 작음)이며 그중 약10GB는 20GB 부모 신규분으로 이미 채택돼 보호 문서가 됐다. 길이 필터·중복 제거 뒤 신규 고유30GB를 채우지 못할 가능성이 크다. 기존 계획의 sources_policy는 shard 자동 추가를 금지한다. 카탈로그는 같은 prefix 300개 중 원래4개를 빼고 random.Random(20261029)로 섞은 첫12개를 골랐다.
- 디스크: 여유197592137728bytes(약184GiB), 최소 여유100GiB·실행당 새 산출물100GiB 상한. 예상 50GB background.jsonl 약55GB, 20GB 실측(신규400블록 42855486526bytes) 기준 신규1200블록 약129GB, 20GB 부모 보호 색인(압축 payload) 최대 약39GB, 추가 shard12개 약26GB다. 실행 디렉터리 하나에 약185GB가 필요해 기존 두 상한을 넘는다. 상한 변경·자료 정리·shard 추가는 사용자 결정 사항이다.
- 결정과 무관하게 필요한 20GB 부모 보호 색인을 검증 사본(source manifest c2d5420b…)으로 UTC2026-11-04T21:30:18 tmux blt-protected-index-bg20gb에서 시작했다(압축 payload, 16스레드, 출력 runs/en-protected-index-bg20gb-20261105-01).
- 50GB 후보 shard: 사용자가 기존12개+같은 규칙12개 추가(총24)를 선택했다. 카탈로그 available_shards는 개수(300)라 경로를 같은 revision에서 다시 조회했다. scripts/extend_shard_selection.py(정렬→원래4개 제외→random.Random(20261029)섞기)가 현재 목록300개(카탈로그와 같음)에서 고정12개를 정확히 재현했고 다음12개를 evidence/english_background_sources_50gb_20261105.json에 기록했다. 즉석 Python 두 번은 f-string/ 타입 오류로 실행 전에 실패했고 저장소 스크립트로 대체했다.
- 정리: 사용자가 제안4개 삭제를 승인했다. 10GB 블록은 20GB가 400개를 참조해 유지했고 1GB/5GB 블록·원문은 유지 실행에서 참조하지 않음을 background_build.json으로 확인했다. UTC2026-11-04T21:33:39에 1GB background_blocks(24207127947)/background.jsonl(1097487894), 5GB background_blocks(21642242292)/background.jsonl(5562729994), 첫20GB 실패 dedup.sqlite(21158420480), run03 dedup.sqlite(2215936000)/journal(12374072)만 삭제했다. 합계75896318679bytes, 여유193557041152→269446918144bytes다. 보고서·fit·진행·계획과 runs/cleanup_authorized_20261105_50gb.json을 남겼다.
- 추가 shard12개 다운로드를 UTC21:33:50 tmux blt-shards-50gb에서 시작했다(LFS SHA256 검증, 검증 사본 manifest 50405a66…). 20GB 부모 보호 색인은 진행 중이다.
- 차단 사항: 실행당 새 산출물 상한100GiB가 build 단계의 50GB background.jsonl(약55.5GB)+신규1200블록(약128.6GB)=약184GB를 막는다. 다운로드 후 여유 약225GiB에서 색인을 지워도 build 최대 시점 여유 약41GiB로 최소 여유100GiB도 어긋난다. 40GB 목표도 약130GB로 실행당 상한을 넘는다. 상한 변경 또는 LMDB 등 추가 정리는 사용자 결정 사항이며 계획 실행 전에 확인한다.
- 사용자 결정(2026-11-05): 50GB 실행에 한해 새 산출물 상한 200GiB, 최소 여유 30GiB. 공용 baseline 설정의 100GiB/100GiB는 바꾸지 않는다.
- 구현: run_background_expansion.py에 계획 키 budget_overrides를 추가했다. maximum_new_artifact_storage_gib와 minimum_free_disk_gib만 양의 정수로 허용하며 다른 키(예: peak_host_ram_gib)나 0 이하는 ValueError다. 적용 값과 덮어쓴 값은 run_report의 effective_budgets/budget_overrides에 남긴다. prepare_disk_background.py에 delete_protected_index_after_prepare(true일 때만)를 추가했다. data_preparation.json을 쓰고 임시 DB를 지운 뒤 보호 색인 DB만 삭제하며 색인 보고서는 남긴다. build 단계 피크에서 약39GB를 확보하기 위한 것이다.
- 검증: 50GB 실행 사본 runs/en-bg50gb-runtime-20261105-01에서 기존 conda phdq_blt_hf로 tests.test_fast_preparation/test_data_preparation/test_native_counts/test_count_patcher 40개가 통과했다. 압축·무압축 모두 '전부' 조합에서 삭제 옵션을 켜도 background.jsonl 바이트가 기본 경로와 같았고, 성공 뒤 DB는 없고 보고서는 남았다. 예산 덮어쓰기 테스트는 허용 키 적용, RAM 키·0 거부, 설정 파일 불변을 확인했다.
- UTC2026-11-04T21:37:13 상태: 보호 색인 구축 진행 중, 추가 shard 다운로드 2/12 완료(각 약2.15GB/175~185초), 여유 240G.
- 50GB 계획 experiments/english_background_50gb_cpp.json을 작성했다. 30GB C++ 계획 기준이며 목표 50000000000 bytes, 출처는 24 shard evidence(config_sha256 6043b4e3…가 파일럿 설정과 일치)다. 고정 20GB 부모·투영(59a32aea…)과 retained_unique_v3는 유지하고, signature_workers 16, 로컬 shard, 20GB 부모 보호 색인 보고서, delete_protected_index_after_prepare, budget_overrides(200/30)를 더했다. 디스크 추정: prepare 피크 약80GB(출력 약55GB+후보 DB; 20GB 재현 scratch 39.1GB 기준), build 피크 약172GiB.
- UTC2026-11-04T21:40경 tmux blt-bg50gb-nested-20261105-01에서 연결 실행기 runs/en-bg50gb-runtime-20261105-01/launch_50gb.sh를 시작했다. 색인·다운로드 두 tmux가 모두 exit0일 때만 진행한다. 이어서 shards.json의 24개 SHA256과 색인 보고서 SHA256을 계획에 고정하고, 파일 존재·hash 일치·실행 디렉터리 부재를 확인하고, 소스 manifest를 작성한 뒤 기존 conda로 run_background_expansion을 실행한다. 어느 하나라도 실패하면 실행하지 않는다. 로그는 launch_50gb.log에 남는다.

## 2026-11-05 확인 / 50GB 실행 시작·prepare 완료

- 선행 작업: 20GB 부모 보호 색인은 exit0(4892488문서, 1051.3초, DB SHA256 015b1634…, 보고서 SHA256 1cb06a94…)이고, 추가 shard 12개 다운로드도 exit0이다. 연결 실행기가 UTC2026-11-04T21:48:04에 shard 24개 hash와 색인 보고서 hash를 계획에 고정하고 검증을 통과했다(계획 SHA256 dc5e87b2…, 소스 manifest 43174883…, 시작 시 여유 224041771008bytes). 이어서 run en-patcher-bg50gb-nested-20261105-01을 시작했다. 서버 계획을 로컬 experiments/english_background_50gb_cpp.json에 반영했다.
- prepare: 21:48:05~23:01:10, 4382.2초. status=prepared, 13821660문서/50000001463 UTF-8 bytes, file_sha256 cc25c676decf6e204feecac9873170114d4dabe281a114fe83ecc21728d5459a, background.jsonl 56150837513bytes. 원래 배경 4891146문서는 보존됐다. 후보 10177366문서, row group 10219개, 24 shard 표집. 중복 제거는 정확(text/URL) 1246715건, 유사 137건이다. 정확 중복이 많은 것은 기존 12 shard에서 20GB 부모가 이미 채택한 문서가 후보로 다시 나오기 때문으로 보인다(가설). 최대 RSS 약666MB. 성공 후 보호 색인 DB만 삭제됐고 보고서는 남았다.
- build: 23:01:10 시작. UTC23:27:37 기준 블록 1241개(부모 800개 재사용 + 신규 441개, 누적 31028010557bytes, build 최대 RSS 약16.4GB), 여유 136G다. 신규 블록은 약114MB(gzip)다. 남은 약760블록이면 여유는 약49GB로 끝날 것으로 추정되며 최소 30GiB보다 크다.

## 2026-11-05 확인(KST 10:05) / 50GB 확장 완료·20GB 대비 비교

- run en-patcher-bg50gb-nested-20261105-01이 status=completed로 끝났다(tmux exit0, 전체 10471.1초). 시각(KST): prepare 06:48:05~08:01:10, build 08:01:10~09:03:54, fit 09:03:54~09:37:11(1996.2초, 투영 로딩 약14분, 특징 약6분, 경계 학습 1.09초, 임계값 15회 각 약47초, 최대 RSS 약8.39GB), compare 09:37:11~09:42:36(325초). 단계 산출물 SHA256: prepare 540ffc45…, build d0a835d8…, fit 9b23ba62…, compare 74083ad1….
- fit: status=validation_gate_failed. 선택 threshold는 0.375(20GB와 같음), 계수 [-4.35965, 0, 0, 2.51806, 0.23993]이다. 검증 F1 0.791227, precision 0.776009, recall 0.807053, entropy MAE 0.440795, 후보 패치 109406/teacher 105220, 평균 패치 4.24428.
- compare: 20GB 기준 재생 F1이 일치했다(baseline_replay_matches=true). F1 0.787836→0.791227, 차이 +0.003391, 111문서 paired bootstrap 95% [+0.002520, +0.004453]. precision 0.771715→0.776009, recall 0.804644→0.807053, entropy MAE 0.446096→0.440795, RMSE 0.659714→0.653391, Spearman 0.838882→0.840901, log loss 0.235453→0.233545, AUPRC 0.848883→0.852424. 0.90 게이트는 미달이다. 같은 검증 111문서를 임계값 선택에 재사용한 기술적 구간이며 독립 평가 증거가 아니다. BPB·속도·heldout 평가는 하지 않았다.
- 배경 크기별 검증 F1(동일 라벨, K8/W무제한): 1GB 0.764086, 5GB 0.780420, 10GB 0.785368, 20GB 0.787836, 50GB 0.791227. 크기를 늘릴 때마다 증가 폭이 줄고 있다(10→20GB +0.002468, 20→50GB +0.003391).
- 디스크: 여유 56G, 실행 디렉터리 176G(background.jsonl 56150837513bytes 포함). 정리는 사용자 승인 사항이다.

## 2026-11-05 / 10GB·20GB background.jsonl 삭제(사용자 승인)와 LMDB 현황

- 확인: 10GB(11224069328bytes)와 20GB(22182942710bytes) background.jsonl은 50GB background.jsonl의 같은 길이 앞부분과 바이트까지 같다. 앞부분 SHA256이 각 준비 보고서의 file_sha256(43a9b591…, ac9aed77…)과 같고, 끝난 바로 다음 바이트가 줄바꿈이다. 50GB 실행은 부모 문서를 순서대로 먼저 쓰는 중첩 표집이다.
- 사용자 승인으로 두 파일만 삭제했다. 직전 재확인: 전체 SHA256이 보고서와 같고 열린 fd가 없었다. 여유 59608756224→93015777280bytes. 감사 기록 runs/cleanup_authorized_20261105_bg10_20_jsonl.json에 크기, SHA, 복원 명령(head -c <bytes> 50GB background.jsonl)을 남겼다. 블록, 보고서, fit, 진행 기록은 보존했다.
- LMDB 현황: en-count-lmdb-full-20261025-01은 10GB(400블록, 10000002264bytes, 원본 보고서 d133f2e4…, complete, 37G)이고, en-blt20gb-compare-20261101-01/counts.lmdb는 20GB(800블록, 20000001834bytes, 원본 보고서 f4098e2f…, complete, 56G)다. 둘 다 블록에서 다시 만들 수 있다. 50GB LMDB는 20GB LMDB를 복사해 신규 1200블록을 더하는 경로로 만들 수 있으며, 추정 크기는 약100~115GB다.
- 사용자 승인으로 10GB LMDB(runs/en-count-lmdb-full-20261025-01/counts.lmdb, data.mdb 39354654720bytes, complete/400블록)와 사전 점검 LMDB(runs/en-count-lmdb-preflight-20261025-02/counts.lmdb, 838434816bytes)를 삭제했다. 직전 확인: 링크 수 1, 열린 fd 없음, plan/run_report 참조 없음. counts.report.json과 로그는 보존했다. 여유 93015744512→133208858624bytes. 감사 기록은 runs/cleanup_authorized_20261105_lmdb10gb_preflight.json이다. 20GB LMDB(56G)와 모든 블록은 남겼다.
- 로컬 shard: datasets/fineweb-local에 FineWeb 원본 parquet 24개, 47G가 있다. LMDB는 count 블록에서 만들므로 shard를 쓰지 않는다. shard는 prepare 재실행(50GB 초과 확장, background.jsonl 복원)에만 쓰이며 HF에서 다시 받을 수 있다(20GB 재현 때 12개 872초).
- 확장분 동질성 점검(보고서 재계산, 문서 수 기준). 누적 length_bands(short≤1KiB/medium≤8KiB/long)는 10GB 783434/1680848/288097(28.5/61.1/10.5%), 20GB 1617780/2515194/758172, 50GB 3470300/9027182/1324178이다. 증분만 보면 10→20GB는 834346/834346/470075(39.0/39.0/22.0%), 20→50GB는 1852520/6511988/566006(20.7/72.9/6.3%)이다. 원인은 expand_to_disk의 길이 구간 라운드로빈이다. 구간마다 한 문서씩 번갈아 뽑아 후보가 남는 동안 구간별 문서 수가 같아지고, 후보 풀(shard별 quota=필요 바이트)이 먼저 바닥난 구간이 빠지면 나머지 구간이 채운다. 따라서 증분 사이 길이 구성이 크게 다르다. 출처 동일성(같은 repo/revision/CC-MAIN-2025-05, 고정 shard 목록, 문서별 shard/row_group/row/document_id/url), 비중복(정규화 SHA256·URL 정확 중복, MinHash LSH b9r13 유사 중복을 부모와 5개 분할에 대해 검사), 중첩(부모 바이트 접두사)은 보장된다. 분포 동질성(길이·도메인·품질 점수)을 검사하거나 맞추는 기준은 없다. 50GB F1 증가에는 배경 크기와 구성 변화가 섞여 있을 수 있다(가설, 미검증).

## 2026-11-05 KST 11:11 / 증분 구성 진단과 길이 구간 바이트 목표 표집 구현(사용자 지시)

- 사용자 지시: (1) 50GB 증분 분포 진단, (2) 이후 확장의 표집 규칙 개선. 로컬 shard는 사용자가 별도 저장소에 백업한 뒤 삭제한다(경로 /home/itcmaster/projects/blt-cache/datasets/fineweb-local/9bb295ddab0e05d785b879661af7260fed5140fc, parquet 24개와 shards.json, 49775048681bytes). 진단이 언어 점수를 shard에서 읽으므로 진단이 끝날 때까지 삭제하지 않는다.
- (2) 구현: disk_dedup.expand_to_disk에 band_byte_shares를 추가했다(opt-in). 부모 문서를 쓴 뒤, 추가 바이트/목표 비율이 가장 작은 구간에서 그 구간의 무작위 순서대로 한 문서씩 뽑는다. 구간이 바닥나면 다른 구간으로 채우지 않고 ValueError다. 결과에 band_selection(목표, 구간별 추가 바이트, 달성 비율, 최대 절대 편차, 남은 후보)을 남긴다. prepare_disk 계획 키는 band_selection_policy=band_byte_target_v1, band_byte_shares, band_share_tolerance(0~1 실수, 초과 시 data_preparation.json을 쓰기 전에 실패), candidate_oversample(≥1, retained_unique_v3에서만, shard quota 배수)이다. 키가 없으면 기존 라운드로빈 경로가 바이트까지 같다.
- (1) 구현: scripts/analyze_background_composition.py(읽기 전용). data_preparation.json의 parent_background를 거슬러 원본2241→100MB→1GB→5GB→10GB→20GB→50GB 경계를 만들고, 경계마다 누적 텍스트 바이트를 보고서와 대조한다(불일치 시 실패, 접두사 SHA는 기록). 구간별로 길이 분위수, 구간 문서/바이트 비율, host/TLD 분포, shard 수, 로컬 shard와 id를 대조한 language_score/token_count를 계산한다. 비교는 증분 대 부모 누적, 증분 대 직전 증분, 구간 대 자연 분포(로컬 shard 전체 중 256~65536바이트 행)이고, 지표는 KS(길이, 언어 점수)와 JS(구간 바이트·문서, TLD, host)다. 구간 내 짝/홀 반분 비교를 잡음 기준선으로 둔다.
- 검증: 새 실행 사본 runs/en-bg50gb-composition-20261105-01(source manifest d775280e…)에서 기존 conda로 42개가 통과했다(신규 test_band_byte_target_selection, test_background_composition, 계획 키 검증 5건과 허용 오차 실패 검사 추가). 첫 실행의 오류 1건은 테스트가 같은 실행 디렉터리에서 build_native를 다시 부른 문제였고, 두 번째는 테스트 괄호 오류였다. 구현 변경은 없었다.
- KST 11:10 tmux blt-bg50gb-composition-20261105-01에서 50GB 진단을 시작했다(--natural-reference, 출력 composition.json).
- 단계별 표집 이력(준비 보고서 확인): 100MB/1GB/5GB/10GB 증분은 원래 4개 shard에서 shard별 quota 없이 뽑았다(Python 경로, 읽은 row group 52/514/2275/2844). 10→20GB 증분은 새 12개 shard에서 redistribute_remaining_v2로, 20→50GB 증분은 24개 shard(기존 12+추가 12)에서 retained_unique_v3로 뽑았다. 모든 단계가 길이 구간 라운드로빈이다. 따라서 50GB는 shard 집합, quota 규칙, 길이 구성이 서로 다른 6개 증분의 혼합이다. 자연 분포에 맞추든 50GB 구성에 맞추든 새 증분이 기존 50GB 전체와 같은 분포가 되지는 않는다. 50GB 구성에 맞추는 방법도 길이 한 축만 맞출 수 있다.
- KST 11:19 진단 v1 완료(composition.json SHA256 9ffaa8c5…, 508.9초, 최대 RSS 약5.9GB, 언어 점수 부여 11069281문서). 7개 경계 모두 누적 바이트가 일치했고, 접두사 SHA는 100MB~50GB 6개 모두 일치했다(원본은 비교 대상 없음). 구간별 바이트 비율(short/medium/long %): 원본 6.0/28.3/65.7, →100MB 5.3/25.6/69.1, →1GB 5.7/27.2/67.0, →5GB 7.4/35.1/57.5, →10GB 3.4/73.0/23.7, →20GB 5.5/26.4/68.1, →50GB 4.1/68.6/27.3. 자연 분포(로컬 24 shard 중 256~65536바이트 21986755행)는 4.3/61.7/33.9이다. 언어 점수 평균은 →20GB 0.9329, →50GB 0.9366, 자연 0.9361이다. TLD JS는 모든 구간 대 자연에서 ≤0.022이다. 한계: 짝/홀 반분 기준선이 라운드로빈 주기와 겹쳐 KS 0.23~0.54로 부풀었다. 설계 오류로 판단해 v1을 보존하고, 고정 seed(20261105) 무작위 반분으로 고쳐 KST 11:23 tmux blt-bg50gb-composition-20261105-02에서 composition-v2.json으로 재실행했다(테스트 통과, source_manifest-v2).
- FineWeb shard 구성 규칙(공식 카드, datatrove DiskWriter 코드, 로컬 24개 file_path 실측): 파일명 FFF_RRRRR.parquet의 RRRRR은 처리 작업 rank(0~49), FFF는 그 rank 출력이 max_file_size(약2.15GB)를 넘을 때마다 늘어나는 분할 번호(000~005)다. 24개 모두에서 각 문서의 CC WARC 번호를 50으로 나눈 나머지가 rank와 같았다. 즉 rank r은 CC-MAIN-2025-05의 100개 segment 전체에서 번호≡r(mod50)인 WARC 파일을 처리한다. shard당 WARC 192~345개, 92~100 segment이고, WARC 파일이 두 shard에 걸친 경우는 7436개 중 1개(같은 rank의 분할 경계)다. 파일 안의 WARC 순서는 segment 순이 아니다. dump 단위 MinHash 중복 제거는 FineWeb가 이미 수행했다. 따라서 shard는 주제나 도메인으로 묶인 것이 아니라 crawl 전체에 걸친 WARC 파일의 계통 표본이다.
- 누적 길이 구성(진단 v1의 구간 바이트×비율, 바이트 %, short/medium/long): 20GB 누적 5.4/39.8/54.8, 50GB 누적 4.6/57.1/38.3, 자연 분포 4.3/61.7/33.9. 증분 사이 편차는 크지만 50GB 전체는 자연 분포와 medium/long에서 약 4.5%p 차이다. 사용자 지적대로 처음부터 다시 만드는 안(3)은 기존 작업을 버리는 것이라 기본안에서 제외한다. 기본 방향: 50GB를 유지하고, 다음 확장분은 자연 분포 기준으로 추가한다. 그러면 누적 구성이 자연 분포에 더 가까워진다(가설: 100GB 기준 약 59.4/36.1 추정). 기존 1~50GB F1 곡선은 크기와 구성 변화가 섞인 결과라는 해석상 한계로 기록하며, 결과를 폐기하지는 않는다.
- 사용자 결정(KST 11:30경): 해석상 한계는 중요하지 않다. 앞으로 확장은 각 shard에서 균등하게 뽑는 규칙으로 통일한다. 이에 따라 아직 실행에 쓰이지 않은 band_byte_target_v1을 제거하고 shard_uniform_v1로 교체했다. 계획 키 selection_policy=shard_uniform_v1은 retained_unique_v3에서만 허용한다. 선택 단계에서는 고정 shard 목록 순서대로 shard별 후보를 seed로 섞고, 추가 바이트가 가장 적은 shard에서 다음 문서를 뽑는다(길이 구간 구분 없음). shard가 바닥나면 다른 shard로 채우지 않고 ValueError다. 고정 목록 밖 shard의 후보도 거부한다. 결과에는 shard_selection(shard별 추가 바이트, 최대-최소 차, 남은 후보)이 남는다. DiskDeduplicator.add는 성공 시 행 identifier를 반환한다(참 값이라 기존 호출과 호환). 키가 없으면 기존 라운드로빈 경로가 바이트까지 같다. candidate_oversample은 유지했다.
- 검증: runs/en-shard-uniform-validation-20261105-01(source manifest e4d3ea41…)에서 기존 conda로 42개가 통과했다. 신규 test_shard_uniform_selection은 shard별 추가 바이트 차이가 문서 1개 이하이고 보고서 값과 실제 출력이 일치하는지, 같은 seed에서 출력이 같은지, 고갈·목록 밖 shard·빈 shard·잘못된 목록을 거부하는지를 확인한다. 계획 키 검증 4건과 shards 전달 확인도 포함했다. 첫 실행은 테스트 파일의 중복 메서드 헤더로 IndentationError가 났고, 테스트만 고쳤다.
- FineWeb 규모: CC-MAIN-2025-05에는 shard 300개가 있고(rank 50개×분할 최대 6개), 지금까지 원래 4개와 고정 24개를 썼다. FineWeb 전체는 dump 약 110개, 52,453,695,892행, 54.8TB다(공식 카드).

## 2026-11-05 KST 11:40 / 한국어 NIKL+FineWeb2 combine 소요 원인 코드 검토(사용자 질문)

- 사용자 질문: Neuron에서 진행 중인 한국어 병합/분할이 왜 오래 걸리는가. itcerdo에서는 관련 프로세스가 없었고 runtimelog에도 해당 로그가 없어 실측 진행률은 확인하지 못했다. neuron/runtime/blt_hf/entropy_fineweb.py combine_corpora 코드만 검토했다.
- 단순 병합+비율 분할이 아닌 이유: 정확 중복과 ID/정규화 본문 연결로 문서 그룹(union-find)을 만들고, 연결된 FineWeb 문서가 기존 NIKL train/validation/test 역할을 따르게 해서 분할 간 누출을 막는다. 새 그룹만 seed42/1%/1% 해시 정책으로 나눈다.
- 느린 원인(코드상 추정, 미측정): (1) FineWeb2 전체 문서를 단일 Python 프로세스로 한 건씩 처리한다(SHA256, NFC 정규화, SELECT 3회, INSERT 2~3회). (2) 모든 본문 전체를 SQLite records에 넣고 색인 3개(identities, exact_text, links PK)를 무작위 키로 갱신한다. (3) 256문서마다 commit하는데 기본 동기화라 fsync가 반복된다. 디스크 예산 검사도 256문서마다 한다. (4) 병합 뒤 모든 행의 group_id를 UPDATE하므로 본문 포함 DB 전체가 다시 쓰인다. (5) GROUP BY/ORDER BY exact_sha로 전체를 다시 정렬해 쓴다. Neuron /scratch(병렬 파일시스템)에서 SQLite의 작은 무작위 I/O와 fsync는 특히 느릴 수 있다(가설).
- 개선안(미구현, 사용자 결정 대기): 본문은 DB에 넣지 않고 문서별 해시와 위치만 shard 병렬로 계산한다. NIKL 해시는 메모리 dict로 연결하고, 그룹·역할은 해시 정렬로 정한 뒤 원본에서 분할 파일을 스트리밍으로 쓴다. 현 구현과 출력 파일 바이트 동일성을 합성·부분 자료로 검증한 뒤 교체한다.
- 사용자 결정(KST 11:45경): 한국어 combine을 C++로 바꿔 다시 진행한다. 진행 중인 Neuron SQLite 통합은 6,646,000문서 처리 시점이며, 재개 기능이 없다(출력 mkdir exist_ok=False, --resume 없음). 중단 여부는 사용자가 정한다.
- 구현: 기존 entropy_fineweb.py와 entropy_corpus.py는 수정하지 않았다. 다운로드·감사 보고서가 두 파일의 코드 SHA를 고정하므로, 수정하면 기존 다운로드를 쓸 수 없다(SHA 2001d151…, b101a696… 그대로). 새 neuron/runtime/blt_hf/native/combine.cpp는 C++11이고 외부 라이브러리를 쓰지 않는다. 엄격한 UTF-8·JSON 파싱, Python json.dumps(ensure_ascii=False)와 같은 재인코딩, SHA-256, 공백 접기, NFC 빠른 검사, 그룹 union-find·역할·키·대표 선택, 버킷 쓰기·병합을 담당한다. NFC 표는 빌드할 때 실행 중인 Python unicodedata에서 생성한다. 결합 문자, NFC가 바뀌는 문자, 합성의 둘째 성분, 한글 V/T 자모가 있는 문서는 Python unicodedata로 처리한다. 새 blt_hf/entropy_combine.py는 기존 입력 검증을 그대로 두고 (1) shard 병렬 스캔, (2) C++ 그룹화, (3) 해시 첫 바이트 256버킷 쓰기와 정렬 병합으로 같은 분할 파일·manifest를 만든다. FineWeb 격리 원장은 quarantine.jsonl이다. bundle FILES에 3개 파일을 추가하고 runtime-manifest를 refresh했다(21개 검증). neuron/command.md에 6-5 빠른 통합 명령을 추가했다.
- 검증(itcerdo, runs/ko-combine-native-validation-20261105-01, 기존 conda, g++ 13.3 -Wall -Wextra 경고 0): 신규 5개와 기존 entropy 19개, 총 24개가 통과했다. 모든 code point(서로게이트 제외)와 접두 조합에서 C++ 결과가 Python NFC+공백 접기 digest와 같거나 Python으로 넘겨졌다. 무작위 3만 문자열, JSON 5천 건 왕복(키 순서와 ensure_ascii 혼합)과 잘못된 입력 12종 거부를 확인했다. 합성 NIKL+FineWeb 25 shard(정확·정규화 복사, NIKL 역할 상속, 빈 본문 3종, 분해 한글, 제어 문자)에서 train/validation/test.jsonl과 manifest.json이 기존 combine_corpora와 바이트까지 같았고, 보고서 주요 필드도 같았다. 식별자 충돌, NIKL 역할 브리지, shard 변조는 기존과 같이 실패했다. 첫 실행의 실패 1건은 테스트가 격리 원장을 splitlines()로 읽어 U+2028에서 잘린 문제였고, 테스트만 고쳤다.
- 실제 자료 대조: FineWeb2 kor_Hang 고정 revision shard 000_00000을 itcerdo datasets/fineweb2-kor-sample에 받는 중이다. 앞 30만 문서를 25 shard로 나누고 합성 NIKL과 함께 native/SQLite 결과를 비교한다(tmux blt-ko-combine-real-check).
- 실제 자료 대조 결과(KST 12:07): FineWeb2 kor_Hang 고정 revision train/000_00000.parquet(4844133014bytes, SHA256 0bb6e638…c7ec)의 앞 30만 문서(1138484401 UTF-8 bytes)를 25 shard로 나눴다. 합성 NIKL fixture와 함께 처리한 결과, native와 기존 SQLite combine_corpora의 train/validation/test.jsonl과 manifest.json(SHA256 6a978ac2…)이 바이트까지 같았다. 보고서 9개 필드(splits, documents, 입력 문서·바이트, 격리 문서·바이트, 정확 중복, policy, manifest_sha256)도 모두 같았다. 소요 시간은 itcerdo 로컬 NVMe, workers 8 기준 native 10.6초, 기존 130.0초다. Neuron 병렬 파일시스템에서는 기존 구현이 훨씬 느릴 수 있다(사용자 보고: 수 일에 660만 문서). 표본 원본과 산출물은 runs/ko-combine-native-validation-20261105-01과 datasets/fineweb2-kor-sample에 보존했다.
- 사용자 승인으로 neuron/ 6개 파일(bundle.py, command.md, runtime-manifest.json, runtime/blt_hf/entropy_combine.py, runtime/blt_hf/native/combine.cpp, runtime/tests/test_hf_entropy_combine.py)만 커밋 88ec437 "[T12][mac] Add native NIKL+FineWeb2 combine"으로 올리고 origin/main에 push했다(3308e13..88ec437). 다른 미커밋 로컬 변경은 포함하지 않았다. Neuron 갱신과 실행은 사용자 담당이다.
- 사용자 승인(백업과 검증은 사용자가 직접 완료)으로 itcerdo datasets/fineweb-local(FineWeb CC-MAIN-2025-05 parquet 24개, 49775048681bytes)을 UTC2026-11-05T03:54:10에 삭제했다. 직전 확인: 이 shard를 읽는 진단 v2는 exit0으로 완료(composition-v2.json, 512.6초), 열린 fd 없음. 고정 SHA256 목록은 runs/fineweb_local_shards_9bb295dd…_sha256.json에 보존했다. 감사 기록은 runs/cleanup_authorized_20261105_fineweb_local_shards.json이다(파일 목록, 복원 방법: 고정 revision 재다운로드 또는 사용자 백업). 여유 123968675840→173743886336bytes. 다음 확장의 prepare에는 shard 재확보가 필요하다.

## 2026-11-05 KST 16:30 / 50GB BLT 비교 준비: native LMDB 구축기

- 사용자 결정: 50GB BLT 적용·비교로 진행한다. LMDB 구축은 C++로 하며, 이 LMDB 실행에 한해 최소 여유를 30GiB로 낮춘다.
- 20GB 비교 실측(runs/en-blt20gb-compare-20261101-01): Python LMDB 구축 159567.9초(약 44.3시간, 10197855299 입력 행 → 875504902 문맥), quality 약 6분, generation 약 24분, timing 약 1분. 같은 방식이면 50GB 신규 블록 1200개(약 156억 행)는 약 5~6일로 추정된다.
- 구현: scripts/native/lmdb_build.cpp(C++17, zlib와 시스템 liblmdb.so.0에 링크, 헤더가 없어 쓰는 API만 선언)와 scripts/build_lmdb_native.py를 추가했다. 블록 SHA256을 병렬로 검증한 뒤 다음 순서로 진행한다. (1) 문맥 해시 표본(1/modulus)을 읽으며 블록별 행 수를 보고서와 대조하고 고유 문맥 수를 추정한다. (2) 메모리 예산으로 키 범위 패스 수를 정하고, 표본 분위수를 경계로 삼는다. (3) 패스마다 전체 블록을 병렬로 읽어 범위 안 문맥만 4096 샤드 해시맵에 합산하고, 정렬 병합으로 MDB_APPEND한다. 검증 규칙은 Python 구축기와 같다(헤더 config, 짝수 길이·최대 문맥, 문맥 ID 어휘·pad·EOS, 행 안 token 중복, count>0, 블록별 행 수). 메타데이터 형식도 같고, builder 항목만 추가된다. 행 안 entry는 token 오름차순이다(조회는 순서 무관이고 행 합계는 정수 합).
- 검증(itcerdo runs/en-lmdb-native-validation-20261105-01, 기존 conda, g++ -Wall -Wextra 경고 0): tests/test_lmdb_native.py 2개가 통과했다. 합성 5블록에서 패스 1/3/7과 예산 기반 자동 분할 모두 Python 구축기와 문맥별 count·키 순서·메타데이터 식별값이 같았고, 패스 수와 무관하게 값 바이트도 같았다. 부분 블록 일치, 블록 변조, manifest 불일치, pad·EOS 문맥, 중복 token, config 불일치, 행 수 불일치는 실패로 처리된다. 실제 50GB 블록 2개(24876924행): native는 패스 3개로 19524535문맥을 약 19초에 썼다(표본 추정 19331072). LMDB 크기는 811M로, 같은 블록의 Python 구축기 결과(534M)보다 크다. 이 Python 결과는 진행 중이라 최종 비교 전 값이다. Python 결과와의 대조는 진행 중이다.
- 비교 실행 스크립트 scripts/run_blt50gb_comparison.sh를 작성했다. 고정 입력 hash 검증(50GB fit 9b23ba62…, build d0a835d8…, prepare 540ffc45…, 파일럿 설정, 모델) → native LMDB(map 192GiB, 22스레드, 예산 28GiB, RSS 48GiB, 최소 여유 30GiB, 출력 상한 160GiB) → quality → generation → timing → total(새 50GB timing 기준) → run_report 순이다. 기존 conda만 쓰고 model-venv와 .venv는 쓰지 않는다.
- 실제 블록 대조 결과: 50GB 블록 2개에서 native와 Python LMDB의 엔트리 19524536개(메타데이터 포함)를 순서대로 비교했고 키·count 불일치는 0개였다. 메타데이터 식별값 13개도 모두 같았다. 시간은 native 19.6초, Python 346.0초이고, 크기는 native 811M, Python 1.3G다.
- KST 16:32 tmux blt-blt50gb-compare-20261105-01에서 run en-blt50gb-compare-20261105-01을 시작했다(source manifest 381742fa…, run 스크립트 478da2e9…, build_lmdb_native.py 2964c9c0…, lmdb_build.cpp d71136e3…). 기존 conda interpreter(/home/itcmaster/miniconda3/envs/phdq_blt_hf/bin/python)를 확인했고, 고정 입력과 모델 hash 검증을 통과했다. 시작 시 GPU는 유휴, 디스크 여유는 161G였다.

## 2026-11-05 KST 16:55 / Neuron native combine 실패: Conflicting FineWeb document identity

- 사용자 보고: Neuron에서 entropy_combine(workers 8)이 scan을 698.8초에 끝냈다(25 shard, 60874355문서, 입력 SHA/문서/바이트 검증 통과). 이어 group 단계에서 ValueError "Conflicting FineWeb document identity"로 실패했다. 같은 FineWeb id에 서로 다른 본문이 있다는 판정이다. 기존 SQLite combine_corpora도 같은 조건에서 같은 오류로 실패하는 계약이다. 기존 실행은 6686000문서에서 멈춰 그 지점에 닿지 않았을 수 있다(가설). 실제 데이터 문제인지 구현 문제인지는 아직 확인하지 않았다.
- 진단 도구 neuron/runtime/blt_hf/entropy_combine_diagnose.py(읽기 전용)를 추가했다. 실패 출력에 남은 work/records-*.npy의 id SHA·본문 SHA로 충돌 id를 찾고, 해당 shard 줄에서 예시(id, 위치, 바이트, 앞 60자, NFC·공백 정규화 후 동일 여부)를 보고한다. 충돌 테스트에 진단 검사를 추가했다(itcerdo runs/ko-combine-native-validation-20261105-02, 24개 통과). bundle FILES에 추가하고 refresh했다(22개 검증). 아직 커밋·push하지 않았다.
- 50GB native LMDB: 블록 2000개 SHA 검증 448.7초, 표본 단계 완료(911.2초 누적). 입력 25757505716행, 문맥 추정 1529863168개, 행당 entry 1.97, 집계 추정 167.9GB, 패스 6개.

- 2026-11-05 KST: 사용자 승인으로 진단 도구, bundle FILES, runtime manifest, 충돌 진단 테스트를 커밋 2b8e371로 push했다. neuron/command.md의 붙여넣은 내용은 제외했다.

## 2026-11-05 KST / FineWeb ID 충돌 진단 결과와 연결 유지 옵션 구현

- Neuron 진단(사용자 실행) 결과: 60874355문서 중 충돌 ID 9개, 문서 18개. 모든 그룹이 2문서이고 shard 1,3,10,11,14,16,18,19,20,23에 걸쳐 있다. 예시 5건 모두 NFC·공백 정규화 후에도 본문이 다르다(같은 사이트의 다른 페이지로 보임). 구현 오류가 아니라 상류 데이터에서 같은 WARC UUID가 다른 레코드에 쓰인 경우로 판단한다(원인은 가설).
- 사용자 결정: ID는 중복 제거 키(원문 SHA)가 아니라 분할 그룹 연결 키이므로, 그룹이 분할을 넘지 않는 규칙만 유지한다. 충돌 단언은 무결성 보장에 필요하지 않다(shard SHA·문서·바이트 검증이 담당).
- 구현: entropy_combine에 명시적 opt-in `--link-id-conflicts`를 추가했다. bltc_group이 충돌 문서를 표시하고, 두 본문을 모두 유지하며 기존 ID 링크로 한 그룹에 묶는다. 충돌 원장 id_conflicts.jsonl(id, 원문 SHA, 파일, 줄, 분할)을 쓰고, manifest의 fineweb_id_conflict_policy와 report에 그 SHA를 기록한다. 기본값은 기존처럼 실패한다. 기존 SQLite 기준 구현은 다운로드 보고서에 코드 SHA로 고정되어 있어 수정하지 않았다.
- 검증(itcerdo runs/ko-combine-native-validation-20261105-03, phdq_blt_hf): 25개 테스트 통과. 추가 테스트로 다음을 확인했다. 충돌이 없으면 옵션을 켜도 분할 요약이 기준과 같다. 충돌 두 문서는 같은 분할에 둘 다 출력된다. 나머지 분할 줄 집합은 충돌이 없는 기준 실행과 같다. 원장 위치와 SHA도 일치한다. 첫 실행은 테스트 코드가 splitlines로 본문의 U+2028에서 줄을 잘라 실패했고, '\n' 분할로 고쳤다. bundle refresh 결과 22개 검증. 커밋·push는 승인 대기다.

- 2026-11-05 KST: 사용자 승인으로 --link-id-conflicts 구현·테스트·runtime manifest를 커밋 df757b3으로 push했다(neuron/command.md 제외). Neuron v002 실행은 사용자가 한다.

## 2026-11-05 KST 20:50 / 50GB BLT 비교 완료와 20GB 대조

- run runs/en-blt50gb-compare-20261105-01 status=completed, finished UTC 09:40:16(KST 18:40). 산출물 SHA: quality f260fb65…, generation 1581b43b…, timing 6d9511ff…, total 60eea769…
- native LMDB: 2000블록, 입력 25757505716행 → 문맥 1530498877개, data 72464367616bytes(du 68G). 전체 5478.1초(SHA 검증 448.7초, 표본 462.5초, 패스 6개 각 663~850초, 피크 RSS 23.8GB). 20GB Python LMDB는 159567.9초, 문맥 875504902개였다.
- 품질(333문서/1497578바이트, 같은 신경망 기준 0.810648): count BPB 20GB 0.812900 → 50GB 0.812976. 차이 +0.002252 → +0.002328(95% [+0.001484, +0.003253]). test +0.002753, wikipedia +0.002118. 0.01 허용은 통과하지만 신경망보다 나쁘고 20GB보다 개선되지 않았다(구간 겹침).
- 경계: TP 275900 / FP 121528 / FN 62998. precision 0.6942, recall 0.8141, F1 0.749396. 20GB F1 0.745449 대비 +0.003947이며 FP가 3665 줄었다.
- 생성 18쌍: 신경망과 같은 ID 0/18(20GB도 0/18). 신경망 출력은 기록 sampling과 18/18 일치, 754.44초(20GB 754.41초). count 24554바이트 / 631.5초 / EOS 10 / UTF-8 18/18. 20GB count는 26211바이트 / 696.4초 / EOS 9였다.
- 시간(8입력, 각 10회 평균 합계):
  - 패처 단독: 초기 0.0735 / 0.8559초, 32바이트 증분 2.3349 / 0.0778초.
  - 전체 모델: 초기 0.2442 / 1.0382초(4.25배 느림), 32바이트 증분 7.8658 / 6.0769초(1.294배 빠름), 초기 포함 전체 8.1099 / 7.1150초(1.140배 빠름).
  - 20GB 증분 1.280배, 전체 1.138배와 같은 수준이다. replay 대조(warm/fresh 경계·logits, 기준 ID)는 모두 true.
- 판정(측정 범위 한정): 50GB로 늘려도 BPB 열세와 신경망 출력 불일치는 해소되지 않았다. 경계 F1만 소폭 개선됐다. 전체 모델 증분 이점은 1.29배, 초기 포함 1.14배로 20GB와 같다. 배경 데이터 규모가 BPB 격차의 주원인이 아니라는 근거로 보며, K=8 문맥 count 모델의 표현 한계라는 해석은 가설이다.

## 2026-11-05 KST 21:03 / 20GB·50GB C++ count 백엔드 BLT 평가 시작

- 사용자 요청: 20GB와 50GB 비교를 C++ count 백엔드로도 실행한다(초기·전체 시간 단축 확인).
- 기존 실행기 scripts/evaluate_cpp_blt_patcher.py(10GB에서 사용)를 그대로 쓴다. 신경망 / Python count / C++ count를 같은 실행에서 측정하고, 모든 청크에서 Python·C++의 경계·logits·NLL 완전 일치를 요구한다. 시간은 8입력 초기 + 동일 32바이트 증분이고, 18개 생성의 C++ 재생은 Python과 ID·문자열이 일치해야 한다.
- 수정 1건: C++ 커널 기준 보고서(en-count-cpp-compare-20261029-02, 10GB 적합 규칙)는 rule이 아닌 count_config와 커널 SHA(e1649434…)만 대조한다. 20GB/50GB 적합 계수가 달라 기존 검사에서 실패하기 때문이다. Python/C++ 정확성은 매 청크에서 재검사하므로 판정력은 줄지 않는다. 품질·전체·생성 기준과의 rule 대조는 유지한다.
- 관련 코드 해시는 로컬, 20GB 고정 소스, 50GB 고정 소스가 모두 같다(count_patcher.cpp e1649434…, 평가기 수정 전 8580ebf3…). 수정 평가기 1464ce08…, 실행 스크립트 scripts/run_blt_cpp_eval_20_50gb.sh d26edb75…
- 실행: runtime runs/en-blt-cpp-eval-runtime-20261105-01(50GB source 복사 + 두 파일, source_manifest 030b6698…), tmux blt-cpp-eval-20261105-01, conda phdq_blt_hf. 출력은 runs/en-blt20gb-cpp-eval-20261105-01 다음 runs/en-blt50gb-cpp-eval-20261105-01. UTC 12:03 20GB 시작, 고정 해시 검사 통과 후 모델 로드.

## 2026-11-05 KST / Neuron combine v002 실패: 데이터 계약 검사의 중복 ID

- 사용자 보고: v002(--link-id-conflicts)가 scan 715초, group·id_conflicts(ids 9, documents 18) 1343.5초를 지나 merge 256버킷을 5506.9초에 끝냈다. 이후 최종 inspect_dataset에서 "Duplicate document identity: ('FineWeb2:kor_Hang', '<urn:uuid:48bdea25-…>')"로 실패했다(report.json 미작성).
- 원인: 학습 데이터 계약 검사(entropy_data.inspect_dataset, 학습 시작 시에도 호출)가 train/validation에서 (source, id) 유일성을 요구한다. 내 합성 테스트에서는 충돌 그룹이 검사 대상이 아닌 test에 배정되어 이 경로를 놓쳤다.
- 수정: manifest의 fineweb_id_conflict_policy가 있으면 원장 SHA를 검증하고, 원장에 (id, 원문 SHA)가 기록된 문서에만 중복 ID를 허용한다. 원문 SHA 중복 금지와 분할 간 텍스트 중복 금지는 그대로다. 테스트 추가: 원장이 없거나 일부만 있거나 변조되면 실패하는 단위 테스트, 그리고 결합 테스트의 충돌 그룹을 train에 강제 배정하는 검사. itcerdo runs/ko-combine-native-validation-20261105-04에서 26개 통과, bundle refresh 22개 검증. 커밋·push는 승인 대기다.
- 다음: Neuron에서 새 출력 v003으로 재실행(사용자). v002는 재개를 지원하지 않는다.

- 2026-11-05 KST: 사용자 승인으로 entropy_data 원장 기반 중복 ID 허용·테스트·runtime manifest를 커밋 8f6a82c로 push했다(neuron/command.md 제외).

- 2026-11-06 KST: 사용자 실행 결과 v002 분할이 수정된 inspect_dataset을 통과했다(train 59791622문서 / 232722508043bytes, validation 609471문서 / 2384020729bytes). report.json이 없어 사용자 결정으로 v003을 처음부터 재실행한다. 완료 후 v002와 분할 SHA를 대조한다.

## 2026-11-06 KST / 20GB·50GB C++ count 백엔드 BLT 평가 결과(retrospective 확인)

- tmux blt-cpp-eval-20261105-01 완료. 20GB는 UTC 12:03 시작, 50GB는 12:51:12 종료(KST 11-05 21:51). 출력 runs/en-blt20gb-cpp-eval-20261105-01, runs/en-blt50gb-cpp-eval-20261105-01(quality/timing/generation status=completed).
- 정확성: 두 실행 모두 928청크에서 Python·C++ 패치 길이·전체 logits·NLL이 완전히 일치했다. 기존 Python/신경망 보고서와의 경계 불일치 0, NLL 차이 0. BPB(+0.002252 / +0.002328)와 F1(0.745449 / 0.749396)은 기존 Python 결과와 같다. C++ 생성 18개는 Python 출력과 ID·문자열이 18/18 일치했다.
- 시간(8입력, 각 반복 10회 중앙값의 합, 순서는 신경망 / Python / C++):
  - 20GB: 초기 0.2439 / 0.9666 / 0.4204초, 32바이트 증분 7.8528 / 6.1338 / 6.0721초, 초기+32 합계 8.0967 / 7.1001 / 6.4923초.
  - 50GB: 초기 0.2440 / 1.0020 / 0.4340초, 증분 7.8583 / 6.0719 / 6.0091초, 합계 8.1022 / 7.0739 / 6.4428초.
  - C++/Python: 초기 2.30배 빠름(20GB와 50GB 같음), 증분 1.01배, 합계 1.094배(20GB) / 1.098배(50GB).
  - C++/신경망: 초기 0.58배(20GB) / 0.56배(50GB), 즉 여전히 약 1.8배 느리다. 증분 1.293 / 1.308배, 합계 1.247 / 1.258배 빠르다.
- 판정(측정 범위 한정): C++는 출력을 바꾸지 않고 초기 count 비용을 절반 이하로 줄였다. 초기+32 합계 이점은 신경망 대비 1.14배에서 1.25배로 커졌다. 초기 단독은 여전히 신경망보다 느리다. 증분 구간의 추가 이득은 1% 수준이다. 생성 총시간(C++ 694.9 / 624.0초)은 Python과 다른 실행이라 속도 비교에 쓰지 않는다.

## 2026-11-06 KST / Neuron combine v003 완료(사용자 실행)

- korean-entropy-nikl-fineweb-native-v003 status=complete, elapsed 7991.6초. 단계 시간은 scan 710초, group·id_conflicts 1526초(ids 9, documents 18), merge 2429→5771초다.
- 분할: train 59791622문서 / 232722508043bytes(groups 59791607, FineWeb 59656641), validation 609471 / 2384020729, test 610715 / 2376034614. 전체 61011808문서, 정확 중복 400, 격리 2문서 / 5bytes(NIKL 감사분, FineWeb 격리 원장은 빈 파일), NIKL 원래 분할 보존 true.
- manifest_sha256 263ec42a…, id_conflicts 원장 7860e13c…, implementation code a74cf983… / source 8572471a… / library 5b07e1fb…(GCC 11.5.0, Unicode 14.0.0).
- train/validation 문서 수와 바이트는 v002 검사 결과와 같다. 분할 파일 SHA의 v002 대조는 사용자 실행을 기다린다.
- 평가기 수정과 실행 스크립트를 로컬 커밋 d12994d로 남겼다(push 안 함). 평가기와 그 의존 파일(benchmark_cpp_count_patcher, compare_blt_patchers, smoke_blt_count_patcher, native/count_patcher.cpp, blt_patcher, native_patcher, lmdb_counts)이 원래 추적되지 않았던 것을 확인했다. 단독 커밋으로는 실행이 재현되지 않으므로 의존 파일의 커밋 범위는 사용자 결정을 기다린다.

- 2026-11-06 KST: 사용자 실행 결과 v002와 v003 manifest의 splits·held_out_test(경로·SHA256)가 identical이다. 같은 입력·코드에서 native combine 분할 출력이 재현됨을 확인했다. v002(report.json 없음)는 v003과 중복이므로 삭제 가능하며, 삭제는 사용자가 결정한다. 학습에는 v003 manifest(263ec42a…)를 사용한다.

- 2026-11-06 KST: 사용자 승인으로 평가기 의존 7개 파일과 count_patcher.py 고정본(2518c559…, lmdb_counts가 쓰는 lookup 포함)을 커밋 8e49076으로, d12994d와 함께 push했다. 커밋된 파일 해시는 10/20/50GB 고정 소스와 같다.

## 2026-11-06 KST / 한국어 엔트로피 패처 CPT 학습 설계 결정(사용자 승인)

- 자료: v003 manifest(263ec42a…). 사용자 확인으로 개인정보는 검토 완료 자료이고, 근접 중복은 확인된 것으로 본다(FineWeb2 상류 MinHash 처리와 우리 정확·정규화 그룹 근거). 승인은 v003 분할 SHA를 그대로 쓰는 별도 manifest에 기록한다.
- 승인 설정:
  - 입력: 4096바이트 시퀀스에 문서를 BOS…EOS로 이어 붙인다. 문서 간 격리는 기존 osc EOS 마스크와 원래 512 sliding window가 담당한다. 이어지는 긴 문서에는 이전 512바이트를 손실 제외 문맥으로 붙인다.
  - 배치: step당 524288바이트(시퀀스 32 × 누적 4, 파일럿에서 조정). FP32 원본 가중치와 BF16 autocast, SDPA(eager와 일치 확인 후).
  - 최적화: AdamW(0.9, 0.95), wd 0.1, clip 1.0, peak lr 3e-4, warmup 5000 step 고정.
  - 스케줄: WSD. validation 고정 약 5000문서를 5000 step마다 평가하고, 최근 3회 동안 최저 BPB 개선이 0.002 미만이면 decay를 시작한다(그때까지 step의 10%, 최소 5000 step, 3e-5까지 선형). 상한은 1 epoch.
  - test는 학습 판단에 쓰지 않는다. 24시간 Slurm 작업을 신호 저장과 재개로 잇는다.
- 다음: entropy_data/entropy_train 구현(연결 시퀀스, 배치 forward, 바이트 위치 재개, WSD/정체 판정, 검증 표본)과 테스트 후 H200 파일럿.

## 2026-11-06 KST / 엔트로피 CPT 학습기 구현과 itcerdo 통합 점검

- 구현(neuron/runtime, 미커밋):
  - entropy_data: PackedStream(BOS…EOS 문서 연결, 고정 길이 시퀀스, 이어지는 문서 앞 512토큰 손실 제외 문맥, 바이트 위치 재개, max_documents/wrap)과 inspect_dataset_cached(최초 전체 검사 후 manifest SHA·분할 size/mtime이 같으면 재사용).
  - entropy_train: 백그라운드 배치 생성, micro-batch forward, FP32 master+AdamW와 BF16 forward/backward, WSD 스케줄, 정체 판정, rolling checkpoint(2개)와 final, 고정 표본 검증, 신호 저장과 재개. 기존 청크 단위 경로는 교체했다.
  - bundle.validate_job: max_seconds는 누적 상한이고 작업별 종료는 SIGUSR1(종료 10분 전)이 담당한다. 작업은 최소 30분 이상 남아야 한다.
  - train_entropy.sh: 기본 24:00:00. 설정 두 개를 새 항목으로 바꿨다(승인 false, 예산 null 유지).
- 정정(측정): 512 window는 층별 직접 attention 범위다. 14층이 쌓이면 수용 영역이 더 넓어서, 실제 패처의 전체 입력 logits는 마지막 512토큰만 넣은 결과와 다르다(작은 모델 최대 차이 1.66). 따라서 이어지는 문맥 512는 각 층의 window를 채울 뿐이며, 추론과 완전히 같은 문맥이라는 이전 설명은 틀렸다. 일반 LM 학습의 시퀀스 시작 근사와 같은 수준이다. 테스트는 같은 문서 구간 전체를 단독으로 넣은 결과와 비교하도록 고쳤다.
- 테스트(itcerdo runs/ko-entropy-train-validation-20261106-01, phdq_blt_hf): runtime 33개와 bundle 5개 통과, ResourceWarning 없음. 포함 항목: 모든 대상의 직접 window가 단독 문서와 같은지, 바이트 위치 재개가 같은 시퀀스를 내는지, 실제 BltPatcher(작은 구성)의 연결 logits와 구간 단독 logits 일치(eager/SDPA, FP32), master step·checkpoint 재개 동일성, micro-batch 분할 불변성, WSD/정체 규칙, 검사 캐시.
- 통합 점검(5090, 실제 B 패처, 영어 소형 셋 형식 변환, 한국어 학습 아님):
  - SDPA와 eager(BF16, 4096×2): 평균 logit 차이 0.022, 최대 1.44, 손실 0.5152 / 0.5149.
  - 실행 흐름: pilot 6 step 중단 → step-6 재개 → step 12 정체 감지로 decay(6 step) → step 18 final 저장과 전체 검증(111문서) → 재실행 시 already_finished. 종료 코드 0/0/0. rolling 2개 유지.
  - 처리량(SDPA, 5090): 4096×4~12는 약 66KB/s(peak 9.6~25.3GiB, micro-batch를 늘려도 속도 같음). 1024 66KB/s(학습 대상 비율 0.525), 2048 78KB/s(0.758), 4096 66KB/s(0.886), 8192 46KB/s. eager 4096×1은 19KB/s, ×2는 OOM.
  - 해석: window 512인데 SDPA가 T×T 전체를 계산해 4096에서 attention 비용이 선형층과 비슷하다. block-sparse(flex attention) 경로를 쓰면 개선 여지가 있다(가설). H200 처리량은 미측정이다.

## 2026-11-06 KST / flex attention 경로 추가와 설정 확정

- 원 BLT 학습 정밀도 확인: facebookresearch/blt bytelatent/distributed.py는 FSDP MixedPrecisionPolicy(param_dtype=bf16, reduce_dtype=float32)를 쓴다. 원본 파라미터와 optimizer는 FP32이고 계산만 BF16이다. 공개 가중치는 BF16으로 배포된다. 우리 FP32 master/AdamW + BF16 forward/backward와 같은 방식이다.
- 구현: entropy_train에 attention_backend=flex_attention을 추가했다. 학습·평가 forward에서 osc 마스크(인과, 같은 EOS 구간, 거리 < 512)를 BlockMask로 만들어 HF flex_attention 경로에 넘긴다. dense T×T 마스크와 쓰지 않는 entropy/patch 출력은 생략한다. 패처 dropout은 0이다.
- 검증(itcerdo 5090):
  - 작은 BltPatcher(FP32, CUDA): flex와 dense eager의 logits·기울기 일치 테스트 통과.
  - 실제 B 패처(BF16): flex와 SDPA logits 평균 차이 0.020, 최대 1.09. SDPA와 eager 차이(0.022 / 1.44)와 같은 수준이다.
  - 처리량(micro-batch당 16K 토큰): flex는 2048 113.9KB/s, 4096 132.0KB/s, 8192 139.0KB/s이고, 토큰 처리량은 길이와 무관하게 약 146~149K tok/s다. SDPA는 2048 79.9, 4096 67.0, 8192 45.3KB/s다. 8192 기준 flex가 SDPA보다 3.07배, SDPA 4096보다 2.07배 빠르다. 학습 대상 비율은 0.766 / 0.893 / 0.953이다. 65K 토큰 micro-batch는 32GB에서 OOM이었다.
  - flex 설정의 실제 run: pilot 3 step → 재개 → max_steps 상한 decay(10→14) → 최종 검증, 종료 코드 0/0, 138.8KB/s, peak 9.4GiB.
- 설정 확정(템플릿 두 개): sequence_length 8192, micro_batch 16, accumulation 4(step당 524288토큰), attention_backend flex_attention. 나머지는 이전 결정과 같다. 실제 H200 micro-batch 메모리는 파일럿에서 확인한다(5090 기준 16K 토큰당 약 9.4GiB이므로 131K 토큰은 약 60~70GiB로 추정).
- 최종 테스트: runtime 34개와 bundle 5개 통과, bundle refresh 22개 검증. 미커밋이다.

- 2026-11-06 KST: 사용자 승인으로 엔트로피 CPT 학습기(packed 8192, flex window mask, FP32 master, WSD/정체 decay, 바이트 위치 재개, 검사 캐시, 24시간 신호 재개)와 테스트·설정·번들 9개 파일을 커밋 f8837f3으로 push했다(neuron/command.md 제외). 다음은 Neuron에서 검토 승인 manifest 작성, 로그인 노드 1회 검사로 캐시 생성, H200 파일럿 50 step이다(사용자 실행).

- 2026-11-06 KST 정정: 1회 전체 검사(232GB SHA·중복 검사)를 로그인 노드에서 돌리라고 안내한 것은 명령표의 "로그인 노드에서 직접 실행하지 않는다" 규칙 위반이었다(앞서 v002 inspect_dataset 확인을 로그인 노드 명령으로 안내한 것도 같은 문제). 이 단계는 sbatch MODE=preflight 작업으로 실행하도록 정정했다.

- 2026-11-07 KST: 사용자 실행 job 970145가 3초 만에 실패했다("Submit with sbatch from /scratch/r984a02"). 학습 코드 진입 전 제출 위치 검사에서 걸린 것으로, 부모 디렉터리 제출 규칙 때문이다. 사용자 결정으로 sbatch 제출 cwd를 /scratch/r984a02/blt-cache로 통일했다(bundle.SUBMIT_ROOT=ROOT, train_entropy.sh 검사·메시지, test_bundle, README, command.md의 cd ../cd blt-cache 제거와 스크립트 경로 neuron/train_entropy.sh). command.md에 실수로 붙여넣은 이전 답변(로그인 노드 combine 안내)은 커밋본으로 되돌려 제거했다. itcerdo에서 bash -n과 bundle 테스트 5개 통과. 미커밋이다.

- 2026-11-07 KST: 수정 커밋 전에 Neuron 명령을 안내해 사용자 job 970303이 이전 코드로 같은 제출 위치 오류로 실패했다(내 안내 오류). 제출 위치 수정 5개 파일을 커밋 b093eaf로 push했고 원격 main 일치를 확인했다.

- 2026-11-07 KST: 사용자 지적으로 로그 전달 절차를 단순화했다. train_entropy.sh의 Slurm --output/--error를 runtimelog/entropy-%j.out/.err로 바꿨다. 전달은 git add runtimelog → commit → push다(작업별 디렉터리와 복사 절차 폐기). .out을 Git에 올리므로 학습 step 표준 출력은 처음 20 step과 100 step마다로 줄였고, metrics.jsonl은 매 step 유지한다. command.md 11절, runtimelog/README, neuron/README를 갱신했다. itcerdo 테스트 25개, bundle refresh 22개, bundle 테스트 통과. 커밋 66123cd로 push했다.

- 2026-11-07 KST: Neuron 로그 수신(runtimelog). preflight job 969335(gpu54)와 970304(gpu55, H200 150110011392 bytes, torch 2.11.0+cu128, transformers 5.16.1, bf16 smoke pass) 모두 training_ready=true, blockers 없음. 데이터는 train 59791622문서 / 232722508043bytes, validation 609471 / 2384020729로 v003 보고서와 같다. 970145와 970303은 제출 위치 검사로 실패한 기록이다. 검사 소요 시간은 로그에 없다. 다음은 H200 파일럿 50 step이다.

- 2026-11-07 KST: H200 파일럿 job 970535 결과(사용자 실행, runtimelog). step 1은 컴파일 포함 55.2초, 이후 step 1.78초. 학습 처리량 약 277KB/s(step당 약 493KB 바이트, 학습 대상 비율 0.94), peak GPU 68278040064bytes(63.6GiB, 상한 120GiB). 학습 BPB 1.75~1.91(warmup 초기, lr ~1e-6). 고정 검증 5000문서(19195793bytes) BPB 1.7820, 27.5초. step-00000050.pt 저장, status pilot. 1 epoch(약 465000 step) 순수 학습 추정 약 9.6일(24시간 작업 약 10개, 추정). 5090 flex 139KB/s 대비 약 2.0배이며, 앞서 추정한 400~550KB/s보다 낮다(추정 오류).

## 2026-11-07 KST / torch.compile 실험(사용자 결정)

- 5090 측정(실제 B 패처, 8192×2, flex): baseline 142.2KB/s. 마스크만 compile 146.5KB/s(마스크 생성 3.5ms→0.7ms). 레이어 compile 197.2KB/s(+39%, peak 9.4→7.2GiB). norm/head까지 compile 198.8KB/s. 레이어 compile max-autotune-no-cudagraphs는 205.8KB/s(+4%)였으나 warmup이 25초이고 triton 자원 초과 경고가 나서 채택하지 않았다. 첫 body NLL 43622.25 → 43618.21(0.01%, BF16 수준).
- 구현: 설정 compile(true/false, flex 전용). 레이어·norm·lm_head를 in-place compile하므로 파라미터 이름과 checkpoint는 같다. 블록 마스크는 _compile=True. 템플릿 두 개에 compile=true를 추가했다.
- 검증: 작은 BltPatcher에서 eager / flex / compiled의 logits·기울기 일치, 이름 보존 테스트. compile 설정의 실제 run(5090)은 pilot 3 → 재개 → decay → final, 종료 코드 0/0, 191~196KB/s, peak 7.2GiB. runtime 34개와 bundle 테스트 통과, bundle refresh 22개. 커밋 21732b3로 push했다.
- 참고: 코드 해시가 run 계약에 포함되므로 기존 파일럿 run(ko-entropy-h200-20261106-01, step 50)은 새 코드로 재개할 수 없다. 새 run으로 H200 파일럿을 다시 한다.

- 2026-11-08 KST: compile H200 파일럿 job 970912(사용자 실행, run ko-entropy-h200-20261107-01) 결과: step 1은 컴파일 포함 41.4초, 이후 step 0.92~0.94초. 처리량 526~536KB/s로 비compile 277KB/s의 약 1.91배다. peak 44.6GiB(이전 63.6GiB), 학습 대상 비율 0.94. 학습 BPB는 이전 파일럿과 step별로 소수 셋째 자리까지 같다. 검증 5000문서 BPB 1.7818(이전 1.7820), 27.7초. step-00000050.pt 저장. stderr에는 create_block_mask _compile 사용 중단 예고 DeprecationWarning만 있다. 1 epoch(약 465000 step) 추정 약 5.0일(24시간 작업 약 6개, 추정).

- 2026-11-08 KST: 사용자 요청으로 24시간 작업 연속 제출을 지원했다. train_entropy.sh에 RESUME=latest를 추가했다. bundle.py latest가 run_dir에서 .sha256까지 기록된 가장 최근 step-*.pt를 고르고, .active가 있거나 완성 checkpoint가 없으면 실패한다. command.md 9절에 afterany 의존성으로 6개 job을 거는 명령을 추가했다. test_bundle 6개 통과, itcerdo 실제 run 디렉터리에서 step-00000012.pt 선택 확인. 제출 스크립트와 bundle.py는 run 계약 해시 밖이라 진행 중 run에 영향이 없다. 커밋 4fe9853로 push했다.

- 2026-11-08 KST: 사용자 보고: H200 partition은 사용자당 job 2개까지라 반복문 대신 한 줄 제출로 명령표를 직접 수정했다. 본 학습 job 971130과 971132가 PENDING(Priority)이다. 971132의 대기 사유가 Dependency가 아니어서 의존성 누락 가능성을 사용자에게 확인 요청했다. 동시에 시작되면 뒤의 job은 .active 잠금으로 즉시 실패하고 checkpoint는 안전하다. 명령표 한 줄 제출 블록에 CONFIG 정의와 이전 job 번호 표기를 보완했다(미커밋).

## 2026-11-10 KST / 한국어 엔트로피 패처 CPT 완료 확인(run ko-entropy-h200-20261107-01)

- job 971130(gpu54): step 50 → 91079, 처리량 약 522~532KB/s, peak 44.6GiB. 검증 표본 BPB는 5000: 1.0735 → 50000: 0.9161 → 90000: 0.8998. stdout 마지막은 status signal(step-00091079.pt 저장)이고, stderr에 "CANCELLED AT 2026-11-09T09:36:37 DUE TO TIME LIMIT"가 있다. 마지막 step의 python 경과 86210초를 보면 종료 10분 전 SIGUSR1(B:)이 python에 오지 않았고, 시간 제한 때의 SIGTERM으로 저장된 것으로 보인다(가설: 사이트 job wrapper가 batch shell의 부모라 B: 신호가 전달되지 않음). 저장은 완료됐다(sha256 검증 후 재개 성공).
- job 971132(gpu56): RESUME=latest → step-00091079.pt. 검증 표본 BPB 95000: 0.8998, 110000: 0.8941, 115000: 0.8936, 120000: 0.8923, 125000: 0.8931. step 125000에서 정체 규칙(최근 3회 최저 0.8923, 이전 최저 0.8941, 개선 0.0018 < 0.002)으로 decay를 시작했다(12500 step, 3e-4 → 3e-5 선형). 130000: 0.8758, 135000: 0.8557. final-00137500.pt, 전체 validation(609471문서 / 2384020729bytes) BPB 0.8558, status finished. 노출량 약 67.8GB(train의 약 29%), 누적 학습 시간 131348초.
- 판정(측정): 규칙대로 정상 완료. 초기 파일럿 표본 BPB 1.782 → 최종 0.856. 표본 BPB와 전체 BPB가 0.0001 차이로 일치해 표본이 대표성을 보인다.
- 해석(가설): decay 12500 step 동안 BPB가 0.037 내려갔다. 정체 판정 기준 0.002보다 훨씬 크므로, stable 구간의 정체는 높은 학습률 때문이었을 수 있고 데이터를 더 보면 최종 BPB가 더 낮아질 여지가 있다. 표본 평가 잡음(125000의 0.8931 > 120000의 0.8923)도 판정에 영향을 줬다. decay 이전 checkpoint는 rolling 2개 보존 규칙 때문에 남아 있지 않다.

## 2026-11-10 KST / 이어서 추가 학습 준비(사용자 승인)

- 사용자 결정: 처음부터 다시 하지 않고 final-00137500.pt에서 학습률을 다시 올려 이어 학습한다. 정체 기준은 최근 5회로 바꾼다.
- 구현(entropy_train):
  - init_from: 다른 run의 checkpoint에서 FP32 가중치, AdamW 상태, 데이터 위치(stream)를 가져온다. step·warmup·평가 이력·decay·RNG는 새로 시작한다. checkpoint 파일과 sidecar의 SHA256이 설정값과 같아야 하며, 출처(step, 노출 바이트)를 progress.init_from에 남긴다.
  - decay 시작 시 predecay-<step>.pt를 rolling과 별도로 보존한다.
  - StopRequest가 신호 외에 마감 시각도 본다. train_entropy.sh가 scontrol의 EndTime에서 10분 전을 --deadline-unix로 넘긴다. 마감 종료는 status deadline, exit 75다.
- 검증(itcerdo 5090): runtime 34개 테스트 통과(마감 StopRequest, init_from 해시·가중치·AdamW step·stream, preflight init_from 검사 추가). 실제 run에서 run A가 predecay-6과 final-10을 남겼고, init_from한 run B는 A의 stream 뒤부터 데이터를 읽고 lr warmup부터 다시 시작했다(pilot 5 → 재개 → predecay-8 → final-12, 종료 코드 0/0/0). 마감 경로는 step 300 저장 후 status deadline, exit 75. bundle refresh 22개, test_bundle 6개 통과. 커밋 5f2f2c3로 push했다.

- 2026-11-12 KST: 이어 학습 run ko-entropy-h200-20261110-01 첫 job 974212(gpu55) 로그 확인. init_from 시작, step 1 lr 6e-08, 처리량 약 520~540KB/s, peak 44.6GiB. 검증 표본 BPB 5000: 0.8908, 10000: 0.8946, 15000: 0.8908, 20000: 0.8905, 25000: 0.8879. rewarm으로 0.856에서 0.89대로 올랐고, 이전 run stable 구간 최저(120000의 0.8923)보다 이미 낮다. stderr는 "CANCELLED AT 2026-11-11T09:06:07"(TIME LIMIT 아님, python 경과 약 24970초)이며, SIGTERM으로 step-00026199.pt를 저장했다(status signal). 이 run의 노출량 12.88GB, 누적 약 80.7GB. 다음 job 976443(Resources 대기), 976444(Dependency)가 대기 중이다. 취소 원인(수동/관리자)은 확인 필요.

- 2026-11-12 KST: 사용자 확인: 974212 취소는 2026-11-11 09시 Neuron 전체 노드 유지보수 중단 때문이다. SIGTERM 저장으로 손실은 없고, 그 뒤 실행된 job이 없어 진행이 멈춰 있었다. 976443(Resources)과 976444(Dependency)가 RESUME=latest로 대기 중이다.

- 2026-11-12 KST: 사용자 결정으로 T13 본체 단계 순서를 ENCODER → HASH → BODY_FULL로 바꿨다(이전 ENCODER → GLOBAL → BODY_FULL). 근거(실측 모수): 해시 n-gram 임베딩 3072.0M(6표×500002×1024), 전역 트랜스포머 1284.6M, 로컬 디코더 157.6M, 로컬 인코더 19.4M, 패처 99.5M. 해시는 조회 연산이라 추가 계산이 작고, FP32 원본·Adam·기울기로 약 49GB를 더 쓴다(H200 수용). 해시는 weight decay에서 제외한다. 각 단계는 같은 공개 본체에서 독립 출발한다는 원칙은 유지한다. KOREAN_NEURON_PREP 표·본문, task T13, korean_neuron_readiness.json, HANDOFF, neuron/command.md를 갱신했다(미커밋).

- 2026-11-13 KST: 사용자 요청으로 README.md의 영어 본문을 한국어로 옮겼다(코드·명령·링크·파일명은 원문 유지). 첫 단락의 "학습 코드·Slurm 작업 미포함" 문장은 원문대로 옮겼으나 현재 neuron/에 entropy 학습 코드와 Slurm 스크립트가 있어 사실과 다르다(수정 여부는 사용자 결정).

## 2026-11-14 KST / 한국어 엔트로피 패처 이어 학습 완료 확인(run ko-entropy-h200-20261110-01)

- 로그 수신: GitHub 3c422f5(runtimelog/entropy-976443, 976444, 978768).
- job 976443(gpu55): RESUME=latest → step-00026199.pt, step 111707까지. 검증 표본 BPB 30000: 0.8885 → 75000: 0.8813 → 90000: 0.8795 → 110000: 0.8789. 종료 10분 전 마감 경로로 step-00111707.pt 저장, status deadline(exit 75라 Slurm에는 FAILED로 표시, 정상 종료).
- job 976444(gpu55): RESUME=latest → step-00111707.pt. step 115000(표본 0.8787)에서 정체 규칙(최근 5회)으로 decay 시작(11500 step, 3e-4 → 3e-5). 120000: 0.8631, 125000: 0.8410. final-00126500.pt, 전체 validation(609471문서 / 2384020729bytes) BPB 0.8441, status finished. 처리량 약 513~518KB/s, peak 47.9GB, 이 run 누적 학습 시간 126030초.
- 노출량: 이 run 62.43GB, run1 67.8GB와 합쳐 약 130.2GB(train 232.7GB의 약 56%, 1 epoch 미만). max_train_bytes 172e9에는 이르지 않고 정체 decay로 끝났다.
- 판정(측정): 전체 validation BPB 0.8558 → 0.8441(−0.0117, 약 −1.4%). stable 구간 최저도 0.8923 → 0.8789(−0.0134)로 내려갔고, decay 이득은 run1 약 0.037, run2 약 0.038로 비슷하다. 학습률 재상승으로 시작 직후 표본 BPB가 0.856 → 0.891로 올랐으며, 이를 회복하고 더 내려가는 데 데이터 62GB(H200 약 35시간)를 썼다.
- 해석(가설): 추가 62GB로 얻은 개선이 0.012 정도라 100M 패처는 수확 체감 구간에 있다. 같은 방식의 추가 이어 학습은 비용 대비 효과가 작다고 본다. run2 표본 BPB(125000: 0.8410)와 전체(126500: 0.8441)의 차이 0.003은 run1(0.0001)보다 커서 5000문서 표본의 대표성은 한정적이다.
- job 978768(gpu55): 시작 직후 "CONFIG: Set CONFIG to an absolute reviewed JSON config path"로 종료. CONFIG 없이 제출되어 학습은 실행되지 않았고 checkpoint 영향은 없다(제출 의도는 사용자 확인 필요).
- 다음: final-00126500.pt를 한국어 교사 패처로 고정하고(sha256 기록 필요), 평균 4/6/8 bytes/patch threshold 보정과 PATCHER 비교, 이어서 T13 ENCODER → HASH → BODY_FULL 준비.

## 2026-11-14 KST / 영어 평가 제외 결정과 패처 비교(BLT 기준·threshold 보정·PATCHER) 구현

- 사용자 결정: 영어 성능은 관심사가 아니므로 한국어 CPT의 평가·학습에서 영어(망각 감시 heldout BPB, 영어 replay 10%)를 뺀다. KOREAN_NEURON_PREP, task T12/T13, korean_neuron_readiness.json에 반영했다.
- 사용자 질문에 대한 정리: 같은 평균 패치 길이에서 패처 선택은 고정 본체의 한국어 BPB로 판정한다. 평균 길이(threshold) 선택은 BPB만으로 정하지 않는다. 짧은 패치는 global step이 늘어 BPB가 낮아지는 대신 계산량이 커지므로 BPB와 패치 수(계산량)를 함께 본다. 공개 설정의 원래 목표 평균 길이는 original_spec patch_size 4.5다.
- 구현: neuron/runtime/blt_hf/patcher_compare.py, neuron/compare_patchers.sh(H200 1GPU, 12시간 할당), tests/test_hf_patcher_compare.py 7개. bundle 24파일로 갱신.
  - 입력은 run1/run2의 contract.json(manifest·모델 경로와 SHA)에서 읽고 해시를 검사한다. checkpoint는 .sha256 확인 후 weights_only로 읽어 FP32 master를 BF16으로 공개 패처 사본에 넣는다.
  - 보정: 두 checkpoint의 stream offset(1 epoch 안) 뒤 train 구간에서 무작위 offset 다음 전체 문서를 약 20MB 뽑는다. 패처마다 BF16 엔트로피 히스토그램으로 평균 4/4.5/6/8 bytes/patch에 가장 가까운 BF16 threshold를 고른다.
  - 평가: validation 앞 5000문서, 2047바이트 청크 + BOS, eager/BF16/batch1/no cache. 설정 13개(public@native + 3패처×4길이)의 본체 BPB, 출처별 BPB, bytes/patch, 길이 분위, 청크당 최대 패치 수, 본체 시간, 패처 자체 BPB, 문서 단위 paired bootstrap(2000회), 같은 길이 패처 간 경계 F1. 처음 3청크는 외부 patch_lengths와 모델 내부 패처 경로의 logits 완전 일치를 검사한다.
- 검증(itcerdo 5090, phdq_blt_hf): 단위 테스트 7개 통과(실제 save_state checkpoint의 weights_only 로드 포함). 실제 공개 본체로 소규모 종단 스모크(phdq3 native GEC 정답 문장으로 만든 가짜 문서 500개, 가짜 run1=공개 가중치 그대로, run2=잡음 추가) exit 0, 22초. 내부 경로 대조 3/3 통과, run1 결과가 public과 완전히 같아 checkpoint 적재 경로를 확인했다. 스모크 수치는 실제 자료가 아니므로 결과로 쓰지 않는다. 가짜 checkpoint는 지웠다.
- 다음: 커밋·push 후 사용자가 Neuron에서 `sbatch --export=ALL,RUN_ID=ko-patcher-compare-20261114-01 neuron/compare_patchers.sh` 실행.

- 2026-11-14 KST: 사용자 지시로 Neuron 실행 파일 6개(compare_patchers.sh, patcher_compare.py, test_hf_patcher_compare.py, bundle.py, runtime-manifest.json, command.md)만 커밋 9ca480d로 push했다. 원격 main 일치 확인. command.md에는 이전에 미커밋이던 연속 제출 블록 수정도 함께 들어갔다. log/task/계획 문서는 미커밋.

## 2026-11-14 KST / 본체 전체 추가 학습(BODY_FULL) 우선 결정과 실행기 구현

- 사용자 결정: ENCODER → HASH → 글로벌을 순차로 하지 않고 BODY_FULL(패처 밖 본체 전체)을 먼저 학습한다. ENCODER/HASH는 그 뒤 학습 범위를 줄여 가며 성능이 어디서 안정되는지 보는 부차적 축소 실험이다. KOREAN_NEURON_PREP, task T13에 반영했다.
- 구현: neuron/runtime/blt_hf/body_train.py, neuron/train_body.sh(H200 1GPU, 128G, 24h, 마감 20분 전 저장), neuron/body.template.json, tests/test_hf_body_train.py 6개, bundle 26파일(validate-job에 --run-base outputs/korean_body 추가), 명령표 13절.
  - 학습 대상: model.patcher.* 를 뺀 4,533,879,808 모수(해시 3,072,012,288, 글로벌 1,284,608,000, 로컬 디코더·인코더, lm_head). 패처와 threshold는 설정(checkpoint+sha256+threshold, 공개면 null)으로 넣고 고정한다. 패칭은 모델 내부 경로 그대로다.
  - 정밀도: BF16 forward/backward, FP32 master + fused AdamW(0.9, 0.95, eps 1e-8), 해시 임베딩만 weight decay 0. 상태 약 91GB, checkpoint 약 55GB(예상).
  - 입력: 문서를 이어 붙이지 않는다(해시 n-gram·패치가 EOS를 넘는 문서 간 누출을 피함). 문서를 4096바이트 청크로 나눠 BOS + 청크(마지막 청크는 EOS 포함)를 micro-batch 1로 처리하고, step당 약 1MB 목표를 채운다. step 0에서 검증 BPB(validation 앞 2000문서)를 먼저 잰다. 스케줄은 패처 CPT와 같은 WSD+정체 decay.
  - 기본 하이퍼파라미터(템플릿, 미승인): lr 1e-4(원본 4e-4·16MB batch를 1MB batch로 √ 축소한 값), warmup 200, wd 0.1, clip 1.0, eval/save 250 step, 정체 5회/0.002, decay 10%/최소 500 step. 예산 5개는 null.
- 측정(itcerdo 5090, 실제 공개 본체, optimizer 제외):
  - 모든 학습 모수가 기울기를 받는다(미수신 0). eager는 4096바이트에서 OOM(밀집 T×T 어텐션), SDPA는 8192바이트까지 peak 24.6GB(가중치+기울기 약 18GB 포함).
  - SDPA와 eager는 FP32에서 logits 최대 차이 5.7e-5, BPB 동일로 같은 마스크 의미다(BF16에서는 최대 2.44, argmax 98.7% 일치의 수치 차이). 학습 기본값을 SDPA로 둔다.
  - forward+backward 처리량: 1024바이트 5.4KB/s, 4096바이트 9.8KB/s, 8192바이트 8.3KB/s. 8192 프로파일에서 메모리 효율 어텐션이 CUDA 시간의 약 55%다(512 창 로컬 어텐션을 밀집 마스크로 계산). 그래서 sequence_bytes 기본값을 4096으로 둔다. 블록 희소(flex) 어텐션은 후속 최적화 후보다(가설: 큰 폭 개선).
- 테스트: runtime 전체 47개 통과(itcerdo). 본체 테스트는 청크가 모든 바이트·EOS를 한 번씩 목표로 삼음, 모든 상태에서 재개 동일, 작은 BLT로 한 step 뒤 패처 불변·본체 master 전부 갱신·입력에 없는 해시 행 불변(weight decay 0 확인), 2+2 step 재개가 4 step 연속과 손실·노출량 일치.
- 한계/미확인: H200에서 91GB 상태+활성 메모리, 실제 처리량(5090 기준 추정 약 2~3배면 하루 2GB 안팎, 가설), 55GB checkpoint 저장 시간은 파일럿에서 확인해야 한다. 패처·threshold는 12절 비교 결과를 기다린다.

## 2026-11-14 KST / 본체 학습 속도 개선(고속 경로) 구현·실측

- 사용자 결정: DDP(H200 2장)는 할당 대기가 길어 쓰지 않는다. H200 1장에서 gradient checkpointing 끄기, 블록 희소(flex) 어텐션, compile을 적용한다.
- 구현: neuron/runtime/blt_hf/fast_body.py(설정 attention_backend "fast"). 모델 함수를 같은 의미의 빠른 계산으로 바꾼다.
  - 로컬 창(512)/EOS, 글로벌 block-causal, 패치 cross-attention 마스크를 flex BlockMask로 만든다(완전히 가려진 블록은 계산하지 않음). 그 밖의 dense 마스크는 SDPA.
  - 해시 n-gram 6개 조회를 한 번의 embedding 호출로 합친다. backward에서 30억 행 표의 dense 기울기를 6번 만들어 더하던 것을 1번으로 줄인다(프로파일상 원소별 커널이 CUDA 시간의 약 26%).
  - compile: 모든 트랜스포머·cross-attention 층을 제자리 compile(파라미터 이름 유지), 재컴파일 한도 64.
  - body_train: attention_backend eager|sdpa|fast, compile 설정 추가, 계약 해시에 fast_body 포함. 템플릿 기본값 fast + compile + checkpointing 끔 + 8192바이트 청크. train_body.sh에 expandable_segments.
- 동등성(측정, 실제 공개 본체 FP32, 5090): fast 대 eager logits 최대 차이 1.2e-4(문서 1개 4001바이트)·8.2e-5(문서 2개, 중간 EOS), BPB 소수 7자리 일치. 작은 BLT 테스트에서 logits와 모든 파라미터 기울기도 일치. 5090의 FP32 flex는 공유 메모리 한도로 비교 때만 타일을 줄였다.
- 처리량(측정, 5090, BF16 forward+backward, optimizer 제외, KB/s):
  - 2048/4096/8192바이트 고정: SDPA 9.3/11.2/9.3 → fast 17.6/22.1/21.9 → fast+compile 21.3/25.7/25.2.
  - 300~4096바이트 가변 60청크: SDPA 9.8 → fast+compile 22.6(두 번째 통과, 첫 통과는 컴파일 포함 5.7).
  - 처음 설정(SDPA+checkpointing, 4096) 9.8 대비 약 2.6배. 8192도 4096과 거의 같은 속도라 문맥을 8192로 늘렸다. peak 메모리 변화 없음(25.8GB).
- runtime 전체 48개 테스트 통과(itcerdo), bundle 27파일.
- 한계: H200 처리량은 미측정(가설: 5090의 2.5~3.5배면 60~90KB/s, 하루 5~8GB). 학습 step마다 FP32 master 기울기 누적(약 45GB 메모리 이동/청크)과 optimizer는 위 측정에 없다. 파일럿에서 확인한다.

- 2026-11-14 KST: 사용자 지시로 본체 학습 실행 파일 8개(train_body.sh, body.template.json, body_train.py, fast_body.py, test_hf_body_train.py, bundle.py, runtime-manifest.json, command.md)만 커밋 d85b80d로 push했다. 원격 main 일치, bundle 27파일 검증. 진행 중인 패처 비교가 쓰는 파일은 9ca480d 이후 변경 없음. log/task/계획 문서는 미커밋.

## 2026-11-14 KST / 패처 비교(BLT 기준·threshold 보정·PATCHER) 결과(job 980258)

- 로그: runtimelog/patcher-compare-980258.out(GitHub e22db71). H200, 보정 614초, 평가 3856초(13설정). 내부 패처 경로 대조 3/3 통과.
- 보정(train 미학습 구간 134.5GB 이후 무작위 5277문서, 20.0MB): 공개 threshold 1.3354에서 평균 bytes/patch는 공개 2.26, run1 6.24, run2 6.34. 목표 4/4.5/6/8의 threshold는 공개 1.766/1.867/2.125/2.453, run1 1.047/1.141/1.313/1.484, run2 1.031/1.125/1.305/1.477. validation에서도 목표 길이와 1% 안으로 맞았다.
- 패처 자체 BPB(2047바이트 청크): 공개 1.8705, run1 0.8858, run2 0.8753.
- 고정 공개 본체의 한국어 BPB(validation 앞 5000문서 19.2MB, FineWeb2가 99.6%):
  - public@native(2.27 B/p) 1.1825
  - 4 B/p: public 1.2325, run1 1.2914, run2 1.2924
  - 4.5 B/p: public 1.2469, run1 1.3110, run2 1.3118
  - 6 B/p: public 1.2947, run1 1.3529, run2 1.3550
  - 8 B/p: public 1.3499, run1 1.3953, run2 1.3975
- 같은 평균 길이 대조(문서 bootstrap 95%): 한국어 CPT 패처가 공개보다 +0.045~+0.065 BPB 나쁘고 구간이 모두 0을 넘는다. run2는 run1보다 +0.0008~+0.0021 나쁘다. 경계 F1은 CPT 대 공개 0.51~0.53, run2 대 run1 0.90~0.91.
- 패치 길이: CPT 패처는 p50 2~5, p99 25~46, 최대 약 1921~2006바이트(2047바이트 청크 거의 전체가 한 패치). 공개는 p99 20~38, 최대 609~639.
- 판정(측정): 고정 본체 조건(PATCHER arm)에서는 한국어 CPT 패처로 바꾸면 같은 패치 길이에서 BPB가 나빠진다. run2의 추가 학습은 본체 BPB에 이득이 없었다. 패치가 짧을수록 BPB가 좋고(공개 native 2.27 B/p가 최선), 패치가 짧을수록 계산도 늘어난다(패치 수 약 2배인 native의 본체 시간 358초, 4.5 B/p는 263초).
- 해석(가설): 본체는 영어 공개 패처의 경계 분포로 학습되어 경계 분포가 바뀌면(F1 0.52) 손해를 본다. CPT 패처가 예측 가능한 구간을 수백~수천 바이트 한 패치로 묶는 것도 고정 본체에 불리할 수 있다. 이는 본체를 학습하지 않은 조건의 결과이며 BODY_FULL 뒤 어느 패처가 나은지는 알 수 없다. 패처 자체 BPB(0.875)가 공개 본체 BPB(1.18~1.40)보다 훨씬 낮아 본체의 한국어 개선 여지는 크다.
- 다음: BODY_FULL에 쓸 패처·threshold를 사용자와 정한다(후보: 공개@4.5, 공개@native, run1@4.5; 필요하면 짧은 BODY_FULL 파일럿으로 비교).

## 2026-11-14 KST / BODY_FULL 패처 결정: 같은 4.5 B/p에서 공개 대 run1 비교 학습

- 사용자 결정: 공개 threshold(1.3354)를 한국어에 그대로 쓰면 평균 2.27 B/p가 되는데 이 길이는 근거가 없으므로 쓰지 않는다. 평균 길이를 원래 설계값 4.5에 맞춘 A(공개 패처, threshold 1.8671875)와 C(run1, threshold 1.140625)를 BODY_FULL로 각각 학습해 비교한다. 패처 차이와 패치 길이 차이가 섞이지 않게 하기 위해서다.
- 준비(명령표 13-3): 두 설정은 패처만 다르다. max_steps 1000(step당 약 1MB, 약 1GB), warmup 200, 고정 lr 200~500, 500~1000 선형 decay(1e-4 → 1e-5), 최종 평가 validation 앞 20000문서. 예산: max_train_bytes 2e9, max_seconds 172800, max_run_bytes 250e9, GPU 135e9. 20 step 파일럿(2시간 job) 뒤 RESUME=latest로 이어 학습한다. 로컬 preflight에서 경로 외 차단 사유 없음, decay 시작 step 500 확인.
- 다음: command.md push 후 사용자가 Neuron에서 설정 생성·파일럿 실행.

- 2026-11-14 KST: 사용자 지시로 비교 학습 A·C를 파일럿 없이 H200 job 2개로 동시에 MODE=train 제출하도록 명령표 13-3을 바꿨다(24시간 내 미완료 시 RESUME=latest로 이어 제출). command.md 커밋 2개를 push했다.

## 2026-11-16 KST / BODY_FULL 비교 학습 결과: A(공개@4.5) 대 C(run1@4.5)

- 로그: GitHub 0ecad02. job 980668(A), 980669(C), 각 H200, 1000 step(1.051GB) 완료(status finished). 앞선 980347/980348은 설정 파일을 만들지 않고 제출해 시작 직후 실패했다(코드 오류 아님).
- 처리량(측정): step당 314청크(약 1.05MB), 학습 처리량 중앙값 A 51.6KB/s, C 50.5KB/s(42~66KB/s), 하루 약 4.4GB. 첫 step은 compile 포함 37~77초. 1000 step 총 약 5.9시간(평가·저장 포함, 250 step마다 평가+checkpoint 약 2~3분 추가). peak GPU 95.7/96.5GB.
- 검증 BPB(validation 앞 2000문서, 8192바이트 청크):

  | step | A 공개@4.5 | C run1@4.5 | C−A |
  |---|---|---|---|
  | 0 | 1.1826 | 1.2609 | +0.0783 |
  | 250 | 0.9978 | 1.0130 | +0.0153 |
  | 500 | 0.9387 | 0.9514 | +0.0128 |
  | 750 | 0.8959 | 0.9066 | +0.0107 |
  | final(1000, 20000문서 76.9MB) | 0.8696 | 0.8778 | +0.0082 |

- 판정(측정): 1GB BODY_FULL 뒤에도 공개 패처가 run1보다 0.0082 BPB 낮다. 차이는 학습 전 0.078에서 줄었지만 남아 있다. 이 평가는 합계만 기록해 bootstrap 구간은 없다. 학습 BPB(step 1000: 0.881 대 0.882)는 비슷하다.
- 해석(가설): 본체가 학습하면서 새 경계에 적응해 차이가 좁혀지는 추세라 더 많이 학습하면 줄거나 뒤집힐 수 있으나, 1GB 기준으로는 공개 패처가 낫다. 1GB만으로 본체 BPB가 1.18 → 0.87로 크게 내려가 한국어 적응 효과가 크다.
- 다음(제안): A로 본 학습(명령표 13-4, 최대 30000 step 약 31GB, 1000 step마다 평가, 최근 5회 개선 0.002 미만이면 decay).

## 2026-11-16 KST / 패처 비교 연장 결정(A 대 C, 각 5GB)

- 사용자 결정: 1GB 비교로는 결론을 내리지 않고 ①안(비교 연장)으로 간다. 사용자는 C(run1)로 본 학습하는 쪽이 맞다고 보며, 연장 결과로 확인한다. A 본 학습 명령(미push 13-4)은 삭제했다.
- 설정(명령표 13-4, 미push): 공개 본체에서 새로 시작, 각 5000 step(약 5.2GB), warmup 200, decay 4500~5000(정체 판정 끔: plateau_patience 1000, 두 run 스케줄 동일), 500 step마다 2000문서 검증, 최종 20000문서. 예산 max_train_bytes 6e9, max_seconds 259200, max_run_bytes 250e9, GPU 135e9. 로컬 preflight에서 경로 외 차단 없음, decay 시작 4500 확인. run당 job 2개(24시간 약 4100 step) 필요.

## 2026-11-17 KST / 본 학습을 C(run1 패처)로 결정, A-5GB는 대조군

- 사용자 판단: 목표가 한국어 전체 적응이므로 패처를 영어로 둔 채 본체만 학습하는 A는 본 학습의 의미가 없다. 본 학습은 C(run1 @4.5, threshold 1.140625)로 하고, A-5GB(실행 중, 약 22시간 경과)는 패처 적응 효과를 재는 대조군으로 끝까지 돌린 뒤 C 본 학습을 시작한다.
- C 본 학습 설정(명령표 13-5, 미push): ko-body-full-run1-45-20261117-01, 공개 본체에서 새로 시작, 최대 30000 step(약 31GB), eval/save 500 step, 정체 판정 최근 10회(약 5GB)·0.002, 예산 max_train_bytes 35e9, max_seconds 864000, max_run_bytes 300e9, GPU 135e9. 4500 step까지 A-5GB와 학습률·데이터 순서가 같아 500 step 단위 검증 BPB로 비교한다(같은 2000문서).
- C-5GB 비교 run은 따로 두지 않는다(본 학습 앞부분이 그 역할).

## 2026-11-20 KST / C 본 학습 진행, A 이어 제출 실패 원인

- 로그 GitHub 2d73463. C 본 학습(ko-body-full-run1-45-20261117-01)은 정상: job 983536(step 0 → 4104), 984721(4104 → 8175) 모두 마감 20분 전 저장 후 status deadline으로 끝났다. 처리량 중앙값 51.2KB/s. 검증 BPB(2000문서) 4000: 0.7956, 6000: 0.7804, 8000: 0.7654. decay 아직 없음.
- A 이어 제출 983538, 984720은 시작 직후 실패: 981511 취소 때 남은 `.active`를 지우지 않아 RESUME=latest가 거부했다(코드 오류 아님). A는 step 3500 checkpoint에 머물러 있다.
- A 대 C 같은 step 검증 BPB(학습률·데이터 순서 동일 구간): C−A = 0(+0.078), 500(+0.0106), 1000(+0.0108), 1500(+0.0075), 2000(+0.0098), 2500(+0.0088), 3000(+0.0108), 3500(+0.0097). 1GB 비교에서 보이던 차이 축소가 3.6GB 안정 구간에서는 이어지지 않고 약 0.01로 유지된다(측정). 원인은 미확인.

## 2026-11-25 KST / itcerdo 디스크 사용 평가(읽기 전용, 삭제 없음)

- 디스크 914G 중 788G 사용(90%, 여유 88G). blt-cache 424G: runs 412G, .venv 7.5G, datasets 4.6G. 실행 중인 blt-cache 프로세스 없음(tmux 세션 10개는 빈 셸).
- 큰 항목: bg50gb 배경 블록 123G + background.jsonl 53G, blt50gb-compare counts.lmdb 68G, blt20gb-compare counts.lmdb 56G, bg20gb 블록 40G, bg10gb-diskcpp 블록 41G(10→20→50GB는 부모 블록을 재사용하는 사슬), ko-entropy-train-validation 19G(init_from·compile 검증용 패처 checkpoint), .venv 7.5G(2026-10-19 생성, 현 규칙상 미사용).
- 평가: 영어 count 패처 결과는 evidence JSON으로 보존돼 있고 한국어 T14에는 영어 count를 재사용할 수 없다. 삭제 여부는 사용자 결정(제안만 함).

## 2026-11-25 KST / itcerdo 영어 count 자료 정리(사용자 승인)

- 사용자 결정: 영어 count는 활용 가능성 확인용이었고 연구의 중심은 한국어이므로 보관할 필요가 없다. 제안안대로 50GB count 표만 압축 보관하고 나머지는 삭제한다. .venv는 보류.
- 삭제(itcerdo runs/): en-patcher-bg10gb-diskcpp-20261024-02/background_blocks 41G, en-patcher-bg20gb-nested-20261029-02/background_blocks 40G, en-patcher-bg50gb-nested-20261105-01/background_blocks 123G·background.jsonl 53G, en-blt20gb-compare-20261101-01/counts.lmdb 56G, ko-entropy-train-validation-20261106-01/integration의 .pt 17개 19G. 보고서·fit·metrics·sidecar는 남겼다. 삭제 후 디스크 사용 384G/914G(44%).
- 압축: en-blt50gb-compare-20261105-01/counts.lmdb → counts.lmdb.tar.zst(zstd -3, 15.8GB). 원본 SHA-256을 counts.lmdb.sha256에 기록했다. 압축본 검증(zstd -t, 압축 해제 후 data.mdb SHA-256 대조) 진행 중이며 일치 확인 후 원본 68G를 지운다.
- 영향: 영어 count 재적합·확장은 처음부터 다시 해야 한다. 50GB count 패처 평가는 압축 해제 후 다시 실행할 수 있다. 결과 수치는 저장소 evidence/에 남아 있다.

## 2026-11-25 KST / itcerdo 정리 완료

- 50GB count 표 압축 검증: zstd -t 통과, 압축 해제한 data.mdb SHA-256 02a75940bbb8e924d6d79489a801badf0cdc9040f0443949570d749b74fa66a2가 원본과 일치(VERIFIED, 압축+검증 410초). 원본 runs/en-blt50gb-compare-20261105-01/counts.lmdb(68G)를 삭제했다.
- 보관본: runs/en-blt50gb-compare-20261105-01/counts.lmdb.tar.zst(15,791,161,145 B)와 counts.lmdb.sha256. 복원은 해당 디렉토리에서 `zstd -dc counts.lmdb.tar.zst | tar -xf -` 후 `sha256sum -c counts.lmdb.sha256`.
- 결과: 디스크 사용 788G(90%) → 316G(37%), 여유 560G. runs 412G → 29G. .venv(7.5G)는 사용자 결정 전까지 유지.

## 2026-11-25 KST / C 본 학습 step 24379, decay는 약 27272 step부터

- 로그 GitHub c9516a9. C 본 학습(ko-body-full-run1-45-20261117-01) job 986315(8175 → 12233), 986316(→ 16325), 988396(→ 20282), 988397(→ 24379)은 모두 마감 저장 후 status deadline으로 끝났다. 987589, 988052는 시작 직후 실패했다(CONFIG 미지정: 새 셸에 C 변수가 없었음, 코드 오류 아님). 986316 종료 뒤 988396 시작까지 약 13시간, 988396 종료 뒤 988397 시작까지 약 16시간 비었다(후자는 대기열).
- 측정: job별 처리량 중앙값 50.6–51.7KB/s, peak 98.6–99.7GB, 평균 gradient norm 0.068 → 0.061, lr 1e-4 유지(decay 없음). 누적 노출 25.6GB, elapsed 509,773초.
- 검증 BPB(같은 2000문서) 구간별 최저: 8000까지 0.7653, 12000까지 0.7440, 16000까지 0.7238, 20000까지 0.7195, 24000까지 0.7098(23500). 4000 step당 개선 0.021, 0.020, 0.004, 0.010으로 느려지지만 정체 기준(최근 10회 0.002)보다 크다. 개별 평가값은 최대 약 0.007 튄다(20000: 0.7264).
- 일정(코드 규칙으로 계산, 예상): 남은 평가에서 정체 판정은 성립하지 않는다(이전 최저 대비 최소 0.0049 개선). max_steps 규칙으로 step 27272에서 decay(길이 2728, 1e-4 → 1e-5)를 시작하고 predecay checkpoint를 저장한다. 다음 24시간 job은 약 28400 step까지, 그다음 job은 약 10시간 안에 30000 step과 20000문서 최종 검증을 마친다. 예산: 노출 약 31.5GB < 35e9, 시간 약 627,000초 < 864,000초.
- 명령표 13-5의 이어 제출 블록에 C= 줄을 넣었다(미push).

## 2026-11-27 KST / 판정 기준 정정, 50GB count 패처 외장 디스크 백업

- 정정: count 패처의 검증 경계 F1 0.90, 패처 증분 1.2배, 전체 모델 초기 처리 1.05배 등은 2026-10-19 T00에서 에이전트가 파일럿 설정(experiments/english_patcher_pilot.json)에 넣은 선별 기준이며 사용자가 정한 기준이 아니다. 이후 count 패처 결과는 합격·미달 판정 없이 측정값으로만 보고한다. 기존 기록은 이력으로 둔다.
- 사용자 지시: 50GB 패처 완성본 실행에 필요한 자료를 /Volumes/T31에 별도 보관한다.
- 백업 위치: /Volumes/T31/blt-cache/count-patcher-50gb-20261105/ (runs/ 아래에 itcerdo의 상대 경로 그대로). 대상: en-patcher-bg50gb-nested-20261105-01(적합 규칙 fit/report.json 9b23ba62…, 적합 특징·투영 1.1G, 준비·구축 보고서), en-blt50gb-compare-20261105-01(counts.lmdb.tar.zst 4e4ae798…, counts.lmdb.sha256, counts.report.json, 실행 source 사본, 평가 결과), en-blt50gb-cpp-eval-20261105-01(C++ 백엔드 평가 결과), en-blt-cpp-eval-runtime-20261105-01(C++ 평가 source). itcerdo에서 계산한 파일 179개 SHA256 목록을 SHA256SUMS로 함께 저장했다.
- 포함하지 않음: BLT 본체 가중치(phdq3 artifacts/converted/blt-1b-hf-own, model.safetensors 4b6115bd…, Neuron에도 사본), 평가 자료(datasets/en-patcher-20261019-01 17M, 교사 라벨 runs/en-patcher-20261019-01 702M). 50GB 배경 블록·background.jsonl은 이미 삭제됐으므로 count 표는 이 압축본으로만 남아 있다.
- 진행: 작은 디렉터리 3개(94파일)는 SHA256 대조 일치. counts 압축본 포함 en-blt50gb-compare-20261105-01은 복사 중(약 11MB/s).

## 2026-11-27 KST / ENCODER/HASH 축소 실험 순서 변경(사용자 결정)

- 사용자 결정: ENCODER/HASH 축소 실험은 T14(한국어 count 패처) 뒤 맨 마지막으로 미룬다. task.md T13과 docs/KOREAN_NEURON_PREP.md에 반영했다.
- T14 의존성 정리(코드·계획 기준): count 패처는 교사 패처(run1, threshold 1.140625)의 경계를 근사하도록 적합하므로 배경 count 표, 교사 라벨, 경계 모수·threshold 적합, 패처 단독 비교는 본체 없이 지금 가능하다. BLT에 넣은 BPB·전체 속도 비교만 C 최종 본체가 필요하다.
- 백업 완료(KST 11:24 복사 종료): 복사 1597초, 이어 외장 디스크에서 179개 파일 전체를 SHA256SUMS와 대조해 179/179 일치(457초). macOS가 exFAT에 만든 `._*` 부속 파일은 목록 밖이다.
- 사용자 결정(T14 진행 방식): 자료는 Neuron에서 v003 train 표본을 뽑아 itcerdo로 전송한다(추출 스크립트·sbatch는 에이전트, 실행·전송은 사용자). 배경 count 표는 50GB로 시작한다. ENCODER/HASH는 T14 뒤.

## 2026-11-27 KST / T14 한국어 count 패처 자료 추출기 구현·검증(Neuron 실행 전)

- 구현: neuron/runtime/blt_hf/count_sample.py, neuron/sample_count_data.sh(cpu 파티션, CPU 4, 16GB, 12시간), 테스트 neuron/runtime/tests/test_hf_count_sample.py. bundle FILES에 추가하고 runtime-manifest를 itcerdo phdq_blt_hf에서 refresh했다(29파일). 명령표 14절 추가.
- 추출 규칙: run1 계약의 dataset manifest에서 train·validation·held_out_test를 끝까지 읽어 SHA-256을 대조한다. 각 줄의 역할은 SHA-256("count-sample:<seed>:"+줄) 앞 8바이트 값으로 정한다(seed 20261127). train에서 [0,1e-4)는 라벨 적합용 train 4MB, [1e-4,0.4001)은 배경 50GB이고, validation(앞 20000문서 제외)과 test는 [0,5e-3)에서 각각 0.5MB, 1.5MB를 뽑는다. 파일 순서대로 바이트 목표까지 문서 단위로 채우고, 길이 256~65536바이트만 쓴다(영어와 같음). 행 형식은 영어 실행기와 같다(document_id, source, text, text_sha256, revision=원본 manifest SHA, source_split, source_line). 배경은 gzip(level 1, mtime 0)으로 쓰고 압축 전·후 SHA를 모두 기록한다.
- 검증(itcerdo runs/ko-count-sample-validation-20261127-01, phdq_blt_hf): 새 테스트 3개(독립 구현과 역할별 줄 번호 일치, 해시·길이·바이트 목표, 같은 seed 재현·다른 seed 차이, 목표 부족·원본 SHA 변조·held_out_test 없음 실패)와 기존 runtime 32개, bundle 6개 통과. 실제 형식 smoke: 이전 30만 문서 native 통합 출력(1.17GB)에서 배경 100MB·train 4MB·validation 0.5MB·test 1.5MB를 3.97초에 추출했고 gzip 비율은 0.48이었다. 50GB 배경의 압축본은 약 24GB로 예상한다(추정).
- 다음: 사용자 승인 후 push, Neuron 제출(사용자), Mac 외장 디스크로 수신(사용자), itcerdo 이동·검증(에이전트). itcerdo 쪽 라벨(run1 교사 교체)·배경 블록·적합 실행기는 이어서 준비한다.

## 2026-11-27 KST / T14 push와 itcerdo 실행기 준비

- 사용자 승인으로 neuron/ 6개 파일을 커밋 fa49202 "[T14][mac] Add Korean count-patcher sample extraction"으로 push했다. 명령표 14절에 itcerdo 수신 경로를 추가했다(datasets/ko-count-sample-20261127-01/, artifacts/korean_entropy/ko-entropy-h200-20261107-01/; 디렉터리는 미리 만듦). Neuron 추출과 전송은 사용자가 한다.
- run1 checkpoint final-00137500.pt SHA-256은 runtimelog/patcher-compare-980258.out의 7505624f…fe0d9이며 설정에 고정했다.
- itcerdo 실행기(미커밋): scripts/run_background_expansion.py에 준비 경로 dataset_background_v1(추출 데이터셋의 background.jsonl을 SHA 확인 후 hard link, data_preparation.json 작성) 추가. scripts/prepare_patcher_labels.py는 설정의 dataset_id와 teacher_patcher(checkpoint·sha256·threshold)를 받아 blt_hf.patcher_compare.checkpoint_patcher로 교사를 바꾸고 계약에 교사 SHA·threshold를 넣는다. scripts/fit_count_patcher.py는 설정의 screened_configurations를 받고, minimum_validation_f1이 없으면 판정 없이 status fitted로 기록한다. 새 설정 experiments/korean_patcher_t14.json(K=8, W 무제한은 영어 설정 재사용, 합격 기준 없음, bootstrap 2000), 계획 experiments/korean_background_50gb.json(25MB gzip 블록, C++ 8 workers), 순서 실행기 scripts/run_korean_t14.sh(전송 SHA 확인→pigz 해제→prepare→build→labels(--blt-project=사본의 neuron/runtime)→fit(cpp_v1, projection 저장)→LMDB; 끝난 단계는 status로 건너뜀), 테스트 test_dataset_background_is_linked_after_hash_check.
- 검증: itcerdo runs/ko-patcher-t14-smoke-20261127-01/source(로컬 코드 사본)에서 관련 테스트 40개와 나머지 35개(1 skip) 통과, bash -n 통과.
- smoke(진행 중): 30만 문서 실제 형식 표본(배경 100MB, train 4MB, validation 0.5MB)과 공개 패처 가중치를 FP32 master로 저장한 대역 교사(SHA 0e841643…, threshold 1.140625)로 전체 순서를 실행했다. 해제·prepare 1초, 블록 4개 23초(peak RSS 11.7GB), 라벨 63초(train 2553청크/4,005,303위치, validation 307청크/502,043위치). 대역 교사의 평균 패치 길이는 1.87바이트다(공개 패처가 한국어에서 entropy가 높아서이며 run1 결과가 아님).
- smoke 완료(UTC 04:58:17~05:15:23, 17분): 적합 15분 5초(배경 투영 20.8초, 특징 265.6초, L-BFGS 1.1초, threshold 시도 15회), LMDB 31초(문맥 34,009,828개, data 1.46GB), 블록 4개 416MB. 적합 status fitted, threshold 0.375. 대역 교사 기준 validation F1 0.774712(문서 bootstrap 95% [0.7680, 0.7808]), 후보 평균 패치 1.49 / 교사 1.88바이트. 대역 교사라서 이 수치는 실행 경로 확인용이며 한국어 결과가 아니다. 라벨 계약에 교사 SHA와 threshold 1.140625가 기록됐다.
- 본 실행 준비: runs/ko-patcher-t14-20261127-01/source에 같은 코드 사본을 만들고 source_manifest.sha256(104파일)을 기록했다(smoke 사본과 코드 일치). 자료가 itcerdo에 도착하면 tmux에서 scripts/run_korean_t14.sh를 실행한다. 영어 50GB 실측으로 추정한 소요는 블록 약 1.5~2시간, 적합 약 40분, LMDB 약 1.5시간이다(추정).
- 미커밋: itcerdo 쪽 변경(scripts 3개, tests 1개, experiments 2개, run_korean_t14.sh). scripts/run_background_expansion.py·fit_count_patcher.py·tests/test_data_preparation.py에는 이전부터 있던 영어 C++ 경로 미커밋 변경도 함께 있다.

## 2026-11-27 KST / T14 추출 job 제출 거부와 수정

- 사용자 보고: `sbatch --export=ALL,RUN_ID=ko-count-sample-20261127-01 neuron/sample_count_data.sh`가 "Invalid --comment value"로 거부됐다. 원인은 스크립트의 `appl=python`이다. 다른 Neuron job에서 받아들여진 `field=nlp;appl=pytorch`로 바꿔 커밋·push했다. 갱신 전에는 명령행 `--comment="field=nlp;appl=pytorch"`가 스크립트 값을 덮어쓴다.

## 2026-11-28 KST / T14 자료 수신 확인

- 사용자 보고: Neuron 추출과 Mac(T31) 경유 itcerdo 전송 완료. 수신 위치는 명령표 14절의 두 디렉터리다(자료 5파일, run1 checkpoint와 .sha256).
- 추출 manifest(status prepared, 소요 1813초, script SHA 118f5afe…): 원본은 v003 manifest-reviewed.json(SHA 420071b0…), 원본 줄 수 train 34,311,395 / validation 39,446 / test 80,653.
- 추출량(측정): 배경 13,693,137문서, 본문 50,000,002,259바이트(FineWeb2 13,667,869문서, NIKL 10출처 합계 25,268문서). gzip 24,141,846,379바이트(본문 바이트 대비 0.483). train 1,074문서 4,000,301바이트, validation 109문서 510,257바이트, test 394문서 1,501,639바이트이며 세 분할 모두 FineWeb2 문서만 뽑혔다.
- SHA-256 대조(itcerdo sha256sum): train b2e258fd…, validation 28ca4846…, test 21afe34c…가 manifest와 일치. checkpoint 7505624f…가 .sha256 파일·설정값과 일치. 배경 압축본(f2ce5eef…)은 실행기 첫 단계에서 대조한다. 실행용 source 사본 104파일도 source_manifest.sha256과 일치.
- 실행 전 상태: itcerdo GPU 사용률 0%, load 0.08, 가용 RAM 58GB, 디스크 여유 548GB.

## 2026-11-28 KST / T14 본 실행 시작(itcerdo)

- 시작: UTC 08:16:07, tmux `blt-ko-t14-20261127-01`, `bash runs/ko-patcher-t14-20261127-01/source/scripts/run_korean_t14.sh`, 출력은 run의 launch.log.
- 배경 압축본 SHA-256(f2ce5eef…) 일치, 43초. pigz 해제 206초(08:16:51~08:20:17), background.jsonl 54,760,725,589바이트. 쓰기 속도가 처음 약 300MB/s에서 28GB 이후 약 90~175MB/s로 떨어졌다(vmstat 측정). 작업 경로는 SATA SSD(sda, Crucial MX500)이며 NVMe에는 마운트되지 않았다.
- prepare 100.6초: 해제본 SHA-256 9efee5ba…가 manifest와 일치했고, 13,693,137문서와 50,000,002,259바이트를 run에 hard link했다(data_preparation.json). build는 UTC 08:22:05에 시작했다(첫 단계에서 해제본을 다시 해시한다).

## 2026-11-28 KST / T14 build 중단과 저장 예산 수정 후 재시작

- 발견: 한국어 블록 하나(본문 25MB)가 gzip 약 112.7MB로 영어 50GB 블록(블록 123G/2000개, 약 61.5MB)의 약 1.8배였다. 완료된 28블록 평균은 문맥 14,103,080개, 압축 112,682,247바이트, 본문 25,004,484바이트다. 영어 50GB의 블록당 입력 행은 약 12.9M개였다. 2000블록이면 약 225GB(209.9GiB)이고, run 안의 hard link background.jsonl(51.0GiB)도 build의 저장량 검사에 포함된다. 합계 약 261GiB는 계획의 저장 예산 250GiB를 넘어 약 1900번째 블록에서 실패하는 계산이다(에이전트가 smoke 블록 크기로 잡은 예산의 오류).
- 조치: build 시작 약 3분(블록 28개 완료) 후 UTC 08:25:19에 tmux에 Ctrl-C를 보내 중단했다. 부분 산출물(블록 32개 3.59GB, native_counts, progress.md, launch.log 사본)은 지우지 않고 runs/ko-patcher-t14-20261127-01.aborted-build-01/로 옮겼다. 중단 전 처리 속도는 블록 28개(본문 0.70GB)에 약 85초였고 peak RSS는 18.6GB였다(측정).
- 계획 experiments/korean_background_50gb.json의 maximum_new_artifact_storage_gib을 250에서 300으로 바꿨다(로컬과 실행 사본 같음, SHA 87df9da2… → 8bf5102d…). 실행 사본의 이전 해시 목록은 source_manifest.sha256.20261127로 보존하고, 새 목록은 이 파일 한 줄만 다르다(104파일 대조 일치). 디스크 예상(추정): 해제 후 여유 약 493GB에서 블록 약 225GB, LMDB(영어 50GB는 68G) 뒤에도 최소 여유 30GiB보다 크다.
- 재시작: UTC 08:26:00 같은 tmux 이름으로 실행기를 다시 시작했다. 검증·해제·prepare는 완료 상태로 건너뛰고 build부터 진행한다.

## 2026-11-28 KST / C 본 학습 job 996490 결과, A 대조군 보류(사용자 결정)

- 로그 GitHub 7d1d0bc(병합 895d31d): runtimelog/body-996490.out/.err, count-sample-login.out.
- job 996490(gpu54, 2026-11-26 23:31 UTC 시작): step 24379 → 28418, status deadline(마감 20분 전 저장, step-00028418.pt). decay는 계산대로 step 27272에서 시작했다(reason max_steps, 길이 2728, 1e-4 → 1e-5). step 28400 lr 6.28e-5.
- 측정: 기록된 404 step의 처리량 중앙값 50.6KB/s(최소 12.2, 최대 82.1), peak 98.1GB, 평균 gradient norm 0.0587. 누적 노출 29.87GB, elapsed 594,782초(step 28410).
- 검증 BPB(같은 2000문서): 24500 0.7082, 25000 0.7106, 25500 0.7082, 26000 0.7067, 26500 0.7064, 27000 0.7062, 27500 0.7022, 28000 0.7009.
- 남은 일(예상): 1582 step(약 21초/step, 약 9.2시간)과 20000문서 최종 검증(2000문서당 약 51초, 약 9분). job 하나로 끝난다. 이어 제출 여부는 사용자 확인 필요.
- 사용자 결정: A-5GB 대조군(step 3500에서 정지)은 의미가 크지 않아 다른 작업이 모두 끝난 뒤로 미룬다.
- count 자료 추출 로그(로그인 노드 실행): train 100만 줄마다 약 49초, 전체 1813초(manifest elapsed와 같음).

## 2026-11-28 KST / T14 BLT 비교 준비: C 본체 export와 한국어 비교 실행기

- 사용자 승인: 병행 작업 1(C 본체 BLT 비교 준비), 3(로그 분석), 4(미커밋 코드 커밋)를 진행한다. 2(한국어 경계 진단)는 이번 범위 밖이다.
- Neuron export(신규): neuron/runtime/blt_hf/body_export.py, neuron/export_body.sh(cpu 파티션, CPU 4, 64GB, 4시간), 명령표 15절. checkpoint .sha256과 run 계약 서명(contract.json)·학습 목록(trainable.json, trainable_sha256)을 대조한 뒤 FP32 master를 BF16으로 바꿔 body.safetensors와 export.json(원본 checkpoint SHA, 계약, progress, 해당 checkpoint의 validation-final, 본체 SHA)을 쓴다. torch.load는 mmap·weights_only다. 패처와 optimizer·RNG 상태는 넣지 않는다. 불러오기(load_exported_body)는 공개 모델 SHA(계약 weights_sha256·config SHA), 본체 SHA, 이름·shape·dtype을 확인하고 계약의 패처 SHA·threshold로 load_body 한 뒤 본체 텐서를 덮어쓴다. bundle FILES에 추가해 runtime-manifest를 itcerdo phdq_blt_hf에서 refresh했다(30파일). C 학습 계약의 source 파일은 바꾸지 않았으므로 남은 C job 재개 서명에는 영향이 없다.
- itcerdo 비교 실행기(신규): scripts/compare_korean_blt.py, scripts/run_korean_blt_comparison.sh, tests/test_korean_blt.py. quality는 test 전체를 2047바이트+BOS 청크로 나눠 original(본체 + run1 패처 @1.140625), count_python, count_cpp 세 모드의 BPB, 경계 일치(정밀도·재현율·F1·F0.5), 패치 길이 분포를 잰다. Python/C++ count 백엔드의 패치 길이와 전체 logits가 모든 청크에서 같아야 한다. timing은 길이 256/512/1024/2048마다 패처 단독 prefill, 패처 단독 32 step 증분, 전체 모델 초기+32 step을 3 warmup+10회 순서 교대로 잰다. 판정 기준은 넣지 않았다(영어 bpb_summary의 0.01 기준을 쓰지 않음). 본체 패처 SHA·threshold가 count 라벨 교사(라벨 계약)와 다르면 중단한다. 생성(generation) 단계는 한국어 프롬프트가 정해지지 않아 넣지 않았다.
- 검증(itcerdo runs/ko-blt-compare-validation-20261128-01/source, phdq_blt_hf): 새 단위 테스트 4개 통과. runtime 테스트 52개 통과(새 export 테스트 포함: 2 step 학습 checkpoint의 master BF16과 export 텐서 일치, 공개 모델에 불러온 뒤 본체는 export·패처는 공개값과 일치, 출력 재사용 거부, 본체 변조·다른 run checkpoint·run 밖 checkpoint 거부). test_bundle 통과.
- smoke(파이프라인 확인, 결과 아님): 공개 본체 + T14 smoke의 대역 교사(0e841643…, @1.140625)·LMDB·적합 규칙, smoke 자료 test 3문서(5청크). quality 45초, Python/C++ 완전 일치, original 1.1705 / count 1.1668 BPB, 경계 F1 0.780, 평균 패치 길이 1.88 / 1.51, peak RSS 10.2GB. timing(길이 256)은 세 종류 모두 완료하고 33회 Python/C++·warm/fresh 일치와 단독 신경망 패처=모델 호출을 확인했다. build가 CPU를 쓰는 중이라 시간 값은 기록하지 않는다.
- itcerdo 수신 경로를 만들었다: artifacts/korean_body_export/ko-body-full-run1-45-20261117-01/.
- T14 build 진행(UTC 09:18): 블록 1096/약 2000, peak RSS 19.4GB, 디스크 여유 379G. 블록당 약 2.8초.

## 2026-11-28 KST / 미커밋 변경 커밋(사용자 승인)

- 커밋 전 검사: itcerdo 검증 사본(phdq_blt_hf)에서 저장소 tests 79개 통과(1 skip), runtime 테스트 52개 통과. 커밋 대상에서 토큰·개인 키·비밀번호 형식 문자열 검색 결과 없음.
- 7ddf2ea [T07-T14][mac] Add count-patcher native/LMDB pipeline, English analyses and Korean T14 runner: 영어 count 경로의 C++ count·LMDB·디스크 준비·분석·진단 스크립트, 실험 설정(english_*, korean_*), T14 itcerdo 실행기(dataset_background_v1, 교사 교체 라벨, 기준 없는 적합)와 테스트(53파일).
- de61030 [T05-T11][mac] Add English count-patcher evidence: evidence/english_*.json 52개. 가장 큰 파일은 english_blt_cpp_quality_20261029.json(22.7MB)과 english_blt_patcher_quality_20261028.json(15.0MB)이며 문서별 수치를 담는다. 생성 결과 파일에는 짧은 원문 접두부(약 211자)와 생성문이 들어 있다.
- 0d96798 [T14][mac] Add C body export and Korean BLT comparison runner(9파일).
- 이어서 문서(README, root command.md의 사용자 추가 절, docs, T13.plan.md, log.md, task.md)를 별도 커밋하고 push한다.

## 2026-11-28 KST / C 학습 길이 검토(사용자 질문: 30000 step 종료가 합리적인가)

- push 결과: 861bba7 [docs][mac] Update log, task, handoff and Korean preparation notes까지 origin/main에 올렸다.
- 자료: C job 7개 로그(983536~996490)의 500 step 검증 BPB(같은 2000문서) 전체 이력.
- 측정: 고정 lr(1e-4) 구간의 직선 기울기는 17000~22000에서 1000 step당 -0.00165, 22000~27000에서 -0.00161로 최근 10000 step 동안 줄지 않았다. 5000 step마다 최저값은 5000 0.7881, 10000 0.7529, 15000 0.7290, 20000 0.7195, 25000 0.7082, 27000 0.7062다. 개별 평가의 흔들림은 곡선 적합 잔차 표준편차로 약 0.0024다.
- 사용자 정체 규칙(최근 10회 최저 개선 0.002 미만)은 27000에서 0.0086(22000까지 최저 0.7148 → 0.7062)이라 성립하지 않았다. decay는 max_steps 30000 상한 때문에 27272에서 시작했다. 27272 이후의 하락(28000 0.7009)은 주로 lr decay 효과로 보며, 고정 lr 학습이 계속 좋아진다는 근거는 위 기울기다.
- 추정(가설, 외삽): 거듭제곱 곡선 적합(시작 2000/5000/10000 step)으로 고정 lr을 27000에서 더 이어 갈 때의 개선은 40000까지 약 0.005~0.017, 50000까지 약 0.007~0.026, 60000까지 약 0.008~0.033 BPB다. 직선 유지 가정은 이보다 크다(40000까지 약 0.021). 곡선 형태에 따라 폭이 크다.
- 비용(측정 처리량 기준): 1000 step당 약 5.8시간, 24시간 job 하나에 약 4040 step. 27272에서 40000/50000/60000까지 각 12728/22728/32728 step으로 약 3.2/5.6/8.1일(대기열 간격 제외). train split 232.7GB 중 노출은 50000 step에서도 약 52GB라 반복은 없다.
- 방법 검토: 현재 run은 이미 decay 중이고 max_steps가 계약 서명에 들어 있어 같은 run에서 늘릴 수 없다. predecay-00027272.pt(고정 lr 상태의 FP32 master·AdamW·자료 위치)에서 새 run으로 이어 가면 지금의 30000 decay 결과를 버리지 않고 decay 시점만 뒤로 옮길 수 있다. body_train에는 이 이어받기(init_from) 경로가 아직 없다. 상한·병행 여부는 사용자 결정 대기.

## 2026-11-28 KST / C 연장 결정과 decay 전 checkpoint 이어받기(init_from) 구현

- 사용자 결정: C는 step 상한 없이 정체 규칙(최근 10회 평가 최저 개선 0.002 미만)으로만 decay를 시작한다. 연장은 30000 decay가 끝난 뒤 돌리는 쪽을 선호하며, 대기 중 job을 모두 취소하고 predecay에서 바로 시작해도 되는지 질문했다.
- 답변 요지: 취소해도 연장 자체에 잃는 것은 없다. 잃는 것은 약 10 GPU시간으로 얻는 30000 decay 본체이며, 이는 T14 BLT 비교에 곧 쓸 수 있는 본체이자 같은 decay 절차로 만든 "짧은 학습" 기준점이다(연장 본체와 decay 대 decay로 학습 길이 효과를 비교할 수 있음). 연장 코드는 C 마지막 job이 끝난 뒤에만 Neuron에 반영할 수 있다(아래 주의).
- 구현(neuron/runtime/blt_hf/body_train.py): config `init_from` {checkpoint, sha256}과 preflight 검사, `branch_from`. checkpoint·sidecar·설정의 SHA, 부모 contract 서명, 한도 키(run_dir, max_steps, max_train_bytes, max_seconds, max_run_bytes, init_from)를 뺀 설정 전체, manifest·가중치·config·학습 목록 SHA가 부모와 같아야 한다. decay 시작 뒤 갱신이 들어간 checkpoint는 거부한다. FP32 master·AdamW·RNG·자료 위치·경과 시간·검증 이력을 이어받고 예정 decay를 지운다. 새 run 시작 때만 적용하고, 이후 job은 기존 RESUME=latest로 이어 간다.
- 테스트(itcerdo 검증 사본, phdq_blt_hf): tiny 모델 부모 run(max_steps 12, step 7부터 decay)의 predecay-00000007에서 max_steps 20으로 이어 간 run의 step 8~10이, 처음부터 max_steps 20으로 승인한 run과 exposed bytes·lr이 같고 byte_bpb 차이가 0.02 이내다. 이어받은 검증 이력은 step [0, 2, 4, 6, 8], decay 없음. 잘못된 SHA, 한도 밖 설정 변경(lr), decay 뒤 checkpoint는 run 디렉터리를 만들기 전에 거부한다. body_train 테스트 9개, runtime 53개, bundle 6개 통과. runtime-manifest를 refresh했다(30파일).
- 명령표 13-6 추가: 연장 run ko-body-full-run1-45-ext-20261128-01, 설정은 C 설정 그대로에 init_from과 한도만 바꾼다. 한도는 필수 항목이라 상한으로 작동하지 않게 잡았다: max_steps 215000(train 1회분 안에서 decay까지 끝나는 값), max_train_bytes 232722508043(train 1회분), max_seconds 8640000(100일), max_run_bytes 3e11.
- 주의: body_train.py는 C 계약의 source 목록에 들어 있다. 아직 시작하지 않은 C job이 새 코드로 시작하면 서명이 달라져 멈춘다. Neuron 코드 갱신은 C 마지막 job이 끝난 뒤에 한다(명령표 13-6·15절). 실행 중인 job은 시작 때만 서명을 확인한다.
- 추정(가설): 곡선 적합 기울기가 1000 step당 0.0004(10회 구간 0.002)로 줄어드는 지점은 약 55000~95000 step이다. decay(10%)까지 27272부터 약 3.4만~7.5만 step, GPU 약 8~18일(대기열 제외)이다. 평가 흔들림(약 0.0024) 때문에 실제 발동은 앞뒤로 달라질 수 있다.
