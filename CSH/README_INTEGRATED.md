# AI 모의면접 통합 시스템 - CSH 모듈

## 📋 개요

TTS, STT, LLM, 화상 면접, 감정 분석을 통합한 AI 모의면접 시스템입니다.

## 🚀 빠른 시작

### 1. 필수 패키지 설치

```bash
pip install -r requirements_integrated.txt
```

### 2. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 값들을 설정하세요:

```env
# LLM 설정 (Ollama)
LLM_MODEL=llama3
LLM_TEMPERATURE=0.7

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
# Ollama 실행 (LLM)
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
- 메인 페이지: http://localhost:8000
- 통합 화상 면접: http://localhost:8000/static/integrated_interview.html
- 웹 채팅 면접: http://localhost:8000/interview
- 감정 대시보드: http://localhost:8000/static/dashboard.html
- API 문서: http://localhost:8000/docs

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
└── static/
    ├── integrated_interview.html  # 통합 면접 UI
    ├── video.html                 # 화상 면접 UI
    └── dashboard.html             # 감정 대시보드
```

---

## 🔧 통합된 기능

### 1. LLM 기반 면접관 (Ollama/Llama3)
- STAR 기법 기반 질문 생성
- 맥락 인식 꼬리 질문
- RAG를 통한 이력서 기반 질문

### 2. TTS 서비스 (Hume AI)
- 자연스러운 감정적 음성 생성
- 한국어 지원
- REST API 및 스트리밍 지원

### 3. STT 서비스 (Deepgram)
- 실시간 음성 인식
- 한국어 지원 (Nova-3 모델)
- WebSocket 기반 스트리밍

### 4. 화상 면접 + 감정 분석
- WebRTC 기반 실시간 영상 통화
- DeepFace 기반 7가지 감정 분석
- Redis 시계열 데이터 저장

### 5. 이력서 RAG (PostgreSQL + PGVector)
- PDF 이력서 자동 인덱싱
- 벡터 유사도 검색
- 맥락 기반 질문 생성

### 6. 면접 리포트
- STAR 기법 분석
- 키워드 추출
- 감정 통계 포함
- AI 기반 종합 평가

---

## 📡 API 엔드포인트

### 세션 관리
- `POST /api/session` - 새 면접 세션 생성
- `GET /api/session/{session_id}` - 세션 정보 조회

### 채팅
- `POST /api/chat` - 메시지 전송 및 AI 응답 받기

### 리포트
- `GET /api/report/{session_id}` - 면접 리포트 생성

### WebRTC
- `POST /offer` - WebRTC offer 처리

### 감정 분석
- `GET /emotion` - 현재 감정 상태
- `GET /emotion/sessions` - 세션 목록
- `GET /emotion/timeseries` - 시계열 데이터
- `GET /emotion/stats` - 통계

### TTS
- `POST /tts/speak` - 텍스트를 음성으로 변환
- `GET /tts/status` - TTS 서비스 상태

### 시스템
- `GET /api/status` - 서비스 상태 확인

---

## 🔌 서비스 활성화 조건

| 서비스 | 필수 조건 |
|--------|-----------|
| LLM | Ollama 실행 + llama3 모델 |
| TTS | HUME_API_KEY 설정 |
| RAG | POSTGRES_CONNECTION_STRING 설정 + pgvector |
| 감정분석 | deepface 패키지 설치 |
| Redis | Redis 서버 실행 |

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

## 📚 참고 문서

- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Ollama 문서](https://ollama.ai/)
- [Hume AI 문서](https://docs.hume.ai/)
- [Deepgram 문서](https://developers.deepgram.com/)
- [DeepFace 문서](https://github.com/serengil/deepface)
