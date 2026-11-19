# EC2 웹과 별도 GPU 서버 배포

브라우저 → EC2 nginx → EC2 FastAPI → Tailscale → GPU PC의 Qwen API 구성입니다.
EC2에는 웹·백엔드만 실행합니다. 모델 가중치·학습 데이터·PC 가상환경은 Git에 포함하지 않습니다.
초안은 Curated1459 어댑터를 사용하고 피드백·채점·추천의 구조화 출력은 같은 Qwen3.5-2B의 기본 가중치를 사용합니다.

## 1. GPU PC

현재 PC의 프로젝트 루트에서 기존 GPU 가상환경을 사용합니다. 가중치는 이 PC의 기존 경로에 그대로 둡니다.
Git 코드를 받을 때 기존 `thinking_llm_token`, `llm_training/outputs/`와 가상환경은 유지합니다.

```powershell
llm_training\.venv\Scripts\python.exe deploy/gpu_server.py --start --adapter llm_training/outputs/qwen35_fresh_20261119_182005_790166/adapter --profile curated_over1000_20261119
```

이미 8001번 포트에서 API가 실행 중이면 중복 실행하지 않고 현재 실행을 사용합니다.
코드를 갱신했다면 기존 GPU API 프로세스를 확인한 후 종료하고 위 명령으로 다시 실행합니다.
실제 로드한 가중치 지문은 `b3446a724b1190bbac4eaf80afc20be300b08ec25f734b7a0fd0ba377db11f1e`입니다.

GPU API는 `127.0.0.1:8001`에 바인딩합니다. PC와 EC2가 같은 tailnet에 로그인되어 있을 때 GPU PC에서 아래 전달 설정을 사용합니다.
기존 Serve 설정이 있으면 `tailscale serve status`로 먼저 확인합니다.

```powershell
tailscale serve --bg --tcp=8001 tcp://127.0.0.1:8001
```

이 명령은 Git 업로드 과정에서 자동 실행하지 않습니다. PC가 켜져 있고 GPU API와 Tailscale이 실행 중이어야 합니다.

## 2. EC2 코드와 환경 설정

EC2의 기존 체크아웃에서 실행합니다. 로컬 수정이 있다면 먼저 `git status`로 확인합니다.
Python 3.11과 Node.js 24에서 검사했습니다. 웹 빌드에는 Node.js 20.19 이상(20.x) 또는 22.12 이상이 필요합니다.

```bash
git fetch origin
git pull --ff-only origin master
python3 -m venv .venv                 # 가상환경이 없을 때만
.venv/bin/python -m pip install -r backend/requirements.txt
```

기존 `backend/.env`의 DB·JWT·메일·결제 설정을 유지하고 아래 두 값을 GPU PC에 맞춥니다.

```dotenv
COMMON_LLM_URL=http://GPU_TAILSCALE_IP:8001
THINKING_LLM_TOKEN=GPU_PC와_동일한_비밀값
```

GPU PC의 `thinking_llm_token` 내용과 EC2의 토큰을 같은 값으로 설정합니다. 이 값은 Git이나 프런트엔드 환경변수에 넣지 않습니다.
EC2에는 torch·transformers나 모델 가중치를 설치할 필요가 없습니다.

```bash
.venv/bin/python deploy/check_remote_llm.py --generate --expected-adapter-sha256 b3446a724b1190bbac4eaf80afc20be300b08ec25f734b7a0fd0ba377db11f1e
```

`reachable: true`, `generation_checked: true`와 선택한 어댑터 지문을 확인합니다.
이 명령은 실제 tailnet 주소와 토큰으로 EC2에서 실행해야 연결 검증이 됩니다.

## 3. 웹 빌드와 백엔드 실행

```bash
cd frontend
npm ci
VITE_API_URL= npm run build
cd ..
```

운영 빌드의 API 주소를 비워 두면 모든 화면이 nginx의 같은 도메인 `/api/`로 요청합니다.
GPU 주소나 토큰은 브라우저에 전달하지 않습니다. 개발 모드의 기본 API는 `http://127.0.0.1:8000`입니다.

기존 EC2 백엔드 서비스가 있으면 새 코드로 재시작합니다. 새 서비스를 구성할 경우
`thinking-backend.service.example`의 계정·절대 경로를 실제 EC2 경로로 바꿔 사용합니다.
백엔드 실행 명령은 다음과 같습니다.

```bash
cd backend
../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

`nginx-thinking.conf.example`은 정적 웹과 `/api/` 프록시 예시입니다. 기존 HTTPS 설정을 유지하고
체크아웃 경로와 `/api/` 프록시를 반영합니다. AI의 제한적 재생성을 기다릴 수 있도록 프록시 읽기 제한은 240초로 잡습니다.
nginx 설정을 바꾼 뒤 `sudo nginx -t`로 검사하고 해당 서비스를 재로드합니다.

EC2에서 `deploy/local_web.py`는 실행하지 않습니다. 이 파일은 PC 시연용 별도 SQLite 웹입니다.
운영 EC2는 기존 DB 설정으로 `backend/main.py`를 실행합니다.

## 4. 확인 순서

1. EC2 → GPU 연결 검사 통과
2. 로그인과 퀴즈·진도 조회
3. 초안의 새 어댑터·검토 안내, 개인 설정 반영
4. 피드백의 원문 인용과 힌트·수정문 모드
5. 추천 주제·자기소개서 문항 생성과 연습 채점·저장

GPU API가 준비되지 않았거나 생성이 실패하면 사용 횟수를 차감하지 않습니다.
문장 길이·주체 보존 보완과 구조화 응답 검증이 포함되어 있지만, 일반 피드백과 채점 설명은 사용자 검토가 필요합니다.
사용자별 문체 학습 어댑터가 없는 계정에는 개인 모델이 없다는 안내가 표시됩니다.

코드 검사는 `python -m pytest backend/tests deploy/tests llm_training/tests -q`로 실행할 수 있습니다
(`pytest`는 개발 검사 환경에 설치). Git에서 제외한 학습·비교 자료가 필요한 검사 3개는 해당 자료가 없는 체크아웃에서만 건너뜁니다.
프런트엔드 검사는 `npm run test:qwen`, `npm run test:navigation`, `npm run test:ai-usage`, `npm run test:api-base`입니다.
