# AI 모의면접 통합 시스템 - CSH 모듈

## 📋 개요

TTS, STT, LLM 기반 답변 평가, 화상 면접, 감정 분석을 통합한 AI 모의면접 시스템입니다.

### ✨ 주요 특징

- **화상 면접 중심**: 채팅 면접과 화상 면접을 하나로 통합
- **LLM 답변 평가**: 질문 생성이 아닌 **답변 분석/평가**에 LLM 활용
- **질문 은행 시스템**: 체계적인 카테고리별 질문 순서
- **이력서 RAG**: PDF 이력서 업로드 → 맞춤형 면접
- **실시간 평가 시각화**: 5가지 평가 항목 실시간 점수 표시

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

# Redis (선택사항)
REDIS_URL=redis://localhost:6379/0
```

### 3. 외부 서비스 실행

```bash
# Ollama 실행 (LLM - 답변 평가용)
ollama serve
ollama pull llama3

# Redis 실행 (감정 데이터 저장)
docker run -d -p 6379:6379 redis:alpine

# PostgreSQL + pgvector 실행 (RAG)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password pgvector/pgvector:pg16
```

### 4. 통합 서버 실행

```bash
cd CSH
python integrated_interview_server.py

# 또는 uvicorn으로 실행
uvicorn integrated_interview_server:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 접속

브라우저에서 다음 URL로 접속:
- **메인 페이지**: http://localhost:8000
- **화상 면접**: http://localhost:8000/static/integrated_interview.html
- 감정 대시보드: http://localhost:8000/static/dashboard.html
- API 문서: http://localhost:8000/docs

---

## 🎯 면접 흐름

```
┌─────────────────────────────────────────────────────────────┐
│  1. 홈페이지 (/)                                             │
│     └─ "AI 화상 면접 시작하기" 클릭                           │
├─────────────────────────────────────────────────────────────┤
│  2. 이력서 업로드 모달                                        │
│     ├─ PDF 이력서 업로드 (선택)                               │
│     │   └─ RAG 인덱싱 → 세션별 retriever 생성                │
│     └─ 또는 "건너뛰기"                                       │
├─────────────────────────────────────────────────────────────┤
│  3. 화상 면접 시작                                           │
│     ├─ WebRTC 카메라/마이크 연결                              │
│     ├─ 질문 은행 기반 순차 질문                               │
│     │   (intro → motivation → strength → project → ...)     │
│     ├─ 답변 입력 → 백그라운드 LLM 평가                        │
│     ├─ 실시간 평가 점수 표시 (5가지 항목)                     │
│     ├─ 실시간 감정 분석 (7가지 감정)                          │
│     └─ TTS 음성 출력                                         │
├─────────────────────────────────────────────────────────────┤
│  4. 면접 종료 → 리포트 생성                                   │
│     ├─ LLM 평가 종합 결과                                    │
│     ├─ STAR 기법 분석                                        │
│     ├─ 키워드 분석                                           │
│     └─ 개선 피드백                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 시스템 구조

```
CSH/
├── integrated_interview_server.py  # 통합 서버 (메인)
├── text_interview.py               # 텍스트 면접 모듈
├── hume_tts_service.py            # TTS 서비스
├── stt_engine.py                  # STT 서비스
├── resume_rag.py                  # 이력서 RAG
├── video_interview_server.py      # 화상 면접 서버
├── requirements_integrated.txt    # 의존성 패키지
├── uploads/                       # 이력서 업로드 디렉토리
└── static/
    ├── integrated_interview.html  # 통합 화상 면접 UI
    ├── video.html                 # 기존 화상 면접 UI
    └── dashboard.html             # 감정 대시보드
```

---

## 🔧 핵심 기능

### 1. LLM 기반 답변 평가 시스템

LLM은 **질문 생성이 아닌 답변 평가**에 사용됩니다.

| 평가 항목 | 설명 | 점수 |
|-----------|------|------|
| 구체성 (Specificity) | 구체적인 사례와 수치 포함 여부 | 1-5점 |
| 논리성 (Logic) | 논리적 흐름의 일관성 | 1-5점 |
| 기술 이해도 (Technical) | 기술적 개념 이해 정확성 | 1-5점 |
| STAR 기법 (STAR) | 상황-과제-행동-결과 구조 | 1-5점 |
| 전달력 (Communication) | 명확하고 이해하기 쉬운 답변 | 1-5점 |

**총점: 25점 만점**

### 2. 질문 은행 시스템

체계적인 카테고리별 질문 순서:

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

### 3. 이력서 RAG 시스템

- **PDF 업로드**: 면접 시작 전 이력서 업로드
- **세션별 인덱싱**: `resume_{session_id}` 컬렉션으로 독립 관리
- **맞춤 평가**: 이력서 내용을 참조하여 답변 평가

### 4. 실시간 감정 분석

- **7가지 감정**: 행복, 중립, 슬픔, 분노, 놀람, 공포, 혐오
- **DeepFace 기반**: 1초 간격 얼굴 분석
- **Redis 시계열 저장**: 면접 전체 감정 추이 기록

### 5. TTS 음성 면접관 (Hume AI)

- 자연스러운 AI 면접관 음성
- 한국어 지원
- 말하는 동안 시각적 피드백 (파형 애니메이션)

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

### 시스템
- `GET /api/status` - 서비스 상태 확인

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
| TTS | HUME_API_KEY 설정 | 음성 출력 |
| RAG | POSTGRES_CONNECTION_STRING 설정 + pgvector | 이력서 맞춤 평가 |
| 감정분석 | deepface 패키지 설치 | 감정 데이터 분석 |
| Redis | Redis 서버 실행 | 감정 시계열 저장 |

모든 서비스는 선택사항입니다. 설정되지 않은 서비스는 비활성화되며, 기본 기능으로 대체됩니다.

---

## 🐛 문제 해결

### Ollama 연결 오류
```bash
# Ollama 서비스 확인
ollama serve
curl http://localhost:11434/api/generate -d '{"model":"llama3","prompt":"hello"}'
```

### WebRTC 연결 실패
- 브라우저에서 카메라/마이크 권한 허용
- HTTPS가 아닌 경우 localhost에서만 동작

### 감정 분석 오류
```bash
# TensorFlow/DeepFace 재설치
pip install --upgrade deepface tf-keras
```

### Redis 연결 오류
```bash
# Redis 상태 확인
redis-cli ping
```

---

## � 파일 설명

| 파일 | 설명 |
|------|------|
| `integrated_interview_server.py` | 통합 FastAPI 서버 (질문 은행 + LLM 평가) |
| `text_interview.py` | 텍스트 면접 기본 모듈 |
| `hume_tts_service.py` | Hume AI TTS 클라이언트 |
| `stt_engine.py` | Deepgram STT 클라이언트 |
| `resume_rag.py` | 이력서 벡터 검색 모듈 |
| `video_interview_server.py` | WebRTC + 감정 분석 서버 |
| `requirements_integrated.txt` | 통합 의존성 목록 |
| `static/integrated_interview.html` | 통합 화상 면접 UI (평가 패널 포함) |
| `uploads/` | 이력서 업로드 디렉토리 |

---

## 📝 변경 이력

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

## 📚 참고 문서

- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Ollama 문서](https://ollama.ai/)
- [Hume AI 문서](https://docs.hume.ai/)
- [Deepgram 문서](https://developers.deepgram.com/)
- [DeepFace 문서](https://github.com/serengil/deepface)
- [core_architecture.md](../docs/Architecture_Diagram/core_architecture.md) - 시스템 아키텍처
