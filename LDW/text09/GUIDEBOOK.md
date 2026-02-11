# AI 면접 시뮬레이션 가이드북 (AI Interview Simulation Guidebook)

본 프로젝트는 OpenAI의 GPT-4o와 Whisper 모델을 활용하여 실시간으로 면접 질문을 생성하고 답변을 평가하는 웹 기반 AI 면접 시뮬레이션 시스템입니다.

## 1. 프로젝트 개요
사용자가 직접 이력서를 업로드하고 원하는 직무의 공고에 지원하면, AI 면접관이 이력서와 직무 내용을 바탕으로 맞춤형 질문을 던집니다. 면접 종료 후에는 기술 능력, 문제 해결 능력, 의사소통 능력 등에 대한 종합적인 평가 결과를 제공합니다.

## 2. 개발 및 실행 환경
- **OS**: Windows (테스트 완료)
- **Backend**: Python 3.9+ (FastAPI)
- **Frontend**: Vanilla JS, HTML5, CSS3
- **Database**: PostgreSQL
- **AI API**: OpenAI API (GPT-4o, Whisper-1)

## 3. 프로그램 실행 방법

### 3.1 사전 준비
1. PostgreSQL 데이터베이스를 설치하고 `interview_db`를 생성합니다.
2. 프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 정보를 입력합니다:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   POSTGRES_PASSWORD=your_db_password
   DB_HOST=localhost
   DB_NAME=interview_db
   DB_USER=postgres
   DB_PORT=5432
   ```

### 3.2 패키지 설치
터미널에서 필요한 라이브러리를 설치합니다:
```bash
pip install -r requirements.txt
```

### 3.3 초기 데이터베이스 설정
테이블을 생성하고 초기 데이터를 설정합니다:
```bash
python create_table.py
python migrate_db_v3.py  # Interview_Result 테이블 생성 등
```

### 3.4 서버 실행
서버를 실행하면 자동으로 브라우저(`http://localhost:5000`)가 열립니다:
```bash
python server.py
```

## 4. 사용하는 주요 모델 및 라이브러리

### 4.1 AI 모델
- **GPT-4o**: 면접 질문 생성, 답변 평가, 최종 결과 분석 수행
- **Whisper-1**: 지원자의 음성 답변을 텍스트로 변환 (STT)

### 4.2 주요 라이브러리
- **FastAPI**: 효율적인 비동기 API 서버 구축
- **psycopg2**: PostgreSQL 데이터베이스 연동
- **OpenAI SDK**: OpenAI API 통신
- **PyPDF**: PDF 이력서 텍스트 추출
- **Web Speech API (Browser)**: AI 질문을 음성으로 출력 (TTS)

## 5. 주요 기능 사용법

### 5.1 회원 관리
- **회원가입/로그인**: 면접자와 관리자 유형으로 가입 가능
- **정보 수정**: 이메일, 주소, 전화번호 및 비밀번호 변경 기능

### 5.2 면접 준비 (지원자)
- **공고 확인**: 등록된 채용 공고 리스트 확인 및 상세 정보 조회
- **이력서 업로드**: 지원 시 PDF 형식의 이력서 등록 필수
- **환경 테스트**: 카메라 및 마이크 작동 여부 자동 확인

### 5.3 면접 진행
- **실시간 Q&A**: AI 면접관의 음성 질문에 음성으로 답변
- **자동 타이머**: 각 질문당 제한 시간(기존 15초 -> 120초로 변경됨) 내 답변
- **진행 단계**: 자기소개 -> 직무 기술 -> 인성 -> 마무리 단계로 총 12개 질문 구성

### 5.4 결과 확인
- **최종 평가**: 면접 종료 후 4가지 지표(기술, 문제해결, 의사소통, 태도) 점수 및 합격 여부 확인
- **관리자 기능**: 전체 지원자의 면접 기록(질문, 답변, 개별 평가) 및 이력서 상세 조회

## 6. 파일 구조 설명

```text
LDW/text09/
├── server.py              # FastAPI 백엔드 서버 (API 엔드포인트 및 LLM 로직)
├── index.html             # 메인 웹 페이지 구조
├── app.js                 # 프론트엔드 비동기 로직 및 UI 제어
├── styles.css             # 웹 페이지 스타일 시트
├── requirements.txt       # 설치가 필요한 Python 패키지 목록
├── create_table.py        # 기본 테이블 생성 스크립트
├── migrate_db_v*.py       # 데이터베이스 구조 변경(마이그레이션) 스크립트
├── uploads/               # 업로드된 이력서(resumes) 및 녹음 파일(audio) 저장소
└── verify_*.py            # 각 기능별 API 작동 검증 스크립트
```
