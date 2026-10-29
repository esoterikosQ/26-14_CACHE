# BLT Cache 작업 명령

이 파일은 **blt-cache 저장소의 안내**다. 함께 열린 phdq3는 참조 전용이며
이번 작업의 코드·설정·명령·로그를 그 프로젝트에 기록하지 않는다.

- [Neuron 작업별 전체 명령](neuron/command.md): 다운로드, 저장 경로, 자료 준비, preflight, 학습/재개, GitHub 로그 전달.
- [Neuron 실행 안내](neuron/README.md): 실행 조건과 검증 범위.
- [사용자 실행 결과](runtimelog/README.md): Neuron에서 GitHub에 올린 로그를 로컬에서 받아 분석.
- [진행 기록](log.md), [작업 상태](task.md).

| 항목 | 위치 |
| --- | --- |
| 코드·테스트·준비 설정 | `neuron/runtime/` |
| SLURM 실행기·환경 guard·명령 문서 | `neuron/` |
| 이번 프로젝트의 Neuron 데이터·설정·출력 루트 | `/scratch/r984a02/blt-cache` |
| GitHub 저장소 | `https://github.com/esoterikosQ/26-14_CACHE.git` |
| 검토한 실행 결과 전달 | `runtimelog/<작업명-JobID>/` |

Neuron의 실행·전송·제출은 전부 사용자가 직접 수행한다.
기존 phdq3 데이터·가중치·실행 환경을 자동으로 옮기거나 덮어쓰지 않는다.