# 독립 캐시 프로젝트 인수인계

이 분리본은 2026-09-27에 `phdq3`의 `main` 커밋 `6dbdb4f`를 기준으로 준비했다.
새 저장소는 `src/phdq_blt_cache/`, 테스트, 이 계획과 향후 캐시 추론 개선을 담당한다.
기존 GEC 프로젝트의 변환·학습·평가 파일은 참조 자료로 보존한다. **2026-10-29 사용자 정정:**
이번 작업에서 phdq3는 읽기 전용이다. 새 코드·설정·테스트·문서·로그는 전부 blt-cache에 둔다.
한국어 entropy 구현은 `neuron/runtime/`에서 직접 관리하며 외부 프로젝트 export는 하지 않는다.
Neuron의 새 데이터·설정·출력 루트는 `/scratch/r984a02/blt-cache`다.
현재 시작점은 [루트 명령 안내](../command.md)와 [Neuron 명령표](../neuron/command.md)다.
정리본 게시 commit은 `0dd953189005c524847fda2f879bfcd8af376132`이며 GitHub main 일치를 확인했다.
이후 제출 위치 수정은 `3fb7eab6af59773fcf72f99be31338cd50b9084e`로 게시하고 원격 main 일치를 확인했다.
sbatch cwd는 `/scratch/r984a02`, 코드 clone·자료·출력은 `/scratch/r984a02/blt-cache`,
job 내부 cwd는 `neuron/runtime/`다. 사용자 확인 제출 조건을 적용했으며 로컬 guard5개와
문서25개 bash 블록/9개 sbatch cwd 검사를 통과했다. Neuron 제출 자체는 실행하지 않았다.
아래 예전 소유/배치 경로 설명은 이력이며 새 기록 위치로 사용하지 않는다.

## 소스와 현재 상태

- 참조 프로젝트에 잘못 만들었던 로컬 entropy 코드/설정/테스트/안내5파일을 blt-cache에
  보존한 뒤 제거했고,그곳 log.md에 덧붙인9줄은 여기 log.md로 이관했다. 기존 사용자
  command.md hash는 불변이다. 과거 안내 원문은 [폐기된 경로 안내 이력](archive/KOREAN_ENTROPY_20261029.md)에 보존했다.
- 경로 정정 후 guard4검사/manifest15파일 검증과 로컬 entropy7검사 통과(optimizer1개 Torch 부재 skip).
  원격 itcerdo의 이전 배치본·자료 경로와 실행 중20GB 작업은 이번 로컬 회수에서 변경하지 않았다.

- `src/phdq_blt_cache/frontier.py`와 `global_reuse.py`는 위 커밋의
  `phdq3/blt_hf/cache/`에서 복사했다. `phdq3`의 가드 백엔드는 현재 디코더 재사용을
  끈 상태에서 `GlobalPrefixReuse.run(..., logits_to_keep=1,
  guard_margin=1.0)`을 호출한다.
- 네이티브 A100 전체 검증 비교에서 생성 토큰 ID, EOS와 문자열이 HF 기준과
  2,634/2,634개 일치했다. 생성만 측정한 시간은 HF 9,074.30초, 가드 적용
  6,906.76초로 1.314배 빨랐다. 보고서는
  `evidence/p3a_native_full_guarded_11.json`이다. 다른 모델·데이터셋·빔 수·배치
  크기·장치나 코드 변경에 대한 동일성을 입증하는 결과는 아니다.
- 가드 여유값 1.0은 실험적 휴리스틱이다. BF16에서 처음 출력이 갈라지는 로짓 차이를
  관측한 뒤 정했으며, 외부의 오차 보장으로 도출한 값이 아니다. 이 값이나 재사용
  규칙을 바꿀 때마다 출력 비교를 유지한다.
- 복사한 `docs/ORIGINAL_P3A_PLAN.md`와 `docs/DESIGN_HISTORY.md`에는 이전 판단
  근거가 보존돼 있다. 일부 내용은 실험 11 이전 기록이므로 현재 후속 작업은
  `docs/PLAN.md`를 따른다.

## 실행 계약

2026-11-01 한국어 자료 정정: 사용자 보고서로 NIKL audit/split만 완료를 확인했다.
전체 자료는 NIKL+FineWeb2이며,사용자는 FineWeb2 한국어 train 전체/새 산출물10TB를 선택했다.
standalone entropy_fineweb catalog/download/combine을 구현하고 실제 합성 Parquet 포함4검사를
통과했다. NIKL 원장·분할을 보존하고 공식 FineWeb test는 내려받지 않는다.
[현재 실행 명령](../neuron/command.md#6-4-fineweb2-한국어-전체-train-확보-및-nikl-통합)을 따른다.
실제 전체 다운로드/통합·권리/PII/근접 중복 검토·학습은 아직 미완료다.
10TB는 상한이지 실제 가용 공간이나 학습 노출량이 아니다. 현재 학습 승인은 false로 유지한다.

최신 대체 패처 연구는 [task.md](../task.md)의 T08·T09를 따른다.2026-10-29에
10GB8설정의 재적합·독립 F1/F0.5 순차 선택·계층별 진단·111문서 paired통계·검증
전용8입력 단독 시간을 완료했다. 최고 F1=0.7854195066으로0.90 미달이며 후보나
기본 백엔드를 새로 채택하지 않았다. [분석](../evidence/english_count_analysis_10gb_20261029.json),
[시간](../evidence/english_count_analysis_timing_20261029.json)과
[통합 설명](INTEGRATION.md)을 참조한다. 사용자 순서는 이 결과 확인 뒤20GB 배경
빈도 적합을 진행하면서 Neuron 한국어 T12를 준비하는 것이다. 기존10GB 결과·평가
보호·48GiB RAM/100GiB 새 산출물 예산을 보존한다. 한국어 제출이나 상시 전환 승인이 아니다.
20GB 계획은 [고정 계획](../experiments/english_background_20gb_nested.json)이며
UTC01:58:50에 itcerdo tmux blt-bg20gb-nested-20261029-01에서 시작했으나 이후 조회한
원격 runs/en-patcher-bg20gb-nested-20261029-01/run_report.json에서 prepare 실패를
확인했다(status=failed,elapsed4368.500978s). fit/compare 완료가 아니며 원본·실패
산출물을 보존했다. 후속 진단에서 shard별 후보 부족과 기존4개 shard의 원문 용량 한계를
확인했고,동일 FineWeb revision의 추가12shard를 고정한 [재시도 계획](../experiments/english_background_20gb_retry.json)으로
UTC08:33:53에 새 tmux blt-bg20gb-nested-20261029-02를 시작했다.2026-11-01 후속 조회에서
2026-10-30 UTC09:15:47의 prepare/build/fit/compare 완료를 확인했다. 배경4891146문서/20000001834바이트,
F1 0.785368→0.787836(+0.002468),111문서 대응95%구간[+0.001639,+0.003274]다.
같은 검증 재사용의 기술통계이며0.90 기준 미달/후보 미채택이다. [20GB 결과 확인](../evidence/english_background_20gb_result_20261101.json)에
고정 보고서 hash/계획·부모 identity 대조·수렴·시간/메모리와 미측정 한계를 기록했다. 이전 prepare 진행 표시는 과거 상태다.
2026-11-01 UTC09:14:41에 [30GB 새 계획](../experiments/english_background_30gb_nested.json)의
fresh run en-patcher-bg30gb-nested-20261101-01을 시작했고09:15:11에 prepare를 확인했다.
20GB 실제 BLT 비교는 [고정 명령](../scripts/run_blt20gb_comparison.sh)으로 등록되어
30GB 종료 후 자동 시작한다. source는 runs/en-blt20gb-compare-20261101-01/source의
독립 snapshot94파일 SHA로 고정했고 기존 source/모델 환경/부모 자료는 수정하지 않았다.
두 단계는 자원 peak/timing 간섭을 피하려고 순차 실행하며 새20GB 비교·30GB 적합 수치는
아직 없다. 실행 상태와 다음 검토는 [통합 문서](INTEGRATION.md), [task](../task.md),
[log](../log.md)를 따른다. 실행 중 snapshot 코드를 수정하거나 중복 실행하지 않는다.
[한국어 준비](KOREAN_NEURON_PREP.md)는 학습 미승인 T12 계약이다. 사용자 요청으로
모두의 말뭉치+FineWeb2를 기본으로 하고 세종 확보는 필수 조건에서 제외했다.
itcerdo 소유 phdq3/data/korean_cpt/incoming/nikl 수신 경로 및 패처 전용
blt_hf.entropy_train/entropy_data·설정·안내를 준비했다. CPU 준비7검사+스케줄3검사와
실제99,512,064모수 BF16 패처 strict load/합성 역전파를 통과했지만 GPU 파일럿은
미실행이다. 자료 수신·약정/분할·자원 예산 승인 및 Neuron 할당 확인은 남았다.
[Neuron 배포](../neuron/README.md)는 기존 소유 코드를 덮어쓰지 않는 고정 사본과 H2001GPU
전용 wrapper다. 기본은 preflight,승인 false/예산 null 유지. 소유 신호 처리 후 CPU11검사,
독립 배포 guard3/entropy8 및 실제 패처 strict load를 통과했다. GPU 학습/재개는 미검증이다.
`neuron/`만 GitHub `esoterikosQ/26-14_CACHE`의 commit
`a0cfa521a272ac61f19d60bde17674cb2e86fa56`로 게시했고 원격 main SHA 일치를 확인했다.
UTC08:42:36 run02 heartbeat는 checks480/scratch4192909863B/RSS201170944B다.

2026-10-29 사용자 제공 [T13.plan.md](../T13.plan.md)를 한국어 준비 문서·JSON과
task T12~T14에 병합했다. 공개 가중치 CPT,BLT/PATCHER/ENCODER/조건부 HASH/BODY_FULL 비교(2026-11-12 순서 변경: ENCODER → HASH → BODY_FULL)와 동일 본체
독립 출발·동일 노출 통제를 따른다. 교사는 본체 비교 전에 확정하며 최종 본체/교사를
고정한 뒤 count 교체를 비교한다.5090 우선안·혼합75/15/10·1GB/5GB 등은 미승인
제안이고 기존 H200 목표를 자동 변경하지 않았다. 원본 외부 경로·Slurm 정책·모델
메모리/기간 추정은 재검증 대상이다. 이번 병합은 학습 실행이나 원격20GB 변경이 아니다.

`GlobalPrefixReuse`에는 `.model` 아래에 `phdq3` OSC BLT 순전파 시그니처를 따르는
`patcher`, `global_transformer`, `local_decoder` 모듈이 있는 모델이 필요하다.
입력은 패딩 없는 배치 1의 바이트 토큰 접두부이며 호출마다 한 바이트씩 늘어나야 한다.
`model.eval()`과 `torch.inference_mode()`를 사용한다. 가드 경로에는
`logits_to_keep=1`과 `reuse_decoder=False`가 필요하다. 이 클래스는 모델 출력과
재사용 진단을 반환하며, 바이트 선택이나 텍스트 디코딩은 수행하지 않는다.
호출 중 모듈의 `forward` 메서드를 일시적으로 교체하므로 동시 캐시 호출 사이에서
모델 인스턴스를 공유하지 않는다.

GitHub 원격은 `https://github.com/esoterikosQ/26-14_CACHE.git`다. 이번 게시에는 신규
`neuron/`만 포함했고 다른 미커밋 실험 변경은 포함하지 않았다. 오래된 초기 게시 안내와
현재 상태를 혼동하지 않는다. 실행 중인 BLT 프로젝트의 기본 경로나 환경은 변경하지 않는다.
설치 없이 `pip`가 GitHub 코드를 직접 가져와 import할 수 있다고 설명하지 않는다.

## 호스트와 데이터의 작업 범위

- Mac: 코드 편집, 순수 Python 검사, JSON 근거 검토를 수행한다.
- Itcerdo: 사용자는 2026-10-19에 개인적으로 관리하는 서버이며 별도의 호스트 제한이
  없다고 명확히 했다. 이는 과거의 BF16 추론·프로파일링 전용 제한과 프로젝트 경로
  제한보다 우선한다. 요청한 작업 범위 안에서 CPU/GPU 최적화, 역전파, 미세조정과
  사전학습을 수행할 수 있다. 실험 경로와 자원 예산을 명시하고 기존 작업·원본
  체크포인트를 보존하며, 모델 파일과 학습 산출물은 이 패키지의 Git 관리 대상에
  넣지 않는다.
- Neuron: 접속·전송·Slurm 작업 제출은 사용자만 수행한다. 여기서는 명령을 준비하고
  전달받은 로그를 분석한다. 이 분리 작업을 위해 현재 대기 중인 네이티브 학습 작업을
  중단해 달라고 요청하지 않는다.
- 연구 데이터와 외부 검증·평가 분할은 이 패키지에 복사하지 않는다. 패키지 테스트는
  합성 입력을 사용하고, 연동 검사는 원래 BLT 프로젝트의 데이터를 수정하지 않고
  사용한다.

재사용 가능한 Codex 작업 절차는 `skills/blt-cache-development/SKILL.md`에 있고,
새 프로젝트의 `AGENTS.md`에서 이를 가리킨다. 새 Codex 환경에서 개인 스킬로 자동
탐색되게 하려면 해당 폴더를 `$CODEX_HOME/skills/`로 복사한다. 프로젝트 작업 자체는
이 스킬 설치에 의존하지 않는다.
