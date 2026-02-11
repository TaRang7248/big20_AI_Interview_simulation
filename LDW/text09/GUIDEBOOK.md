# 📘 AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 프로젝트 개요
**프로젝트명**: 웹 기반 AI 면접 시뮬레이션
**설명**: 사용자가 웹 브라우저를 통해 AI 면접관과 실제 면접처럼 대화하며 진행하는 시뮬레이션 프로그램입니다. OpenAI GPT-4o가 면접관 역할을 수행하며 질문을 생성하고 평가를 진행합니다. Whisper 모델을 통해 사용자의 음성을 텍스트로 변환합니다.

### 주요 특징
- **실시간 대화형 면접**: 음성 인식(STT) 및 음성 합성(TTS)을 통한 자연스러운 대화
- **맞춤형 질문 생성**: 지원자의 이력서(PDF)와 직무 내용을 분석하여 개인화된 질문 제공
- **자동 평가 시스템**: 면접 종료 후 4가지 항목(기술, 문제해결, 의사소통, 비언어적 태도)에 대한 정량적/정성적 평가 제공
- **관리자 기능**: 면접 공고 관리 및 지원자 결과 확인

---

## 2. 개발 환경 (Environment)
이 프로젝트는 **Python (Backend)**과 **Vanilla JavaScript (Frontend)**로 구성되어 있습니다.

- **OS**: Windows / Mac / Linux
- **Language**: Python 3.9+, JavaScript (ES6+)
- **Database**: PostgreSQL
- **Backend Framework**: FastAPI
- **Frontend**: HTML5, CSS3, Vanilla JS
- **AI Models**: 
  - GPT-4o (OpenAI API) - 질문 생성 및 평가
  - Whisper-1 (OpenAI API) - STT (Speech-to-Text)

---

## 3. 프로그램 실행 방법

### 3.1 사전 준비
1. **PostgreSQL 설치 및 실행**: 로컬 또는 서버에 PostgreSQL이 설치되어 있어야 합니다.
2. **.env 파일 설정**: 프로젝트 루트에 `.env` 파일을 생성하고 다음 정보를 입력하세요.
   ```ini
   DB_HOST=localhost
   DB_NAME=interview_db
   DB_USER=postgres
   POSTGRES_PASSWORD=your_password
   DB_PORT=5432
   OPENAI_API_KEY=sk-your-api-key...
   ```

### 3.2 데이터베이스 초기화
최초 실행 시 데이터베이스 테이블이 필요합니다. `server.py` 실행 시 자동으로 테이블을 생성하는 로직은 없으므로, 별도의 SQL 스크립트나 DB 툴을 사용하여 아래 테이블을 생성해야 합니다.
- `users`: 사용자 정보
- `interview_announcement`: 채용 공고
- `interview_information`: 이력서 정보
- `Interview_Progress`: 면접 진행 로그
- `Interview_Result`: 면접 결과
- `job_question_pool`: 직무별 질문 풀

### 3.3 서버 실행
터미널에서 다음 명령어를 실행합니다.
```bash
# 1. 가상환경 생성 (선택)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 패키지 설치
pip install fastapi uvicorn psycopg2-binary python-dotenv openai pypdf

# 3. 서버 실행
python server.py
```
서버가 정상적으로 실행되면 브라우저가 자동으로 열리며 `http://localhost:5000`으로 접속됩니다.

---

## 4. 주요 기능 사용법

### 4.1 회원가입 및 로그인
- **회원가입**: `면접자` 또는 `관리자` 유형을 선택하여 가입합니다.
- **로그인**: 가입한 아이디로 로그인합니다.

### 4.2 (관리자) 채용 공고 등록
1. 관리자 계정으로 로그인합니다.
2. '관리자 메뉴' > '공고 관리' > '공고 등록' 버튼을 클릭합니다.
3. 직무, 제목, 내용, 마감일을 입력하고 등록합니다.

### 4.3 (면접자) 면접 지원 및 진행
1. 면접자 계정으로 로그인합니다.
2. '지원 가능한 공고' 목록에서 원하는 공고의 '확인하기' 버튼을 누릅니다.
3. 공고 상세 페이지에서 '지원하기' 버튼을 누릅니다.
4. **이력서 업로드**: PDF 형식의 이력서를 업로드합니다.
5. **환경 테스트**: 카메라와 마이크 권한을 허용하고 연결 상태를 확인합니다.
6. **면접 시작**: '면접 시작' 버튼을 누르면 AI 면접관과 연결됩니다.
7. **면접 진행**:
   - AI가 질문을 음성으로 읽어줍니다.
   - 답변을 마치면 '답변 제출' 버튼을 누릅니다. (90초 제한 시간이 지나면 자동 제출됩니다.)
   - 자기소개 -> 직무 질문(5개) -> 인성 질문(5개) -> 마무리 질문 순으로 진행됩니다.

### 4.4 결과 확인
- 면접이 종료되면 자동으로 결과 페이지로 이동합니다.
- AI가 분석한 합격 여부와 상세 평가 내용을 확인할 수 있습니다.

---

## 5. 파일 구조 (File Structure)

```
📂 Project Root
├── 📄 server.py           # Backend: FastAPI 서버, DB 연결, AI 로직 처리
├── 📄 app.js              # Frontend: 라우팅, API 호출, 미디어 레코딩, 인터랙션
├── 📄 index.html          # Frontend: UI 구조 (SPA 형태)
├── 📄 styles.css          # Frontend: 스타일 시트
├── 📄 GUIDEBOOK.md        # 가이드북 (현재 파일)
├── 📂 uploads             # 업로드된 파일 저장소
│   ├── 📂 resumes         # 이력서 PDF 파일
│   └── 📂 audio           # 면접 답변 오디오 파일
└── 📄 .env                # 환경 변수 (API Key, DB 정보)
```

### 주요 파일 설명
- **server.py**: 
  - `/api/interview/start`: 면접 시작, 첫 질문 생성.
  - `/api/interview/answer`: 답변 제출, STT 변환, 다음 질문 생성.
  - `analyze_interview_result`: 백그라운드 작업으로 전체 면접 결과 분석 수행.
  
- **app.js**:
  - `AppState`: 전역 상태 관리 (현재 사용자, 진행 중인 면접 정보 등).
  - `initRouter`: 페이지 전환 관리.
  - `startRecording` / `stopRecording`: Web API를 이용한 마이크 제어 및 녹음.
  - `speakText`: Web Speech API를 이용한 음성 합성(TTS).

---

## 6. 사용 라이브러리 (Libraries)

### Backend (Python)
- **FastAPI**: 고성능 웹 프레임워크
- **Uvicorn**: ASGI 서버
- **Psycopg2**: PostgreSQL 데이터베이스 어댑터
- **OpenAI**: GPT-4o 및 Whisper API 연동
- **PyPDF**: PDF 이력서 텍스트 추출
- **Python-Dotenv**: 환경 변수 관리

### Frontend (JavaScript)
- **Vanilla JS**: 별도 프레임워크 없음
- **Web Speech API**: 음성 인식(STT) 및 합성(TTS) (브라우저 내장)
- **MediaRecorder API**: 음성 녹음 (브라우저 내장)

---
*Created by AI Agent "Antigravity"*
