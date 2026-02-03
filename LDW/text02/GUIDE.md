# AI 면접 시뮬레이션 가이드북 (User Guide)

본 프로그램은 선진화된 AI 기술을 활용하여 실제와 유사한 면접 경험을 제공하는 시스템입니다.

## 🚀 주요 기능

1. **지능형 질문 생성 (RAG)**
   - 기존의 면접 질문 데이터베이스(PostgreSQL/pgvector)에서 지원자의 직무와 유사한 기출 질문을 찾아 참고합니다.
   - LLM이 직무에 최적화된 맞춤형 첫 질문을 생성합니다.

2. **실시간 음성 인식 (STT)**
   - OpenAI Whisper 모델을 사용하여 사용자의 음성 답변을 즉시 텍스트로 변환합니다.
   - 면접 중 실시간으로 본인의 답변이 텍스트로 표시되는 것을 확인할 수 있습니다.

3. **꼬리 질문 및 평가**
   - 사용자의 답변 내용이 미흡하거나 추가 설명이 필요하다고 판단될 경우, LLM이 '꼬리 질문(Follow-up)'을 생성합니다.
   - 모든 답변은 점수(0-100)와 피드백이 포함된 JSON 형태로 분석되어 저장됩니다.

4. **이중 데이터 저장**
   - 면접 진행 로그: `db/interview_save.db` (SQLite)
   - 결과 및 임베딩 분석: `interview_db` (PostgreSQL)

## 🛠️ 시작하기

1. **환경 설정**
   - 프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 입력합니다.
     ```env
     OPENAI_API_KEY=your_api_key_here
     POSTGRES_USER=postgres
     POSTGRES_PASSWORD=your_password
     POSTGRES_HOST=localhost
     POSTGRES_PORT=5432
     POSTGRES_DB=interview_db
     ```

2. **프로그램 실행**
   - 터미널에서 아래 명령어를 실행합니다.
     ```bash
     python main.py
     ```
   - 실행과 동시에 브라우저가 자동으로 열리며 면접 인터페이스로 접속됩니다.

3. **면접 진행**
   - 이름과 지원 직무를 입력하고 '면접 시작하기'를 누릅니다.
   - 질문에 대해 마이크 버튼을 눌러 음성으로 답변하거나, 텍스트로 입력할 수 있습니다.
   - 모든 면접 데이터는 실시간으로 저장됩니다.

## 📁 파일 구조

- `main.py`: 서버 실행 및 브라우저 자동 접속 제어
- `api/interview.py`: 면접 관련 API 엔드포인트
- `services/`: STT, LLM, 면접 비즈니스 로직
- `db/`: 데이터베이스 모델 및 초기화 스크립트
- `templates/index.html`: 프리미엄 웹 인터페이스

---
*본 시뮬레이션은 사용자의 면접 역량 강화를 위해 설계되었습니다.*
