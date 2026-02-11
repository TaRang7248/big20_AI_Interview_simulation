# AI 면접 시뮬레이션 프로그램 가이드북

본 프로그램은 생성형 AI(OpenAI GPT-4o, Whisper)를 활용하여 실제 면접과 유사한 경험을 제공하는 웹 기반 AI 면접 시뮬레이션 시스템입니다.

## 1. 개요
지원자는 원하는 채용 공고에 지원하여 AI 면접관과 음성으로 실시간 면접을 진행할 수 있습니다. 면접이 종료되면 AI가 지원자의 답변을 분석하여 기술, 문제해결, 의사소통, 태도 등 다양한 지표로 평가 결과를 제공합니다.

## 2. 환경 설정 및 요구사항
- **OS**: Windows (테스트 완료)
- **Language**: Python 3.9+
- **Database**: PostgreSQL
- **AI API**: OpenAI API Key (GPT-4o, Whisper 모델 사용 권한 필요)
- **Browser**: Chrome, Edge 등 최신 웹 브라우저 (마이크/카메라 권한 필요)

## 3. 프로그램 실행 방법
1. **의존성 설치**:
   ```bash
   pip install -r requirements.txt
   ```
2. **환경 변수 설정**:
   `.env` 파일에 다음 항목을 설정합니다.
   - `OPENAI_API_KEY`: OpenAI API 키
   - `DB_HOST`, `DB_NAME`, `DB_USER`, `POSTGRES_PASSWORD`, `DB_PORT`: 데이터베이스 연결 정보
3. **데이터베이스 초기화**:
   ```bash
   python create_table.py
   python migrate_db_v2.py  # 초기 데이터 로드 포함
   python migrate_db_v3.py
   python migrate_db_v4.py
   python migrate_db_v5.py
   python migrate_db_v6.py
   ```
4. **서버 실행**:
   ```bash
   python server.py
   ```
   - 서버가 실행되면 자동으로 브라우저(`http://localhost:5000`)가 열립니다.

## 4. 사용 모델 및 라이브러리
- **AI 모델**:
    - `gpt-4o`: 질문 생성, 답변 평가, 최종 면접 결과 분석
    - `whisper-1`: 지원자 음성 답변의 텍스트 변환(STT)
- **주요 라이브러리**:
    - `FastAPI`: 백엔드 API 서버
    - `psycopg2`: PostgreSQL 연동
    - `pypdf`: 이력서(PDF) 텍스트 추출
    - `OpenAI SDK`: AI 모델 인터페이스

## 5. 주요 기능 사용법
- **면접자**:
    1. 회원가입 후 로그인
    2. 공고 목록에서 원하는 공고 선택 후 '지원하기'
    3. 이력서(PDF) 업로드 및 환경 테스트 완료 후 면접 시작
    4. AI의 질문을 듣고 마이크로 답변 (답변 완료 후 제출 버튼 클릭)
    5. 면접 종료 후 자동으로 생성되는 평가 결과 확인
- **관리자**:
    1. 회원가입 시 '관리자' 유형 선택
    2. '공고 관리' 메뉴에서 채용 공고 등록/수정/삭제
    3. '지원자 현황' 메뉴에서 지원자 목록 확인
    4. 각 지원자의 **'상세보기'**를 통해 이력서 내용, 전체 면접 대화 기록, 상세 AI 평가 결과 확인

## 6. 파일 구조 설명
- `server.py`: FastAPI 기반 메인 백엔드 서버 로직
- `index.html`: 프론트엔드 메인 페이지 구성
- `app.js`: 프론트엔드 인터랙션 및 API 통신 로직
- `styles.css`: 애플리케이션 스타일 시트
- `uploads/`: 업로드된 이력서 및 녹음된 음성 파일 저장소
- `data.json`: 초기 면접 질문 데이터셋
- `migrate_db_*.py`: 데이터베이스 스키마 마이그레이션 스크립트
