# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 **FastAPI**를 기반으로 한 **웹 기반 AI 면접 시뮬레이션**입니다.  
사용자는 회원가입 후 채용 공고를 확인하고 지원할 수 있으며, **Google Gemini (LLM)**을 활용하여 직무에 맞는 가상의 면접 질문을 받고 답변할 수 있습니다. 시스템은 사용자의 답변을 자동으로 평가하고 기록합니다.

---

## 2. 환경 설정 (Environment Setup)

### 필수 요구 사항
- **OS**: Windows, macOS, Linux
- **Python**: 3.8 이상
- **Database**: PostgreSQL
- **LLM API**: Google Gemini API Key

### 설치 방법

1. **프로젝트 폴더로 이동**
    ```bash
    cd C:\big20\big20_AI_Interview_simulation\LDW\text09
    ```

2. **패키지 설치**
    `requirements.txt`에 명시된 라이브러리를 설치합니다.
    ```bash
    pip install -r requirements.txt
    ```

3. **환경 변수 설정**
    프로젝트 루트 또는 상위 디렉토리에 `.env` 파일을 생성하고 다음 정보를 입력합니다.
    ```ini
    DB_HOST=localhost
    DB_NAME=interview_db
    DB_USER=postgres
    POSTGRES_PASSWORD=your_password
    DB_PORT=5432
    GEMINI_API_KEY=your_gemini_api_key_here
    ```

---

## 3. 프로그램 실행 방법 (Execution)

서버를 실행하면 FastAPI 앱이 구동되고 데이터베이스 테이블이 자동으로 초기화됩니다.

```bash
python server.py
```

- 실행 후 브라우저에서 `http://localhost:5000` 으로 접속합니다.
- 서버 로그에서 `FastAPI Server running on http://localhost:5000` 메시지를 확인하세요.

---

## 4. 사용 라이브러리 및 기술 스택

| 라이브러리 | 용도 | 설명 |
| :--- | :--- | :--- |
| **FastAPI** | 백엔드 프레임워크 | 고성능 비동기 API 서버 구축 |
| **Uvicorn** | ASGI 서버 | FastAPI 애플리케이션 실행 |
| **Psycopg2** | DB 드라이버 | PostgreSQL 데이터베이스 연동 |
| **Google Generative AI** | LLM | 면접 질문 생성 및 답변 평가 (Gemini Pro) |
| **Pydantic** | 데이터 검증 | 요청/응답 데이터의 유효성 검사 및 스키마 정의 |
| **Python-Multipart** | 파일 업로드 | 이력서(PDF) 업로드 처리 |

---

## 5. 주요 기능 사용법

### 1) 회원가입 및 로그인
- `applicant`(지원자) 계정으로 가입하여 서비스를 이용합니다.
- 로그인 후 메인 대시보드 접근이 가능합니다.

### 2) 채용 공고 (Job Board)
- 관리자가 등록한 공고를 확인하고 상세 내용을 볼 수 있습니다.
- `지원하기` 버튼을 통해 해당 직무에 대한 면접을 준비할 수 있습니다.

### 3) 이력서 업로드
- PDF 형식의 이력서를 업로드하여 자신의 정보를 등록합니다.

### 4) AI 면접 진행 (핵심 기능)
- **질문 생성**: 선택한 직무(`Job Title`)와 이력서를 바탕으로 LLM이 맞춤형 첫 질문을 생성합니다.
- **답변 제출**: 사용자가 답변을 입력(또는 음성 인식 후 텍스트 변환)하여 제출합니다.
- **자동 평가**: LLM이 답변의 논리성, 직무 적합성 등을 분석하여 평가 점수와 피드백을 생성합니다. (평가 내용은 관리자/DB에서 확인 가능)
- **심층 질문**: 이전 답변을 바탕으로 꼬리 질문이 이어집니다.

---

## 6. 파일 구조 설명 (File Structure)

```
📂 text09
├── 📄 server.py        # 메인 서버 파일 (FastAPI, DB연동, LLM로직)
├── 📄 app.js           # 프론트엔드 로직 (API 호출, UI 제어)
├── 📄 index.html       # 메인 웹 페이지 HTML
├── 📄 styles.css       # 스타일시트
├── 📄 requirements.txt # 파이썬 패키지 목록
└── 📂 uploads          # 업로드된 이력서 저장소
```

---

## 7. 데이터베이스 구조 (Interview_Progress)

면접 진행 상황은 `Interview_Progress` 테이블에 실시간으로 저장됩니다.

- **Interview_Number**: 면접 세션 고유 ID
- **Applicant_Name**: 지원자 이름
- **Create_Question**: AI가 생성한 질문
- **Question_answer**: 지원자의 답변
- **Answer_Evaluation**: AI의 답변 평가 (피드백)
- **answer_time**: 답변 소요 시간

---
