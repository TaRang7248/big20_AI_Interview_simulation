# SETUP.md — AI 모의면접(파이썬 백엔드/AI) 개발 환경 구축 가이드 (Windows)

이 문서는 팀원들이 **동일한 파이썬 개발 환경**을 빠르게 구축하도록 돕기 위한 안내서입니다.  
프로젝트 설계서에서 제시한 핵심 스택(예: FastAPI, WebRTC(aiortc), LangChain/LangGraph, STT/음성 분석, DeepFace 등)을 기준으로 작성했습니다. fileciteturn1file0

---

## 0) 전제 조건

- OS: Windows 10/11
- Python: **3.10.x 고정**
- 가상환경 이름: **interview_env**
- GPU 사용 시(Pytorch CUDA): CUDA 12.1 휠 사용(명령어는 아래에 있음)
- ffmpeg: 이미 DLL 설치/세팅되어 있다고 가정  
  - **torchcodec**은 ffmpeg DLL과 충돌 가능성이 있어 **설치 후 삭제(또는 설치 금지)** 권장

---

## 1) 프로젝트 루트에서 venv 생성/활성화

```cmd
# 1) venv 생성
py -3.10 -m venv interview_env

# 2) 활성화
.\interview_env\Scripts\activate

# 3) pip 업그레이드
python -m pip install --upgrade pip
```

> 실행 정책 오류가 나면:
```cmd
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 2) PyTorch(CUDA 12.1) 설치 (필수 고정)

**가장 먼저 설치**하세요. (다른 패키지가 torch를 CPU 버전으로 갈아끼우는 경우를 예방)

```cmd
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## 3) torchcodec 제거(또는 설치 금지)

ffmpeg DLL 환경에서 충돌 가능성이 있어 제거합니다.

```cmd
pip uninstall -y torchcodec
```

---

## 4) 프로젝트 의존성 설치 (constraints 포함)

requirements는 “필요한 것 목록”, constraints는 “꼭 고정해야 하는 버전”입니다.

```cmd
pip install -c constraints.txt -r requirements.txt
```

- `numpy==1.26.2`, `pyannote-audio==3.1.1`는 호환성 때문에 고정합니다.
- 설치 후 `pip check`로 의존성 충돌을 확인하세요:

```cmd
pip check
```

---

## 5) 빠른 동작 확인(테스트 스크립트)

`interview_env_test.py`를 실행해서 핵심 모듈 import / CUDA 인식을 확인합니다.

```cmd
python interview_env_test.py
```

정상이라면 다음과 같은 정보를 출력합니다:
- torch/torchvision/torchaudio 버전
- CUDA 사용 가능 여부 + GPU 이름
- numpy / pyannote-audio import 성공 여부

---

## 6) 환경 변수(.env) 설정

`.env.example`을 복사해서 `.env`를 만들고 키를 채우세요.

```cmd
copy .env.example .env
notepad .env
```

---

## 7) (선택) 개발 서버 실행 예시

FastAPI 예시:

```cmd
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 8) 라이브러리 용도 요약(팀원 공유용)

아래는 “왜 이 라이브러리가 필요한지”를 한 줄씩 정리한 것입니다.  
프로젝트 문서에서 제시한 아키텍처 구성요소(예: FastAPI 코어, Signaling 서버, aiortc 미디어 서버, LangChain/LangGraph 오케스트레이터, DeepFace 감정 분석, Celery 비동기 작업 등)와 매칭됩니다. fileciteturn1file0

### Web/API
- **fastapi**: 백엔드 API 서버(인증/세션/비즈니스 로직), 비동기 I/O 기반
- **uvicorn[standard]**: FastAPI 실행 ASGI 서버(개발/운영)
- **pydantic**: 요청/응답 스키마 검증 및 타입 기반 데이터 처리
- **python-dotenv**: `.env` 환경변수 로딩
- **httpx**: 외부 API(OpenAI/Deepgram 등) 비동기 호출

### Realtime
- **aiortc**: WebRTC 미디어(오디오/비디오) 수신/처리(서버 측 파이프라인)
- **websockets**: WebRTC 시그널링/실시간 이벤트 전송(WebSocket)

### LLM / RAG
- **openai**: LLM 호출(질문 생성/피드백 생성)
- **langchain**: 프롬프트/메모리/도구 호출 등 LLM 애플리케이션 프레임워크
- **langgraph**: 면접 흐름(상태머신/그래프) 기반 오케스트레이션
- **langchain-openai**: OpenAI 모델 어댑터
- **tiktoken**: 토큰 카운팅/프롬프트 비용 추정

### Audio / Speech
- **pyannote-audio (3.1.1)**: 화자 분리/다이어리제이션 등 음성 분석(연구/프로덕션 모두 활용 가능)
- **soundfile/librosa**: 오디오 I/O, 특징 추출(발화 속도/피치 등 보조 분석)

### Emotion / CV (선택)
- **deepface**: 얼굴 표정/감정 분석(프로젝트 문서의 Emotion Engine 후보)
- **opencv-python**: 프레임 추출/영상 전처리

### Data / Infra
- **sqlalchemy/alembic**: RDB 모델링/마이그레이션
- **psycopg2-binary / asyncpg**: PostgreSQL 드라이버(동기/비동기)
- **redis**: 세션/캐시/브로커
- **celery**: 리포트 생성/영상 인코딩 등 비동기 작업 큐

### Dev Tools
- **pytest**: 테스트
- **ruff / black**: 린트/포매터(팀 코드 스타일 통일)

---

## 9) 흔한 설치 문제와 해결 팁

1) **pyannote-audio 설치 후 torch가 CPU 버전으로 바뀜**
- 해결: (1) torch를 먼저 설치하고, (2) constraints로 고정 설치, (3) `pip check`로 확인

2) **PowerShell 실행 정책 오류**
- `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

3) **설치 실패 로그 공유 규칙**
- 팀 채널에 아래 3개를 그대로 붙여주세요:
  - `python --version`
  - `pip --version`
  - 에러 로그 전체

---

## 10) 파일 목록

- `requirements.txt` : 필요한 패키지 목록
- `constraints.txt`  : 충돌 방지용 버전 고정
- `.env.example`     : 환경변수 템플릿
- `interview_env_test.py` : 설치 검증 스크립트
