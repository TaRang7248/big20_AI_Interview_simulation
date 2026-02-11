# 웹 기반 AI 면접 시뮬레이션 가이드북 (GUIDEBOOK.md)

## 1. 개요 (Overview)
본 프로젝트는 웹 기반의 **AI 면접 시뮬레이션** 프로그램입니다. 사용자는 이력서를 업로드하고 AI 면접관과 음성 및 화상으로 면접을 진행할 수 있습니다. 면접 종료 후에는 AI가 답변을 분석하여 평가 결과를 제공합니다.

## 2. 환경 설정 (Environment Setup)

### 필수 요구 사항
- Python 3.8 이상
- PostgreSQL 데이터베이스
- OpenAI API Key

### 설치 라이브러리
`requirements.txt`에 명시된 라이브러리를 설치해야 합니다.
```bash
pip install -r requirements.txt
```
주요 라이브러리:
- `fastapi`, `uvicorn`: 웹 서버 프레임워크
- `psycopg2`: PostgreSQL 데이터베이스 연동
- `openai`: AI 모델 사용 (GPT-4o, Whisper)
- `pypdf`: PDF 이력서 텍스트 추출
- `python-dotenv`: 환경 변수 관리

### 환경 변수 (.env)
프로젝트 루트 경로에 `.env` 파일을 생성하고 다음 정보를 입력해야 합니다.
```env
DB_HOST=localhost
DB_NAME=interview_db
DB_USER=postgres
POSTGRES_PASSWORD=your_password
DB_PORT=5432
OPENAI_API_KEY=sk-proj-...
```

## 3. 프로그램 실행 방법 (How to Run)
터미널에서 `server.py`를 실행하면 웹 서버가 시작되고 자동으로 브라우저가 열립니다.

```bash
python server.py
```
- 서버 주소: `http://localhost:5000`

## 4. 사용 모델 및 라이브러리 (Models & Libraries)
- **OpenAI GPT-4o**: 
    - 면접 질문 생성 (직무 맞춤형 질문)
    - 답변 평가 및 피드백 생성
    - 면접 결과 종합 분석
- **OpenAI Whisper (whisper-1)**:
    - 지원자의 음성 답변을 텍스트로 변환 (STT)
- **FastAPI**: 비동기 처리를 지원하는 고성능 Python 웹 프레임워크
- **Vanilla JS**: 프론트엔드는 별도의 프레임워크 없이 순수 JavaScript로 구현되어 가볍고 빠릅니다.

## 5. 주요 기능 사용법 (Features)

### [지원자]
1.  **회원가입/로그인**: 계정을 생성하고 로그인합니다.
2.  **이력서 업로드**: 지원하려는 공고를 선택하고 이력서(PDF)를 업로드합니다.
3.  **환경 테스트**: 카메라와 마이크 작동 여부를 확인합니다.
4.  **AI 면접 진행**:
    - AI 면접관이 질문을 제시하고 음성으로 읽어줍니다 (TTS).
    - 지원자는 마이크를 통해 답변을 녹음합니다.
    - 약 5~10개의 질문이 이어지며, 꼬리 질문이나 심층 질문이 나올 수 있습니다.
5.  **결과 확인**: 면접 종료 후 AI가 분석한 평가 점수(기술, 문제해결, 의사소통, 태도)와 합격 여부를 확인합니다.
6.  **내 정보 수정**: 주소, 전화번호 등 개인정보를 수정할 수 있습니다.

### [관리자]
1.  **공고 관리**: 채용 공고를 등록, 수정, 삭제할 수 있습니다.
2.  **지원자 현황**: 지원자들의 면접 진행 상황과 결과를 조회할 수 있습니다.

## 6. 파일 구조 설명 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── server.py                # 메인 백엔드 서버 (FastAPI)
├── index.html               # 메인 프론트엔드 HTML
├── app.js                   # 프론트엔드 로직 (SPA 라우팅, API 호출, 녹음 등)
├── styles.css               # 스타일 시트
├── create_table.py          # 데이터베이스 테이블 생성 스크립트
├── requirements.txt         # 파이썬 의존성 패키지 목록
├── uploads/                 # 업로드된 파일 저장소
│   ├── resumes/             # 이력서 PDF 파일
│   └── audio/               # 면접 답변 오디오 파일
└── GUIDEBOOK.md             # 프로젝트 가이드북 (본 파일)
```

## 7. 문제 해결 (Troubleshooting)
- **DB 연결 오류**: `.env` 파일의 DB 설정이 올바른지 확인하세요. PostgreSQL 서비스가 실행 중이어야 합니다.
- **OpenAI API 오류**: API Key가 유효한지 확인하고 잔액이 충분한지 확인하세요.
- **브라우저 권한**: 카메라/마이크 권한을 허용해야 면접을 진행할 수 있습니다.
