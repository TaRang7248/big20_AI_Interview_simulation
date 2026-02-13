# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 시뮬레이션 개요
이 프로젝트는 웹 기반의 AI 면접 시뮬레이션 플랫폼입니다. 사용자는 이력서를 등록하고, AI 면접관과 음성으로 실시간 면접을 진행할 수 있습니다. 면접이 종료되면 AI가 답변을 분석하여 평가 결과와 피드백을 제공합니다.

## 2. 주요 기능
- **회원 관리**: 회원가입, 로그인, 개인정보 수정
- **채용 공고 관리**: 관리자 및 작성자가 공고를 등록/수정/삭제
- **이력서 업로드**: PDF 형식의 이력서를 업로드하고 텍스트를 자동 추출
- **실시간 AI 면접**: 
    - **TTS (Text-to-Speech)**: AI 면접관이 음성으로 질문
    - **STT (Speech-to-Text)**: 사용자의 음성 답변을 텍스트로 변환
    - **LLM (Large Language Model)**: 답변 내용을 분석하고 꼬리물기 질문 생성
- **면접 결과 분석**: 면접 종료 후 기술, 문제해결, 의사소통, 태도 등을 종합 평가

## 3. 실행 환경 및 요구 사항
- **OS**: Windows (권장), macOS, Linux
- **Python**: 3.8 이상
- **Database**: PostgreSQL
- **필수 라이브러리**:
    - `fastapi`, `uvicorn`: 웹 서버
    - `psycopg2`: 데이터베이스 연동
    - `openai`: AI 기술 (LLM, STT)
    - `edge-tts`: 음성 합성
    - `easyocr`, `pymupdf (fitz)`: 이력서 OCR 및 텍스트 추출
    - `torch`: Deep Learning 프레임워크 (OCR용)

## 4. 실행 방법
1. **데이터베이스 설정**: PostgreSQL이 실행 중이어야 하며, `.env` 파일에 DB 접속 정보가 설정되어 있어야 합니다.
2. **패키지 설치**:
   ```bash
   pip install -r requirements.txt
   ```
3. **서버 실행**:
   프로젝트 루트 폴더(`text09`)에서 다음 명령어를 실행합니다.
   ```bash
   python server.py
   ```
   - 서버가 시작되면 자동으로 웹 브라우저가 열리며 `http://localhost:5000`으로 접속됩니다.

## 5. 파일 구조 설명
이번 리팩토링을 통해 기능별로 모듈화된 구조는 다음과 같습니다.

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── app\
│   ├── __init__.py
│   ├── config.py          # 환경변수, 경로 설정
│   ├── database.py        # DB 연결 관리
│   ├── main.py            # FastAPI 앱 초기화 및 라우터 통합
│   ├── models.py          # 데이터 모델 (Pydantic)
│   ├── routers\           # API 엔드포인트
│   │   ├── admin.py       # 관리자 기능
│   │   ├── auth.py        # 인증 (로그인/가입)
│   │   ├── interview.py   # 면접 진행 로직
│   │   ├── job.py         # 공고 관리
│   │   └── user.py        # 사용자 정보 관리
│   └── services\          # 핵심 비즈니스 로직
│       ├── analysis_service.py # 면접 결과 분석
│       ├── llm_service.py      # OpenAI GPT 연동 (질문 생성, 평가)
│       ├── pdf_service.py      # PDF 처리 및 OCR
│       ├── stt_service.py      # Whisper STT 구현
│       └── tts_service.py      # Edge TTS 구현
├── server.py              # 실행 진입점 (Launcher)
├── index.html             # 메인 프론트엔드 페이지
├── app.js                 # 프론트엔드 로직
├── styles.css             # 스타일 시트
└── requirements.txt       # 의존성 목록
```

## 6. 사용된 모델 및 라이브러리
- **LLM**: GPT-4o (OpenAI) - 면접 질문 생성, 이력서 요약, 답변 평가
- **STT**: Whisper-1 (OpenAI) - 사용자 음성 인식
- **TTS**: Microsoft Edge TTS (`ko-KR-HyunsuMultilingualNeural` 등)
- **OCR**: EasyOCR - 이력서(PDF) 이미지 텍스트 추출

---
**참고**: 서버 실행 중 `ImportError` 등이 발생하면 `pip install`을 통해 필요한 라이브러리가 설치되었는지 확인해주세요.
