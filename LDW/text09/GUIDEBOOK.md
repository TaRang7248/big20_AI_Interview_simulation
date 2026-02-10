# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션**입니다. 사용자는 가상의 면접관(AI)과 함께 실제 면접과 유사한 환경에서 질문을 주고받으며 면접 연습을 할 수 있습니다. Google Gemini Pro API를 활용하여 직무에 맞는 질문을 생성하고, 사용자의 답변을 분석하여 꼬리 질문과 피드백을 제공합니다.

---

## 2. 환경 (Environment)
본 프로젝트는 다음 환경에서 개발 및 테스트되었습니다.

*   **OS**: Windows 10/11
*   **Language**: Python 3.9+
*   **Database**: PostgreSQL
*   **Architecture**: Client-Server (FastAPI + Vanilla JS/HTML/CSS)

---

## 3. 프로그램 실행 방법 (How to Run)

### 3.1. 필수 조건
1.  **PostgreSQL**이 설치되어 있고 실행 중이어야 합니다.
2.  `.env` 파일에 데이터베이스 연결 정보(`DB_HOST`, `DB_NAME`, `DB_USER`, `POSTGRES_PASSWORD`, `DB_PORT`)와 `GEMINI_API_KEY`가 올바르게 설정되어 있어야 합니다.
3.  필요한 라이브러리가 설치되어 있어야 합니다 (아래 `4. 사용 라이브러리` 참고).

### 3.2. 실행 명령어
터미널(CMD 또는 PowerShell)에서 프로젝트 폴더(`text09`)로 이동한 후 다음 명령어를 실행합니다.

```bash
python server.py
```

### 3.3. 실행 확인
*   서버가 정상적으로 실행되면 **1초 뒤에 기본 웹 브라우저가 자동으로 열립니다.**
*   브라우저 주소창에 `http://localhost:5000`이 입력되어 시뮬레이션 메인 페이지(로그인 화면)가 나타납니다.

---

## 4. 사용 라이브러리 (Libraries)
본 프로젝트는 다음과 같은 Python 라이브러리를 사용합니다. `requirements.txt`에 명시되어 있습니다.

*   **FastAPI**: 고성능 비동기 웹 프레임워크 (백엔드 서버).
*   **uvicorn**: ASGI 서버 구현체 (FastAPI 실행을 위해 필요).
*   **psycopg2 / psycopg2-binary**: PostgreSQL 데이터베이스 어댑터.
*   **google-generativeai**: Google Gemini API 연동을 위한 클라이언트 라이브러리.
*   **python-dotenv**: 환경 변수(`.env`) 로드.
*   **pydantic**: 데이터 유효성 검사 및 설정 관리.
*   **python-multipart**: 파일 업로드 처리를 위해 필요.

설치 명령어 예시:
```bash
pip install fastapi uvicorn psycopg2-binary google-generativeai python-dotenv pydantic python-multipart
```

---

## 5. 주요 기능 사용법 (Key Features)

### 5.1. 회원가입 및 로그인
*   **회원가입**: 아이디(이메일 형식 권장), 비밀번호, 이름 등을 입력하여 계정을 생성합니다.
*   **로그인**: 생성한 계정으로 로그인합니다. 로그인 성공 시 메인 대시보드로 이동합니다.

### 5.2. 공고 관리 (Job Management)
*   **공고 등록**: '채용 공고 관리' 메뉴에서 제목, 직무, 마감일, 내용을 입력하여 새로운 공고를 등록합니다.
*   **공고 조회**: 등록된 공고 목록을 확인하고, 상세 내용을 볼 수 있습니다.
*   **공고 수정/삭제**: 본인이 작성한 공고에 한해 수정 및 삭제가 가능합니다.

### 5.3. 이력서 업로드
*   '이력서 업로드' 섹션에서 PDF 형식의 이력서를 업로드할 수 있습니다.
*   업로드된 이력서는 AI가 면접 질문을 생성하는 데 참고 자료로 활용될 수 있습니다 (현재 버전에서는 직무 기반 질문 생성에 집중).

### 5.4. AI 면접 진행 (AI Interview)
1.  **면접 시작**: 'AI 면접 시작' 메뉴에서 지원할 공고(직무)를 선택하고 '면접 시작하기' 버튼을 누릅니다.
2.  **질문 생성**: AI가 해당 직무에 적합한 **첫 번째 질문**을 생성하여 화면에 표시하고 음성(TTS)으로 읽어줍니다.
3.  **답변 녹음**: 사용자는 마이크를 통해 답변을 말합니다. 답변이 끝나면 '답변 제출'을 합니다 (자동/수동).
4.  **평가 및 꼬리 질문**: AI가 사용자의 답변을 분석하여 **평가(점수 및 피드백)** 를 저장하고, 답변 내용을 바탕으로 **다음 꼬리 질문**을 생성합니다.
5.  **반복**: 위 과정을 반복하며 심층 면접을 진행합니다.

### 5.5. 마이페이지 (My Page)
*   사용자 정보를 확인하고 수정할 수 있습니다.
*   비밀번호 변경 기능을 제공합니다.

---

## 6. 파일 구조 설명 (File Structure)

```
text09/
├── server.py               # [메인] FastAPI 백엔드 서버 실행 규격
├── app.js                  # [프론트엔드] 주요 로직 (API 호출, UI 조작)
├── index.html              # [프론트엔드] 메인 웹 페이지 구조
├── styles.css              # [프론트엔드] 웹 페이지 스타일링
├── check_table.py          # 데이터베이스 테이블 구조 확인용 스크립트
├── create_table.py         # 데이터베이스 테이블 초기 생성 스크립트
├── diagnose_db.py          # 데이터베이스 연결 진단 스크립트
├── migrate_db.py           # 데이터베이스 스키마 마이그레이션 스크립트
├── setup_interview_data.py # 초기 면접 데이터 셋업 스크립트
├── test_job_api.py         # 공고 API 테스트용 스크립트
├── requirements.txt        # 필요 라이브러리 목록
└── uploads/                # 업로드된 파일(이력서 등) 저장 폴더
    └── resumes/
```

### 주요 파일 상세
*   **server.py**: 전체 시스템의 핵심입니다. 데이터베이스 연결, API 엔드포인트 정의(`login`, `register`, `interview/start` 등이), Google Gemini API 호출 로직이 포함되어 있습니다.
*   **app.js**: 사용자의 브라우저에서 실행됩니다. 버튼 클릭 이벤트 처리, 서버와의 비동기 통신(`fetch`), 화면 갱신(DOM 조작)을 담당합니다.
*   **create_table.py**: 프로그램 최초 실행 시 필요한 테이블(`users`, `interview_announcement`, `interview_information`, `interview_answer`, `Interview_Progress`)을 생성합니다.
