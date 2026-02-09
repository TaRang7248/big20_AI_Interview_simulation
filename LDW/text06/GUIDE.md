# AI 면접 시뮬레이션 가이드북

본 프로그램은 OpenAI의 LLM과 Whisper STT를 활용하여 실제 면접과 유사한 환경을 제공하는 AI 면접 시뮬레이션 시스템입니다. 

## 🚀 시작하기

### 1. 환경 요구사항
- **Python**: 3.8 이상
- **데이터베이스**: 
  - PostgreSQL (pgvector 확장 설치 필요)
  - SQLite (기본 포함)
- **OpenAI API Key**: GPT-4o 및 Whisper 사용을 위한 키

### 2. 설치 및 설정
1. 필요한 라이브러리 설치:
   ```bash
   pip install -r requirements.txt
   ```
2. `.env` 파일 설정:
   `.env.example` 파일을 복사하여 `.env`를 생성하고 OpenAI API 키와 PostgreSQL 접속 정보를 입력합니다.
   ```env
   OPENAI_API_KEY=your_key_here
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=interview_db
   ```
3. (선택사항) 기존 질문 데이터 마이그레이션:
   ```bash
   python migrate_questions.py
   ```

### 3. 프로그램 실행
```bash
python main.py
```
실행 시 자동으로 웹 브라우저(`http://127.0.0.1:8000`)가 열립니다.

## 🛠 주요 기능

1. **상세 면접 절차**
   - **1단계**: 자기소개
   - **2-4단계**: 인성 질문
   - **5-10단계**: 직무 지식 질문 (지원 직무 기반)
2. **실시간 음성 인식 (STT)**
   - OpenAI Whisper를 통해 답변하는 동안 실시간으로 텍스트가 화면에 표시됩니다.
3. **90초 시간 제한**
   - 각 질문당 90초의 제한 시간이 있으며, 시간이 종료되면 자동으로 답변이 제출됩니다.
4. **꼬리 질문 (Tail Question)**
   - 답변 내용에 따라 심층 분석이 필요한 경우 면접관이 추가 꼬리 질문을 던집니다.
5. **자동 평가 및 결과**
   - 모든 질문 종료 후 평균 점수가 70점 이상이면 '합격' 결과를 보여주며, 각 질문별 피드백을 제공합니다.
6. **데이터 저장**
   - 모든 면접 기록은 `db/interview_save.db`(SQLite)와 PostgreSQL에 상세히 저장됩니다.

## 📋 참고 사항
- 답변은 오직 **음성**으로만 가능합니다.
- 마이크 권한 허용이 필요합니다.
- 스크롤 기능을 통해 면접 진행 상황을 한눈에 확인할 수 있습니다.
