# AI 면접 시뮬레이션 (AI Interview Simulation) 가이드북

## 1. 개요 (Overview)
본 프로젝트는 **OpenAI GPT-4o**와 **Whisper API**를 활용한 **웹 기반 AI 면접 시뮬레이션**입니다.  
사용자는 이력서(PDF)를 업로드하고, 실제 면접처럼 음성으로 질문에 답변하며, AI 면접관으로부터 꼬리 질문과 평가를 받을 수 있습니다.

**주요 목표:**
- 실제 면접 환경과 유사한 시뮬레이션 제공
- 이력서 기반 맞춤형 질문 생성
- 음성 인식(STT) 및 음성 합성(TTS)을 통한 양방향 소통
- 관리자 기능을 통한 채용 공고 관리

---

## 2. 개발 환경 (Environment)

### 2.1. 필수 프로그램
- **Python 3.8+**: 백엔드 서버 구동
- **PostgreSQL**: 데이터베이스 (DB명: `interview_db` 권장)
- **Chrome Browser**: 최신 버전 권장 (음성 인식/합성 호환성)

### 2.2. 사용 라이브러리 (Dependencies)
**Backend (Python):**
- `FastAPI`: 고성능 웹 프레임워크
- `Uvicorn`: ASGI 서버
- `Psycopg2-binary`: PostgreSQL 연동
- `OpenAI`: GPT-4o 및 Whisper API 사용
- `Pypdf`: PDF 이력서 텍스트 추출
- `Python-dotenv`: 환경 변수 관리
- `Pydantic`: 데이터 검증

**Frontend (Vanilla JS):**
- HTML5 / CSS3
- JavaScript (ES6+)

---

## 3. 프로그램 실행 방법 (Execution Guide)

### 3.1. 환경 설정 (.env)
프로젝트 루트 디렉토리의 `.env` 파일에 다음 정보를 설정해야 합니다.
```ini
DB_HOST=localhost
DB_NAME=interview_db
DB_USER=postgres
POSTGRES_PASSWORD=your_password
DB_PORT=5432
OPENAI_API_KEY=your_openai_api_key_sk-...
```

### 3.2. 데이터베이스 설정
PostgreSQL에 `interview_db` 데이터베이스를 생성하고, 필요한 테이블을 생성해야 합니다.
(프로젝트 내 `create_table.py` 또는 마이그레이션 스크립트 활용 가능)

### 3.3. 서버 실행
터미널(CMD/PowerShell)에서 프로젝트 폴더로 이동 후 아래 명령어를 입력합니다.

```bash
# 필수 패키지 설치 (최초 1회)
pip install -r requirements.txt

# 서버 실행
python server.py
```

서버가 정상적으로 실행되면, 브라우저가 자동으로 열리며 `http://localhost:5000`으로 접속됩니다.

---

## 4. 주요 기능 사용법 (Feature Guide)

### 4.1. 회원가입 및 로그인
- **지원자(Applicant):** 면접에 참여하는 일반 사용자입니다.
- **관리자(Admin):** 채용 공고를 등록하고 관리하는 사용자입니다.
- 최초 접속 시 '회원가입'을 통해 계정을 생성하고 로그인합니다.

### 4.2. 관리자 기능 (Admin)
1. **공고 관리:** 채용 공고를 등록(제목, 직무, 내용, 마감일)하고 수정/삭제할 수 있습니다.
2. **지원자 현황:** (구현 예정) 지원자들의 면접 진행 상황을 모니터링할 수 있습니다.

### 4.3. 지원자 기능 (Applicant)
1. **공고 지원:** 대시보드에서 채용 공고를 확인하고 '확인하기' -> '지원하기'를 클릭합니다.
2. **이력서 업로드:** PDF 형식의 이력서를 업로드합니다.
3. **환경 테스트 및 면접 시작:**
    - '면접 시작' 버튼을 누르면 즉시 면접 페이지로 이동합니다.
    - 이동 후 자동으로 카메라/마이크 권한을 확인하고 이력서를 업로드합니다.
    - 권한이 없다면 알림창이 뜨고 다시 설정 페이지로 돌아옵니다.
    - 준비가 완료되면 AI 면접관이 첫 질문을 시작합니다.
4. **AI 면접 진행:**
    - AI 면접관이 이력서를 분석하여 질문을 합니다.
    - 사용자는 음성으로 답변합니다. (답변 시간 제한 있음)
    - 답변이 끝나면 '답변 제출' 버튼을 누릅니다.
    - AI는 답변을 분석하여 꼬리 질문을 이어갑니다.
5. **면접 종료:** 면접관이 면접 종료를 선언하면 시뮬레이션이 끝납니다.

---

## 5. 파일 구조 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
│
├── server.py             # 메인 백엔드 서버 (FastAPI)
├── app.js                # 메인 프론트엔드 로직 (SPA, API호출, 미디어처리)
├── index.html            # 메인 웹 페이지 구조
├── styles.css            # 웹 페이지 스타일시트
├── requirements.txt      # 파이썬 패키지 목록
├── create_table.py       # (참고용) DB 테이블 생성 스크립트
├── GUIDEBOOK.md          # 프로젝트 가이드북 (현재 파일)
├── uploads/              # 업로드된 파일 저장소
│   ├── resumes/          # 이력서 PDF 파일
│   └── audio/            # 면접 답변 오디오 파일
└── .env                  # (숨김 파일) 환경 변수 및 API 키 설정
```

---

## 6. 문제 해결 (Troubleshooting)

- **"면접 시작" 버튼을 눌렀는데 반응이 없거나 에러가 떠요:**
  - 이력서를 올바르게 업로드했는지 확인하세요.
  - 브라우저의 카메라/마이크 권한을 '허용'해야 합니다.
- **오디오 녹음이 안 돼요:**
  - 마이크가 정상적으로 연결되어 있는지 확인하세요.
  - HTTPS 또는 localhost 환경에서만 마이크 접근이 가능합니다.
- **DB 연결 오류:**
  - PostgreSQL 서비스가 실행 중인지 확인하세요.
  - `.env` 파일의 비밀번호가 정확한지 확인하세요.

---

**작성일:** 2026-02-10
**작성자:** AI Assistant
