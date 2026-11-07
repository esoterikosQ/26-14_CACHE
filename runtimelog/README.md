# 사용자 실행 결과 로그

Neuron의 접속·전송·제출·실행은 모두 사용자가 직접 수행한다.
사용자가 Neuron에서 이 디렉터리에 결과를 모아 GitHub에 commit/push하고,
로컬 저장소에서 pull한 결과를 바탕으로 에이전트가 분석하고 후속 명령을 준비한다.
이곳은 Git으로 추적하는 결과 전달 위치다.
구체적인 업로드/수신 명령은 [작업별 명령표](../neuron/command.md#11-github를-통한-결과-전달)를 따른다.

Slurm job의 stdout/stderr는 이 디렉터리에 `entropy-<JobID>.out`, `entropy-<JobID>.err`로 바로 기록된다.
preflight 보고서, 학습 step(처음 20개와 100 step마다), 검증 결과, 종료 상태가 모두 .out에 남는다.
전달은 `git add runtimelog` 후 commit/push만 하면 된다. 내용을 한 번 확인한다.
토큰·비밀번호·개인정보·원문 데이터·가중치·체크포인트는 넣지 않는다. `git add -f`로 제외 규칙을 우회하지 않는다.