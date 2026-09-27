# 새 프로젝트에서 GitHub 저장소 만들고 연결하기

이 디렉터리는 **파일만 준비된 상태**다. 새 프로젝트 위치는 사용자가 선택한다.
현재 폴더를 그대로 Codex 프로젝트로 열거나, 원하는 위치에 파일을 복사해
그 폴더를 열면 된다. 아래 명령은 새 프로젝트의 루트에서 실행한다.
`phdq3` 저장소 안에 이 프로젝트를 Git subdirectory/worktree로 만들지 않는다.
다른 폴더를 선택한다면 Mac 터미널에서 다음처럼 **파일만** 복사한다.

```bash
mkdir -p "/원하는/새/프로젝트/경로"
rsync -a "/Users/esoterikos/Library/CloudStorage/Nextcloud-cloud.fruittravelers.net-monbug/projects_on/blt-cache/" "/원하는/새/프로젝트/경로/"
```

macOS 기본 `rsync`가 지원하는 `-a`만 사용한다. 대상 폴더의 기존 파일을
삭제하는 옵션은 쓰지 않는다.

## 1. 파일과 패키지 확인

```bash
pwd
test -f pyproject.toml
test -f AGENTS.md
test -f docs/HANDOFF.md
test -f skills/blt-cache-development/SKILL.md
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

현재 Mac에는 PyTorch가 없어 GPU 모델 테스트 1개가 건너뛰어질 수 있다.
wheel 빌드에는 `setuptools`와 `wheel`이 필요하다. BF16 실제 모델 검사는
새 프로젝트에서 준비된 GPU 환경으로 이어서 한다.

## 2. 빈 GitHub 저장소 만들기

GitHub 웹의 **New repository**에서 소유자와 저장소 이름을 정한다.
예시 이름은 `blt-cache`지만 원하는 이름을 써도 된다. 공개 여부도 그때
결정한다. 이 폴더에 이미 `README.md`와 `.gitignore`가 있으므로 원격
저장소 생성 화면의 README, `.gitignore`, license 자동 생성 옵션은 선택하지
않는다. GitHub의 [새 저장소 안내](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)와
[로컬 코드 게시 안내](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)를 따른다.

## 3. 선택한 로컬 폴더를 Git 저장소로 만들고 푸시

`OWNER`와 `REPO`를 실제 GitHub 값으로 바꾼다. 아직 `.git`이 없는 폴더에서:

```bash
git init -b main
git add .gitignore AGENTS.md README.md pyproject.toml src tests docs evidence skills
git diff --cached --stat
git commit -m "Initial standalone BLT cache package"
git remote add origin https://github.com/OWNER/REPO.git
git remote -v
git push -u origin main
git rev-parse HEAD
```

이미 Git 저장소로 생성한 프로젝트라면 `git init`은 생략하고 먼저
`git status --short --branch`를 확인한다. 원격이 이미 있으면
`git remote add`를 다시 실행하지 않는다. 원격 저장소를 README와 함께
만들었다면 강제 푸시하지 말고, 빈 저장소를 새로 만들거나 원격을 clone한
뒤 준비된 파일을 옮겨 정상적으로 커밋한다.

HTTPS 푸시가 사용자명과 비밀번호를 물으면 비밀번호 칸에는 **GitHub 계정
비밀번호가 아니라 개인 액세스 토큰(PAT)**을 입력한다. 토큰을 URL, 명령
인자, 문서, Git 파일에 넣지 않는다. GitHub의
[인증 안내](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)와
[토큰 안내](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)를
참고한다. 푸시는 개인 Mac에서 수행하고 공유 Neuron 노드에 상시 인증을
설정하지 않는다.

## 4. GitHub 패키지를 Python에서 사용

`git rev-parse HEAD`의 전체 SHA를 `COMMIT_SHA`에 넣고, 해당 호스트의
준비된 Python 환경에서 설치한다. GitHub URL을 그대로 `import`하는 것이
아니라 Git 소스를 **설치한 다음** 패키지 이름으로 import한다.

```bash
python -m pip install --no-deps \
  "phdq-blt-cache @ git+https://github.com/OWNER/REPO.git@COMMIT_SHA"
python -c 'from phdq_blt_cache import GlobalPrefixReuse; print(GlobalPrefixReuse)'
```

`--no-deps`는 이미 준비된 PyTorch/CUDA 환경을 유지하기 위한 것이다.
새 프로젝트의 `docs/INTEGRATION.md`에 적힌 대로, 현재 대기 중인 Neuron
학습이 끝나기 전에는 `phdq3`의 import를 바꾸지 않는다. 이후 새 run에서만
Git commit을 고정해 설치하고, `phdq3`의 학습·평가 manifest에 그 외부 코드
식별자를 포함시킨다.

## 새 Codex 프로젝트 첫 지시 예시

> 이 폴더의 `AGENTS.md`, `docs/HANDOFF.md`, `docs/PLAN.md`,
> `docs/INTEGRATION.md`, `docs/PUBLISH_GITHUB.md`를 읽고 standalone BLT
> cache 프로젝트를 이어서 진행해. 먼저 패키지 설치와 실제 BLT 모델 smoke를
> 확인하고, GitHub 원격 저장소를 만들거나 연결한 뒤 commit을 고정해.
> Neuron에는 직접 접속하지 말고, 현재 진행 중인 `phdq3` 학습 코드를
> 변경하지 마.
