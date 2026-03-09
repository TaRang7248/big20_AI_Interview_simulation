# AI 모의면접 통합 시스템

## 📋 개요

Text-to-Speech(TTS), Speech-to-Text(STT), LLM 기반 질문생성 및 답변 평가, 화상 면접, 감정 분석, Celery 비동기 작업 처리 등의 기능을 통합한 AI 모의면접 시스템입니다.

### ✨ 주요 특징

- **화상 면접 중심**
- **LLM**: EXAONE 3.5 7.8B 모델 기반 AI 면접 두뇌 역할. 질문을 생성하고 답변을 평가 (컨텍스트 윈도우 8192)
- **코딩 테스트 LLM**: Qwen3-Coder-30B-A3B (Q3_K_M 양자화) — 코딩 문제 생성 및 코드 분석 전용
- **LangGraph 워크플로우**: 조건부 분기 + 루프 제어 + 체크포인트 기반 면접 상태머신
- **이력서 RAG**: PDF 이력서 업로드 → 맞춤형 면접 평가
- **통합 평가 시스템**: 언어 평가(5축) 60% + 비언어 평가(발화/시선/감정/Prosody) 40% → 합격/불합격 이진 판정
- **비언어 분석**: 발화 속도/발음 등급, 시선 추적 집중도, 감정 안정성, 음성 감정(Prosody) 분석
- **PDF 리포트**: ReportLab 기반 PDF 종합 리포트 자동 생성 (커버 + 평가 + 비언어 차트)
- **Celery 비동기 처리**: 무거운 작업(LLM 평가, 감정 분석, 리포트 생성, 미디어 트랜스코딩)을 백그라운드에서 처리
- **회원가입/로그인**: 이메일 기반 회원가입 및 소셜 로그인 (카카오, 구글, 네이버) 지원, 회원 탈퇴 및 GDPR 데이터 삭제
- **보안 시스템**: bcrypt 비밀번호 해싱, AES-256-GCM 파일 암호화, JWT 인증, CORS 제한, WebSocket JWT 인증, TLS 지원
- **종합 리포트**: STAR 기법 분석, 키워드 추출, 합격/불합격 추천 포함
- **Recharts 리포트 시각화**: 7종 인터랙티브 차트 (레이더, 바, 파이, 영역) + 비언어 평가 카드로 면접 결과 시각 대시보드
- **지연 시간 모니터링 (SLA)**: 모든 API 요청 자동 측정, 1.5초 SLA 위반 감지, 단계별(LLM/TTS) Phase 측정
- **미디어 녹화/트랜스코딩**: aiortc + GStreamer/FFmpeg 하이브리드 아키텍처 기반 면접 영상 녹화 및 자동 트랜스코딩
- **코딩 테스트**: Python, JavaScript, Java, C/C++ 지원하는 웹 IDE 통합 + Docker 샌드박스 보안
- **화이트보드 면접**: Claude 3.5 Sonnet Vision을 활용한 시스템 아키텍처 다이어그램 분석
- **채용공고 관리**: 인사담당자(recruiter)용 공고 CRUD + 지원자용 공고 열람
- **AI 답변 스트리밍**: SSE(Server-Sent Events) 기반 실시간 AI 답변 스트리밍
- **Next.js 프론트엔드**: TypeScript + Tailwind CSS + Recharts 기반 현대적 UI (App Router, 10개 페이지)
- **원클릭 시작**: 배치/PowerShell 스크립트 + VS Code Tasks로 전체 시스템 한 번에 실행

---

## 🚀 빠른 시작

### 1. 필수 패키지 설치

```bash
pip install -r requirements_integrated.txt
```

### 2. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 값들을 설정하세요:

```env
# LLM 설정 (Ollama)
LLM_MODEL=exaone3.5:7.8b
LLM_TEMPERATURE=0.7
LLM_NUM_CTX=8192
LLM_TIMEOUT_SEC=60

# 코딩 테스트 전용 LLM
CODING_LLM_MODEL=hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q3_K_M
CODING_CELERY_LLM_MODEL=hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q3_K_M

# Ollama 최적화
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_NUM_PARALLEL=2

# JWT 인증
JWT_SECRET_KEY=your_jwt_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=120

# 암호화 (AES-256-GCM)
ENCRYPTION_KEY=your_encryption_key

# TLS (선택)
TLS_CERTFILE=path/to/cert.pem
TLS_KEYFILE=path/to/key.pem

# Hume AI TTS
HUME_API_KEY=your_hume_api_key
HUME_SECRET_KEY=your_hume_secret_key
HUME_CONFIG_ID=your_config_id

# Deepgram STT 
DEEPGRAM_API_KEY=your_deepgram_api_key

# PostgreSQL RAG
POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/interview_db

# Redis (Celery 브로커 및 감정 데이터 저장)
REDIS_URL=redis://localhost:6379/0

# 소셜 로그인
KAKAO_CLIENT_ID=your_kakao_client_id
KAKAO_CLIENT_SECRET=your_kakao_client_secret
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
OAUTH_REDIRECT_BASE=http://localhost:8000

# Claude API (화이트보드 분석용)
ANTHROPIC_API_KEY=your_anthropic_api_key

# D-ID API (AI 아바타용, 선택)
DID_API_KEY=your_did_api_key

# RAG 임베딩 모델 (선택, 기본값 제공)
EMBEDDING_MODEL=nomic-embed-text
CHUNK_SIZE=1500
CHUNK_OVERLAP=300
```

### 3. 외부 서비스 실행

```bash
# Ollama 실행
ollama serve
ollama pull exaone3.5:7.8b

# Redis 실행 (Celery 브로커 + 감정 데이터 저장)
docker run -d -p 6379:6379 redis:alpine

# PostgreSQL + pgvector 실행 (RAG)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password pgvector/pgvector:pg16
```

### 4. Celery Worker 실행 (권장)

Celery Worker를 실행하면 LLM 평가, 감정 분석, 리포트 생성 등을 비동기로 처리할 수 있습니다.

```bash
# Windows
celery -A celery_app worker --pool=solo --loglevel=info

# Linux/Mac (멀티 프로세스)
celery -A celery_app worker --concurrency=4 --loglevel=info

# Flower 모니터링 (선택사항)
celery -A celery_app flower --port=5555
```

### 5. 통합 서버 실행

```bash
cd CSH
python integrated_interview_server.py

# 또는 uvicorn으로 실행
uvicorn integrated_interview_server:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 접속

브라우저에서 다음 URL로 접속:
- **메인 페이지 (Next.js)**: http://localhost:3000
- **화상 면접**: http://localhost:3000/interview
- **코딩 테스트**: http://localhost:3000/coding
- **화이트보드**: http://localhost:3000/whiteboard
- **대시보드**: http://localhost:3000/dashboard
- **감정 분석**: http://localhost:3000/emotion
- **채용공고**: http://localhost:3000/jobs
- **인사담당자**: http://localhost:3000/recruiter
- **FastAPI 백엔드**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **Celery 모니터링** (Flower 실행 시): http://localhost:5555

---

## 🎯 면접 흐름

```
┌─────────────────────────────────────────────────────────────┐
│  1. 홈페이지 (/)                                             │
│     ├─ 회원가입/로그인 (이메일 또는 소셜 로그인)               │
│     └─ "AI 화상 면접 시작하기" 클릭                           │
├─────────────────────────────────────────────────────────────┤
│  2. 이력서 업로드 모달                                        │
│     ├─ PDF 이력서 업로드 (선택)                               │
│     │   └─ RAG 인덱싱 → 세션별 retriever 생성                │
│     └─ 또는 "건너뛰기"                                       │
├─────────────────────────────────────────────────────────────┤
│  3. 화상 면접 시작                                           │
│     ├─ WebRTC 카메라/마이크 연결                              │
│     ├─ D-ID AI 아바타 면접관 영상                             │
│     ├─                                                      │
│                                                             │
│     ├─ 답변 입력 → Celery 백그라운드 LLM 평가                 │
│     ├─                                                      │
│     ├─ 실시간 감정 분석 (7가지 감정 - DeepFace)               │
│     └─ TTS 음성 출력 (Hume AI)                               │
├─────────────────────────────────────────────────────────────┤
│  4. 코딩 테스트 (선택)                                       │
│     ├─                                                      │
│     ├─ 샌드박스 코드 실행 (Python/JS/Java/C/C++)             │
│     └─ AI 코드 분석 (복잡도, 스타일, 베스트 프랙티스)         │
├─────────────────────────────────────────────────────────────┤
│  5. 시스템 설계 면접 (선택)                                   │
│     ├─ 화이트보드에 아키텍처 다이어그램 그리기                 │
│     ├─ Claude Vision으로 다이어그램 인식 및 분석              │
│     └─ 구조, 확장성, 보안 평가 및 피드백                      │
├─────────────────────────────────────────────────────────────┤
│  6. 면접 종료 → 리포트 생성                                   │
│     ├─ LLM 평가 종합 결과 (5가지 항목 평균)                   │
│     ├─ 비언어 평가 (발화/시선/감정/Prosody)                  │
│     ├─ 통합 점수 (언어 60% + 비언어 40%)                      │
│     ├─ 합격/불합격 추천 (통합 점수 기반)                      │
│     ├─ STAR 기법 분석 (상황-과제-행동-결과)                   │
│     ├─ 키워드 분석 (기술 키워드 + 일반 키워드)                │
│     ├─ 코딩 테스트 결과 (코드 품질 점수)                      │
│     ├─ 시스템 설계 결과 (아키텍처 평가)                       │
│     ├─ PDF 리포트 다운로드                                     │
│     └─ 개선 피드백 및 권장사항                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 시스템 구조

```
CSH/
├── integrated_interview_server.py  # 통합 FastAPI 서버 (메인)
├── celery_app.py                   # Celery 애플리케이션 설정 (큐, 라우팅)
├── celery_tasks.py                 # Celery 비동기 태스크 정의
├── text_interview.py               # 텍스트 면접 모듈 (STAR 분석, 리포트)
├── hume_tts_service.py             # Hume AI TTS 서비스 (OAuth2 토큰 인증)
├── stt_engine.py                   # Deepgram STT 서비스 (Nova-3 모델)
├── resume_rag.py                   # 이력서 RAG (PostgreSQL + PGVector + Redis 캐싱)
├── code_execution_service.py       # 코딩 테스트 서비스 (샌드박스 실행, AI 분석, LLM 문제 생성)
├── whiteboard_service.py           # 화이트보드 다이어그램 분석 (Claude Vision)
├── media_recording_service.py      # 미디어 녹화/트랜스코딩 서비스 (aiortc + GStreamer/FFmpeg 하이브리드)
├── interview_workflow.py           # LangGraph 기반 면접 상태머신 (조건부 분기, 체크포인트)
├── prompt_templates.py             # 면접관/평가 프롬프트 템플릿 (INTERVIEWER_PROMPT, EVALUATION_PROMPT)
├── speech_analysis_service.py      # 발화 속도/발음 분석 서비스 (SPM, 등급 판정)
├── gaze_tracking_service.py        # 시선 추적 분석 서비스 (눈 접촉 비율, 등급)
├── hume_prosody_service.py         # 음성 감정 Prosody 분석 서비스 (Hume AI, 10개 지표)
├── pdf_report_service.py           # PDF 종합 리포트 생성 (ReportLab, 차트 포함)
├── latency_monitor.py              # 지연 시간 측정 및 SLA 모니터링 (REQ-N-001)
├── whisper_stt_service.py          # Whisper 기반 로컬 STT 서비스 (오프라인 폴백)
├── json_utils.py                   # LLM JSON 안정적 추출/파싱 방어 로직 (6단계)
├── security.py                     # 보안 유틸리티 (bcrypt, JWT, AES-256-GCM 암호화, TLS, CORS)
├── events.py                       # 이벤트 타입 정의 (30+ EventType, Pydantic 모델)
├── event_bus.py                    # Redis Pub/Sub EventBus (싱글턴, WebSocket 브로드캐스트)
├── event_handlers.py               # 도메인별 이벤트 핸들러 등록 (9개 도메인)
├── Dockerfile                      # 컨테이너 빌드 설정 (python:3.11-slim + FFmpeg)
├── start_interview.bat             # 원클릭 시작 스크립트 (Windows Batch)
├── start_all.ps1                   # 원클릭 시작 스크립트 (PowerShell)
├── start_prerequisites.bat         # 사전 서비스 실행 스크립트
├── .env.example                    # 환경변수 예시 파일
├── uploads/                        # 이력서 업로드 디렉토리
│   ├── recordings/                 # 면접 녹화 파일
│   ├── thumbnails/                 # 녹화 썸네일
│   └── transcoded/                 # 트랜스코딩된 동영상
├── documents/                      # 설계 문서 및 보고서
│   ├── 소프트웨어 아키텍처 설계서 (SAD).md
│   ├── 시스템 요구사항 명세서 (SRS).md
│   ├── 시스템 보안 종합 리뷰 보고서.md
│   ├── RAG 시스템 DB 구조.md
│   └── requirements_integrated.txt # 통합 의존성 패키지 목록
├── frontend/                       # Next.js 프론트엔드
│   ├── src/app/                    # App Router 페이지 (10개)
│   ├── src/components/             # 재사용 컴포넌트
│   ├── src/contexts/               # 인증 + 이벤트 + 토스트 컨텍스트
│   ├── src/lib/                    # API 유틸리티
│   └── public/                     # 정적 자산 (stt-processor.js 등)
├── nginx/                          # NGINX 설정 (리버스 프록시, SSL)
└── sandbox/                        # 코딩 테스트 Docker 샌드박스
```

---

## 🔧 핵심 기능

### 1. LLM 기반 답변 평가 시스템

LLM은 **질문 생성이 아닌 답변 평가**에 사용됩니다. Ollama의 **EXAONE 3.5 7.8B** 모델을 활용하여 지원자 답변을 5가지 기준으로 평가합니다.

> **변경 이력**: Llama3 → Qwen3-4B → exaone-deep:2.4b → **EXAONE 3.5 7.8B** 전환, 컨텍스트 윈도우 16384 → 8192 조정 (VRAM 6GB 환경 최적화)

> **JSON 파싱**: `json_utils.py` 모듈을 통한 6단계 다층 파싱 전략 적용 — EXAONE Deep의 `<thought>` 블록 및 Qwen3의 `<think>` 블록 자동 제거, Markdown 코드블록 추출, 괄호 매칭, 구문 오류 자동 수정, 정규식 추출, fallback 기본값 반환

| 평가 항목 | 설명 | 점수 |
|-----------|------|------|
| 문제해결력 (Problem Solving) | 문제 분석 및 해결 접근 방식의 체계성 | 1-5점 |
| 논리성 (Logic) | 논리적 흐름의 일관성 | 1-5점 |
| 기술 이해도 (Technical) | 기술적 개념 이해 정확성 | 1-5점 |
| STAR 기법 (STAR) | 상황-과제-행동-결과 구조 | 1-5점 |
| 전달력 (Communication) | 명확하고 이해하기 쉬운 답변 | 1-5점 |

**총점: 25점 만점**



### 2-1. JSON 안정적 파싱 (json_utils.py)

LLM 응답에서 JSON을 안정적으로 추출하고 파싱하기 위한 방어 로직 모듈입니다.

| 단계 | 방법 | 설명 |
|------|------|------|
| 1단계 | 직접 파싱 | `json.loads()` 직접 시도 |
| 2단계 | 코드블록 추출 | Markdown ` ```json ``` ` 코드블록에서 JSON 추출 |
| 3단계 | 괄호 매칭 | 가장 바깥쪽 `{...}` 또는 `[...]` 객체 추출 |
| 4단계 | 구문 오류 수정 | trailing comma, 작은따옴표→큰따옴표, 키 따옴표 누락 자동 수정 |
| 5단계 | 정규식 추출 | greedy 패턴 매칭 |
| 6단계 | fallback | 기본값 반환 |

- **Qwen3 `<think>...</think>` 사고 블록** 및 **EXAONE Deep `<thought>...</thought>` 블록** 자동 제거
- 제어문자 정리 및 타입 검증 기능 내장

### 3. 이력서 RAG 시스템

- **PDF 업로드**: 면접 시작 전 이력서 업로드
- **세션별 인덱싱**: `resume_{session_id}` 컬렉션으로 독립 관리
- **맞춤 평가**: 이력서 내용을 참조하여 답변 평가 시 컨텍스트 제공
- **벡터 검색**: PostgreSQL + PGVector를 활용한 유사도 검색
- **임베딩 모델**: nomic-embed-text (768차원, 8192 토큰 컨텍스트, Ollama 로컬 실행)
- **청킹 설정**: 청크 크기 1500자, 오버랩 300자 (환경변수로 조정 가능)

### 4. 실시간 감정 분석

- **7가지 감정**: 행복(happy), 중립(neutral), 슬픔(sad), 분노(angry), 놀람(surprise), 공포(fear), 혐오(disgust)
- **DeepFace 기반**: 1초 간격 얼굴 분석
- **Redis 시계열 저장**: 면접 전체 감정 추이 기록
- **대시보드 시각화**: 실시간 감정 차트 제공

### 5. TTS 음성 면접관 (Hume AI)

- **Hume EVI**: 감정 인식 기반 자연스러운 AI 면접관 음성
- **한국어 지원**: EVI 4-mini 모델 활용
- **OAuth2 토큰 인증**: API Key + Secret Key 기반 인증
- **시각적 피드백**: 말하는 동안 파형 애니메이션

### 6. STT 음성 인식 (Deepgram)

- **Nova-3 모델**: 고정밀 한국어 음성 인식
- **실시간 스트리밍**: WebSocket 기반 실시간 변환
- **VAD 지원**: 음성 활동 감지로 자연스러운 구간 분리
- **한국어 띄어쓰기 보정**: pykospacing 연동

### 7. Celery 비동기 작업 처리

무거운 작업들을 백그라운드에서 처리하여 사용자 경험을 개선합니다.

| 태스크 | 설명 | 큐 |
|--------|------|-----|
| `evaluate_answer_task` | 개별 답변 LLM 평가 | llm_evaluation |
| `batch_evaluate_task` | 다수 답변 배치 평가 | llm_evaluation |
| `analyze_emotion_task` | 단일 이미지 감정 분석 | emotion_analysis |
| `batch_emotion_analysis_task` | 다수 이미지 배치 분석 | emotion_analysis |
| `generate_report_task` | 종합 리포트 생성 | report_generation |
| `generate_tts_task` | TTS 음성 생성 | tts_generation |
| `process_resume_task` | 이력서 PDF 인덱싱 | rag_processing |
| `complete_interview_workflow_task` | 면접 완료 후 전체 워크플로우 | default |
| `save_session_to_redis_task` | 세션 데이터 Redis 저장 | default |

**추가 태스크 (celery_tasks.py 기준 총 16개):**
- `retrieve_resume_context_task` — RAG 컨텍스트 검색
- `prefetch_tts_task` — TTS 사전 생성 (지연 최소화)
- `save_session_to_redis_task` — 세션 데이터 Redis 저장
- `transcode_recording_task` — 미디어 트랜스코딩 (GStreamer/FFmpeg, 비디오+오디오 합성, H.264+AAC)
- `cleanup_recording_task` — 만료/삭제된 녹화 파일 정리
- `pre_generate_coding_problem_task` — 코딩 문제 LLM 사전 생성

**주기적 작업 (Celery Beat):**
- `cleanup_sessions_task`: 5분마다 만료 세션 정리
- `aggregate_statistics_task`: 1시간마다 통계 집계

### 8. 회원가입 및 소셜 로그인

- **이메일 회원가입**: 이메일, 비밀번호, 이름, 생년월일, 주소, 성별, 역할(user/recruiter)
- **소셜 로그인 지원**:
  - 카카오 로그인
  - 구글 로그인
  - 네이버 로그인
- **세션 관리**: localStorage 기반 클라이언트 세션
- **회원 탈퇴**: 계정 삭제 및 GDPR 데이터 전체 삭제 지원

### 8-1. 보안 시스템 (security.py)

보안 유틸리티 모듈로 인증, 해싱, TLS 등 보안 기능을 통합 관리합니다.

| 기능 | 설명 |
|------|------|
| **비밀번호 해싱** | bcrypt (rounds=12) 기반, SHA-256 하위 호환 및 자동 마이그레이션 (`needs_rehash()`) |
| **AES-256-GCM 암호화** | 파일/바이트 단위 암호화/복호화 (`encrypt_file`, `decrypt_file`, `encrypt_bytes`, `decrypt_bytes`) |
| **JWT 인증** | HS256 알고리즘, python-jose 라이브러리, 120분 만료 |
| **FastAPI 인증** | `get_current_user()` / `get_current_user_optional()` — `Depends()` 기반 미들웨어 |
| **TLS 지원** | `get_ssl_context()` — 환경변수 기반 SSL 컨텍스트 생성 |
| **CORS 제한** | 허용 오리진 제한, WebSocket JWT 인증 |
| **보호 API** | 16개 엔드포인트에 JWT Bearer Token 인증 적용 |

**보호된 API 엔드포인트:**
- 사용자 정보 조회/수정
- 이력서 업로드/삭제
- 면접 세션 생성/관리
- 리포트 조회
- 평가 결과 조회

### 9. 종합 리포트 생성

면접 종료 후 다음 항목이 포함된 상세 리포트를 생성합니다:

- **STAR 분석**: 상황/과제/행동/결과 요소 점수 (각 25점, 총 100점)
- **언어 평가 점수 집계**: 5가지 평가 항목 평균 (verbal_average)
- **비언어 평가 통합**: 발화 속도(speech) + 시선 추적(gaze) + 감정 안정성(emotion) + Prosody 분석
- **통합 점수 산정**: 언어 평가 × 60% + 비언어 평가 × 40% = 최종 통합 점수 (final_score)
- **합격/불합격 판정**: 통합 점수 ≥ 4.0 AND 총점 ≥ 20 AND 저점수 항목 0개 → 합격, 이외 불합격
- **키워드 분석**: 기술 키워드 + 일반 키워드 추출
- **강점/개선점**: 빈도 기반 Top 5 추출
- **PDF 리포트**: 커버페이지 + 평가표 + 비언어 차트 포함 PDF 자동 생성
- **권장사항**: 맞춤형 개선 제안

### 10. 코딩 테스트 시스템 (code_execution_service.py)

실시간 코딩 면접을 위한 샌드박스 코드 실행 및 AI 분석 서비스입니다.

| 기능 | 설명 |
|------|------|
| **다국어 지원** | Python, JavaScript, Java, C, C++ 지원 |
| **샌드박스 실행** | subprocess + 타임아웃으로 안전한 코드 실행 |
| **AI 코드 분석** | 시간/공간 복잡도, 코드 스타일, 베스트 프랙티스 평가 |
| **코딩 문제 은행** | 난이도별 알고리즘 문제 제공 (easy/medium/hard) |
| **실행 측정** | 실행 시간, 메모리 사용량 측정 |

### 11. 화이트보드 다이어그램 분석 (whiteboard_service.py)

시스템 설계 면접을 위한 다이어그램 인식 및 평가 서비스입니다.

| 기능 | 설명 |
|------|------|
| **Claude Vision API** | **Claude 3.5 Sonnet** (메인 모델로 설정)을 사용한 다이어그램 인식 |
| **아키텍처 평가** | 구조, 확장성, 보안, 데이터 흐름 분석 |
| **AI 동적 문제 생성** | 카테고리별 맞춤 아키텍처 문제 생성 |
| **컴포넌트 분석** | 각 구성요소의 역할 및 연결 관계 평가 |
| **피드백 제공** | 강점, 약점, 개선 제안 자동 생성 |

### 12. D-ID AI 아바타 (미구현 — 환경변수 예약됨)

D-ID API를 활용한 실시간 AI 면접관 영상 생성 서비스입니다. 현재 `did_avatar_service.py` 파일은 제거되었으며, `.env.example`에 `DID_API_KEY` 환경변수만 예약되어 있습니다.

| 기능 | 설명 |
|------|------|
| **Talks API** | 텍스트 → 말하는 아바타 영상 생성 (10-30초) |
| **Streams API** | WebRTC 실시간 스트리밍 (1-3초 지연) |
| **한국어 TTS** | Microsoft TTS (ko-KR-SunHiNeural, ko-KR-InJoonNeural) |
| **커스텀 아바타** | 사용자 정의 프레젠터 이미지 지원 |

### 13. 이벤트 기반 아키텍처 (Event-Driven Architecture)

SAD 설계서의 "이벤트 기반 마이크로서비스" 패턴을 구현합니다. **Redis Pub/Sub 기반 EventBus**를 도입하여 서비스 간 느슨한 결합(Loose Coupling)을 달성합니다.

#### EventBus 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                     EventBus (Singleton)                │
│                                                         │
│  ┌───────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │ Local     │   │ Redis        │   │ WebSocket    │   │
│  │ Dispatch  │   │ Pub/Sub      │   │ Broadcast    │   │
│  │ (async)   │   │ (cross-proc) │   │ (frontend)   │   │
│  └─────┬─────┘   └──────┬───────┘   └──────┬───────┘   │
│        │                │                   │           │
│        ▼                ▼                   ▼           │
│  Event Handlers   Celery Workers      React Client      │
│  (server-side)    (sync publish)      (EventToast)      │
└─────────────────────────────────────────────────────────┘
```

#### 이벤트 흐름

1. **FastAPI 엔드포인트** → `event_bus.publish()` → 로컬 핸들러 실행 + Redis 채널 발행 + WebSocket 푸시
2. **Celery 워커** → `_publish_event()` (sync Redis) → Redis 채널 발행 → EventBus 리스너가 수신 → 로컬 핸들러 + WebSocket 푸시
3. **프론트엔드 수신**: WebSocket `onmessage` → `type: "event"` 메시지 → `EventToastContainer`로 실시간 알림

#### 이벤트 타입 (30+ EventType)

| 도메인 | 이벤트 | 설명 |
| --- | --- | --- |
| **Session** | `session.created`, `session.ended` | 면접 세션 생명주기 |
| **Interview** | `interview.question_generated`, `interview.answer_submitted`, `interview.turn_started`, `interview.turn_ended` | 면접 질의응답 흐름 |
| **Evaluation** | `evaluation.completed`, `evaluation.batch_completed` | AI 답변 평가 |
| **Emotion** | `emotion.analyzed`, `emotion.alert` | 감정 분석 및 경고 |
| **STT/TTS** | `stt.transcribed`, `tts.generated` | 음성 처리 |
| **Resume** | `resume.uploaded`, `resume.indexed` | 이력서 업로드/RAG 색인 |
| **Report** | `report.generated` | 면접 리포트 생성 완료 |
| **Coding** | `coding.problem_generated`, `coding.submitted`, `coding.analyzed` | 코딩 테스트 흐름 |
| **Whiteboard** | `whiteboard.submitted`, `whiteboard.analyzed` | 아키텍처 설계 |
| **System** | `system.error`, `system.service_status` | 시스템 상태/오류 |

#### 구현 파일

| 파일 | 역할 |
| --- | --- |
| `events.py` | `EventType` enum (30+), 도메인별 Pydantic 이벤트 모델, `EventFactory` |
| `event_bus.py` | Redis Pub/Sub + 로컬 비동기 디스패처 + WebSocket 브로드캐스트 (싱글턴) |
| `event_handlers.py` | 9개 도메인별 핸들러 등록 (`register_all_handlers(bus)`) |

#### Celery 이벤트 통합

Celery 워커는 비동기 컨텍스트 외부에서 실행되므로 `_publish_event()` 헬퍼를 통해 동기식 Redis 발행을 수행합니다:

| 태스크 | 발행 이벤트 |
|--------|------------|
| `evaluate_answer_task` | `evaluation.completed` |
| `analyze_emotion_task` | `emotion.analyzed` |
| `generate_report_task` | `report.generated` / `system.error` |
| `process_resume_task` | `resume.indexed` |
| `complete_interview_workflow_task` | `report.generated` / `system.error` |

#### 서버 이벤트 발행 지점

| API 엔드포인트 | 발행 이벤트 |
| --- | --- |
| `POST /api/sessions` | `session.created` |
| `POST /api/chat` | `interview.answer_submitted`, `interview.question_generated` |
| `POST /api/upload-resume` | `resume.uploaded` |
| `startup` | `system.service_status` (started) |
| `shutdown` | `system.service_status` (shutting_down) |

#### 프론트엔드 실시간 이벤트 처리

| 파일 | 역할 |
| --- | --- |
| `frontend/src/contexts/EventBusContext.tsx` | WebSocket 이벤트 컨텍스트 Provider — `useEventBus()` 훅 |
| `frontend/src/components/common/EventToast.tsx` | 실시간 토스트 알림 (평가 완료, 감정 경고, 리포트 생성 등) |

지원 알림 유형:
- ✅ 평가 완료 — 점수 표시 (`evaluation.completed`)
- 🧠 감정 경고 — 부정 감정 감지 (`emotion.alert`)
- 📊 리포트 생성 완료 (`report.generated`)
- 💻 코드 분석 완료 (`coding.analyzed`)
- ⚠️ 시스템 오류 (`system.error`)

### 14. 미디어 녹화/트랜스코딩 서비스 (media_recording_service.py)

aiortc와 GStreamer/FFmpeg를 결합한 **하이브리드 아키텍처** 기반 면접 영상 녹화 및 트랜스코딩 서비스입니다.

#### 아키텍처 개요

```
┌──────────────┐     raw frames (BGR24)     ┌──────────────────────┐
│   aiortc     │  ─────────────────────►    │  GStreamer / FFmpeg   │
│  (WebRTC     │     stdin pipe              │  (실시간 인코딩)       │
│   Track      │                            │                      │
│   수신)       │     audio frames           │  H.264 + AAC         │
│              │  ─────────────────────►    │  → MP4 컨테이너        │
└──────────────┘                            └──────────┬───────────┘
                                                       │
                                                       ▼
                                            ┌──────────────────────┐
                                            │  recordings/         │
                                            │  ├── {session_id}/   │
                                            │  │   ├── video.mp4   │
                                            │  │   ├── audio.wav   │
                                            │  │   ├── merged.mp4  │
                                            │  │   └── thumb.jpg   │
                                            │  └── metadata.json   │
                                            └──────────────────────┘
                                                       │
                                            ┌──────────▼───────────┐
                                            │  Celery Worker       │
                                            │  (media_processing)  │
                                            │  ├── transcode_task  │
                                            │  └── cleanup_task    │
                                            └──────────────────────┘
```

#### 핵심 설계: Graceful Degradation

서비스는 실행 환경에 따라 최적의 미디어 처리 백엔드를 자동으로 선택합니다:

| 우선순위 | 백엔드 | 파이프라인 명령 | 조건 |
|----------|--------|----------------|------|
| 1순위 | **GStreamer** | `gst-launch-1.0 fdsrc ! video/x-raw,format=BGR ! videoconvert ! x264enc ! mp4mux ! filesink` | `gst-launch-1.0` 실행 가능 |
| 2순위 | **FFmpeg** | `ffmpeg -f rawvideo -pixel_format bgr24 -c:v libx264 -preset ultrafast` | `ffmpeg` 실행 가능 |
| 3순위 | **비활성화** | — | 둘 다 미설치 시 경고 로그 출력, 녹화 기능 비활성화 |

#### 주요 클래스/타입

| 이름 | 타입 | 설명 |
|------|------|------|
| `RecordingStatus` | Enum | `IDLE`, `RECORDING`, `STOPPING`, `COMPLETED`, `FAILED`, `TRANSCODING`, `READY` |
| `RecordingMetadata` | dataclass | 세션 ID, 파일 경로, 상태, 시작/종료 시간, 프레임 수, 해상도, fps, 파일 크기 |
| `MediaRecordingService` | class | 녹화 서비스 메인 클래스 (싱글턴 인스턴스) |

#### MediaRecordingService API

| 메서드 | 설명 |
|--------|------|
| `start_recording(session_id, width, height, fps)` | 녹화 시작 — stdin pipe로 GStreamer/FFmpeg 프로세스 생성 |
| `write_video_frame(session_id, frame)` | BGR24 raw 비디오 프레임을 파이프에 기록 |
| `write_audio_frame(session_id, audio_data)` | PCM 오디오 데이터를 WAV 파일에 기록 |
| `stop_recording(session_id)` | 녹화 중지 — 파이프 닫기, 프로세스 종료, 썸네일 생성, 메타데이터 저장 |
| `transcode(input_path, output_path, format)` | 정적 메서드, GStreamer/FFmpeg로 비디오+오디오 합성 (H.264 + AAC) |
| `delete_recording(session_id)` | 녹화 파일 및 메타데이터 삭제 |
| `get_recording(session_id)` | 녹화 메타데이터 조회 |
| `cleanup()` | 전체 녹화 세션 정리 (서버 종료 시 호출) |

#### 서버 통합 (`integrated_interview_server.py`)

- **`_video_pipeline(track, session_id)`**: WebRTC 비디오 트랙에서 프레임 추출 → 녹화 서비스에 프레임 기록 (매 프레임) + 감정 분석 (1초 간격) + 시선 추적
- **`_audio_pipeline(track, session_id)`**: WebRTC 오디오 트랙 라우팅 — STT+녹화 동시 처리 또는 녹화 전용
- **`_process_audio_with_stt_and_recording(track, session_id)`**: Deepgram STT와 녹화 오디오 파이프를 단일 프레임 루프에서 동시 처리

#### FFmpeg / GStreamer 설치

```powershell
# FFmpeg 설치 (Windows — winget)
winget install Gyan.FFmpeg

# 또는 수동 설치: https://ffmpeg.org/download.html
# PATH에 ffmpeg.exe 경로 추가 필요

# GStreamer 설치 (Windows — MSI 인스톨러)
# https://gstreamer.freedesktop.org/download/
# Runtime + Development 모두 설치
# 설치 후 시스템 PATH에 자동 추가됨
```

### 15. Recharts 리포트 시각화 (InterviewReportCharts.tsx)

면접 종료 후 생성되는 종합 리포트를 **Recharts** 라이브러리를 활용하여 7종의 인터랙티브 차트로 시각화합니다.

#### 차트 구성

| 차트 | 컴포넌트 | 유형 | 데이터 소스 |
|------|----------|------|-------------|
| 평가 항목 레이더 | `EvalRadarChart` | RadarChart | LLM 5가지 평가 점수 (문제해결력, 논리성, 기술이해도, STAR, 전달력) |
| 답변별 점수 비교 | `EvalBarChart` | BarChart (Grouped) | 질문별 5항목 점수 비교 |
| STAR 기법 분석 | `StarBarChart` | BarChart (Horizontal) | 상황/과제/행동/결과 각 점수 |
| 감정 분포 | `EmotionPieChart` | PieChart (Donut) | 7가지 감정 비율 |
| 핵심 키워드 | `KeywordBarChart` | BarChart | 기술 키워드 + 일반 키워드 Top 10 |
| 발화 속도 추이 | `SpeechAreaChart` | AreaChart | 답변별 SPM (분당 음절 수) + 단어 수 |
| 시선 분석 | `GazeBarChart` | BarChart | 답변별 시선 집중도(%) — 조건부 색상 표시 |

#### 부가 컴포넌트

| 컴포넌트 | 설명 |
|----------|------|
| `ScoreCard` | 요약 메트릭 카드 (아이콘 + 점수 + 라벨) — "통합 점수", "언어 평가" 2종 |
| 합격/불합격 배지 | 통합 점수 기반 이진 판정 — 합격(파란색) / 불합격(빨간색) 색상 코딩 |
| 비언어 평가 카드 | 발화 속도(speech), 시선 추적(gaze), 감정 안정성(emotion), Prosody 개별 점수 + 색상 코딩 |
| 통합 점수 수식 | "언어 X × 60% + 비언어 Y × 40% = 통합 Z" 공식 표시 |
| 답변별 상세 피드백 | 각 답변의 강점(strengths)과 개선점(improvements) 표시 |

#### TypeScript 인터페이스

```typescript
interface ReportData {
  session_id: string;
  llm_evaluation: LLMEvaluation;  // verbal_average, nonverbal_scores, nonverbal_average, final_score, recommendation, recommendation_reason 포함
  emotion_stats: EmotionStats;
  speech_analysis: SpeechAnalysis;
  gaze_analysis: GazeAnalysis;
  star_analysis: StarAnalysis;
  keywords: { tech: Record<string, number>; general: Record<string, number> };
  total_score: number;
}
```

#### 데이터 흐름

```
면접 종료 → GET /api/report/{session_id}
        → React useEffect에서 데이터 fetch
        → InterviewReportCharts 컴포넌트에 전달
        → 7개 서브 차트 렌더링
        → 로딩 상태: 스피너 표시
        → 에러 시: 기존 텍스트 리포트 fallback
```

#### interview/page.tsx 통합

면접 페이지의 리포트 phase에서 자동으로 차트 대시보드가 표시됩니다:
- **로딩 상태**: 스피너 + "리포트 데이터를 불러오는 중..." 텍스트
- **차트 대시보드**: 7종 차트 + ScoreCard (통합 점수, 언어 평가) + 합격/불합격 배지 + 비언어 평가 카드
- **액션 버튼**: JSON 다운로드 / PDF 다운로드 / 대시보드 이동 (Lucide 아이콘)

---

## 📡 API 엔드포인트

### 페이지 라우팅 (Next.js 프록시)
- `GET /` - 홈페이지 (Next.js → localhost:3000)
- `GET /interview` - 면접 페이지
- `GET /coding` - 코딩 테스트 페이지
- `GET /coding-test` - 코딩 테스트 페이지 (레거시 경로)
- `GET /dashboard` - 대시보드 페이지
- `GET /emotion` - 감정 분석 페이지
- `GET /whiteboard` - 화이트보드 페이지
- `GET /profile` - 프로필 페이지
- `GET /settings` - 설정 페이지
- `GET /_next/{path}` - Next.js 정적 자산 프록시

### 세션 관리
- `POST /api/session` - 새 면접 세션 생성
- `POST /api/session/create` - 새 면접 세션 생성 (동일)
- `GET /api/session/{session_id}` - 세션 정보 조회

### 채팅
- `POST /api/chat` - 메시지 전송 및 다음 질문 받기
- `POST /api/chat/with-intervention` - 개입(인터벤션) 포함 채팅
- `POST /api/chat/stream` - SSE 기반 실시간 AI 답변 스트리밍

### 면접 개입 (Intervention)
- `POST /api/intervention/start-turn` - 사용자 답변 턴 시작
- `POST /api/intervention/vad-signal` - 음성 활동 감지(VAD) 신호 전송
- `POST /api/intervention/check` - 개입 필요성 확인
- `POST /api/intervention/end-turn` - 답변 턴 종료
- `GET /api/intervention/stats/{session_id}` - 개입 통계 조회
- `POST /api/intervention/settings` - 개입 설정 변경
- `GET /api/intervention/settings` - 개입 설정 조회

### 이력서 업로드
- `POST /api/resume/upload` - PDF 이력서 업로드 및 RAG 인덱싱
- `GET /api/resume/status/{session_id}` - 업로드 상태 확인
- `GET /api/resume/user/{user_email}` - 사용자별 이력서 조회
- `DELETE /api/resume/{session_id}` - 이력서 삭제

### QA 데이터 RAG
- `POST /api/qa-data/index` - QA 데이터 RAG 인덱싱
- `GET /api/qa-data/status` - QA RAG 인덱싱 상태
- `GET /api/qa-data/search` - QA RAG 검색

### LLM 평가
- `POST /api/evaluate` - 개별 답변 평가 (5가지 항목)
- `GET /api/evaluations/{session_id}` - 전체 평가 결과 조회

### 리포트
- `GET /api/report/{session_id}` - 종합 면접 리포트 (LLM 평가 + 비언어 평가 + 통합 점수 포함)
- `GET /api/report/{session_id}/pdf` - PDF 종합 리포트 다운로드 (ReportLab 생성)

### 면접 이력
- `GET /api/interviews` - 면접 목록 조회
- `GET /api/interview/history` - 면접 이력 목록 조회
- `GET /api/interview/{session_id}/workflow-status` - 워크플로우 상태 조회
- `POST /api/interview/{session_id}/collect-evaluations` - 평가 수집
- `POST /api/interview/{session_id}/start-workflow` - 워크플로우 시작

### WebRTC
- `POST /offer` - WebRTC offer 처리

### WebSocket
- `WS /ws/interview/{session_id}` - 실시간 면접 WebSocket 연결 (JWT 인증)

### 감정 분석
- `GET /api/emotion/current` - 현재 감정 상태
- `GET /emotion/sessions` - 세션 목록
- `GET /emotion/timeseries` - 시계열 데이터
- `GET /emotion/stats` - 통계

### TTS (hume_tts_service.py 라우터)
- `POST /api/tts/speak` - TTS 음성 생성
- `POST /api/tts/question` - 질문 TTS 생성
- `GET /api/tts/greeting` - 인사말 TTS
- `GET /api/tts/status` - TTS 서비스 상태
- `GET /api/tts/test-token` - TTS 토큰 테스트
- `GET /api/tts/result/{task_id}` - TTS 결과 조회
- `POST /api/tts/prefetch` - TTS 사전 생성

### 회원 인증
- `POST /api/auth/register` - 회원가입
- `POST /api/auth/login` - 로그인
- `GET /api/auth/check-email` - 이메일 중복 확인
- `POST /api/auth/verify-identity` - 본인 인증 (비밀번호 재설정용)
- `POST /api/auth/reset-password` - 비밀번호 재설정
- `GET /api/auth/user/{email}` - 사용자 정보 조회
- `PUT /api/auth/user/update` - 사용자 정보 수정
- `POST /api/auth/user/delete` - 회원 탈퇴
- `GET /api/user` - 현재 로그인 사용자 정보 조회
- `PUT /api/user` - 현재 로그인 사용자 정보 수정
- `GET /api/auth/social/{provider}` - 소셜 로그인 (kakao/google/naver)
- `GET /api/auth/social/{provider}/callback` - 소셜 로그인 콜백
- `GET /api/auth/social/verify` - 소셜 로그인 토큰 검증
- `GET /api/auth/social/status` - 소셜 로그인 설정 상태

### GDPR 데이터 삭제
- `POST /api/gdpr/delete-all-data` - GDPR 규정 준수 전체 데이터 삭제

### 채용공고 관리
- `GET /api/job-postings` - 채용공고 목록 조회
- `GET /api/job-postings/{posting_id}` - 채용공고 상세 조회
- `POST /api/job-postings` - 채용공고 등록 (recruiter 전용)
- `PUT /api/job-postings/{posting_id}` - 채용공고 수정
- `DELETE /api/job-postings/{posting_id}` - 채용공고 삭제

### Celery 비동기 작업
- `POST /api/async/evaluate` - 비동기 답변 평가
- `POST /api/async/batch-evaluate` - 배치 답변 평가
- `POST /api/async/emotion-analysis` - 비동기 감정 분석
- `POST /api/async/batch-emotion` - 배치 감정 분석
- `POST /api/async/generate-report` - 비동기 리포트 생성
- `POST /api/async/complete-interview` - 면접 완료 워크플로우
- `GET /api/async/task/{task_id}` - 태스크 상태 조회
- `GET /api/async/task/{task_id}/result` - 태스크 결과 조회 (상세)
- `DELETE /api/async/task/{task_id}` - 태스크 삭제
- `GET /api/celery/status` - Celery 연결 상태 확인
- `GET /api/celery/queues` - Celery 큐 정보 조회

### 시스템
- `GET /health` - 헬스 체크 (Docker/로드밸런서)
- `GET /api/status` - 전체 서비스 상태 확인
- `GET /api/stt/status` - STT 서비스 상태 확인
- `GET /api/debug/db` - DB 연결 디버그

### 지연 시간 모니터링 (SLA)
- `GET /api/monitoring/latency` - 지연 시간 대시보드 (SLA 위반 횟수, 엔드포인트별 통계, 최근 위반 내역)
- `DELETE /api/monitoring/latency/reset` - 모니터링 통계 초기화

### 이벤트 모니터링
- `GET /api/events/stats` - EventBus 통계 (총 이벤트 수, 타입별 카운트, 핸들러 수, WebSocket 연결 수)
- `GET /api/events/history` - 최근 이벤트 히스토리 (타입 필터 지원)
- `GET /api/events/registered` - 등록된 이벤트 타입 및 핸들러 수

### 코딩 테스트 (code_execution_service.py 라우터)
- `GET /api/coding/generate` - LLM 기반 코딩 문제 동적 생성
- `GET /api/coding/problems/{problem_id}` - 문제 상세 조회
- `POST /api/coding/execute` - 코드 실행 (샌드박스)
- `POST /api/coding/run` - 코드 실행 (execute 별칭)
- `POST /api/coding/submit` - 코드 제출 및 AI 분석
- `GET /api/coding/templates/{language}` - 언어별 코드 템플릿 조회

### 화이트보드 (whiteboard_service.py 라우터)
- `GET /api/whiteboard/problems` - 아키텍처 문제 목록
- `GET /api/whiteboard/problems/{problem_id}` - 문제 상세 조회
- `POST /api/whiteboard/generate` - AI 문제 동적 생성
- `GET /api/whiteboard/categories` - 문제 카테고리 목록
- `POST /api/whiteboard/analyze` - 다이어그램 분석
- `GET /api/whiteboard/results/{session_id}` - 분석 결과 조회
- `GET /api/whiteboard/status` - 화이트보드 서비스 상태

### 워크플로우 모니터링 (LangGraph)
- `GET /api/workflow/status` - 워크플로우 상태
- `GET /api/workflow/graph` - 워크플로우 그래프 시각화
- `GET /api/workflow/graph-definition` - 그래프 정의 조회
- `GET /api/workflow/{session_id}/trace` - 세션 워크플로우 트레이스
- `GET /api/workflow/{session_id}/state` - 세션 상태 조회
- `GET /api/workflow/{session_id}/checkpoint` - 세션 체크포인트
- `GET /api/workflow/{session_id}/checkpoints` - 세션 체크포인트 목록

### D-ID 아바타 (미구현 — 환경변수 예약)
- _현재 `did_avatar_service.py`가 제거되어 아바타 API 엔드포인트는 비활성 상태_

### 미디어 녹화
- `POST /api/recording/{session_id}/start` - 녹화 시작 (GStreamer/FFmpeg 파이프라인 생성)
- `POST /api/recording/{session_id}/stop` - 녹화 중지 (파이프 닫기, 썸네일 생성, 메타데이터 저장)
- `GET /api/recording/{session_id}` - 녹화 메타데이터 조회 (상태, 파일 크기, 해상도, 프레임 수 등)
- `GET /api/recording/{session_id}/download` - 녹화 파일 다운로드 (FileResponse)
- `DELETE /api/recording/{session_id}` - 녹화 파일 및 메타데이터 삭제
- `GET /api/recording/status` - 녹화 서비스 전체 상태 조회 (활성 녹화 세션 수, GStreamer/FFmpeg 가용 여부)

---

## 🖥️ Next.js 프론트엔드 (CSH/frontend)

Next.js 기반 프론트엔드 애플리케이션

### 기술 스택

| 기술 | 설명 |
|------|------|
| **Next.js 16** | App Router 기반 React 풀스택 프레임워크 |
| **TypeScript** | 타입 안전성 보장 |
| **Tailwind CSS** | 유틸리티 기반 CSS (다크 네이비 테마) |
| **Recharts** | 면접 리포트 시각화 (레이더, 바, 파이, 영역 차트) |
| **Chart.js** | 감정 분석 시계열/도넛/레이더 차트 |
| **Monaco Editor** | 코딩 테스트용 웹 IDE |
| **Lucide React** | 아이콘 라이브러리 (액션 버튼, UI 아이콘) |

### 프론트엔드 구조

```
CSH/frontend/
├── next.config.ts           # FastAPI 백엔드 프록시 rewrite 규칙
├── tsconfig.json            # TypeScript 설정
├── postcss.config.mjs       # PostCSS + Tailwind CSS 플러그인
├── eslint.config.mjs        # ESLint (Next.js core-web-vitals)
├── package.json             # 의존성 관리
└── src/
    ├── app/
    │   ├── layout.tsx       # 루트 레이아웃 (AuthProvider + ToastProvider 래핑)
    │   ├── globals.css      # 다크 네이비 테마 전역 CSS
    │   ├── page.tsx         # 랜딩 페이지
    │   ├── error.tsx        # 전역 에러 바운더리 (Next.js Error Boundary)
    │   ├── dashboard/       # 대시보드 페이지
    │   ├── interview/       # 면접 페이지
    │   ├── coding/          # 코딩 테스트 페이지 (Monaco Editor)
    │   ├── whiteboard/      # 화이트보드 시스템 설계 페이지
    │   ├── jobs/            # 채용공고 목록/상세 페이지
    │   ├── recruiter/       # 인사담당자 전용 대시보드 (공고 관리)
    │   ├── profile/         # 프로필/마이페이지
    │   ├── settings/        # 회원정보 수정 + 비밀번호 변경
    │   └── emotion/         # 감정 분석 페이지
    ├── components/
    │   ├── common/
    │   │   ├── Header.tsx   # 공통 네비게이션 헤더
    │   │   ├── Modal.tsx    # 재사용 가능한 모달 컴포넌트
    │   │   ├── Toast.tsx    # 커스텀 토스트 알림 (success/error/warning/info)
    │   │   └── EventToast.tsx # WebSocket 실시간 이벤트 토스트 알림
    │   ├── auth/
    │   │   ├── LoginModal.tsx         # 로그인 모달
    │   │   ├── RegisterModal.tsx      # 회원가입 모달
    │   │   └── ForgotPasswordModal.tsx # 비밀번호 찾기 모달
    │   ├── report/
    │   │   └── InterviewReportCharts.tsx # Recharts 리포트 시각화 (7종 차트)
    │   └── emotion/
    │       └── EmotionCharts.tsx      # Chart.js 차트 컴포넌트
    ├── contexts/
    │   ├── AuthContext.tsx  # JWT 세션 관리, 자동 로그아웃 (60분/유효 30분)
    │   ├── ToastContext.tsx # 전역 토스트 상태 관리 (success/error/warning/info + confirm)
    │   └── EventBusContext.tsx # WebSocket 이벤트 컨텍스트 Provider (useEventBus 훅)
    └── lib/
        └── api.ts           # API 통신 라이브러리
```

### 페이지 구성

| 경로 | 페이지 | 기능 |
|------|--------|------|
| `/` | 랜딩 페이지 | 서비스 소개, AI 면접 시작 CTA |
| `/dashboard` | 대시보드 | 면접 결과 종합, 통계 차트 |
| `/interview` | 면접 | 화상 면접 인터페이스 |
| `/coding` | 코딩 테스트 | Monaco Editor, 문제 선택, 코드 실행/제출 |
| `/whiteboard` | 화이트보드 | 시스템 아키텍처 설계 |
| `/jobs` | 채용공고 | 공고 목록 열람, 카테고리/경력 필터, 검색 |
| `/recruiter` | 인사담당자 | 공고 등록/수정/마감/삭제, 통계 요약 |
| `/profile` | 프로필 | 마이페이지, 정보 조회 |
| `/settings` | 설정 | 회원정보 수정 (이름/생년월일/성별/주소/전화번호/역할), 비밀번호 변경 |
| `/emotion` | 감정 분석 | 시계열/도넛/레이더 차트 시각화 |

---

## UI 구성


### 면접 화면 구성


## 🔌 서비스 활성화 조건

| 서비스 | 필수 조건 | 역할 |
|--------|----------|------|
| LLM | Ollama 실행 + exaone3.5:7.8b 모델 |
| TTS | HUME_API_KEY + HUME_SECRET_KEY 설정 | 음성 출력 |
| STT | DEEPGRAM_API_KEY 설정 + pyaudio | 음성 인식 |
| RAG | POSTGRES_CONNECTION_STRING 설정 + pgvector | 이력서 맞춤 평가 |
| 감정분석 | deepface + opencv-python 패키지 설치 | 감정 데이터 분석 |
| Redis | Redis 서버 실행 + REDIS_URL 설정 | 감정 시계열 저장 + Celery 브로커 + EventBus Pub/Sub |
| Celery | Redis + celery_app.py 실행 | 비동기 작업 처리 |
| 소셜 로그인 | KAKAO/GOOGLE/NAVER Client ID/Secret | OAuth 인증 |
| 코딩 테스트 | Python 3.8+ (기본), Node.js, JDK (선택) | 코드 실행 |
| 화이트보드 | ANTHROPIC_API_KEY 설정 (Claude) | 다이어그램 분석 |
| AI 아바타 | DID_API_KEY 설정 | 실시간 아바타 영상 |
| 미디어 녹화 | GStreamer 또는 FFmpeg 설치 (선택) | 면접 영상 녹화/트랜스코딩 |
| 발화 분석 | speech_analysis_service.py | 발화 속도(SPM)/발음 등급 판정 |
| 시선 추적 | gaze_tracking_service.py + OpenCV | 눈 접촉 비율/집중도 등급 |
| Prosody 분석 | HUME_API_KEY + hume_prosody_service.py | 음성 감정 10개 지표 분석 |
| 지연 시간 모니터링 | 자동 활성화 (latency_monitor.py) | API SLA 1.5초 위반 감지 + Phase 측정 |

모든 서비스는 선택사항입니다. 설정되지 않은 서비스는 비활성화되며, 기본 기능으로 대체됩니다.

서버 시작 시 각 서비스 상태가 콘솔에 표시됩니다:
```
✅ Hume TTS 서비스 활성화됨
✅ Resume RAG 서비스 활성화됨
✅ LLM 서비스 활성화됨
✅ 감정 분석 서비스 활성화됨
✅ Redis 서비스 활성화됨
✅ Celery 비동기 작업 서비스 활성화됨
✅ 코딩 테스트 서비스 활성화됨
✅ 화이트보드 분석 서비스 활성화됨
✅ D-ID 아바타 서비스 활성화됨
✅ 미디어 녹화 서비스 활성화됨 (GStreamer)
✅ 발화 분석 서비스 활성화됨
✅ 시선 추적 서비스 활성화됨
✅ Prosody 분석 서비스 활성화됨
✅ 지연 시간 모니터링 활성화됨 (SLA: 1.5s)
```

---

## 🚀 원클릭 시작 (One-Click Start)

### Windows Batch 스크립트

```bash
# 전체 시스템 시작 (Redis, Ollama 사전 실행 필요)
start_interview.bat

# 사전 서비스만 시작 (Redis, Ollama)
start_prerequisites.bat
```

### PowerShell 스크립트

```powershell
# PowerShell에서 전체 시스템 시작
.\start_all.ps1
```

### 시작 스크립트 기능

| 스크립트 | 기능 |
|----------|------|
| `start_interview.bat` | Redis/Ollama 상태 확인 → Celery Worker → FastAPI 서버 |
| `start_all.ps1` | PowerShell 버전 (컬러 출력, 상세 로그) |
| `start_prerequisites.bat` | Redis, Ollama만 실행 (Docker 사용) |

---

## 🐛 문제 해결

### Ollama 연결 오류
```bash
# Ollama 서비스 확인
ollama serve
curl http://localhost:11434/api/generate -d '{"model":"exaone3.5:7.8b","prompt":"hello"}'

# 모델 다운로드 확인
ollama list
ollama pull exaone3.5:7.8b
```

### WebRTC 연결 실패
- 브라우저에서 카메라/마이크 권한 허용
- HTTPS가 아닌 경우 localhost에서만 동작
- 방화벽 설정 확인

### 감정 분석 오류
```bash
# TensorFlow/DeepFace 재설치
pip install --upgrade deepface tf-keras opencv-python

# GPU 사용 시
pip install tensorflow[and-cuda]
```

### Redis 연결 오류
```bash
# Redis 상태 확인
redis-cli ping

# Docker로 Redis 재시작
docker run -d -p 6379:6379 redis:alpine
```

### Celery Worker 연결 오류
```bash
# Redis 연결 확인
redis-cli ping

# Worker 실행 (Windows)
celery -A celery_app worker --pool=solo --loglevel=info

# Worker 상태 확인
celery -A celery_app status
```

### PostgreSQL + pgvector 오류
```bash
# pgvector 확장 설치 확인
docker exec -it <container_id> psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 연결 문자열 형식 확인 (psycopg3 사용)
# postgresql+psycopg://user:password@localhost:5432/interview_db
```

### Hume TTS 토큰 인증 실패
```bash
# .env 파일에 API_KEY와 SECRET_KEY 모두 설정 필요
HUME_API_KEY=your_api_key
HUME_SECRET_KEY=your_secret_key

# 토큰 인증 테스트
curl -X POST https://api.hume.ai/oauth2-cc/token \
  -H "Authorization: Basic $(echo -n 'API_KEY:SECRET_KEY' | base64)" \
  -d "grant_type=client_credentials"
```

### 소셜 로그인 오류
- OAuth 콜백 URL이 각 플랫폼에 등록되어 있는지 확인
- `OAUTH_REDIRECT_BASE` 환경 변수가 올바르게 설정되어 있는지 확인
- 각 플랫폼의 Client ID/Secret이 올바른지 확인

---

## 📁 파일 설명

| 파일 | 설명 |
|------|------|
| `integrated_interview_server.py` | **통합 FastAPI 서버** (7,987 lines) - 질문 은행, LLM 평가 (5축 + 비언어 통합 + 합격/불합격), 회원 인증 (GDPR 포함), 소셜 로그인, WebRTC, WebSocket, 감정 분석, 면접 개입(인터벤션), 지연 시간 미들웨어, Celery 워크플로우, 미디어 녹화 통합, 채용공고 CRUD, 워크플로우 모니터링 |
| `celery_app.py` | **Celery 애플리케이션 설정(설계도)** (111 lines) - Celery 앱 생성, Redis 브로커 연결, 큐 정의 & 라우팅 (media_processing 큐 포함), Beat 스케줄 정의 |
| `celery_tasks.py` | **Celery 비동기 태스크** (1,132 lines) - 16개 태스크 정의: LLM 평가 (5축 + 합격/불합격), 감정 분석, 리포트 생성, TTS prefetch, RAG 이력서 컨텍스트, 세션 정리, 통계, 워크플로우, 미디어 트랜스코딩, 코딩 문제 사전 생성 |
| `text_interview.py` | **텍스트 면접 모듈** (605 lines) - STAR 기법 분석, 키워드 추출, 리포트 생성 클래스 |
| `hume_tts_service.py` | **Hume AI TTS 클라이언트** (479 lines) - OAuth2 토큰 인증, EVI 음성 생성, 스트리밍 지원 |
| `stt_engine.py` | **Deepgram STT 클라이언트** (303 lines) - Nova-3 모델, 실시간 마이크 입력, VAD 지원, 한국어 띄어쓰기 보정 (pykospacing) |
| `resume_rag.py` | **이력서 RAG 모듈** (311 lines) - PDF 로딩, 청킹, PGVector 벡터 저장, nomic-embed-text 임베딩 (768차원, 8192 토큰) |
| `code_execution_service.py` | **코딩 테스트 서비스** (2,242 lines) - Docker 샌드박스 코드 실행, AI 코드 분석 (Qwen3-Coder-30B), 문제 은행, 동적 문제 생성, 실행 이력 관리 |
| `whiteboard_service.py` | **화이트보드 분석 서비스** (785 lines) - Claude 3.5 Sonnet Vision (메인) + Qwen3-VL (폴백), 아키텍처 평가, 동적 문제 생성 |
| `media_recording_service.py` | **미디어 녹화/트랜스코딩 서비스** (534 lines) - aiortc + GStreamer/FFmpeg 하이브리드, stdin pipe 실시간 인코딩, 썸네일 생성, 메타데이터 관리, Graceful Degradation |
| `interview_workflow.py` | **LangGraph 면접 상태머신** (1,053 lines) - 조건부 분기 + 루프 제어 + 체크포인트 기반 면접 흐름 제어, StateGraph |
| `speech_analysis_service.py` | **발화 속도/발음 분석 서비스** (324 lines) - SPM(분당 음절 수) 계산, 등급 판정, 5점 척도 변환 |
| `gaze_tracking_service.py` | **시선 추적 분석 서비스** (286 lines) - 눈 접촉 비율 측정, 집중도 등급 판정, OpenCV 기반 |
| `hume_prosody_service.py` | **음성 감정 Prosody 분석 서비스** (699 lines) - Hume AI API, 10개 감정 지표 (confidence, joy, sadness 등), 평균 점수 산출 |
| `pdf_report_service.py` | **PDF 종합 리포트 생성** (473 lines) - ReportLab 기반, 커버페이지(합격/불합격 + 통합 점수) + 평가표 + 비언어 바 차트 + 키워드 + STAR 각 섹션 |
| `latency_monitor.py` | **지연 시간 모니터링** (202 lines) - Thread-safe LatencyMonitor 클래스, SLA 1.5초 임계값, Phase 측정 (LLM/TTS), 위반 내역 deque, 대시보드 API 데이터 |
| `whisper_stt_service.py` | **Whisper 기반 로컬 STT** (501 lines) - 오프라인 폴백용 음성 인식 서비스, Deepgram 불가 시 자동 전환 |
| `prompt_templates.py` | **프롬프트 템플릿 모듈** (89 lines) - INTERVIEWER_PROMPT, EVALUATION_PROMPT, build_question_prompt() 함수, 면접관 역할/평가 기준 정의 |
| `Dockerfile` | **Docker 컨테이너 설정** (57 lines) - python:3.11-slim 기반, FFmpeg 포함, uvicorn 워커 실행 |
| `data_entry.ipynb` | 데이터 입력용 Jupyter Notebook |
| `start_interview.bat` | **원클릭 시작 스크립트** (Windows Batch) - 전체 시스템 실행 |
| `start_all.ps1` | **원클릭 시작 스크립트** (PowerShell) - 컬러 출력, 상세 로그 |
| `start_prerequisites.bat` | **사전 서비스 스크립트** - Redis, Ollama만 실행 |
| `json_utils.py` | **JSON 안정적 파싱 모듈** (307 lines) - 6단계 다층 파싱, EXAONE `<think>` / `</think>` Deep Thought 블록 제거, 구문 오류 자동 수정 |
| `security.py` | **보안 유틸리티 모듈** (551 lines) - bcrypt 해싱, JWT 인증, AES-256-GCM 민감정보 암호화, CORS, WebSocket JWT, TLS, 보호 API 16개, GDPR 데이터 삭제 지원 |
| `events.py` | **이벤트 정의 모듈** (199 lines) - EventType enum (30+), 도메인별 Pydantic 이벤트 모델, EventFactory |
| `event_bus.py` | **이벤트 버스 모듈** (346 lines) - Redis Pub/Sub + 로컬 비동기 디스패치 + WebSocket 브로드캐스트 (싱글턴) |
| `event_handlers.py` | **이벤트 핸들러 모듈** (272 lines) - 9개 도메인별 핸들러 등록, 감정 경고 자동 발행 |
| `.env.example` | **환경변수 템플릿** (60 lines) - 모든 필수/선택 환경변수 목록 및 기본값 안내 |
| `requirements_integrated.txt` | 통합 의존성 목록 (FastAPI, LangChain, Celery, DeepFace, anthropic, cryptography 등) |
| `__init__.py` | 패키지 초기화 파일 |
| `uploads/` | 이력서 PDF 업로드 디렉토리 |
| `sandbox/` | **Docker 샌드박스** - 코딩 테스트 격리 실행 환경 (Dockerfile + 보안 설정) |
| `nginx/` | **NGINX 리버스 프록시 설정** - 라우팅 및 로드 밸런싱 |
| `documents/` | **설계 문서 디렉토리** - SAD, SRS, 보안 리뷰 보고서, RAG DB 구조, TODO |
| `frontend/` | **Next.js 16 프론트엔드** - TypeScript + Tailwind CSS + Recharts, 10개 페이지, 인증 시스템 (JWT + GDPR), Chart.js, Recharts 리포트 시각화 (7종 차트 + 비언어 평가 카드 + 통합 점수 + 합격/불합격 배지), 실시간 이벤트 알림, 채용공고 관리, 인사담당자 대시보드 |

---


## 🛠️ 개발 가이드

### 새 Celery 태스크 추가하기

1. `celery_tasks.py`에 태스크 함수 정의:
```python
@celery_app.task(
    bind=True,
    name="celery_tasks.my_new_task",
    soft_time_limit=60,
    time_limit=90
)
def my_new_task(self, arg1, arg2):
    task_id = self.request.id
    # 작업 수행
    return {"result": "success", "task_id": task_id}
```

2. `celery_app.py`에 라우팅 추가 (선택):
```python
task_routes={
    "celery_tasks.my_new_task": {"queue": "my_queue"},
}
```

3. API 엔드포인트에서 호출:
```python
from celery_tasks import my_new_task
result = my_new_task.delay(arg1, arg2)
# 또는 동기 실행
result = my_new_task.apply(args=[arg1, arg2]).get(timeout=90)
```

### 새 API 엔드포인트 추가하기

`integrated_interview_server.py`에 추가:
```python
@app.post("/api/my-endpoint")
async def my_endpoint(request: MyRequestModel):
    # 비동기 작업 호출
    task = my_new_task.delay(request.data)
    return {"task_id": task.id}

@app.get("/api/my-endpoint/{task_id}")
async def get_my_result(task_id: str):
    from celery.result import AsyncResult
    result = AsyncResult(task_id, app=celery_app)
    if result.ready():
        return {"status": "completed", "result": result.get()}
    return {"status": "pending"}
```

---

## 📚 참고 문서

- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Celery 문서](https://docs.celeryq.dev/)
- [Ollama 문서](https://ollama.ai/)
- [Hume AI 문서](https://docs.hume.ai/)
- [Deepgram 문서](https://developers.deepgram.com/)
- [DeepFace 문서](https://github.com/serengil/deepface)
- [LangChain 문서](https://python.langchain.com/)
- [PGVector 문서](https://github.com/pgvector/pgvector)
- [Anthropic Claude 문서](https://docs.anthropic.com/)
- [D-ID API 문서](https://docs.d-id.com/)
- [aiortc WebRTC 문서](https://github.com/aiortc/aiortc)
- [Recharts 문서](https://recharts.org/)
- [GStreamer 문서](https://gstreamer.freedesktop.org/documentation/)
- [FFmpeg 문서](https://ffmpeg.org/documentation.html)

---

## 🤝 기여 방법

1. 이 저장소를 Fork합니다.
2. 새 브랜치를 생성합니다: `git checkout -b feature/my-feature`
3. 변경사항을 커밋합니다: `git commit -m 'Add my feature'`
4. 브랜치에 Push합니다: `git push origin feature/my-feature`
5. Pull Request를 생성합니다.

---

---

## 📝 변경 이력 (Changelog)

### 2026-03-04

#### 📄 문서 및 품질 개선
- **배포 가이드 문서** 신규 작성
- **STT 성능 개선**: Deepgram Nova-3 최적화, 음성 인식 품질 향상 작업 수행 및 방안 문서화
- **SAD/SRS 대비 실제 구현 상태 점검** 후 결과 문서화
- **Latency 해결 방안** 정리 및 문서화

### 2026-03-03

#### 🎙️ STT 엔진 및 TTS 개선
- **STT 엔진 교체 테스트**: Google Web Speech ↔ Deepgram Nova-3 간 전환 테스트, 최종 **Deepgram Nova-3** 확정
- **Deepgram 서버 STT**: 중간 인식 결과를 회색 이탤릭(interimText)으로 실시간 표시, 확정되면 검은 글씨(sttText)로 전환하는 UX 구현
- **SSE와 TTS 발화 동시 진행**: AI 답변 스트리밍과 음성 합성 병렬 처리
- **Celery에 TTS prefetch 태스크 추가**: `prefetch_tts_task` 비동기 음성 사전 생성
- **VAD 시스템 오작동 수정**: 면접 개입(인터벤션) 안정화
- **AI 영어 답변 버그 수정**: 프롬프트 엔지니어링으로 한국어 응답 강제

### 2026-02-26

#### 🔧 STT 품질 및 시스템 안정화
- **듀얼 STT 충돌 해결**: 프론트엔드에서 Deepgram 사용 시 브라우저 STT 비활성화하여 동시 누적 충돌 방지
- **AI 면접 종료 멘트**: 마지막 멘트 출력으로 사용자 경험 향상
- **AI 영어 질문 버그 수정**: 프롬프트 엔지니어링 적용
- **PowerShell 원클릭 실행 스크립트** (`start_all.ps1`) 작성
- **STT 미작동 버그 해결**
- **VAD 설정값 조정**: 실시간 면접 개입 시스템 파라미터 최적화

### 2026-02-25

#### 🤖 AI 답변 품질 및 안정성 대규모 개선
- **AI 답변 스트리밍 방식 구현**: SSE 기반 실시간 토큰 출력으로 사용자 경험 향상
- **LLM 문맥 기반 질문 생성 개선** (3가지 근본 원인 해결):
  1. RAG 컨텍스트 메시지 순서 재배치 (대화 흐름 단절 방지)
  2. `build_question_prompt()`에 `user_answer` 파라미터 추가 (직전 답변 기반 후속 질문)
  3. 대화 이력 `max_messages` 증가 (6→10, 3턴→5턴)
- **LLM 무한 반복/무한 꼬리 질문 버그 해결**
- **RAG 타임아웃 문제 해결**
- **VAD 개입 메시지 템플릿 변경** 및 프론트엔드 연동
- **Deepgram 파라미터 추가**: 인식 정확도 향상
- **환경 테스트 피드백 개선**: 면접 시작 전 정확한 피드백 제공
- **AI 개입 후 시스템 정지 버그 수정**

### 2026-02-24

#### 🧠 LLM 모델 전환 및 아키텍처 최적화
- **LLM 모델 전환**: exaone-deep:2.4b-q8_0 → **EXAONE 3.5 7.8B** (exaone3.5:7.8b)
- **VRAM 6GB 환경 최적화**: 컨텍스트 윈도우 16384 → 8192 조정
- **코딩 테스트 전용 LLM 변경**: Qwen3-Coder-30B-A3B (Q3_K_M) 설정
- **LangGraph 아키텍처 개선**: 노드 간 독립적 상태 변환 활용
- **Celery RAG 컨텍스트 조회 추가**: `retrieve_resume_context_task` 및 토픽 추적 기능 보완
- **대화 이력 이중 관리 버그 해결**
- **Thinking Mode 추론 블록 중복 제거 버그 수정**
- **프롬프트 엔지니어링**: 질문 품질 지속 개선
- **DB 구조 변경 사항** 면접 시스템 반영 및 문서화
- **질문 개수 UI 반영**: 백엔드에서 확인 후 프론트엔드에 표시

### 2026-02-23

#### 🔧 LLM 엔진 교체 및 안정화
- **LLM 엔진 교체**: Qwen3 → EXAONE (엑사원) 전환 시작
- **LLM 폴백 답변 제거**: 불필요한 기본 응답 삭제
- **LLM 응답 지연/오류 수정**: 답변 생성 성능 개선
- **Hume TTS 토큰 인증 에러 해결**
- **자동 새로고침 방지**: 서버 reload 기능 비활성화
- **면접 진행 중 LLM 무응답 버그 해결**

### 2026-02-19

#### 🚀 코딩 테스트 개선 및 D-ID 제거
- **D-ID 아바타 완전 제거**: `did_avatar_service.py` 파일 삭제, AI 면접관 아바타 기능 미구현 상태로 전환
- **코딩 테스트 최적화**: 문제 생성 시간 단축, 병목현상 해결, "다음 단계로 건너뛰기" 버튼 추가
- **면접 자동 새로고침 버그 수정** (3건)
- **질문 생성 안 되던 문제 해결**
- **UI 개선**: 전반적 인터페이스 정비

### 2026-02-13

#### 🏗️ Docker/NGINX 인프라 및 프롬프트 체계화
- **NGINX API Gateway 설정**: SSL 종단, 리버스 프록시, Rate Limiting, 보안 헤더, 로드 밸런싱
- **개발용 자체서명 SSL 인증서** 생성 스크립트 (OpenSSL 기반)
- **Docker 컨테이너화**: FastAPI 백엔드 + Next.js 프론트엔드 이미지 생성
- **Trusted Proxy 미들웨어** 추가 (X-Real-IP, X-Forwarded-For, X-Request-ID)
- **Docker Gateway 모드 원샷 시작 안정화** 및 컨테이너 헬스체크 수정
- **프롬프트 템플릿화**: `prompt_templates.py` 모듈로 공통 프롬프트 분리
- **카메라/마이크 테스트 페이지 삭제**: 면접 페이지 내 환경 테스트로 통합
- **SAD/SRS 실제 구현 점검 결과** 업데이트
- **Celery Worker, Next.js dev 서버** PowerShell 창 실행 수정

### 2026-02-12

#### 🎨 UX 대규모 개선 및 신규 페이지
- **채용공고 시스템**: `/jobs` 지원 공고 페이지 생성, LLM이 공고 내용 기반 지능적 질문 가능
- **인사담당자 대시보드**: `/recruiter` 전용 페이지 생성 (공고 CRUD)
- **채용 공고 등록/수정/삭제 버그 수정** 및 성공 시 토스트 피드백 추가
- **커스텀 Toast 알림 시스템**: 네이티브 `alert()`/`confirm()` → 커스텀 토스트 + 확인 모달 교체 (`Toast.tsx`, `ToastContext.tsx`)
- **모바일 반응형 헤더**: Drawer 메뉴 + 햄버거 토글
- **모달 접근성(a11y) 전면 개선**: ARIA 속성, 키보드 탐색
- **회원 탈퇴 기능 구현** (GDPR 대응)
- **회원 유형 선택 항목** 추가 및 DB 저장 검증
- **이력서 DB 연동**: 업로드된 이력서 파일 DB 기억
- **면접 기록 열람**: 내 정보 페이지에서 과거 면접 기록 접근 가능
- **WebRTC 영상 버그 수정**: 면접 진행 시 AI/본인 영상 미표시 및 환경 테스트 카메라 스트림 문제 해결
- **시스템 아키텍처 다이어그램** 생성 및 수정
- **로그인/대시보드 이동 버그 수정**

### 2026-02-11 (후반)

#### 🎯 통합 평가 시스템 구현 (5축 언어 + 비언어 + 합격/불합격)
- **평가 축 통일**: 기존 불일치 키(`specificity`/`problem_solving_and_logic`) → 정규 5축(`problem_solving`, `logic`, `technical`, `star`, `communication`)으로 통합
- **S/A/B/C/D 등급 시스템 완전 제거**: 서버, Celery, 프론트엔드, PDF, json_utils 전체에서 grade 관련 코드 삭제
- **비언어 평가 통합**:
  - `_compute_nonverbal_scores(report)` 함수 신규 — 발화 속도(speech), 시선 추적(gaze), 감정 안정성(emotion), Prosody(prosody) 각 5점 척도 변환
  - `_compute_evaluation_summary()` 리디자인 — 언어 평가 60% + 비언어 평가 40% 가중 평균 → `final_score` 산출
- **합격/불합격 이진 판정**:
  - 기존 3단계(합격/보류/불합격) → 2단계(합격/불합격)로 단순화
  - 합격 조건: `final_score ≥ 4.0 AND total_25 ≥ 20 AND low_count == 0`
  - 6개 파일 동시 수정: `integrated_interview_server.py`, `celery_tasks.py`, `json_utils.py`, `InterviewReportCharts.tsx`, `pdf_report_service.py`, Pydantic 모델
- **프론트엔드 업데이트** (`InterviewReportCharts.tsx`, 855 lines):
  - `ScoreCard` 2종: "통합 점수"(final_score) + "언어 평가"(verbal_avg)
  - 비언어 평가 카드: 개별 점수(speech/gaze/emotion/prosody) 색상 코딩
  - 통합 수식 표시: "언어 X × 60% + 비언어 Y × 40% = 통합 Z"
  - `recColors`/`recIcons`: 합격(파란색, ✅) / 불합격(빨간색, ❌) 전용
- **PDF 리포트 업데이트** (`pdf_report_service.py`, 496 lines):
  - 커버: 합격/불합격 + 통합 점수 (등급 없음)
  - LLM 평가 섹션: 언어 평균 + 비언어 바 차트 + 비언어 평균 + 최종 통합 점수
  - 색상 매핑: `{"합격": "#4CAF50", "불합격": "#F44336"}` (보류 제거)

#### ⏱️ N-001 지연 시간 모니터링 구현 (SLA 검증)
- **신규 모듈** (`latency_monitor.py`, 242 lines):
  - `LatencyMonitor` 클래스 (Thread-safe, 싱글턴)
  - `_history` deque (최근 1000개 요청), `_violations` deque (최근 100개 SLA 위반)
  - `_stats` defaultdict (엔드포인트별 count/total/max/min/violations)
  - Phase 측정: `start_phase(request_id, phase)` / `end_phase(request_id, phase)` — LLM 추론, TTS 합성 등 단계별 지연
  - SLA 임계값: 1.5초 (환경변수로 조정 가능)
  - 자동 로깅: `⚠️ [SLA 위반]` 경고 출력
- **HTTP 미들웨어** (`integrated_interview_server.py`):
  - `latency_measurement_middleware` — 모든 `/api/**` 요청 자동 측정
  - `X-Response-Time-Ms` 응답 헤더 추가
  - `request.state.request_id` UUID 할당
- **모니터링 API**:
  - `GET /api/monitoring/latency` — 대시보드 (총 요청, SLA 위반, 엔드포인트별 통계, 최근 위반 내역)
  - `DELETE /api/monitoring/latency/reset` — 통계 초기화
- **Phase 측정 적용**: `/api/chat`, `/api/chat/with-intervention` 엔드포인트에서 `llm_inference`, `tts_synthesis` 단계별 시간 측정

#### 📄 문서 업데이트
- **TODO.md**: N-001 항목 `✅ 구현` 상태 업데이트
- **README_INTEGRATED.md**: 전체 문서 포괄적 업데이트 (평가 시스템, 신규 파일, API, 서비스 활성화 조건 등)

### 2026-02-11 (전반)

#### 📊 Recharts 리포트 시각화 구현
- **신규 컴포넌트** (`frontend/src/components/report/InterviewReportCharts.tsx`, 470+ lines):
  - 7종 인터랙티브 차트 — `EvalRadarChart` (5가지 평가 레이더), `EvalBarChart` (답변별 그룹 바), `StarBarChart` (STAR 기법 수평 바), `EmotionPieChart` (감정 도넛), `KeywordBarChart` (Top 10 키워드 바), `SpeechAreaChart` (발화 속도 영역), `GazeBarChart` (시선 집중도 조건부 색상 바)
  - `ScoreCard` 요약 메트릭 컴포넌트, 통합 점수 + 언어 평가 2종
  - TypeScript 인터페이스: `ReportData`, `LLMEvaluation` (verbal_average, nonverbal_scores, final_score, recommendation 포함), `EmotionStats`, `SpeechAnalysis`, `GazeAnalysis`, `StarAnalysis`
  - 답변별 상세 피드백 (강점/개선점) 섹션
- **면접 페이지 통합** (`frontend/src/app/interview/page.tsx`):
  - 리포트 phase에서 `InterviewReportCharts` 자동 렌더링
  - `useEffect` 훅으로 리포트 데이터 비동기 fetch (`interviewApi.getReport()`)
  - 로딩 스피너 → 차트 대시보드 → 에러 시 텍스트 리포트 fallback
  - 액션 버튼: JSON 다운로드 / PDF 다운로드 / 대시보드 이동 (Lucide React 아이콘: `FileText`, `Download`, `LayoutDashboard`)
- **Recharts 패키지 설치**: `npm install recharts` (38개 패키지 추가)
- **API 타입 수정** (`frontend/src/lib/api.ts`): `authApi.register()` 타입에 `phone?: string` 필드 추가

#### 🎬 aiortc + GStreamer/FFmpeg 하이브리드 미디어 녹화 아키텍처 구현
- **신규 서비스** (`media_recording_service.py`, 430+ lines):
  - aiortc에서 raw 프레임 추출 → stdin pipe로 GStreamer/FFmpeg에 실시간 전달하는 하이브리드 아키텍처
  - Graceful Degradation: GStreamer (1순위) → FFmpeg (2순위) → 비활성화 (3순위)
  - GStreamer 파이프라인: `fdsrc ! video/x-raw,format=BGR ! videoconvert ! x264enc ! mp4mux ! filesink`
  - FFmpeg 파이프라인: `-f rawvideo -pixel_format bgr24 -c:v libx264 -preset ultrafast`
  - `RecordingStatus` enum (7 상태), `RecordingMetadata` dataclass
  - `MediaRecordingService` 클래스: `start_recording()`, `write_video_frame()`, `write_audio_frame()`, `stop_recording()`, `transcode()`, `delete_recording()`, `cleanup()`
  - 썸네일 자동 생성 (`_generate_thumbnail()`), 영상 길이 감지 (`_get_duration()`)
  - 싱글턴 `recording_service` 인스턴스
- **서버 통합** (`integrated_interview_server.py`):
  - `_video_pipeline(track, session_id)`: 비디오 트랙 프레임 → 녹화(매 프레임) + 감정 분석(1초) + 시선 추적
  - `_audio_pipeline(track, session_id)`: 오디오 트랙 라우팅 — STT+녹화 동시 처리 또는 녹화 전용
  - `_process_audio_with_stt_and_recording(track, session_id)`: Deepgram STT + 녹화 오디오 단일 루프
  - WebRTC `on_track` 핸들러 리팩토링: 기존 `analyze_emotions()` → `_video_pipeline()` + `_audio_pipeline()`
  - 6개 녹화 API 엔드포인트 추가 (POST start/stop, GET info/download, DELETE, GET status)
  - shutdown 핸들러에 `recording_service.cleanup()` 추가
  - startup 상태 출력에 녹화 서비스 상태 추가
- **Celery 미디어 처리** (`celery_tasks.py`, `celery_app.py`):
  - `transcode_recording_task`: GStreamer/FFmpeg 트랜스코딩, H.264+AAC 합성, 이벤트 발행, 재시도 (max 2)
  - `cleanup_recording_task`: 만료/삭제 녹화 파일 정리
  - `media_processing` 큐 추가 (`Exchange("media")`, routing_key `media.#`)
  - 태스크 라우팅: `transcode_recording_task` → `media_processing`, `cleanup_recording_task` → `media_processing`
- **TODO.md 업데이트**: SAD-2 (미디어 서버), SAD-5 (WebRTC/미디어 흐름), SAD-6 (비동기 작업 처리) → ✅ 해결

### 2026-02-10

#### 🏗️ 이벤트 기반 아키텍처 구현
- **EventBus 코어** (`event_bus.py`): Redis Pub/Sub + 로컬 비동기 디스패치 + WebSocket 브로드캐스트 싱글턴
- **이벤트 정의** (`events.py`): 30+ EventType enum, 10개 도메인별 Pydantic 이벤트 모델, EventFactory
- **이벤트 핸들러** (`event_handlers.py`): 9개 도메인 핸들러 등록 (감정 경고 자동 발행 포함)
- **Celery 이벤트 통합**: 5개 태스크에서 완료 이벤트 동기 발행 (`_publish_event()` 헬퍼)
- **서버 통합**: startup/shutdown 이벤트, 5개 엔드포인트 이벤트 발행, 3개 모니터링 API
- **프론트엔드 실시간 알림**: `EventBusContext.tsx` (WebSocket 이벤트 컨텍스트), `EventToast.tsx` (실시간 토스트 알림)
- **아키텍처 문서 업데이트**: SAD + README_INTEGRATED에 이벤트 기반 아키텍처 섹션 추가

#### 🔧 코딩 테스트 LLM 동적 생성
- **LLM 문제 생성**: 하드코딩된 5문제 → Qwen3-4B 기반 동적 문제 생성 (`CodingProblemGenerator`)
- **난이도 선택**: easy/medium/hard 난이도별 실시간 문제 생성
- **프론트엔드 갱신**: 문제 목록 드롭다운 → 난이도 선택 버튼 + "새 문제" 생성 UI

### 2026-02-09 (약 80+ 커밋)

#### 🔧 백엔드
- **LLM 엔진 교체**: Llama3 → Qwen3-4B 전환
- **컨텍스트 윈도우 확장**: 8192 → 16384 (더 긴 면접 대화 처리)
- **화이트보드 분석 모델**: Claude 3.5 Sonnet으로 메인 모델 설정
- **벡터 임베딩 모델 변경**: RAG 시스템 임베딩 모델 교체 및 코드 최적화
- **JSON 안정적 파싱** (`json_utils.py`): 6단계 다층 파싱 전략, Qwen3 `<think>` 블록 제거
- **보안 모듈** (`security.py`): bcrypt 해싱, JWT 인증 (120분 만료), TLS 지원, CORS 제한
- **WebSocket JWT 인증**: WebSocket 연결 시 JWT 토큰 검증
- **보호 API 16개**: JWT Bearer Token 인증 적용
- **환경변수 로드 기능**: `.env` 파일 자동 로드
- **로그인/마이페이지 API**: 사용자 인증 및 정보 관리
- **TASK-001**: 로깅 인프라 기반 구축
- **TASK-002**: 종료 처리 및 문서 상태 정합성 정비
- **TASK-003**: Provider 인터페이스 정의 및 Mock 구현
- `.gitignore`에 `*.py[cod]` 패턴 추가

#### 🖥️ Next.js 프론트엔드 (신규 구축)
- **프로젝트 초기화**: React + TypeScript + Tailwind CSS + Chart.js + Monaco Editor
- **FastAPI 프록시**: `next.config.ts`에 백엔드 rewrite 규칙 추가
- **다크 네이비 테마**: 전역 CSS 적용
- **인증 시스템**: AuthContext (JWT 세션 관리, 자동 로그아웃 60분/유효 30분)
- **공통 컴포넌트**: Header, Modal
- **인증 모달**: 로그인, 회원가입, 비밀번호 찾기
- **7개 페이지**: 랜딩, 대시보드, 면접, 코딩 테스트, 화이트보드, 프로필, 감정 분석
- **데이터 시각화**: Chart.js 기반 시계열/도넛/레이더 차트


#### 📄 문서
- **시스템 보안 종합 리뷰 보고서** 작성 (bcrypt ✅, JWT ✅, TLS ✅)
- **SAD/SRS Gap 분석**: 26개 항목 중 구현 완료 27%, 부분 구현 46%, 미구현 27%
- **RAG 시스템 DB 구조** 정리
- **시스템 아키텍처 다이어그램** 생성 (API 방식 / On-Premise 방식 분리)

#### 🔀 기타

---

## 📄 라이선스

이 프로젝트는 교육 목적으로 개발되었습니다.
