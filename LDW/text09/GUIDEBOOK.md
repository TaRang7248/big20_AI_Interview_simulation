# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션** 프로그램입니다. 지원자가 이력서를 업로드하고, AI 면접관과 실제 면접처럼 대화(음성/텍스트)를 주고받으며 면접 연습을 할 수 있습니다. GPT-4o를 활용하여 맞춤형 질문을 생성하고, Whisper 모델을 통해 음성을 텍스트로 변환합니다.

## 2. 환경 (Environment Setup)
### 필수 요구 사항
- **OS:** Windows / Mac / Linux
- **Python:** 3.10 이상
- **PostgreSQL:** 14 이상
- **Browser:** Chrome, Edge 등 최신 브라우저

### 환경 변수 (.env)
프로젝트 루트 디렉토리에 `.env` 파일이 필요합니다.
```ini
DB_HOST=localhost
DB_NAME=interview_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432
OPENAI_API_KEY=sk-proj-...
```

## 3. 프로그램 실행 방법 (How to Run)
1. **가상 환경 활성화 (선택 사항)**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **라이브러리 설치**
   ```bash
   pip install -r requirements.txt
   ```
   *(없을 경우 아래 `사용 라이브러리` 참고하여 설치)*

3. **서버 실행**
   `server.py`가 있는 디렉토리에서 아래 명령어를 실행합니다.
   ```bash
   python server.py
   ```
   - 서버가 시작되면 자동으로 웹 브라우저(`http://localhost:5000`)가 실행됩니다.

## 4. 사용 라이브러리 (Libraries)
- **Backend:** `fastapi`, `uvicorn`, `psycopg2`, `python-dotenv`
- **AI/ML:** `openai` (GPT-4o, Whisper)
- **Utils:** `pypdf` (PDF 파싱), `pydantic` (데이터 검증)

## 5. 주요 기능 사용법 (Usage)

### 5.1 회원가입 및 로그인
- `회원가입` 페이지에서 계정을 생성합니다.
- `로그인` 후 서비스를 이용할 수 있습니다.

### 5.2 면접 공고 확인 및 지원
- **지원자 대시보드**에서 등록된 채용 공고를 확인할 수 있습니다.
- 공고를 클릭하여 상세 내용을 보고 `지원하기` 버튼을 누릅니다.

### 5.3 면접 진행
1. **이력서 업로드:** PDF 형식의 이력서를 업로드합니다.
2. **환경 테스트:** 카메라와 마이크가 자동으로 연결되는지 확인합니다.
3. **면접 시작:**
   - **Q1:** 자기소개 (고정 질문)
   - **Q2 ~ Q6:** 직무 기술 관련 질문
   - **Q7 ~ Q11:** 인성 및 가치관 관련 질문
   - **Q12:** 마무리 답변
4. **답변 방식:** 마이크를 통해 음성으로 답변하고, `답변 제출` 버튼을 누르면 녹음이 종료되고 다음 질문으로 넘어갑니다.

### 5.4 관리자 기능
- `admin` 계정으로 로그인하면 공고를 등록/수정/삭제할 수 있습니다.
- 지원자들의 면접 기록(질문/답변/평가)을 조회할 수 있습니다.

## 6. 파일 구조 설명 (File Structure)
```
/
├── server.py              # 메인 백엔드 서버 (FastAPI)
├── app.js                 # 프론트엔드 로직 (API 호출, UI 제어)
├── index.html             # 메인 웹 페이지
├── styles.css             # 스타일 시트
├── create_table.py        # 데이터베이스 테이블 생성 스크립트
├── requirements.txt       # 의존성 패키지 목록
└── uploads/               # 업로드된 이력서 및 오디오 파일 저장소
```
