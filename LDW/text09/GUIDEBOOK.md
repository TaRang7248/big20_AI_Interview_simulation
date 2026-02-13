# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 시뮬레이션 개요
본 프로젝트는 사용자의 이력서와 지원 직무를 기반으로 AI가 면접관이 되어 실전과 유사한 면접 경험을 제공하는 웹 기반 시뮬레이션입니다.
LLM(Large Language Model)을 활용하여 지원자의 답변을 분석하고, 꼬리 질문을 생성하며, 피드백을 제공합니다.

---

## 2. 시뮬레이션 환경
-   **OS**: Windows (테스트 환경)
-   **Language**: Python 3.10+
-   **Framework**: FastAPI (Backend)
-   **Database**: PostgreSQL
-   **AI Engines**:
    -   **LLM**: OpenAI GPT-4o (질문 생성 및 답변 평가, 이력서 요약)
    -   **STT**: OpenAI Whisper (음성 인식)
    -   **TTS**: OpenAI TTS (음성 합성)

---

## 3. 실행 방법

### 사전 준비
1.  Python 및 PostgreSQL 설치
2.  가상 환경 생성 및 활성화 (권장)
3.  패키지 설치: `pip install -r requirements.txt`
4.  `.env` 파일 설정 (DB 접속 정보 및 OpenAI API Key)

### 서버 실행
cmd 또는 터미널에서 프로젝트 루트(`C:\big20\big20_AI_Interview_simulation\LDW\text09`)로 이동 후 다음 명령어를 실행합니다.

```bash
python server.py
```

-   서버가 시작되면 브라우저가 자동으로 열립니다 (`http://localhost:5000`).
-   API 문서는 `http://localhost:5000/docs`에서 확인할 수 있습니다.

---

## 4. 모델 및 라이브러리 목록

| 구분 | 이름 | 용도 |
| :--- | :--- | :--- |
| **Framework** | **FastAPI** | 고성능 웹 프레임워크 |
| | **Uvicorn** | ASGI 서버 |
| **Database** | **Psycopg2** | PostgreSQL 어댑터 |
| **AI / ML** | **OpenAI API** | GPT-4o, Whisper, TTS 모델 사용 |
| **Utilities** | **PyPDF2** | PDF 이력서 텍스트 추출 |
| | **Python-Multipart** | 파일 업로드 처리 |
| | **Webbrowser** | 브라우저 자동 실행 |

---

## 5. 주요 기능 사용법

### 1) 회원가입 및 로그인
-   지원자(Applicant) 또는 관리자(Admin)로 회원가입 후 로그인합니다.

### 2) 이력서 등록
-   [이력서 등록] 페이지에서 PDF 형식의 이력서를 업로드하고, 지원할 직무를 선택합니다.

### 3) 면접 시작
-   [면접 시작] 버튼을 누르면 AI 면접관이 자기소개를 요청하며 면접이 시작됩니다.
-   면접은 총 12개의 질문으로 구성됩니다.
    -   **1번**: 자기소개
    -   **2~6번**: 직무 기술 (Technical Skill)
    -   **7~11번**: 인성 및 가치관 (Culture Fit)
    -   **12번**: 마무리 질문

### 4) 답변 및 진행
-   질문을 듣고 마이크를 통해 답변을 녹음합니다.
-   답변이 완료되면 AI가 내용을 분석하고 다음 질문을 생성합니다.
-   이때, **등록한 이력서의 내용**과 **직무별 기출 질문**을 바탕으로 맞춤형 질문이 제시됩니다.

### 5) 결과 확인
-   면접이 종료되면 [결과 페이지]에서 합격/불합격 여부와 AI의 상세 피드백을 확인할 수 있습니다.

---

## 6. 파일 구조 설명

```
C:\big20\big20_AI_Interview_simulation\LDW\text09
├── app/
│   ├── main.py              # FastAPI 앱 초기화 및 설정
│   ├── models.py            # Pydantic 데이터 모델 정의
│   ├── database.py          # DB 연결 및 세션 관리
│   ├── config.py            # 환경 변수 및 설정 로드
│   ├── routers/             # API 엔드포인트
│   │   ├── interview.py     # 면접 진행 로직 (핵심)
│   │   ├── auth.py          # 인증 관련
│   │   └── ...
│   └── services/            # 비즈니스 로직 및 외부 API 연동
│       ├── llm_service.py   # OpenAI GPT 연동 (질문 생성, 평가)
│       ├── stt_service.py   # Whisper STT 연동
│       ├── tts_service.py   # TTS 연동
│       └── pdf_service.py   # PDF 처리
├── scripts/                 # 유틸리티 및 데이터베이스 스크립트
├── static/                  # 프론트엔드 정적 파일 (HTML, CSS, JS)
├── uploads/                 # 사용자 업로드 파일 저장소
├── server.py                # 서버 실행 진입점
├── requirements.txt         # 의존성 패키지 목록
└── GUIDEBOOK.md             # 본 가이드북
```
