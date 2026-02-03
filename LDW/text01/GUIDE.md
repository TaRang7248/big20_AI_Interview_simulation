# AI 면접 시뮬레이션 가이드북

본 프로그램은 FastAPI와 LLM(OpenAI)을 활용하여 지원자의 직무에 맞는 면접 질문을 생성하고, 답변을 분석하여 실시간으로 꼬리 질문 및 평가를 수행하는 시스템입니다.

## 1. 주요 기능
- **직무 맞춤형 질문 생성**: 지원자가 입력한 이름과 직업을 바탕으로 첫 질문을 생성합니다.
- **실시간 꼬리 질문**: 지원자의 답변이 부족하거나 추가 설명이 필요하다고 판단되면 LLM이 자동으로 꼬리 질문을 던집니다.
- **데이터 저장 (Dual DB)**:
    - **PostgreSQL (pgvector)**: 모든 면접 질문, 답변, 평가 결과를 벡터 임베딩과 함께 저장하여 향후 유사 답변 검색 및 분석에 사용합니다.
    - **SQLite (interview_save.db)**: 면접 진행 내역을 로컬 파일에 즉시 기록하여 보존합니다.
- **자동 브라우저 실행**: 프로그램을 실행하면 자동으로 인터페이스(Web UI)가 브라우저에서 열립니다.

## 2. 설치 및 실행 방법

### 사전 준비
1. **Python 3.9+** 설치가 필요합니다.
2. **PostgreSQL**과 **pgvector** 확장 프로그램이 설치되어 있어야 합니다.
3. **OpenAI API Key**가 필요합니다.

### 설치 단계
1. `.env.example` 파일을 복사하여 `.env` 파일을 생성합니다.
   ```bash
   copy .env.example .env
   ```
2. `.env` 파일에 자신의 `OPENAI_API_KEY`와 PostgreSQL 접속 정보를 입력합니다.
3. 필요한 패키지를 설치합니다.
   ```bash
   pip install fastapi uvicorn openai sqlalchemy psycopg2-binary pgvector python-dotenv jinja2
   ```

### 실행 방법
1. 터미널에서 다음 명령어를 실행합니다.
   ```bash
   python main.py
   ```
2. 자동으로 브라우저가 열리며 `http://127.0.0.1:8000` 접속됩니다.

## 3. 프로그램 구조 (Vertical Slice)
- `main.py`: 서버 실행 및 앱 초기화, 자동 브라우저 로직
- `api/`: API 엔드포인트 및 스키마 정의
- `services/`: LLM 대화 로직 및 면접 흐름 오케스트레이션
- `db/`: PostgreSQL 및 SQLite 연동 로직
- `templates/`: 사용자 인터페이스 (HTML/CSS/JS)
- `db/interview_save.db`: 면접 세션 로그 저장 파일

## 4. 참고 사항
- 프로그램의 모든 텍스트 인터페이스는 **한국어**로 구성되어 있습니다.
- 면접 결과는 PostgreSQL의 `interview_results` 테이블과 SQLite의 `interview_logs` 테이블에서 확인할 수 있습니다.
