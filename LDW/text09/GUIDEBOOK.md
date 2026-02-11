# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 웹 기반의 AI 면접 시뮬레이션 프로그램입니다. 사용자는 이력서를 업로드하고, AI 면접관과 음성 및 화상으로 실시간 면접을 진행할 수 있습니다. 면접이 종료되면 AI가 지원자의 답변 태도, 직무 적합성, 의사소통 능력 등을 종합적으로 분석하여 합격 여부와 피드백을 제공합니다.

### 주요 특징
- **실시간 AI 면접**: OpenAI GPT-4o 기반의 질문 생성 및 답변 평가.
- **음성 인식 (STT)**: OpenAI Whisper 모델을 활용한 고정밀 음성 인식.
- **음성 안내 (TTS)**: Web Speech API를 활용한 질문 음성 안내.
- **자동 평가 시스템**: 면접 종료 후 즉시 결과 분석 및 합불 판정.
- **관리자 기능**: 면접 공고 관리 및 지원자 현황 조회.

---

## 2. 환경 설정 (Environment Setup)

### 필수 요구 사항
- **OS**: Windows, macOS, Linux
- **Python**: 3.8 이상
- **PostgreSQL**: 13 이상
- **Browser**: Chrome, Edge, Safari (Web Speech API 지원 브라우저 권장)

### 설치 및 설정 (Installation)

1. **프로젝트 클론 및 이동**
   ```bash
   # 프로젝트 폴더로 이동 (예시)
   cd C:\big20\big20_AI_Interview_simulation\LDW\text09
   ```

2. **가상 환경 생성 및 활성화 (선택 사항)**
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **필수 라이브러리 설치**
   ```bash
   pip install -r requirements.txt
   ```
   *`requirements.txt`가 없는 경우 아래 패키지 직접 설치:*
   ```bash
   pip install fastapi uvicorn psycopg2-binary python-dotenv openai pydantic pypdf python-multipart
   ```

4. **환경 변수 설정 (.env)**
   프로젝트 루트 또는 상위 디렉토리에 `.env` 파일을 생성하고 아래 내용을 입력하세요.
   ```env
   DB_HOST=localhost
   DB_NAME=interview_db
   DB_USER=postgres
   DB_PASS=013579
   DB_PORT=5432
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

5. **데이터베이스 설정**
   PostgreSQL에 `interview_db` 데이터베이스를 생성하고, 필요한 테이블을 생성해야 합니다.
   `create_table.py` 또는 `migrate_db_v3.py` 스크립트를 실행하면 테이블이 자동 생성됩니다.
   ```bash
   python migrate_db_v3.py
   ```

---

## 3. 프로그램 실행 방법 (Execution)

서버를 실행하면 자동으로 브라우저가 열리며 웹 애플리케이션에 접속됩니다.

```bash
python server.py
```

- **서버 주소**: `http://localhost:5000`
- **관리자 계정**: 초기 설정이 필요하거나 DB에서 직접 생성해야 할 수 있습니다. (회원가입 시 관리자 선택 가능)

---

## 4. 사용 라이브러리 (Libraries)

### Backend (Python)
- **FastAPI**: 고성능 비동기 웹 프레임워크.
- **Uvicorn**: ASGI 서버 구현체.
- **Psycopg2**: PostgreSQL 데이터베이스 어댑터.
- **OpenAI**: GPT-4o 및 Whisper API 연동.
- **PyPDF**: PDF 이력서 텍스트 추출.
- **Pydantic**: 데이터 유효성 검사 및 설정 관리.

### Frontend (HTML/JS/CSS)
- **Vanilla JS**: 별도 프레임워크 없이 순수 자바스크립트로 구현.
- **Web Speech API**: 브라우저 내장 음성 합성(TTS) 및 인식(STT) 기능 사용.
- **MediaRecorder API**: 사용자 음성 녹음 및 서버 전송.

---

## 5. 주요 기능 사용법 (Features)

### [지원자]
1. **회원가입/로그인**: '지원자' 유형으로 회원가입 후 로그인합니다.
2. **이력서 등록**: 면접 설정 페이지에서 PDF 형식의 이력서를 업로드합니다.
3. **면접 진행**:
   - 카메라/마이크 권한을 허용합니다.
   - AI 면접관의 질문을 듣고 답변을 말합니다.
   - 답변이 끝나면 "답변 제출" 버튼을 누르거나 시간이 만료되면 자동 제출됩니다.
4. **결과 확인**: 면접 종료 후 AI가 분석한 평가 점수와 합격 여부를 확인합니다.

### [관리자]
1. **공고 관리**: 채용 공고를 등록, 수정, 삭제할 수 있습니다.
2. **지원자 현황**: 지원자들의 면접 진행 상황과 결과를 조회할 수 있습니다 (기능 구현 예정).

---

## 6. 파일 구조 설명 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09
├── app.js                 # 프론트엔드 로직 (라우팅, API 호출, 면접 진행 등)
├── index.html             # 메인 웹 페이지 (SPA 구조)
├── styles.css             # 스타일 시트
├── server.py              # FastAPI 백엔드 서버 (API 엔드포인트)
├── requirements.txt       # 의존성 패키지 목록
├── data.json              # (임시) 데이터 파일
├── create_table.py        # DB 테이블 초기 생성 스크립트
├── migrate_db_v3.py       # DB 마이그레이션 스크립트 (최신 스키마 적용)
├── uploads/               # 업로드된 이력서 및 오디오 파일 저장소
│   ├── resumes/           # 이력서 (PDF)
│   └── audio/             # 면접 녹음 파일 (WebM)
└── GUIDEBOOK.md           # 프로젝트 가이드북 (본 문서)
```

---

## 7. 문제 해결 (Troubleshooting)

- **DB 연결 오류**: `.env` 파일의 DB 접속 정보가 정확한지 확인하고, PostgreSQL 서비스가 실행 중인지 확인하세요.
- **마이크/카메라 권한**: 브라우저 주소창 옆의 권한 설정에서 마이크와 카메라 허용 여부를 확인하세요.
- **OpenAI API 오류**: API Key가 유효한지 확인하고, 잔액이 충분한지 확인하세요.
- **면접 종료 후 멈춤**: TTS 오류로 인해 종료되지 않는 경우, 약 10초 후 자동으로 결과 페이지로 이동하도록 안전장치가 마련되어 있습니다.
