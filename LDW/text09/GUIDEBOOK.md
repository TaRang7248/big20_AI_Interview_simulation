# AI 면접 시뮬레이션 (AI Interview Simulation) - 사용자 가이드

## 1. 프로젝트 개요
본 프로젝트는 **GPT-4o**와 **Whisper** 기술을 활용하여 실제 면접과 유사한 환경을 제공하는 **AI 면접 시뮬레이션 플랫폼**입니다.
지원자의 이력서와 채용 공고를 분석하여 맞춤형 면접 질문을 생성하고, 음성 답변을 텍스트로 변환(STT)하여 내용을 평가합니다.

### 주요 기능
- **AI 맞춤형 질문 생성**: 지원자의 이력서(PDF)와 직무 내용을 분석하여 GPT-4o가 심층 질문을 생성합니다.
- **음성 인식 인터뷰**: OpenAI Whisper 모델을 사용하여 지원자의 음성 답변을 실시간으로 텍스트로 변환합니다.
- **자동 평가 시스템**: 답변 내용에 대해 AI가 즉각적으로 점수와 피드백을 생성하여 데이터베이스에 저장합니다.
- **관리자 모드**: 채용 공고 관리 및 지원자별 면접 결과(질문, 답변, 평가)를 조회할 수 있습니다.
- **자동화된 환경 테스트**: 카메라와 마이크 연결 상태를 자동으로 점검하여 원활한 면접 진행을 돕습니다.

---

## 2. 환경 설정 (Environment Setup)

### 필수 요구 사항
- **OS**: Windows 10/11
- **Python**: 3.8 이상
- **Database**: PostgreSQL (기본 포트 5432)
- **Browser**: Chrome, Edge 등 모던 브라우저 (카메라/마이크 권한 필요)

### 라이브러리 설치
프로젝트 실행을 위해 `requirements.txt`에 명시된 라이브러리를 설치해야 합니다.

```bash
pip install -r requirements.txt
```

주요 라이브러리:
- `fastapi`, `uvicorn`: 웹 서버 프레임워크
- `psycopg2-binary`: PostgreSQL 데이터베이스 연동
- `openai`: GPT-4o 및 Whisper API 사용
- `pypdf`: 이력서(PDF) 텍스트 추출
- `python-dotenv`: 환경 변수 관리

### 환경 변수 설정 (.env)
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 설정해주세요.

```ini
# Database Info
DB_HOST=localhost
DB_NAME=interview_db
DB_USER=postgres
DB_PORT=5432
POSTGRES_PASSWORD=your_password

# OpenAI API Key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 3. 데이터베이스 설정 및 마이그레이션

최초 실행 시 또는 데이터베이스 구조 변경 시 마이그레이션 스크립트를 실행해야 합니다.

```bash
python migrate_db_v2.py
```

- **interview_answer**: 기본 면접 질문 데이터셋 저장
- **job_question_pool**: 직무별로 선별된 질문 풀 저장
- **Interview_Progress**: 면접 진행 기록 (질문, 답변, 평가) 저장

---

## 4. 프로젝트 실행 (Execution)

서버를 실행하면 자동으로 브라우저가 열리며 애플리케이션이 시작됩니다.

```bash
python server.py
```

- **서버 주소**: `http://localhost:5000`
- **API 문서**: `http://localhost:5000/docs` (Swagger UI)

---

## 5. 사용 방법 (User Guide)

### 5.1 지원자 (Applicant)
1. **회원가입/로그인**: 계정을 생성하고 로그인합니다.
2. **공고 확인**: '지원 가능한 공고' 목록에서 원하는 직무를 선택합니다.
3. **면접 준비**:
   - **이력서 업로드**: PDF 형식의 이력서를 업로드합니다.
   - **환경 점검**: 카메라와 마이크가 자동으로 연결되는지 확인합니다.
4. **면접 진행**:
   - AI 면접관이 첫 번째 질문을 합니다 (음성 안내 + 텍스트).
   - 본인의 답변을 음성으로 말하면 녹음됩니다.
   - 답변이 끝나면 '답변 제출' 버튼을 누릅니다.
   - AI가 답변을 분석하고 다음 꼬리 질문을 이어갑니다.
5. **면접 종료**: 모든 과정이 끝나면 종료 메시지가 표시됩니다.

### 5.2 관리자 (Admin)
1. **관리자 로그인**: 회원가입 시 '관리자' 유형으로 가입하거나, DB에서 권한을 수정합니다.
2. **공고 관리**: 새로운 채용 공고를 등록, 수정, 삭제할 수 있습니다.
3. **결과 조회**: '지원자 현황' 메뉴에서 각 지원자의 면접 상세 기록(질문, 답변 텍스트, AI 평가 결과)을 확인할 수 있습니다.

---

## 6. 파일 구조 (File Structure)

```
📂 Project Root
├── 📄 server.py           # FastAPI 백엔드 서버 (API, DB, LLM 로직)
├── 📄 app.js              # 프론트엔드 로직 (UI 제어, 오디오 녹음, API 호출)
├── 📄 index.html          # 메인 웹 페이지 구조
├── 📄 styles.css          # 스타일 시트
├── 📄 migrate_db_v2.py    # 데이터베이스 초기화 및 마이그레이션 스크립트
├── 📄 requirements.txt    # 파이썬 의존성 목록
├── 📄 .env                # 환경 변수 (API Key, DB 접속 정보)
├── 📂 uploads             # 업로드된 이력서 및 오디오 파일 저장소
└── 📄 GUIDEBOOK.md        # 프로젝트 가이드북 (본 파일)
```

---

## 7. 문제 해결 (Troubleshooting)

- **DB 연결 오류**: `.env` 파일의 DB 정보가 정확한지, PostgreSQL 서비스가 실행 중인지 확인하세요.
- **OpenAI API 오류**: API Key가 유효한지, 잔액이 충분한지 확인하세요.
- **마이크/카메라 작동 안 함**: 브라우저 주소창 옆의 권한 설정에서 마이크/카메라 허용 여부를 확인하세요. `localhost`가 아닌 경우 HTTPS 환경이 필요할 수 있습니다.
- **의존성 오류**: `pip install --upgrade -r requirements.txt`로 라이브러리를 최신 버전으로 업데이트하세요.
