# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로그램은 사용자가 AI 면접관과 1:1로 모의 면접을 진행할 수 있는 웹 애플리케이션입니다.
FastAPI, PostgreSQL, OpenAI LLM을 기반으로 동작하며, 실시간 음성 인식(STT) 및 자동 평가 기능을 제공합니다.

## 2. 주요 기능 (Features)
- **실전 같은 면접 환경**: 총 10개의 질문으로 구성된 체계적인 면접 프로세스.
- **맞춤형 질문 생성**: 사용자의 직업(Job)에 맞춰 `interview.db` 데이터를 기반으로 질문을 생성합니다.
- **꼬리 질문 (Follow-up Questions)**: 사용자의 답변이 부족하거나 추가 검증이 필요한 경우, AI가 심층 질문을 던집니다.
- **실시간 STT**: 사용자의 음성 답변을 실시간 텍스트로 변환하여 보여줍니다.
- **아키텍처 캔버스**: 시스템 설계 질문 시, 화면에 직접 아키텍처를 그리고 AI의 평가를 받을 수 있습니다.
- **상세 피드백**: 면접 종료 후 합격 여부, 점수, 답변별 상세 피드백을 제공합니다.
- **자동 실행**: 프로그램 실행 시 브라우저가 자동으로 열립니다.

## 3. 설치 및 실행 (Installation & Run)

### 필수 요구 사항
- Python 3.9 이상
- PostgreSQL (pgvector 확장 필요)
- OpenAI API Key

### 환경 설정 (.env)
`.env` 파일을 생성하고 아래 정보를 입력하세요.
```ini
OPENAI_API_KEY=your_api_key_here
DATABASE_URL=postgresql+psycopg2://user:password@localhost/dbname
```

### 실행 방법
1. 가상환경 생성 및 활성화
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
2. 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```
3. 데이터베이스 초기화
   ```bash
   python init_db.py  # (최초 1회)
   ```
4. 서버 실행
   ```bash
   python main.py
   ```
   실행 시 자동으로 브라우저가 열리며 면접 프로그램이 시작됩니다.

## 4. 면접 진행 순서 (Process)
1. **로그인**: 이름과 지원 직무를 입력합니다.
2. **면접**:
   - 자기소개 (1번)
   - 인성 질문 (2~4번)
   - 직무 지식 질문 (5~9번)
   - 마무리 질문 (10번)
   *각 질문당 90초의 제한 시간이 주어집니다.*
3. **피드백**: 면접 결과를 확인하고 부족한 점을 보완합니다.

## 5. 기술 스택 (Tech Stack)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL + pgvector
- **AI/ML**: OpenAI GPT (Text Generation), Whisper (STT)
