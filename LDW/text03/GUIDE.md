# AI 면접 시뮬레이션 프로그램 가이드북

본 프로그램은 FastAPI, OpenAI LLM, Whisper STT 기술을 활용하여 실제 면접 환경을 시뮬레이션하는 도구입니다.

## 주요 기능
1. **맞춤형 면접 지원**: 지원자의 이름과 지원 직무를 기반으로 개인 맞춤형 면접 질문을 생성합니다.
2. **실시간 음성 인식 (STT)**: Whisper 모델을 사용하여 사용자의 음성 답변을 실시간으로 텍스트로 변환하여 화면에 표시합니다.
3. **지능형 질문 생성**: 답변 내용에 따라 추가적인 꼬리 질문을 생성하여 심층 면접을 진행합니다.
4. **결과 분석 및 저장**: 각 답변에 대한 LLM 평가 JSON을 생성하고, PostgreSQL(pgvector) 및 SQLite에 안전하게 저장합니다.

## 시스템 요구 사항
- Python 3.9 이상
- PostgreSQL (pgvector 확장 설치 필요)
- OpenAI API Key (.env 파일에 설정)

## 실행 방법
1. **환경 설정**: `.env` 파일에 필요한 환경 변수를 설정합니다.
   ```env
   OPENAI_API_KEY=your_api_key_here
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=interview_db
   ```
2. **프로그램 실행**:
   ```bash
   python main.py
   ```
3. **자동 접속**: 프로그램 실행 시 브라우저가 자동으로 열려 `http://127.0.0.1:8000`에 접속합니다.

## 사용 방법
1. 메인 화면에서 **이름**과 **지원 직무**를 입력합니다.
2. '면접 시작' 버튼을 누르면 첫 번째 질문이 출력됩니다.
3. 질문을 듣고(또는 읽고) '답변하기' 버튼을 눌러 음성으로 답변합니다.
4. 답변하는 동안 실시간으로 텍스트가 표시됩니다.
5. 답변 완료 시 LLM이 내용을 분석하여 추가 질문 또는 다음 질문을 생성합니다.
6. 모든 면접이 완료되면 결과가 자동으로 저장됩니다.

## 데이터 저장 경로
- 기출 문제 데이터베이스: `C:\big20\big20_AI_Interview_simulation\LDW\text03\db\interview.db`
- 면접 기록 데이터베이스: `C:\big20\big20_AI_Interview_simulation\LDW\text03\db\interview_save.db`
- 벡터 검색 및 분석 결과: PostgreSQL `interview_db`

## 주의 사항
- 마이크 사용 권한을 허용해야 음성 답변이 가능합니다.
- 인터넷 연결이 안정적이어야 OpenAI API를 통한 실시간 분석이 원활합니다.
