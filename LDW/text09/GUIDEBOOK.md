# 웹 기반 AI 면접 시뮬레이션 가이드북

본 가이드북은 웹 기반 AI 면접 시뮬레이션 프로그램의 개요, 환경 설정, 실행 방법, 사용 기술, 주요 기능 사용법, 그리고 파일 구조에 대해 설명합니다.

## 1. 개요 (Overview)
이 프로그램은 사용자가 가상의 AI 면접관과 함께 모의 면접을 진행할 수 있는 웹 애플리케이션입니다.
- **주요 목적**: 실제 면접 상황과 유사한 경험 제공 및 피드백
- **핵심 기능**:
  - PDF 이력서 업로드 및 자동 분석 (OCR)
  - 맞춤형 면접 질문 생성 (OpenAI GPT-4o)
  - 음성 답변 녹음 및 텍스트 변환 (Whisper STT)
  - 실시간 답변 평가 및 꼬리 질문 생성
  - 최종 면접 결과 분석 및 리포트 제공

## 2. 환경 설정 (Environment Setup)
이 프로그램은 Python 3.10 이상 기반의 환경에서 실행됩니다.

### 필수 요구 사항
- **OS**: Windows, macOS, Linux
- **Python**: 3.10+
- **PostgreSQL**: 로컬 또는 원격 데이터베이스 서버 필요
- **OpenAI API Key**: `.env` 파일에 설정 필요

### 설치 방법
1. **리포지토리 클론 또는 다운로드**
2. **가상 환경 생성 및 활성화 (권장)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Mac/Linux
   venv\Scripts\activate     # Windows
   ```
3. **필수 라이브러리 설치**
   ```bash
   pip install -r requirements.txt
   # PyTorch (CUDA 지원 버전, 필요시 별도 설치)
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
4. **환경 변수 설정**
   - `.env` 파일을 프로젝트 루트에 생성하고 다음 내용을 작성합니다.
     ```env
     OPENAI_API_KEY=your_openai_api_key
     DB_HOST=localhost
     DB_NAME=interview_db
     DB_USER=postgres
     DB_PASS=your_password
     DB_PORT=5432
     ```
5. **데이터베이스 초기화**
   - `create_table.py` 등을 실행하여 필요한 테이블을 생성합니다.
   ```bash
   python create_table.py
   ```

## 3. 프로그램 실행 방법 (How to Run)
1. **서버 실행**
   ```bash
   uvicorn server:app --reload
   ```
   - 서버가 `http://127.0.0.1:8000` 에서 실행됩니다.

2. **웹 접속**
   - 브라우저를 열고 `http://127.0.0.1:8000/index.html` (또는 해당 파일 경로)로 접속합니다.
   - 프론트엔드 파일(`index.html`)을 직접 열거나, 정적 파일 서버를 통해 호스팅할 수도 있습니다.
   - **주의**: 카메라/마이크 권한을 위해 `localhost` 또는 HTTPS 환경에서 실행해야 합니다.

## 4. 사용 모델 및 라이브러리 (Tech Stack)

### Backend
- **FastAPI**: 고성능 비동기 Python 웹 프레임워크
- **Uvicorn**: ASGI 서버
- **PostgreSQL + Psycopg2**: 데이터베이스 관리

### AI / ML
- **EasyOCR**: PDF 이력서 텍스트 추출 (OCR)
  - *특징*: 한국어/영어 지원, GPU 가속 지원
  - *역활*: 업로드된 이미지/PDF 형식의 이력서 내용을 텍스트로 변환
- **PyMuPDF (fitz)**: PDF 파일을 이미지로 변환하여 OCR 전처리
- **OpenAI GPT-4o**: 
  - *역활*: 이력서 기반 질문 생성, 답변 평가, 면접관 페르소나 연기
- **OpenAI Whisper (API)**:
  - *역활*: 사용자의 음성 답변을 텍스트로 변환 (STT)

### Frontend
- **HTML5 / CSS3 / Vanilla JavaScript**: 가볍고 빠른 웹 인터페이스
- **Web APIs**: MediaDevices API (카메라/마이크), Fetch API

## 5. 주요 기능 사용법 (User Manual)

### 1) 회원가입 및 로그인
- 초기 화면에서 회원가입을 진행합니다.
- '면접자' 또는 '관리자' 유형을 선택할 수 있습니다.

### 2) 이력서 등록
- 로그인 후 [공고 목록]에서 원하는 직무를 선택하고 [지원하기]를 클릭합니다.
- **PDF 형식**의 이력서를 업로드합니다.
- 시스템이 이력서 내용을 자동으로 인식하여 면접 질문 생성에 활용합니다.

### 3) 환경 테스트 및 면접 시작
- 카메라와 마이크 작동 여부를 확인합니다.
- [면접 시작] 버튼을 누르면 AI 면접관과 연결됩니다.

### 4) 면접 진행
- AI가 질문을 하면 마이크를 통해 답변합니다.
- [답변 제출] 버튼을 누르면 답변이 전송되고 분석됩니다.
- 총 12개 내외의 질문(자기소개, 직무 기술, 인성, 마무리)이 진행됩니다.

### 5) 결과 확인
- 면접이 종료되면 AI가 종합적인 평가 리포트를 생성합니다.
- [내 면접 기록] 메뉴에서 과거 면접 결과와 피드백을 확인할 수 있습니다.

## 6. 파일 구조 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── server.py              # 메인 백엔드 서버 (FastAPI)
├── index.html             # 메인 프론트엔드 UI
├── app.js                 # 프론트엔드 로직 (API 호출, UI 제어)
├── styles.css             # 스타일 시트
├── requirements.txt       # 의존성 패키지 목록
│
├── uploads/               # 파일 업로드 디렉토리
│   ├── resumes/           # 이력서 저장소
│   └── audio/             # 음성 답변 저장소
│
├── db/                    # DB 관련 파일 (스키마 등)
├── *.py                   # 각종 유틸리티 및 테스트 스크립트
│   ├── create_table.py    # DB 테이블 생성
│   ├── verify_ocr_test.py # OCR 기능 테스트
│   └── ...
│
└── GUIDEBOOK.md           # 본 가이드북
```
