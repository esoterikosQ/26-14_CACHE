# Neuron Entropy CPT

사용자가 GitHub에서 받아 Neuron에서 직접 실행하는 T12 전용 배포 디렉터리다.
에이전트는 Neuron에 접속하거나 파일 전송/SLURM 제출을 하지 않는다.
영어20GB 빈도 자료 확장은 itcerdo에서 별도로 실행한다.

데이터 저장 위치와 작업별 셸 명령은 [command.md](command.md)를 따른다.

## 배포 범위

- `train_entropy.sh`: 기존 `phdq3/scripts`의 root/SLURM/환경 정책을 참조한 entropy 전용1GPU job.
- `runtime/`: blt-cache에서 직접 관리하는 실행 코드·테스트·설정. phdq3는 최초 코드/정책을 참고한 읽기 전용 프로젝트다.
- `runtime-manifest.json`: 참조 이력과 현재 파일SHA256. 과거 참조 commit만으로 현재 구현을 재현했다고 주장하지 않는다.
- `bundle.py`: 무결성/SLURM 승인 검사. 변경은 이 저장소에서만 하고,검사 후 `python neuron/bundle.py refresh`로 manifest를 갱신한다. 참조 프로젝트 export는 하지 않는다.
- 가중치,원문,체크포인트,`ssh.md`,토큰,환경은 포함하지 않는다. 패키지 설치나 CUDA 모듈 로드도 하지 않는다.

## 다운로드와 기본 검사

아래 명령은 **사용자가 Neuron에서** 실행한다. 기존 clone이 있으면 새로 clone하지 말고 작업 중 job이 없는지 확인 후 지정 commit을 checkout한다.

```bash
git clone --filter=blob:none --sparse https://github.com/esoterikosQ/26-14_CACHE.git "$HOME/26-14_CACHE"
cd "$HOME/26-14_CACHE"
git sparse-checkout set neuron
git checkout --detach HEAD
git rev-parse HEAD
export BUNDLE="$HOME/26-14_CACHE/neuron"
conda activate phdq_blt_hf
export CONDA_SH="$(conda info --base)/etc/profile.d/conda.sh"
python "$BUNDLE/bundle.py" verify
python -m unittest discover -s "$BUNDLE" -p test_bundle.py -v
mkdir -p /scratch/r984a02/blt-cache
cd /scratch/r984a02/blt-cache
mkdir -p data/korean_cpt/{incoming/nikl,incoming/fineweb2,licenses,manifests,prepared}
mkdir -p artifacts/korean_entropy outputs/korean_entropy
export CONFIG="$BUNDLE/entropy.template.json"
showque
showappl
sbatch --export=ALL,MODE=preflight "$BUNDLE/train_entropy.sh"
```

`git rev-parse HEAD`가 인계받은 검증 commit과 일치하는지 확인한다. 실행/재개 중에는 clone을 갱신하지 않는다.
기본 job은 기존 한국어 목표인 H2001GPU/CPU8/host RAM48G/2시간이다. 이는 제출 자원이며 학습 예산 승인이 아니다.
A100 환경 검사로 변경할 때는 `sbatch -p amd_a100nv_8 --export=ALL,MODE=preflight ...`로 **1GPU**만 사용한다.
`amd_a100_4`는 GPU당 CPU16 이하,그 외 두 partition은8 이하를 검사한다. V100/다중GPU는 거부한다.
기존 `phdq_blt_hf`(Python3.11,Torch2.11.0+cu128,Transformers5.16.1)가 필요하다.

preflight는 tiny BF16 CUDA 환경 검사와 승인 상태 보고만 수행한다. optimizer는 실행하지 않는다.
보고서는 `artifacts/korean_entropy/neuron-<jobid>-<restart>/`에 새로 생성된다.
현재 template의 `training_authorized=false`,5개 예산 null,자료 manifest null은 **의도된 차단 상태**다.
job exit0만 보고 학습 가능으로 판단하지 말고 `preflight.json`의 `training_ready`와 `blockers`를 확인한다.

## 자료와 실행 설정

NIKL 수신은 `data/korean_cpt/incoming/nikl`,약정은 `data/korean_cpt/licenses`다.
FineWeb2는 별도 승인된 수집/정제와 train/validation 분할이 필요하다. 세종은 필수가 아니다.
runtime의 `python -m blt_hf.entropy_data --plan <절대경로> --output <신규경로>`는 명시적 JSONL,
NIKL paragraph/utterance JSON을 지원한다. 실제 수령 schema 확인과 권리/PII/근접중복 분할 검토는 아직 남았다.
최종평가 자료는 입력하지 않는다. manifest의 승인 필드3종은 검토 없이 true로 바꾸지 않는다.

승인 후 template을 `/scratch/r984a02/blt-cache/artifacts/korean_entropy/configs/`의 새 설정 경로로 복사하고 `CONFIG`를 그 절대경로로 지정한다.
`dataset_manifest`,고유 `run_dir`,`max_steps`,`max_train_bytes`,`max_seconds`,
`max_run_bytes`,`max_gpu_memory_bytes`,승인 여부를 확정한다. 양의 값만 허용한다.
GPU 상한은 실제 장치 메모리보다 작아야 하며 `max_seconds`는 남은 job 시간보다 최소15분 짧아야 한다.
고정 공개 entropy revision의 변환본을 `artifacts/converted/blt-1b-hf-own`에 사용자가 준비한다.
새 프로젝트 경로에 가중치가 이미 있다고 가정하지 않는다. 기존 phdq3 가중치를 자동 이동/덮어쓰기하지 않는다.
preflight와 학습 job은 설정 사본을 자체 보고서 디렉터리에 보존한다.

```bash
# 승인된 CONFIG를 지정한 뒤 사용자만 실행. 최초에는2step 파일럿.
sbatch --export=ALL,MODE=pilot,PILOT_STEPS=2 "$BUNDLE/train_entropy.sh"
# 같은 설정/자료/런타임/장치와 신뢰 가능한 체크포인트로 명시적 재개.
export RESUME=/scratch/r984a02/blt-cache/outputs/korean_entropy/<run>/step-00000002.pt
sbatch --export=ALL,MODE=pilot,PILOT_STEPS=2,RESUME "$BUNDLE/train_entropy.sh"
# GPU 파일럿/재개/처리량·VRAM·검증 결과 검토 및 본 학습 예산 승인 후에만:
sbatch --export=ALL,MODE=train,RESUME "$BUNDLE/train_entropy.sh"
```

새 run은 기존 출력 디렉터리를 거부한다. `RESUME`은 본인이 생성한 체크포인트만 지정한다(torch pickle).
SIGUSR1/SIGTERM은 현재 step 완료 후 저장하고 exit75로 중단한다. 검증 도중 신호가 오면 검증 미완료를 기록한다.
SIGKILL/노드 장애/OOM에는 마지막 완성 checkpoint와 SHA sidecar만 사용한다. `.active`가 남으면
실행 중 프로세스가 없음을 사용자가 확인하기 전에는 지우거나 재개하지 않는다. 자동 재제출/예산 증가는 없다.
시간 제한은 step 경계의 소프트 한도다. 모델 로드/해시/저장과 큰 검증 자료의 시간을 별도로 고려한다.

## 검증 범위

macOS guard3개/shell 구문, itcerdo CPU entropy8개+기존 학습3개 검사가 통과했다.
경로 정정 후 macOS guard4개(참조 root 거부 포함),entropy7개 통과/optimizer1개 Torch 부재 skip,
manifest15파일 및 shell 검증을 통과했다. 이전 itcerdo 검사는 계산 코드에 대한 이력이다.
독립 배포 경로에서도 guard3개/entropy8개와 실제99,512,064모수 BF16 패처 strict load를 확인했다.
합성 CPU backward는 앞선 준비에서 확인했다. 실제 CPT는 실행하지 않았다.
**Neuron 할당,실제 GPU optimizer·신호 중단·재개,처리량·VRAM,한국어 CPT 품질은 아직 검증하지 않았다.**
이 bundle은 T12 교사 준비용이며 한국어 본체5개 arm의 학습/비교 구현을 완료했다는 뜻이 아니다.