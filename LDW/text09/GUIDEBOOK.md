# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

이 문서는 웹 기반 AI 면접 시뮬레이션 프로그램의 설치, 실행, 기능 사용법 및 데이터 이관에 대한 상세한 안내를 담고 있습니다.

## 1. 개요 (Overview)
AI 면접 시뮬레이션은 사용자가 이력서를 업로드하고, 원하는 직무에 지원하여 실제 면접과 유사한 환경에서 AI 면접관과 대화하며 면접 연습을 할 수 있는 웹 애플리케이션입니다.
OpenAI의 GPT-4o 모델을 활용하여 이력서 기반의 맞춤형 질문을 생성하고, 지원자의 답변을 평가합니다. 또한 STT(Speech-to-Text) 기술을 통해 음성 답변을 텍스트로 변환하여 분석합니다.

## 2. 환경 설정 (Environment Setup)
이 프로젝트를 실행하기 위해서는 다음의 소프트웨어와 라이브러리가 필요합니다.

### 필수 소프트웨어
- **Python 3.8 이상**: 서버 및 백엔드 로직 실행
- **PostgreSQL**: 데이터베이스 관리 (Docker 컨테이너 사용 권장)
- **Tesseract OCR (선택)**: PDF 텍스트 추출 보조 (EasyOCR 사용 시 불필요할 수 있으나 설치 권장)

### 라이브러리 설치
프로젝트 루트 디렉터리(`C:\big20\big20_AI_Interview_simulation\LDW\text09`)에서 다음 명령어를 실행하여 필요한 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

> **참고**: `torch` (PyTorch)는 시스템 환경(CUDA 지원 여부)에 따라 별도 설치가 필요할 수 있습니다.

## 3. 프로그램 실행 방법 (Execution)

### 3.1. 데이터베이스 실행
PostgreSQL 데이터베이스가 실행 중이어야 합니다. Docker를 사용하는 경우, 해당 컨테이너가 켜져 있는지 확인하십시오.

### 3.2. 서버 실행
터미널에서 다음 명령어를 입력하여 FastAPI 서버를 실행합니다.

```bash
python server.py
# 또는 uvicorn을 직접 사용할 경우
# uvicorn server:app --reload
```

서버가 정상적으로 실행되면 `http://127.0.0.1:8000` 주소로 접속할 수 있습니다.

### 3.3. 웹 접속
브라우저(Chrome 권장)를 열고 `C:\big20\big20_AI_Interview_simulation\LDW\text09\index.html` 파일을 직접 열거나, VS Code의 Live Server 등을 통해 `index.html`을 실행합니다.

## 4. 주요 기능 및 사용법 (Features)

### 4.1. 회원가입 및 로그인
- `applicant`(지원자) 또는 `admin`(관리자) 계정으로 가입이 가능합니다.
- 로그인 후 각 권한에 맞는 대시보드로 이동합니다.

### 4.2. 채용 공고 관리 (관리자)
- 관리자는 채용 공고를 등록, 수정, 삭제할 수 있습니다.
- 공고에는 직무 제목, 내용, 마감기한이 포함됩니다.

### 4.3. 이력서 업로드 및 지원 (지원자)
- PDF 형식의 이력서를 업로드하여 특정 공고에 지원합니다.
- 업로드된 이력서는 AI가 분석하여 면접 질문 생성에 활용합니다.

### 4.4. 실전 AI 면접
- **자기소개**: 첫 질문으로 자기소개를 진행합니다.
- **꼬리물기 질문**: 지원자의 답변을 바탕으로 AI가 심층 질문을 생성합니다.
- **음성 답변**: 마이크를 통해 음성으로 답변하면 텍스트로 변환되어 저장됩니다.
- **평가**: 답변 내용, 태도 등을 종합적으로 평가하여 피드백을 제공합니다.

## 5. 파일 구조 설명 (File Structure)

```
text09/
├── server.py               # FastAPI 백엔드 메인 서버 파일
├── index.html              # 프론트엔드 메인 페이지
├── app.js                  # 프론트엔드 로직 (API 호출 등)
├── styles.css              # 스타일시트
├── requirements.txt        # 의존성 패키지 목록
├── db/                     # SQLite DB 파일 (레거시/참조용)
├── db_data/                # PostgreSQL 데이터 (Docker 볼륨)
├── uploads/                # 업로드된 이력서 및 오디오 파일 저장소
│   ├── resumes/            
│   └── audio/
├── export_db.py            # [NEW] 데이터베이스 백업 스크립트
├── import_db.py            # [NEW] 데이터베이스 복원 스크립트
└── interview_db_backup.json # [NEW] 백업 파일 (export_db.py 실행 결과)
```

## 6. 데이터 이관 가이드 (Data Migration)
다른 컴퓨터로 작업 환경을 옮기거나 데이터를 백업해야 할 때 사용합니다.

### 6.1. 데이터 내보내기 (Backup)
현재 컴퓨터에서 다음 명령어를 실행하여 DB 데이터를 `interview_db_backup.json` 파일로 저장합니다.

```bash
python export_db.py
```

> **주의**: 이 스크립트는 데이터베이스의 텍스트 데이터만 백업합니다. `uploads` 폴더에 있는 이력서(PDF) 및 오디오 파일은 **직접 복사**하여 옮겨야 합니다.

### 6.2. 데이터 가져오기 (Restore)
새로운 컴퓨터에서 PostgreSQL 데이터베이스를 설정한 후, 백업 파일(`interview_db_backup.json`)과 `uploads` 폴더를 해당 위치에 가져다 놓습니다. 그 후 다음 명령어를 실행합니다.

```bash
python import_db.py
```

이 스크립트는 중복된 데이터는 건너뛰고, 없는 데이터만 삽입합니다.

## 7. 설치된 모델 및 라이브러리 정보
- **FastAPI**: 고성능 웹 프레임워크
- **OpenAI API (GPT-4o)**: 지능형 면접 질문 생성 및 평가
- **Whisper (OpenAI)**: 고정밀 음성 인식 (STT)
- **EasyOCR / PyMuPDF**: 이력서(PDF/이미지) 텍스트 추출
- **Psycopg2**: PostgreSQL 데이터베이스 연동

---
작성일: 2026-02-13
작성자: AntiGravity Agent
