# AI 면접 시뮬레이션 가이드북 (AI Interview Simulation Guidebook)

본 문서는 **웹 기반 AI 면접 시뮬레이션** 프로그램의 개요, 환경 설정, 실행 방법 및 주요 기능을 설명합니다.

## 1. 개요 (Overview)
이 프로젝트는 실제 면접 상황을 시뮬레이션하기 위해 개발된 **AI 기반 웹 애플리케이션**입니다.
사용자는 이력서(PDF)를 업로드하고, **OpenAI GPT-4o** 기반의 AI 면접관과 음성으로 대화하며 모의 면접을 진행할 수 있습니다.
면접이 종료되면 AI가 답변 내용을 분석하여 기술 역량, 문제 해결 능력, 의사소통 능력 등을 평가합니다.

## 2. 시스템 요구 사항 (System Requirements)
- **OS**: Windows / macOS / Linux
- **Python**: 3.8 이상
- **Database**: PostgreSQL
- **Browser**: Chrome, Edge (음성 인식/녹음 기능 지원 브라우저)
- **Hardware**: 마이크, 웹캠 (선택 사항)

## 3. 환경 설정 (Environment Setup)

### 3.1. 필수 라이브러리 설치
프로젝트 폴더에서 다음 명령어를 실행하여 필요한 패키지를 설치하십시오.
```bash
pip install -r requirements.txt
```
*(만약 `requirements.txt`가 없다면 다음 패키지들이 필요합니다: `fastapi`, `uvicorn`, `psycopg2`, `openai`, `python-multipart`, `python-dotenv`, `pymupdf` (fitz), `easyocr`, `torch` 등)*

### 3.2. 데이터베이스 설정 (Database)
1. PostgreSQL을 설치하고 실행합니다.
2. `interview_db` 데이터베이스를 생성합니다 (또는 `.env`에서 설정 가능).
3. `.env` 파일을 프로젝트 루트에 생성하고 아래 내용을 설정합니다.
   ```env
   DB_HOST=localhost
   DB_NAME=interview_db
   DB_USER=postgres
   POSTGRES_PASSWORD=your_password
   OPENAI_API_KEY=your_openai_api_key_here
   ```

### 3.3. 테이블 생성
최초 실행 시 데이터베이스 테이블을 생성해야 합니다.
```bash
python create_table.py
```

## 4. 프로그램 실행 (Execution)
서버를 실행하면 자동으로 브라우저가 열리며(http://localhost:5000), 접속할 수 있습니다.

```bash
python server.py
```
또는 `uvicorn`을 직접 사용할 수도 있습니다:
```bash
uvicorn server:app --host 0.0.0.0 --port 5000 --reload
```

## 5. 주요 기능 사용법 (Features)

### 5.1. 회원가입 및 로그인
- 초기 실행 시 `회원가입`을 통해 계정을 생성합니다.
- `관리자` 권한으로 가입하면 면접 공고를 생성할 수 있습니다.
- `면접자` 권한으로 가입하면 공고에 지원하고 면접을 볼 수 있습니다.

### 5.2. 이력서 등록 (Resume Upload)
- 면접자는 지원 시 **PDF 형식**의 이력서를 필수로 업로드해야 합니다.
- **[NEW] AI 이력서 요약 기능**: 업로드된 이력서는 AI가 자동으로 분석하여 **핵심 역량, 주요 프로젝트, 경력 사항**을 요약하므로, 면접 질문의 정확도가 향상됩니다.

### 5.3. AI 면접 진행
1. 공고 지원 후 `면접 시작` 버튼을 누릅니다.
2. 카메라와 마이크 권한을 허용합니다.
3. AI 면접관이 첫 질문(자기소개)을 합니다.
4. 답변 후 `답변 제출` 버튼을 누르면 음성이 녹음되어 전송됩니다.
5. AI가 답변을 분석하고 꼬리 질문을 이어갑니다.

### 5.4. 결과 분석
- 면접 종료 후 `내 면접 기록`에서 결과를 확인할 수 있습니다.
- 관리자는 지원자들의 면접 점수와 상세 평가 내용을 조회할 수 있습니다.

## 6. 기술 스택 (Tech Stack)

### Backend
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL (`psycopg2`)
- **AI Core**:
  - **LLM**: OpenAI GPT-4o (면접 진행 및 평가, 이력서 요약)
  - **STT**: OpenAI Whisper (음성 -> 텍스트 변환)
  - **OCR**: EasyOCR, PyMuPDF (PDF 이력서 텍스트 추출)

### Frontend
- **Language**: HTML5, CSS3, JavaScript (Vanilla JS)
- **Styling**: Custom CSS (`styles.css`)

## 7. 주요 파일 구조 (File Structure)
- `server.py`: 메인 백엔드 서버 로직 (API 엔드포인트 포함)
- `create_table.py`: DB 테이블 초기화 스크립트
- `index.html`: 메인 웹 페이지 (SPA 구조)
- `app.js`: 프론트엔드 로직 (API 호출, UI 제어)
- `styles.css`: 스타일 시트
- `uploads/`: 업로드된 이력서 및 음성 파일 저장소
- `migration_*.py`: DB 스키마 변경 이력 관리 스크립트들
