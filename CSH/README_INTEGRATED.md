# AI 모의면접 통합 시스템 - CSH 모듈

## 📋 개요

TTS, STT, LLM 기반 답변 평가, 화상 면접, 감정 분석, Celery 비동기 작업 처리를 통합한 AI 모의면접 시스템입니다.

### ✨ 주요 특징

- **화상 면접 중심**: 채팅 면접과 화상 면접을 하나로 통합
- **LLM 답변 평가**: 질문 생성이 아닌 **답변 분석/평가**에 LLM 활용
- **질문 은행 시스템**: 체계적인 카테고리별 질문 순서 (9개 카테고리)
- **이력서 RAG**: PDF 이력서 업로드 → 맞춤형 면접 평가
- **실시간 평가 시각화**: 5가지 평가 항목 실시간 점수 표시
- **Celery 비동기 처리**: 무거운 작업(LLM 평가, 감정 분석, 리포트 생성)을 백그라운드에서 처리
- **회원가입/로그인**: 이메일 기반 회원가입 및 소셜 로그인 (카카오, 구글, 네이버) 지원
- **종합 리포트**: STAR 기법 분석, 키워드 추출, 등급 산정 포함
- **코딩 테스트**: Python, JavaScript, Java, C/C++ 지원 샌드박스 코드 실행
- **화이트보드 면접**: Claude Vision을 활용한 시스템 아키텍처 다이어그램 분석
- **AI 아바타**: D-ID WebRTC 스트리밍으로 실시간 AI 면접관 영상 생성
- **원클릭 시작**: 배치/PowerShell 스크립트로 전체 시스템 한 번에 실행

---

## 🚀 빠른 시작

### 1. 필수 패키지 설치

```bash
pip install -r requirements_integrated.txt
```

### 2. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 값들을 설정하세요:

```env
# LLM 설정 (Ollama) - 답변 평가용
LLM_MODEL=llama3
LLM_TEMPERATURE=0.3

# Hume AI TTS (선택사항)
HUME_API_KEY=your_hume_api_key
HUME_SECRET_KEY=your_hume_secret_key
HUME_CONFIG_ID=your_config_id

# Deepgram STT (선택사항)
DEEPGRAM_API_KEY=your_deepgram_api_key

# PostgreSQL RAG (선택사항)
POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/interview_db

# Redis (Celery 브로커 및 감정 데이터 저장)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 소셜 로그인 (선택사항)
KAKAO_CLIENT_ID=your_kakao_client_id
KAKAO_CLIENT_SECRET=your_kakao_client_secret
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
OAUTH_REDIRECT_BASE=http://localhost:8000

# Claude API (화이트보드 분석용)
ANTHROPIC_API_KEY=your_anthropic_api_key

# D-ID API (AI 아바타용)
DID_API_KEY=your_did_api_key
```

### 3. 외부 서비스 실행

```bash
# Ollama 실행 (LLM - 답변 평가용)
ollama serve
ollama pull llama3

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
- **메인 페이지**: http://localhost:8000
- **화상 면접**: http://localhost:8000/static/integrated_interview.html
- **코딩 테스트**: http://localhost:8000/coding-test
- **감정 대시보드**: http://localhost:8000/static/dashboard.html
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
│     ├─ D-ID AI 아바타 면접관 영상 (선택)                      │
│     ├─ 질문 은행 기반 순차 질문                               │
│     │   (intro → motivation → strength → project → ...)     │
│     ├─ 답변 입력 → Celery 백그라운드 LLM 평가                 │
│     ├─ 실시간 평가 점수 표시 (5가지 항목)                     │
│     ├─ 실시간 감정 분석 (7가지 감정 - DeepFace)               │
│     └─ TTS 음성 출력 (Hume AI)                               │
├─────────────────────────────────────────────────────────────┤
│  4. 코딩 테스트 (선택)                                       │
│     ├─ 문제 은행에서 알고리즘 문제 선택                       │
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
│     ├─ STAR 기법 분석 (상황-과제-행동-결과)                   │
│     ├─ 키워드 분석 (기술 키워드 + 일반 키워드)                │
│     ├─ 등급 산정 (S/A/B/C/D)                                 │
│     ├─ 코딩 테스트 결과 (코드 품질 점수)                      │
│     ├─ 시스템 설계 결과 (아키텍처 평가)                       │
│     └─ 개선 피드백 및 권장사항                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 시스템 구조

```
CSH/
├── integrated_interview_server.py  # 통합 FastAPI 서버 (메인, 4700+ lines)
├── celery_app.py                   # Celery 애플리케이션 설정 (큐, 라우팅)
├── celery_tasks.py                 # Celery 비동기 태스크 정의 (1000+ lines)
├── text_interview.py               # 텍스트 면접 모듈 (STAR 분석, 리포트)
├── hume_tts_service.py             # Hume AI TTS 서비스 (OAuth2 토큰 인증)
├── stt_engine.py                   # Deepgram STT 서비스 (Nova-3 모델)
├── resume_rag.py                   # 이력서 RAG (PostgreSQL + PGVector)
├── code_execution_service.py       # 코딩 테스트 서비스 (샌드박스 실행, AI 분석)
├── whiteboard_service.py           # 화이트보드 다이어그램 분석 (Claude Vision)
├── did_avatar_service.py           # D-ID AI 아바타 영상 생성 (WebRTC 스트리밍)
├── video_interview_server.py       # 화상 면접 서버 (레거시)
├── start_interview.bat             # 원클릭 시작 스크립트 (Windows Batch)
├── start_all.ps1                   # 원클릭 시작 스크립트 (PowerShell)
├── start_prerequisites.bat         # 사전 서비스 실행 스크립트
├── requirements_integrated.txt     # 의존성 패키지
├── uploads/                        # 이력서 업로드 디렉토리
└── static/
    ├── integrated_interview.html   # 통합 화상 면접 UI
    ├── video.html                  # 기존 화상 면접 UI
    └── dashboard.html              # 감정 대시보드
```

---

## 🔧 핵심 기능

### 1. LLM 기반 답변 평가 시스템

LLM은 **질문 생성이 아닌 답변 평가**에 사용됩니다. Ollama의 Llama3 모델을 활용하여 지원자 답변을 5가지 기준으로 평가합니다.

| 평가 항목 | 설명 | 점수 |
|-----------|------|------|
| 구체성 (Specificity) | 구체적인 사례와 수치 포함 여부 | 1-5점 |
| 논리성 (Logic) | 논리적 흐름의 일관성 | 1-5점 |
| 기술 이해도 (Technical) | 기술적 개념 이해 정확성 | 1-5점 |
| STAR 기법 (STAR) | 상황-과제-행동-결과 구조 | 1-5점 |
| 전달력 (Communication) | 명확하고 이해하기 쉬운 답변 | 1-5점 |

**총점: 25점 만점**

### 2. 질문 은행 시스템

체계적인 카테고리별 질문 순서 (9개 카테고리):

```python
INTERVIEW_FLOW = [
    "intro",           # 자기소개
    "motivation",      # 지원 동기
    "strength",        # 강점
    "project",         # 프로젝트 경험
    "teamwork",        # 팀워크
    "technical",       # 기술 스택
    "problem_solving", # 문제 해결
    "growth",          # 성장 목표
    "closing"          # 마무리
]
```

각 카테고리별로 다양한 질문이 준비되어 있으며, 순차적으로 진행됩니다.

### 3. 이력서 RAG 시스템

- **PDF 업로드**: 면접 시작 전 이력서 업로드
- **세션별 인덱싱**: `resume_{session_id}` 컬렉션으로 독립 관리
- **맞춤 평가**: 이력서 내용을 참조하여 답변 평가 시 컨텍스트 제공
- **벡터 검색**: PostgreSQL + PGVector를 활용한 유사도 검색

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
- **한국어 띄어쓰기 보정**: pykospacing 연동 (선택사항)

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

**주기적 작업 (Celery Beat):**
- `cleanup_sessions_task`: 5분마다 만료 세션 정리
- `aggregate_statistics_task`: 1시간마다 통계 집계

### 8. 회원가입 및 소셜 로그인

- **이메일 회원가입**: 이메일, 비밀번호, 이름, 생년월일, 주소, 성별
- **소셜 로그인 지원**:
  - 카카오 로그인
  - 구글 로그인
  - 네이버 로그인
- **세션 관리**: localStorage 기반 클라이언트 세션

### 9. 종합 리포트 생성

면접 종료 후 다음 항목이 포함된 상세 리포트를 생성합니다:

- **STAR 분석**: 상황/과제/행동/결과 요소 점수 (각 25점, 총 100점)
- **평가 점수 집계**: 5가지 평가 항목 평균
- **키워드 분석**: 기술 키워드 + 일반 키워드 추출
- **강점/개선점**: 빈도 기반 Top 5 추출
- **등급 산정**: S/A/B/C/D (종합 점수 기반)
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
| **Claude Vision API** | Claude 3.5 Sonnet을 사용한 다이어그램 인식 |
| **아키텍처 평가** | 구조, 확장성, 보안, 데이터 흐름 분석 |
| **AI 동적 문제 생성** | 카테고리별 맞춤 아키텍처 문제 생성 |
| **컴포넌트 분석** | 각 구성요소의 역할 및 연결 관계 평가 |
| **피드백 제공** | 강점, 약점, 개선 제안 자동 생성 |

### 12. D-ID AI 아바타 (did_avatar_service.py)

D-ID API를 활용한 실시간 AI 면접관 영상 생성 서비스입니다.

| 기능 | 설명 |
|------|------|
| **Talks API** | 텍스트 → 말하는 아바타 영상 생성 (10-30초) |
| **Streams API** | WebRTC 실시간 스트리밍 (1-3초 지연) |
| **한국어 TTS** | Microsoft TTS (ko-KR-SunHiNeural, ko-KR-InJoonNeural) |
| **커스텀 아바타** | 사용자 정의 프레젠터 이미지 지원 |

---

## 📡 API 엔드포인트

### 세션 관리
- `POST /api/session` - 새 면접 세션 생성
- `GET /api/session/{session_id}` - 세션 정보 조회

### 채팅
- `POST /api/chat` - 메시지 전송 및 다음 질문 받기

### 이력서 업로드
- `POST /api/resume/upload` - PDF 이력서 업로드 및 RAG 인덱싱
- `GET /api/resume/status/{session_id}` - 업로드 상태 확인
- `DELETE /api/resume/{session_id}` - 이력서 삭제

### LLM 평가
- `POST /api/evaluate` - 개별 답변 평가 (5가지 항목)
- `GET /api/evaluations/{session_id}` - 전체 평가 결과 조회

### 리포트
- `GET /api/report/{session_id}` - 종합 면접 리포트 (LLM 평가 포함)

### WebRTC
- `POST /offer` - WebRTC offer 처리

### 감정 분석
- `GET /emotion` - 현재 감정 상태
- `GET /emotion/sessions` - 세션 목록
- `GET /emotion/timeseries` - 시계열 데이터
- `GET /emotion/stats` - 통계

### TTS
- `GET /tts/status` - TTS 서비스 상태

### 회원 인증
- `POST /api/auth/register` - 회원가입
- `POST /api/auth/login` - 로그인
- `GET /api/auth/social/{provider}` - 소셜 로그인 (kakao/google/naver)
- `GET /api/auth/social/{provider}/callback` - 소셜 로그인 콜백
- `GET /api/auth/social/verify` - 소셜 로그인 토큰 검증
- `GET /api/auth/social/status` - 소셜 로그인 설정 상태

### Celery 비동기 작업
- `POST /api/async/evaluate` - 비동기 답변 평가 요청
- `GET /api/async/result/{task_id}` - 비동기 작업 결과 조회
- `GET /api/celery/status` - Celery 연결 상태 확인

### 시스템
- `GET /api/status` - 전체 서비스 상태 확인

### 코딩 테스트
- `POST /api/coding/execute` - 코드 실행 (샌드박스)
- `POST /api/coding/analyze` - AI 코드 분석
- `GET /api/coding/problems` - 코딩 문제 목록
- `GET /api/coding/problems/{problem_id}` - 문제 상세 조회

### 화이트보드 (시스템 설계)
- `POST /api/whiteboard/analyze` - 다이어그램 분석
- `GET /api/whiteboard/problems` - 아키텍처 문제 목록
- `POST /api/whiteboard/generate-problem` - AI 문제 동적 생성

### D-ID 아바타
- `POST /api/avatar/stream/create` - 스트림 세션 생성
- `POST /api/avatar/stream/{stream_id}/speak` - 텍스트로 아바타 말하기
- `DELETE /api/avatar/stream/{stream_id}` - 스트림 종료

---

## � UI 구성

### 평가 패널 (실시간)

화면 우측에 평가 패널이 표시됩니다:

```
┌─────────────────────────────────────┐
│     📊 LLM 답변 평가                │
├─────────────────────────────────────┤
│  구체성    ████████░░ 4/5           │
│  논리성    ██████████ 5/5           │
│  기술이해  ██████░░░░ 3/5           │
│  STAR기법  ████████░░ 4/5           │
│  전달력    ██████████ 5/5           │
├─────────────────────────────────────┤
│  총점: 21/25 (84%)                  │
├─────────────────────────────────────┤
│  💬 피드백                          │
│  "구체적인 프로젝트 사례를 잘..."     │
└─────────────────────────────────────┘
```

### 면접 화면 구성

```
┌───────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐ │
│  │                             │  │   📊 LLM 답변 평가          │ │
│  │        📹 비디오            │  │   ─────────────────────     │ │
│  │        미리보기             │  │   구체성  ████████░░ 4     │ │
│  │                             │  │   논리성  ██████████ 5     │ │
│  │                             │  │   기술    ██████░░░░ 3     │ │
│  └─────────────────────────────┘  │   ...                       │ │
│                                    │                             │ │
│  ┌─────────────────────────────┐  │   😊 감정 분석              │ │
│  │  💬 채팅 영역               │  │   행복 60% 중립 30%        │ │
│  │  AI: 자기소개 해주세요      │  │                             │ │
│  │  나: 안녕하세요, 저는...    │  └─────────────────────────────┘ │
│  │  평가: 구체성 4점...        │                                  │
│  └─────────────────────────────┘                                  │
│                                                                    │
│  [메시지 입력...]                              [전송] [리포트]    │
└───────────────────────────────────────────────────────────────────┘
```

---

## 🔌 서비스 활성화 조건

| 서비스 | 필수 조건 | 역할 |
|--------|----------|------|
| LLM | Ollama 실행 + llama3 모델 | **답변 평가** (질문 생성 X) |
| TTS | HUME_API_KEY + HUME_SECRET_KEY 설정 | 음성 출력 |
| STT | DEEPGRAM_API_KEY 설정 + pyaudio | 음성 인식 |
| RAG | POSTGRES_CONNECTION_STRING 설정 + pgvector | 이력서 맞춤 평가 |
| 감정분석 | deepface + opencv-python 패키지 설치 | 감정 데이터 분석 |
| Redis | Redis 서버 실행 + REDIS_URL 설정 | 감정 시계열 저장 + Celery 브로커 |
| Celery | Redis + celery_app.py 실행 | 비동기 작업 처리 |
| 소셜 로그인 | KAKAO/GOOGLE/NAVER Client ID/Secret | OAuth 인증 |
| 코딩 테스트 | Python 3.8+ (기본), Node.js, JDK (선택) | 코드 실행 |
| 화이트보드 | ANTHROPIC_API_KEY 설정 (Claude) | 다이어그램 분석 |
| AI 아바타 | DID_API_KEY 설정 | 실시간 아바타 영상 |

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
curl http://localhost:11434/api/generate -d '{"model":"llama3","prompt":"hello"}'

# 모델 다운로드 확인
ollama list
ollama pull llama3
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
| `integrated_interview_server.py` | **통합 FastAPI 서버** (4700+ lines) - 질문 은행, LLM 평가, 회원 인증, 소셜 로그인, WebRTC, 감정 분석, ThreadPoolExecutor 비동기 처리 |
| `celery_app.py` | **Celery 애플리케이션 설정** - Redis 브로커, 7개 큐 라우팅, Beat 스케줄 정의 |
| `celery_tasks.py` | **Celery 비동기 태스크** (1000+ lines) - LLM 평가, 감정 분석, 리포트 생성, TTS, RAG, 워크플로우 처리 |
| `text_interview.py` | **텍스트 면접 모듈** - STAR 기법 분석, 키워드 추출, 리포트 생성 클래스 |
| `hume_tts_service.py` | **Hume AI TTS 클라이언트** (440+ lines) - OAuth2 토큰 인증, EVI 음성 생성, 스트리밍 지원 |
| `stt_engine.py` | **Deepgram STT 클라이언트** - Nova-3 모델, 실시간 마이크 입력, VAD 지원 |
| `resume_rag.py` | **이력서 RAG 모듈** - PDF 로딩, 청킹, PGVector 벡터 저장, 유사도 검색 |
| `code_execution_service.py` | **코딩 테스트 서비스** (1100+ lines) - 샌드박스 코드 실행, AI 코드 분석, 문제 은행 |
| `whiteboard_service.py` | **화이트보드 분석 서비스** (750+ lines) - Claude Vision API, 아키텍처 평가, 동적 문제 생성 |
| `did_avatar_service.py` | **D-ID 아바타 서비스** (520+ lines) - WebRTC 스트리밍, 실시간 아바타 영상 생성 |
| `video_interview_server.py` | WebRTC + 감정 분석 서버 (레거시, integrated에 통합됨) |
| `start_interview.bat` | **원클릭 시작 스크립트** (Windows Batch) - 전체 시스템 실행 |
| `start_all.ps1` | **원클릭 시작 스크립트** (PowerShell) - 컬러 출력, 상세 로그 |
| `start_prerequisites.bat` | **사전 서비스 스크립트** - Redis, Ollama만 실행 |
| `requirements_integrated.txt` | 통합 의존성 목록 (FastAPI, LangChain, Celery, DeepFace, anthropic 등) |
| `__init__.py` | 패키지 초기화 파일 |
| `static/integrated_interview.html` | **통합 화상 면접 UI** - 실시간 평가 패널, 감정 분석 포함 |
| `static/dashboard.html` | 감정 분석 대시보드 - 시계열 차트, 통계 시각화 |
| `static/video.html` | 기존 화상 면접 UI (레거시) |
| `uploads/` | 이력서 PDF 업로드 디렉토리 |

---

## 📝 변경 이력

### v3.1 (2026-02-05)
- ✅ **코딩 테스트 시스템 추가** (`code_execution_service.py`)
  - Python, JavaScript, Java, C, C++ 다국어 지원
  - 샌드박스 환경에서 안전한 코드 실행 (subprocess + 타임아웃)
  - AI 기반 코드 품질 분석 (시간/공간 복잡도, 코드 스타일)
  - 코딩 문제 은행 (난이도별 알고리즘 문제)
- ✅ **화이트보드 다이어그램 분석 추가** (`whiteboard_service.py`)
  - Claude 3.5 Sonnet Vision API 연동
  - 시스템 아키텍처 평가 (구조, 확장성, 보안, 데이터 흐름)
  - AI 동적 문제 생성 (카테고리별 맞춤 아키텍처 문제)
  - 컴포넌트 분석 및 피드백 자동 생성
- ✅ **D-ID AI 아바타 서비스 추가** (`did_avatar_service.py`)
  - Talks API: 텍스트 → 아바타 영상 생성
  - Streams API: WebRTC 실시간 스트리밍 (1-3초 지연)
  - 한국어 TTS 지원 (Microsoft Neural Voice)
- ✅ **원클릭 시작 스크립트 추가**
  - `start_interview.bat`: Windows Batch 스크립트
  - `start_all.ps1`: PowerShell 스크립트 (컬러 출력)
  - `start_prerequisites.bat`: 사전 서비스(Redis, Ollama) 실행
- ✅ **비동기 처리 최적화**
  - ThreadPoolExecutor로 LLM, RAG, DeepFace 비블로킹 처리
  - `run_llm_async()`, `run_rag_async()`, `run_deepface_async()` 헬퍼 함수
- ✅ **Celery 큐 확장**
  - 7개 전용 큐: llm_evaluation, emotion_analysis, report_generation, tts_generation, rag_processing, question_generation, default

### v3.0 (2026-02-04)
- ✅ **Celery 비동기 작업 처리 시스템 추가**
  - 6개 전용 큐 (llm_evaluation, emotion_analysis, report_generation, tts_generation, rag_processing, default)
  - 태스크별 타임아웃 및 재시도 설정
  - Beat 스케줄러로 주기적 작업 (세션 정리, 통계 집계)
  - 복합 워크플로우 태스크 (면접 완료 후 전체 처리)
- ✅ **회원가입/로그인 시스템 추가**
  - 이메일 기반 회원가입 (이메일, 비밀번호, 이름, 생년월일, 주소, 성별)
  - 비밀번호 유효성 검증 (8자 이상)
- ✅ **소셜 로그인 지원**
  - 카카오 로그인
  - 구글 로그인
  - 네이버 로그인
  - OAuth2 콜백 처리 및 토큰 검증
- ✅ **Hume TTS 개선**
  - OAuth2 토큰 인증 방식 추가 (API Key + Secret Key)
  - 토큰 캐싱 및 자동 갱신
- ✅ **리포트 시스템 강화**
  - 등급 산정 (S/A/B/C/D)
  - 맞춤형 권장사항 생성
  - 강점/개선점 빈도 분석

### v2.0 (2025-01-XX)
- ✅ 채팅 면접 제거, 화상 면접으로 통합
- ✅ LLM 역할 변경: 질문 생성 → **답변 평가**
- ✅ 질문 은행 시스템 도입 (9개 카테고리)
- ✅ 5가지 평가 항목 실시간 표시
- ✅ 이력서 PDF 업로드 + RAG 연동
- ✅ 종합 리포트에 LLM 평가 결과 포함
- ✅ 홈페이지 UI 개선

### v1.0
- 초기 통합 버전 (TTS, STT, LLM, 화상면접, 감정분석)

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
- [core_architecture.md](../docs/Architecture_Diagram/core_architecture.md) - 시스템 아키텍처

---

## 🤝 기여 방법

1. 이 저장소를 Fork합니다.
2. 새 브랜치를 생성합니다: `git checkout -b feature/my-feature`
3. 변경사항을 커밋합니다: `git commit -m 'Add my feature'`
4. 브랜치에 Push합니다: `git push origin feature/my-feature`
5. Pull Request를 생성합니다.

---

## 📄 라이선스

이 프로젝트는 교육 목적으로 개발되었습니다.
