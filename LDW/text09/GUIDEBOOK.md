# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요
본 프로그램은 웹 기반의 AI 면접 시뮬레이션 플랫폼입니다. 사용자는 실제 면접과 유사한 환경에서 AI 면접관과 음성으로 대화하며 면접을 진행할 수 있고, 면접 종료 후 AI가 분석한 상세한 피드백(기술, 문제해결, 의사소통, 태도 등)을 받을 수 있습니다. 관리자는 지원자들의 면접 결과와 상세 대화 기록을 조회하고 관리할 수 있습니다.

## 2. 개발 환경
- **OS**: Windows
- **Language**: Python 3.x, JavaScript (ES6+)
- **Backend Framework**: FastAPI
- **Database**: PostgreSQL (psycopg2)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **AI Models**:
    - **OpenAI GPT-4o**: 면접 질문 생성, 답변 평가, 결과 분석
    - **OpenAI Whisper**: 음성 인식 (STT)
    - **Web Speech API**: 실시간 자막 (브라우저 내장)

## 3. 프로그램 실행 방법

### 3.1. 사전 준비
1. **Python 설치**: Python 3.8 이상이 설치되어 있어야 합니다.
2. **PostgreSQL 설치 및 실행**: 로컬 환경에 PostgreSQL이 설치되어 있고 실행 중이어야 합니다.
3. **환경 변수 설정**: 프로젝트 루트 디렉토리에 `.env` 파일이 있어야 하며, 다음 정보가 포함되어야 합니다.
    ```env
    OPENAI_API_KEY=sk-...
    POSTGRES_PASSWORD=...
    DB_HOST=localhost
    DB_NAME=interview_db
    DB_USER=postgres
    DB_PORT=5432
    ```

### 3.2. 서버 실행
터미널(PowerShell 또는 CMD)을 열고 프로젝트 디렉토리(`C:\big20\big20_AI_Interview_simulation\LDW\text09`)로 이동한 후 다음 명령어를 실행합니다.

```bash
python server.py
```

서버가 성공적으로 실행되면 브라우저가 자동으로 열리거나 `http://localhost:5000`으로 접속하여 프로그램을 사용할 수 있습니다.

### 3.3. 데이터베이스 초기화 (필요 시)
테이블이 없다면 `create_table.py`를 실행하여 테이블을 생성할 수 있습니다.
```bash
python create_table.py
```

## 4. 사용하는 모델 및 라이브러리

### 백엔드 (Python)
- **FastAPI**: 고성능 웹 프레임워크
- **Uvicorn**: ASGI 서버
- **Psycopg2**: PostgreSQL 데이터베이스 어댑터
- **OpenAI API**: GPT-4o (텍스트 생성), Whisper (음성 인식)
- **PyPDF**: 이력서(PDF) 텍스트 추출
- **Python-Multipart**: 파일 업로드 처리
- **Pydantic**: 데이터 유효성 검사

### 프론트엔드 (JavaScript)
- **Web Speech API**: 브라우저 내장 음성 인식 (실시간 피드백용)
- **MediaRecorder API**: 음성 녹음 및 서버 전송용
- **Fetch API**: 비동기 서버 통신

## 5. 주요 기능 사용법

### 5.1. 지원자 (Applicant)
1. **회원가입/로그인**: 계정을 생성하고 로그인합니다.
2. **공고 확인 및 지원**: 대시보드에서 채용 공고를 확인하고 '확인하기' -> '면접 응시하기'를 클릭합니다.
3. **환경 설정**: 카메라와 마이크 권한을 허용하고 테스트합니다.
4. **이력서 업로드**: PDF 형식의 이력서를 업로드합니다.
5. **실전 면접**:
    - AI 면접관의 질문을 듣고(TTS) 답변을 말합니다(STT).
    - 총 12개의 질문이 단계별(자기소개 -> 직무 -> 인성 -> 마무리)로 진행됩니다.
6. **결과 확인**: 면접 종료 후 합격/불합격 여부와 피드백을 확인합니다. '내 정보'의 '면접 기록'에서도 확인 가능합니다.

### 5.2. 관리자 (Admin)
1. **공고 관리**: 채용 공고를 등록, 수정, 삭제할 수 있습니다.
2. **지원자 현황**:
    - 전체 지원자의 면접 현황을 목록으로 확인합니다.
    - **상세보기**를 클릭하면 지원자의 합격 여부와 4가지 평가 항목(기술/직무, 문제해결, 의사소통, 태도/인성)에 대한 **상세 텍스트 평가**를 볼 수 있습니다.
    - 면접 당시의 상세 대화 기록(질문/답변)을 검토할 수 있습니다.

## 6. 파일 구조
```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── server.py             # 메인 백엔드 서버 (FastAPI)
├── app.js                # 프론트엔드 로직 (SPA, 면접 로직)
├── index.html            # 메인 HTML 페이지
├── styles.css            # 스타일시트
├── create_table.py       # DB 테이블 생성 스크립트
├── GUIDEBOOK.md          # 프로그램 가이드북 (본 파일)
├── uploads/              # 업로드된 이력서 및 오디오 파일 저장소
│   ├── resumes/
│   └── audio/
└── db/                   # (옵션) DB 관련 파일
```
