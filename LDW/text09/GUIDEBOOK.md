# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 웹 기반의 **AI 면접 시뮬레이션** 프로그램입니다. 사용자는 이력서를 업로드하고, AI 면접관과 음성으로 대화하며 실제 면접과 유사한 경험을 할 수 있습니다. 면접이 종료되면 AI가 답변 내용을 분석하여 직무 적합성, 문제 해결 능력, 의사소통 능력 등을 평가하고 피드백을 제공합니다.

## 2. 환경 요구사항 (Environment)
이 프로그램을 실행하기 위해서는 다음과 같은 환경이 필요합니다.

- **OS**: Windows (테스트 환경), Mac/Linux 호환 가능
- **Python**: 3.8 이상
- **Database**: PostgreSQL (기본 설정: localhost:5432)
- **API Key**: OpenAI API Key (GPT-4o, Whisper 모델 사용)

## 3. 프로그램 실행 방법 (How to Run)

### 3.1. 사전 준비
1. **PostgreSQL 설치 및 실행**: 로컬 환경에 PostgreSQL이 설치되어 있어야 하며, `.env` 파일에 설정된 정보로 접속 가능해야 합니다.
2. **`.env` 파일 설정**: 프로젝트 루트(또는 상위 디렉토리)에 `.env` 파일을 생성하고 다음 정보를 입력하세요.
   ```env
   OPENAI_API_KEY=sk-...
   DB_HOST=localhost
   DB_NAME=interview_db
   DB_USER=postgres
   # POSTGRES_PASSWORD=yourpassword
   DB_PORT=5432
   ```

### 3.2. 의존성 설치
터미널에서 다음 명령어를 실행하여 필요한 패키지를 설치합니다.
```bash
pip install -r requirements.txt
```
*(참고: `requirements.txt` 파일이 없는 경우, `server.py`에 명시된 라이브러리를 직접 설치해야 합니다: fastapi, uvicorn, psycopg2-binary, pydantic, python-dotenv, openai, pypdf 등)*

### 3.3. 서버 실행
프로젝트 디렉토리에서 다음 명령어로 서버를 실행합니다.
```bash
python server.py
# 또는 uvicorn 사용 시
# uvicorn server:app --reload
```
서버가 정상적으로 실행되면 브라우저에서 `http://localhost:8000` (또는 설정된 포트, `server.py` 실행 시 포트 확인 필요)로 접속합니다. `server.py` 직접 실행 시 보통 `http://localhost:5000` 또는 `8000`을 사용하도록 설정되어 있을 수 있습니다.

## 4. 사용하는 모델 및 라이브러리 (Models & Libraries)

### AI Models (OpenAI)
- **GPT-4o**: 
    - 면접 질문 생성 (직무 및 이전 답변 기반)
    - 답변 평가 및 점수 산정
    - 직무별 면접 질문 풀(Pool) 생성
- **Whisper (whisper-1)**:
    - 사용자 음성 답변을 텍스트로 변환 (STT: Speech-to-Text)

### Backend Libraries
- **FastAPI**: 고성능 웹 프레임워크
- **Psycopg2**: PostgreSQL 데이터베이스 연동
- **Pydantic**: 데이터 유효성 검사 및 설정 관리
- **PyPDF**: PDF 이력서 텍스트 추출
- **Python-dotenv**: 환경 변수 관리

### Frontend
- **HTML/CSS/JS**: 바닐라 자바스크립트 및 CSS 사용

## 5. 주요 기능 사용법 (Key Features)

### 5.1. 회원가입 및 로그인
- 접속 초기 화면에서 회원가입을 진행합니다.
- 아이디, 비밀번호, 이름 등 기본 정보를 입력합니다.
- 가입 후 로그인하여 메인 대시보드로 이동합니다.

### 5.2. 기업(관리자) 모드: 공고 등록 (시뮬레이션)
- 채용 공고를 등록할 수 있습니다.
- 직무 제목(Title), 직무 내용(Job Description), 마감일 등을 입력합니다.
- 등록된 공고는 지원자가 면접을 시작할 때 선택할 수 있습니다.

### 5.3. 지원자 모드: 면접 체험
1. **이력서 업로드**: 지원하고자 하는 공고를 선택하고 PDF 형식의 이력서를 업로드합니다.
2. **면접 시작**: '면접 시작' 버튼을 누르면 AI 면접관이 첫 질문(자기소개 등)을 합니다.
3. **답변 하기**: 마이크를 통해 음성으로 답변합니다. 답변이 끝나면 '답변 완료' 등의 버튼을 눌러 전송합니다.
4. **꼬리 질문**: AI는 사용자의 답변과 이력서 내용을 바탕으로 심층 질문을 이어갑니다.
5. **면접 종료**: 정해진 질문 횟수 또는 단계(인성, 직무 등)가 끝나면 면접이 종료됩니다.

### 5.4. 결과 확인
- 면접이 종료된 후, AI가 분석한 **종합 평가 결과**를 확인할 수 있습니다.
- **평가 항목**: 기술(Tech), 문제해결능력, 의사소통능력, 비언어적 요소(태도)
- **합격/불합격 여부**: AI가 판단한 예측 결과를 보여줍니다.
- **면접 기록**: 진행했던 질의응답 내용을 다시 볼 수 있습니다.

## 6. 파일 구조 설명 (File Structure)

```
/
├── server.py                # 메인 백엔드 서버 (FastAPI) & 로직 포함
├── index.html               # 메인 프론트엔드 페이지 (SPA 구조)
├── style.css                # 스타일 시트
├── app.js                   # 프론트엔드 로직 (API 호출, UI 제어)
├── migrate_db_v4.py         # DB 마이그레이션 스크립트 (최신)
├── requirements.txt         # 파이썬 의존성 목록
├── /db                      # 데이터베이스 스크립트 모음
│   ├── create_table.py      # 초기 테이블 생성
│   └── ...
├── /uploads                 # 업로드된 이력서 및 오디오 파일 저장소
│   ├── /resumes             # 이력서 PDF
│   └── /audio               # 면접 답변 오디오 (.webm)
└── GUIDEBOOK.md             # 본 가이드북 파일
```

---
*Created by AI Assistant*
