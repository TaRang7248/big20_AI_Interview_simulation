# AI 면접 시뮬레이션 프로그램 가이드북

본 가이드북은 웹 기반 AI 면접 시뮬레이션 프로그램의 개요, 시스템 환경, 실행 방법 및 주요 기능에 대해 설명합니다.

## 1. 프로젝트 개요
이 프로그램은 지원자가 웹을 통해 AI 면접관과 대화하며 실시간 면접을 경험할 수 있도록 돕는 시스템입니다. 지원자의 답변을 음성으로 인식(STT)하고, GPT-4o 모델을 통해 실시간으로 평가 및 다음 질문을 생성하며, 최종적으로 면접 결과를 분석하여 리포트를 제공합니다.

## 2. 개발 및 실행 환경
*   **Operating System**: Windows (권장)
*   **Language**: Python 3.9+, JavaScript (ES6+), HTML5, CSS3
*   **Framework**: FastAPI (Backend), Vanilla JS (Frontend)
*   **Database**: PostgreSQL
*   **API**: OpenAI API (GPT-4o, Whisper-1)

## 3. 프로그램 실행 방법

### 1) 사전 준비
- PostgreSQL 서버가 실행 중이어야 합니다.
- `.env` 파일에 `OPENAI_API_KEY`, `POSTGRES_PASSWORD` 등 필요한 설정이 완료되어 있어야 합니다.

### 2) 데이터베이스 설정
처음 실행하거나 테이블을 생성해야 할 경우 다음 스크립트를 순서대로 실행합니다.
```bash
python create_table.py
python migrate_db_v2.py
python migrate_db_v3.py
python migrate_db_v4.py
python migrate_db_v5.py
```

### 3) 서버 실행
```bash
python server.py
```
서버가 실행되면 자동으로 브라우저가 열리며 `http://localhost:5000`으로 접속됩니다.

## 4. 사용하는 주요 모델 및 라이브러리

| 구분 | 기술 / 모델 | 용도 |
| :--- | :--- | :--- |
| **AI LLM** | GPT-4o | 질문 추천, 답변 평가, 면접 결과 최종 분석 |
| **STT** | Whisper-1 | 지원자의 음성 답변을 텍스트로 변환 |
| **TTS** | Web Speech API | AI 면접관의 질문을 음성으로 출력 (브라우저 내장) |
| **Backend** | FastAPI | 비동기 API 서버 구축 |
| **Database** | psycopg2 | PostgreSQL 데이터베이스 연동 |
| **Frontend** | Vanilla JavaScript | SPA(Single Page Application) 구조 구현 |

## 5. 주요 기능 사용법

### 1) 회원가입 및 로그인
- 관리자(Admin)와 지원자(Applicant) 유형을 선택하여 가입할 수 있습니다.
- 중복 확인 기능을 통해 유효한 아이디를 생성합니다.

### 2) 공고 관리 (관리자 전용)
- 관리자는 면접 공고를 등록, 수정, 삭제할 수 있습니다.
- 각 공고에 대해 지원 직무와 마감일을 설정합니다.

### 3) AI 면접 진행 (지원자)
- 원하는 공고를 선택하고 **이력서(PDF)**를 업로드합니다.
- 카메라와 마이크 테스트를 거친 후 면접을 시작합니다.
- AI 면접관이 질문을 하면 음성으로 답변하고 **답변 제출** 버튼을 누릅니다.

### 4) 면접 결과 확인
- 면접이 종료되면 AI가 전체 대화 내용을 분석합니다.
- 기술(Tech), 문제해결, 의사소통, 비언어적 요소에 대한 점수와 총평이 제공됩니다.
- **수정 사항**: 이제 면접 결과 테이블(`interview_result`)에 지원자의 아이디가 함께 저장되어 관리가 용이해졌습니다.

## 6. 파일 구조 설명

```text
.
├── server.py               # FastAPI 서버 및 비즈니스 로직
├── index.html              # 메인 웹 페이지 구조
├── styles.css              # 전반적인 UI 스타일링
├── app.js                  # 프론트엔드 라우팅 및 인터랙션 로직
├── data.json               # 면접 질문 풀 기초 데이터
├── create_table.py         # 초기 테이블 생성 스크립트
├── migrate_db_v*.py        # 버전별 DB 스키마 변경 스크립트
├── uploads/                # 업로드된 이력서 및 오디오 파일 저장소
│   ├── resumes/
│   └── audio/
└── requirements.txt        # 필요한 Python 패키지 목록
```

## 7. 주요 문의 및 문제 해결
- **DB 연동 에러**: `.env` 파일의 설정 정보와 DB 서버의 실제 설정이 일치하는지 확인하십시오.
- **API 에러**: OpenAI API 키의 유효성과 잔액을 확인하십시오.
