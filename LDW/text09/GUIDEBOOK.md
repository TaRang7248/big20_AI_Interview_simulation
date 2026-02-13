# AI 면접 시뮬레이션 가이드북 (Guidebook)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션** 서비스입니다. 사용자는 실제 면접과 유사한 환경에서 AI 면접관과 음성으로 대화하며 면접 연습을 할 수 있습니다. 
면접이 종료되면 AI가 답변 내용을 분석하여 기술(Tech), 문제해결(Problem Solving), 의사소통(Communication), 태도(Non-verbal) 4가지 항목에 대해 평가하고 피드백을 제공합니다. 관리자는 채용 공고를 등록하고 지원자들의 면접 결과를 조회할 수 있습니다.

## 2. 시스템 환경 (Environment)
*   **OS**: Windows (권장), macOS, Linux
*   **Language**: Python 3.9+, JavaScript (ES6+)
*   **Database**: PostgreSQL
*   **Backend Framework**: FastAPI (Python)
*   **Frontend**: HTML5, CSS3, Vanilla JavaScript

## 3. 실행 방법 (How to Run)

### 사전 준비
1.  **PostgreSQL 설치 및 실행**: 로컬에서 PostgreSQL 서버가 실행 중이어야 합니다.
2.  **데이터베이스 생성**: `interview_db` 데이터베이스가 생성되어 있어야 합니다. (초기 실행 시 `scripts/create_table.py`로 생성 가능)
3.  **환경 변수 설정**: `.env` 파일에 DB 접속 정보와 OpenAI API Key가 설정되어야 합니다.

### 서버 실행
터미널에서 `server.py`가 있는 디렉토리(`LDW/text09`)로 이동 후 다음 명령어를 실행합니다.

```bash
python server.py
```

*   서버가 시작되면 자동으로 브라우저가 열리며 `http://localhost:5000`으로 접속됩니다.
*   수동으로 접속하려면 브라우저 주소창에 `http://localhost:5000`을 입력하세요.

## 4. 사용 모델 및 라이브러리 (Models & Libraries)

### 주요 AI 모델
*   **LLM (Large Language Model)**: OpenAI GPT-4o (면접 질문 생성, 답변 평가, 이력서 요약)
*   **STT (Speech-to-Text)**: OpenAI Whisper (음성 답변을 텍스트로 변환, 클라이언트 측 Web Speech API도 보조적으로 사용)
*   **TTS (Text-to-Speech)**: OpenAI TTS (AI 면접관의 음성 생성)
*   **OCR**: EasyOCR (PDF 이력서 텍스트 추출 보조)

### 주요 라이브러리 (Python)
*   `fastapi`: 웹 서버 프레임워크
*   `uvicorn`: ASGI 서버
*   `psycopg2-binary`: PostgreSQL 데이터베이스 연동
*   `openai`: OpenAI API 클라이언트
*   `python-multipart`: 파일 업로드 처리
*   `pydantic`: 데이터 검증
*   `pdf2image`: PDF를 이미지로 변환 (이력서 이미지화)
*   `pytesseract` / `easyocr`: 이미지 내 텍스트 추출

## 5. 주요 기능 사용법 (Key Features)

### [지원자]
1.  **회원가입/로그인**: '면접자' 유형으로 가입합니다.
2.  **공고 조회**: 대시보드에서 지원 가능한 채용 공고를 확인합니다.
3.  **면접 시작**: 공고의 [지원하기] 버튼을 누르고 이력서(PDF)를 업로드합니다.
4.  **카메라/마이크 설정**: 웹캠과 마이크 권한을 허용하고 테스트를 통과해야 합니다.
5.  **실전 면접**:
    *   AI 면접관이 질문을 하면 답변을 말합니다.
    *   답변이 끝나면 [답변 제출] 버튼을 누르거나 시간이 종료되면 자동 제출됩니다.
    *   자기소개, 직무 기술, 인성 질문 등 총 12개의 질문이 이어집니다.
6.  **결과 확인**: 면접 종료 후 [내 면접 기록]에서 합격/불합격 여부와 상세 평가(점수, 피드백)를 확인할 수 있습니다.

### [관리자]
1.  **회원가입/로그인**: '관리자' 유형으로 가입합니다.
2.  **공고 관리**: 새로운 채용 공고를 등록, 수정, 삭제할 수 있습니다.
3.  **지원자 현황**: 본인이 등록한 공고에 지원한 지원자 목록을 확인하고, 각 지원자의 이력서, 면접 답변 내용, AI 평가 결과를 상세하게 조회할 수 있습니다.

## 6. 파일 구조 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── app/
│   ├── routers/       # API 라우터 (admin, auth, interview, job, user)
│   ├── services/      # 비즈니스 로직 (LLM, PDF, STT, TTS 등)
│   ├── models.py      # Pydantic 데이터 모델
│   ├── database.py    # DB 연결 설정
│   ├── config.py      # 환경 변수 및 설정
│   └── main.py        # FastAPI 앱 초기화 및 라우터 등록
├── static/            # 프론트엔드 정적 파일
│   ├── index.html     # 메인 HTML (SPA 구조)
│   ├── app.js         # 프론트엔드 로직 (라우팅, API 호출, 상태 관리)
│   └── styles.css     # 스타일시트
├── scripts/           # DB 마이그레이션 및 유틸리티 스크립트
├── uploads/           # 업로드된 파일 저장소 (이력서, 오디오 등)
├── server.py          # 서버 실행 진입점
└── requirements.txt   # 의존성 패키지 목록
```
