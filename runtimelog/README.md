# 사용자 실행 결과 로그

Neuron의 접속·전송·제출·실행은 모두 사용자가 직접 수행한다.
사용자가 Neuron에서 이 디렉터리에 결과를 모아 GitHub에 commit/push하고,
로컬 저장소에서 pull한 결과를 바탕으로 에이전트가 분석하고 후속 명령을 준비한다.
이곳은 Git으로 추적하는 결과 전달 위치이며 Neuron의 기존 출력 경로를 변경하지 않는다.
구체적인 업로드/수신 명령은 [작업별 명령표](../neuron/command.md#11-github를-통한-결과-전달)를 따른다.

작업마다 `preflight-<JobID>/`, `pilot-<JobID>/`, `train-<JobID>/`처럼
별도 하위 디렉터리를 권장한다. 실패 로그도 보존하고 이전 결과를 덮어쓰지 않는다.

가능한 파일만 넣으면 된다.

- SLURM stdout/stderr: `entropy-<JobID>.out`, `entropy-<JobID>.err`.
- 환경/승인 검사: `environment.json`, `preflight.json`.
- 학습 결과: `metrics.jsonl`, `validation-*.json`, `contract.json`.
- 실행 정보: 실제 명령, 코드 commit, Run ID/Job ID, GPU/partition, `sacct` 상태와 종료 코드.

토큰·비밀번호·전체 환경변수 덤프·개인정보·원문 데이터·가중치·체크포인트는 넣지 않는다.
로그에 원문이나 비밀정보가 출력됐다면 해당 부분을 제거한 사본만 전달한다.
검토한 로그와 보고서도 이 안내 파일과 함께 Git에 올린다. 디렉터리 전체를 제외하지 않는다.
가중치/checkpoint 등 저장소의 기존 제외 규칙은 유지하며 `git add -f`로 우회하지 않는다.
실행용 clone은 고정 commit을 유지하고, 로그용 별도 clone의 main에서 결과만 올린다.
큰 로그는 필요한 구간과 요약만 공유하고 원본 전체는 Neuron에 보존한다.