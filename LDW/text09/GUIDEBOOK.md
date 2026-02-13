# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

본 문서는 AI 면접 시뮬레이션 프로젝트의 개요, 환경 설정, 실행 방법, 구성 요소 및 주요 기능을 설명합니다.

## 1. 시뮬레이션 개요
이 프로젝트는 웹 기반의 **AI 면접 시뮬레이션 플랫폼**입니다. 사용자는 이력서를 등록하고 AI 면접관과 음성으로 실시간 면접을 진행할 수 있습니다. AI는 사용자의 답변을 분석하여 다음 질문을 생성하고, 면접 종료 후 종합적인 평가 결과를 제공합니다.

### 주요 특징
- **음성 대화**: Microsoft Edge TTS와 OpenAI Whisper를 활용한 자연스러운 음성 인터랙션
- **이력서 기반 맞춤형 질문**: PDF 이력서를 분석하여 개인화된 면접 질문 생성
- **다단계 면접**: 자기소개 -> 직무 기술 -> 인성 및 가치관 -> 마무리 단계로 구성
- **관리자 기능**: 면접 공고 관리 및 지원자 현황/결과 확인

## 2. 시뮬레이션 환경 (Requirements)

### 시스템 요구사항
- **OS**: Windows, macOS, Linux (CUDA 지원 시 성능 향상)
- **Python**: 3.8 이상
- **Database**: PostgreSQL
- **Browser**: Chrome, Edge (마이크/카메라 접근 허용 필요)

### 사용된 라이브러리 및 모델

#### Backend (Python)
- **FastAPI**: 웹 서버 프레임워크
- **Uvicorn**: ASGI 서버
- **Psycopg2**: PostgreSQL 데이터베이스 연동
- **OpenAI API**: GPT-4o (질문/평가 생성), Whisper (STT)
- **Edge-TTS**: 음성 합성 (TTS, `ko-KR-HyunsuMultilingualNeural` 사용)
- **PyMuPDF (fitz)**: PDF 텍스트 추출 및 이미지 변환
- **EasyOCR**: 이미지 내 텍스트 추출 (OCR)
- **Torch / Numpy**: OCR 및 ML 연산 지원

#### Frontend
- **Vanilla JS (ES6+)**: SPA(Single Page Application) 구조 구현
- **HTML5 / CSS3**: UI/UX 디자인

## 3. 시뮬레이션 실행 방법

1. **데이터베이스 설정**
   - PostgreSQL 설치 및 실행
   - `interview_db` 데이터베이스 생성
   - `.env` 파일에 DB 접속 정보 설정

2. **환경 변수 설정 (.env)**
   ```env
   DB_HOST=localhost
   DB_NAME=interview_db
   DB_USER=postgres
   POSTGRES_PASSWORD=your_password
   OPENAI_API_KEY=your_openai_api_key
   ```

3. **서버 실행**
   ```bash
   uvicorn server:app --reload
   ```
   또는
   ```bash
   python server.py (if main block exists)
   ```

4. **접속**
   - 웹 브라우저에서 `http://localhost:8000/index.html` 접속

## 4. 파일 구조 설명

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── server.py             # 메인 백엔드 서버 (FastAPI)
├── index.html            # 메인 프론트엔드 HTML
├── app.js                # 프론트엔드 로직 (SPA, API 호출, 인터랙션)
├── styles.css            # 스타일 시트
├── requirements.txt      # 파이썬 의존성 목록
├── .env                  # 환경 설정 파일
├── uploads/              # 업로드된 파일 저장소 (이력서, 오디오)
│   ├── resumes/          # PDF 이력서
│   ├── audio/            # 사용자 답변 오디오 (WebM)
│   └── tts_audio/        # AI 질문 오디오 (MP3)
├── db/                   # 데이터베이스 스키마 및 마이그레이션 스크립트
└── test_voice_standalone.py # TTS 테스트 스크립트
```

## 5. 주요 기능 사용법

### 5.1 회원가입 및 로그인
- **지원자**: 이력서를 등록하고 면접을 볼 수 있습니다.
- **관리자**: 공고를 작성하고 지원자들의 면접 결과를 확인할 수 있습니다.

### 5.2 면접 공고 확인 및 지원 (지원자)
- 대시보드에서 현재 진행 중인 면접 공고를 확인합니다.
- '지원하기' 버튼을 누르면 이력서(PDF)를 업로드하고 면접을 준비합니다.

### 5.3 실전 AI 면접 (지원자)
1. **환경 점검**: 카메라와 마이크가 정상 작동하는지 확인합니다.
2. **면접 시작**: AI 면접관이 첫 번째 질문(자기소개)을 합니다.
3. **답변하기**: 질문을 듣고 마이크를 통해 답변합니다. 답변이 끝나면 '제출' 버튼을 누르거나 시간이 종료되면 자동 제출됩니다.
4. **꼬리 질문**: AI는 이전 답변을 분석하여 연관된 심층 질문을 던집니다.
5. **면접 종료**: 모든 질문 단계가 끝나면 면접이 종료되고 분석이 시작됩니다.

### 5.4 면접 결과 확인 (지원자/관리자)
- **지원자**: '내 면접 기록'에서 합격/불합격 여부를 확인합니다.
- **관리자**: '지원자 현황'에서 각 지원자의 상세 답변 내역, 이력서, 항목별 점수(기술, 문제해결, 의사소통, 태도)를 상세하게 검토할 수 있습니다.
