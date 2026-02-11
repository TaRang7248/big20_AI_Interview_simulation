# AI 면접 시뮬레이션 가이드북 (Guidebook)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션** 프로그램입니다.  
사용자는 이력서를 업로드하고, AI 면접관과 음성으로 인터뷰를 진행할 수 있습니다.  
면접은 자기소개부터 시작하여 직무 적합성, 인성, 마무리 단계로 진행되며, 모든 답변은 STT(Speech-to-Text)로 변환되어 LLM(GPT-4o)에 의해 실시간으로 평가됩니다.  
면접 종료 후에는 종합적인 평가 결과(합격/불합격)를 확인할 수 있습니다.

---

## 2. 환경 설정 (Environment)

### 2.1 필수 요구 사항
- **OS**: Windows (권장)
- **Python**: 3.10 이상
- **PostgreSQL**: 데이터베이스 서버 실행 필요
- **OpenAI API Key**: `.env` 파일에 설정 필요

### 2.2 설치 방법
1. **Python 패키지 설치**:
   ```bash
   pip install -r requirements.txt
   ```
2. **.env 파일 설정**:
   프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 입력하세요.
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   DB_HOST=localhost
   DB_NAME=interview_db
   DB_USER=postgres
   POSTGRES_PASSWORD=your_password
   DB_PORT=5432
   ```

### 2.3 데이터베이스 설정
PostgreSQL이 실행 중이어야 합니다.
최초 실행 시 테이블 생성을 위해 마이그레이션 스크립트를 실행합니다.
```bash
python migrate_db_v3.py
```
(또는 `create_table.py` 등 초기 설정 스크립트 실행)

---

## 3. 프로그램 실행 방법 (Execution)

### 3.1 서버 실행
터미널에서 다음 명령어를 실행하여 FastAPI 서버를 시작합니다.
```bash
python server.py
```
- 서버가 정상적으로 실행되면 브라우저가 자동으로 열리며 `http://localhost:5000`으로 접속됩니다.
- 만약 브라우저가 열리지 않으면 주소창에 직접 입력하여 접속하세요.

---

## 4. 사용 라이브러리 (Libraries)
주요 Python 라이브러리는 다음과 같습니다.
- **FastAPI**: 웹 서버 프레임워크
- **Uvicorn**: ASGI 서버
- **Psycopg2**: PostgreSQL 데이터베이스 연동
- **OpenAI**: GPT-4o 및 Whisper API 사용
- **PyPDF**: 이력서 PDF 텍스트 추출
- **Pydantic**: 데이터 유효성 검사

주요 프론트엔드 기술:
- **Vanilla JS**: 프레임워크 없는 순수 자바스크립트 구현 (단일 페이지 애플리케이션 구조)
- **Web Speech API**: 실시간 음성 인식 보조
- **MediaRecorder API**: 음성 녹음 및 전송

---

## 5. 주요 기능 사용법 (Features)

### 5.1 회원가입 및 로그인
- 초기 접속 시 로그인 페이지가 표시됩니다.
- 회원가입을 통해 계정을 생성할 수 있습니다. (관리자/면접자 유형 선택 가능)

### 5.2 (관리자) 공고 등록
- 관리자로 로그인하면 공고 관리 페이지에 접속할 수 있습니다.
- 새로운 채용 공고를 등록하고 수정/삭제할 수 있습니다.

### 5.3 면접 진행 (지원자)
1. **공고 지원**: 대시보드에서 원하는 공고를 선택하고 '지원하기' 버튼을 누릅니다.
2. **이력서 업로드**: PDF 형식의 이력서를 업로드합니다.
3. **환경 테스트**: 카메라와 마이크 상태를 확인합니다.
4. **면접 시작**: 자기소개부터 시작하여 AI 면접관의 질문에 음성으로 답변합니다.
5. **실시간 평가**: 답변은 자동으로 텍스트로 변환되고 평가됩니다.
6. **면접 종료 및 결과 확인**: 모든 질문이 끝나면 합격/불합격 결과를 확인할 수 있습니다.

---

## 6. 파일 구조 설명 (File Structure)

```
📂 Project Root
│
├── 📄 server.py              # 메인 백엔드 서버 (FastAPI)
├── 📄 app.js                 # 프론트엔드 로직 (SPA, STT, 녹음 등)
├── 📄 index.html             # 메인 HTML 뷰
├── 📄 styles.css             # 스타일 시트
├── 📄 requirements.txt       # Python 의존성 목록
├── 📄 migrate_db_v3.py       # DB 마이그레이션 스크립트 (Interview_Result 테이블 생성)
├── 📄 create_table.py        # 초기 테이블 생성 스크립트
├── 📄 .env                   # 환경 설정 파일 (API 키, DB 정보)
│
├── 📂 uploads/               # 업로드된 파일 저장소
│   ├── 📂 resumes/           # 이력서 PDF
│   └── 📂 audio/             # 면접 녹음 파일
│
└── 📂 db/                    # (옵션) 로컬 DB 관련 파일
```

---

## 7. 문제 해결 (Troubleshooting)
- **DB 연결 오류**: `.env` 파일의 DB 접속 정보가 정확한지 확인하고, PostgreSQL 서비스가 실행 중인지 확인하세요.
- **마이크/카메라 오류**: 브라우저의 권한 설정에서 마이크와 카메라 사용을 허용해주세요.
- **OpenAI API 오류**: API 키가 만료되었거나 올바르지 않은지 확인해주세요.
