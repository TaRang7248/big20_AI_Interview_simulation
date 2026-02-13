# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 시뮬레이션 개요
본 시뮬레이션은 사용자가 실제 면접처럼 음성으로 질문에 답변하고, AI 면접관이 이를 평가하여 꼬리 질문을 이어가는 웹 기반 인터뷰 연습 플랫폼입니다.
OpenAI GPT-4o와 Whisper, TTS 기술을 활용하여 실시간 상호작용이 가능합니다.

## 2. 시뮬레이션 환경
- **OS**: Windows (권장)
- **Language**: Python 3.9+
- **Frontend**: HTML5, CSS (Vanilla), JavaScript
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (Docker 또는 로컬 설치)

## 3. 시뮬레이션 실행 방법

### 사전 준비
1. `requirements.txt` 패키지 설치:
   ```bash
   pip install -r requirements.txt
   ```
2. PostgreSQL 데이터베이스 실행 및 연결 설정 (`app/config.py` 또는 환경 변수 확인)
3. OpenAI API Key 설정 (`.env` 파일 또는 환경변수)

### 서버 실행
```bash
python server.py
```
- 실행 시 자동으로 브라우저가 열리며 `http://localhost:5000`으로 접속됩니다.
- 포트 5000번이 사용 중인 경우 `server.py`에서 포트를 변경하세요.

## 4. 사용되는 모델 및 라이브러리 목록

### AI Models (API)
- **LLM (Large Language Model)**: OpenAI `gpt-4o` (질문 생성, 답변 평가, 이력서 요약)
- **STT (Speech-to-Text)**: OpenAI `whisper-1` (사용자 음성 답변 -> 텍스트 변환)
- **TTS (Text-to-Speech)**: OpenAI `tts-1` (AI 면접관 음성 생성)

### Key Libraries
- **FastAPI**: 웹 서버 프레임워크
- **Uvicorn**: ASGI 서버
- **Psycopg2**: PostgreSQL 데이터베이스 어댑터
- **Pydantic**: 데이터 검증
- **OpenAI**: AI API 클라이언트

## 5. 주요 기능 사용법

### 1) 이력서 등록
- 메인 화면에서 이름(ID)과 직무를 입력하고 PDF 형식의 이력서를 업로드합니다.
- 업로드된 이력서는 텍스트로 추출되어 면접 질문 생성에 활용됩니다.

### 2) 면접 시작
- 이력서 등록 후 [면접 시작] 버튼을 누르면 AI 면접관이 자기소개를 요청합니다.
- 브라우저의 마이크 권한을 허용해야 합니다.

### 3) 답변 녹음 및 제출
- 질문을 듣고 [답변 시작] 버튼을 눌러 녹음을 시작합니다.
- 답변이 끝나면 [답변 종료] 버튼을 누르면 자동으로 서버로 전송됩니다.
- AI가 답변을 분석하고 꼬리 질문을 생성하여 다음 단계로 넘어갑니다.

### 4) 면접 결과 확인
- 총 10~12개의 질문이 끝나면 면접이 종료됩니다.
- [결과 보기] 페이지에서 각 질문에 대한 평가, 피드백, 합격/불합격 여부를 확인할 수 있습니다.

## 6. 파일 구조 설명

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── app/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── config.py            # 설정 파일 (DB, API Key 등)
│   ├── database.py          # DB 연결 관리
│   ├── models.py            # Pydantic 모델 정의
│   ├── routers/             # API 라우터
│   │   └── interview.py     # 면접 관련 API (핵심 로직)
│   └── services/            # 비즈니스 로직
│       ├── llm_service.py   # OpenAI 연동 (질문 생성, 평가)
│       ├── stt_service.py   # 음성 인식
│       ├── tts_service.py   # 음성 합성
│       └── pdf_service.py   # PDF 텍스트 추출
├── static/                  # 프론트엔드 정적 파일 (HTML, CSS, JS)
├── uploads/                 # 업로드된 이력서 저장소
├── server.py                # 실행 스크립트
├── requirements.txt         # 의존성 목록
└── GUIDEBOOK.md             # 본 가이드 문서
```

## 7. 최신 업데이트 사항 (v1.1)
- **중복 질문 방지 기능**: 같은 면접 세션 내에서 AI가 동일하거나 유사한 질문을 반복하지 않도록 개선되었습니다.
