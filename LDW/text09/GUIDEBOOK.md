# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션**입니다. 사용자는 지원자로서 면접 공고에 지원하고, AI 면접관과 음성으로 실시간 면접을 진행할 수 있습니다. 관리자는 채용 공고를 관리하고 지원자의 면접 결과를 확인할 수 있습니다.

## 2. 개발 환경 및 요구사항 (Environment)
- **OS**: Windows (권장)
- **Language**: Python 3.x, JavaScript (ES6+)
- **Database**: PostgreSQL (기본 설정 필요)
- **Web Browser**: Chrome, Edge (마이크/카메라 권한 필요)

### 필수 라이브러리
- `FastAPI`: 웹 서버 프레임워크
- `Uvicorn`: ASGI 서버
- `Psycopg2`: PostgreSQL 데이터베이스 어댑터
- `OpenAI`: AI 모델 연동 (GPT-4o, Whisper)
- `PyPDF`: 이력서 PDF 텍스트 추출
- `Python-Dotenv`: 환경 변수 관리
- `Requests`: HTTP 요청 (테스트용)

## 3. 프로그램 실행 방법 (How to Run)
1. **데이터베이스 설정**: 로컬 PostgreSQL 실행 및 데이터베이스 생성 (`interview_db`).
2. **환경 변수 설정**: `.env` 파일에 DB 접속 정보 및 OpenAI API Key 설정.
3. **서버 실행**:
   ```bash
   python server.py
   ```
4. **접속**: 웹 브라우저를 열고 `http://localhost:5000` 접속.

## 4. 주요 기능 (Key Features)

### 공통
- **회원가입/로그인**: 지원자 및 관리자 계정 생성, 로그인.
- **내 정보 수정**: 개인 정보 수정 (비밀번호 확인 절차 포함).

### 지원자 (Applicant)
- **채용 공고 확인**: 현재 등록된 공고 목록 및 상세 내용 확인.
- **이력서 업로드**: PDF 형식의 이력서 업로드.
- **AI 면접 진행**:
    - 웹캠/마이크 자동 연결 테스트.
    - AI 면접관의 음성 질문 (TTS).
    - 사용자의 음성 답변 녹음 및 텍스트 변환 (STT).
    - 실시간 꼬리 질문 생성 (LLM).
- **면접 결과 확인**: 합격/불합격 여부 및 상세 피드백 확인.

### 관리자 (Admin)
- **공고 관리**: 채용 공고 등록, 수정, 삭제.
- **지원자 현황**: 지원자 목록 조회 및 면접 결과 상세(점수, 평가 내용, 대화 기록) 확인.

## 5. 파일 구조 설명 (File Structure)
- **`server.py`**: 메인 FastAPI 백엔드 서버. API 엔드포인트 및 비즈니스 로직 처리.
- **`app.js`**: 프론트엔드 JavaScript. SPA 라우팅, API 호출, 미디어 레코딩, UI 인터랙션 담당.
- **`index.html`**: 메인 HTML 파일. UI 레이아웃 및 화면 구성.
- **`styles.css`**: 스타일시트.
- **`db/`**: 데이터베이스 초기화 및 마이그레이션 스크립트.
- **`uploads/`**: 업로드된 이력서 및 오디오 파일 저장소.

## 6. 사용된 AI 모델
- **GPT-4o**: 면접 질문 생성, 답변 평가, 최종 결과 분석.
- **Whisper-1**: 사용자 음성 답변을 텍스트로 변환 (STT).
