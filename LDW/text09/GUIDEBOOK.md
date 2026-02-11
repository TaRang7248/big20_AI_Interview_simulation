# AI 면접 시뮬레이션 프로그램 가이드북 (GUIDEBOOK)

본 가이드북은 웹 기반 AI 면접 시뮬레이션 프로그램의 개요, 설치 환경, 실행 방법 및 주요 기능에 대해 설명합니다.

---

## 1. 개요 (Overview)
본 프로그램은 지원자가 AI 면접관과 실시간으로 대화를 나누며 면접을 경험할 수 있는 시뮬레이션 도구입니다. 
- **목적**: 면접 연습 및 지원자 답변 분석을 통한 역량 평가 지원
- **핵심 가치**: 사용자 경험 중심의 UI, 실시간 STT/TTS 연동, LLM을 활용한 심층 면접 질문 생성

## 2. 개발 환경 (Environment)
프로그램 실행을 위해 다음과 같은 환경이 권장됩니다.
- **OS**: Windows / macOS / Linux (최신 브라우저 권장)
- **Backend**: Python 3.9+ (FastAPI)
- **Database**: PostgreSQL 13+
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3

## 3. 프로그램 실행 방법 (Getting Started)

### 3.1 종속성 설치
```bash
pip install -r requirements.txt
```

### 3.2 환경 변수 설정
프로젝트 루트 폴더 또는 상위 폴더의 `.env` 파일에 다음 항목을 설정해야 합니다.
- `OPENAI_API_KEY`: OpenAI API 키
- `DB_HOST`, `DB_NAME`, `DB_USER`, `POSTGRES_PASSWORD`, `DB_PORT`: PostgreSQL 접속 정보

### 3.3 서버 실행
```bash
python server.py
```
서버 실행 후 브라우저에서 `http://localhost:8000`으로 접속합니다.

## 4. 사용하는 모델 및 라이브러리 (Models & Libraries)

### 4.1 AI 모델
- **GPT-4o (OpenAI)**: 면접 질문 생성, 답변 평가 및 최종 결과 분석
- **Whisper-1 (OpenAI)**: 지원자의 음성 답변을 텍스트로 변환 (STT)

### 4.2 주요 라이브러리
- **FastAPI**: 효율적인 API 서버 구축
- **psycopg2**: PostgreSQL 데이터베이스 연동
- **Web Speech API (Browser Sync)**: 실시간 음성 인식 피드백 및 음성 출력 (TTS)
- **pypdf**: 이력서(PDF) 텍스트 추출

## 5. 주요 기능 사용법 (Main Features)

- **회원가입/로그인**: 면접자와 관리자 유형으로 가입 및 로그인 가능
- **공고 관리 (관리자)**: 면접 공고를 등록, 수정, 삭제 및 지원 현황 확인 가능
- **이력서 업로드 (면접자)**: 면접 시작 전 PDF 형식의 이력서 등록
- **실시간 AI 면접**: 
    - AI가 질문을 말하는 동안에는 '답변 제출' 버튼이 비활성화됩니다.
    - 지원자의 음성은 실시간으로 녹음 및 분석됩니다.
- **결과 확인**: 면접 종료 후 AI의 다각도 평가(기술, 문제해결 등) 및 합격/불합격 결과 확인

## 6. 파일 구조 설명 (File Structure)

```text
text09/
├── server.py             # FastAPI 백엔드 서버 (API 및 DB 로직)
├── index.html            # 메인 SPA HTML 구조
├── app.js                # 프론트엔드 비즈니스 로직 및 API 연동
├── styles.css            # 웹 애플리케이션 스타일링
├── requirements.txt      # Python 종속성 목록
├── uploads/              # 이력서 및 오디오 파일 저장소
├── db/                   # 데이터베이스 스크립트 (선택사항)
├── create_table.py       # DB 테이블 초기 생성 스크립트
└── migrate_*.py          # DB 스키마 마이그레이션 스크립트들
```

---
*본 가이드북은 프로젝트의 원활한 운영과 유지보수를 위해 작성되었습니다.*
