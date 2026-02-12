# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요
이 프로그램은 AI 기술을 활용하여 실제 면접과 유사한 환경을 제공하는 웹 기반 면접 시뮬레이션입니다.
사용자는 지원자로서 면접을 체험하거나, 관리자로서 공고를 등록하고 지원자의 면접 결과를 분석할 수 있습니다.

## 2. 환경 및 요구사항
- **OS**: Windows (권장)
- **Web Browser**: Chrome (권장), Edge
- **Backend Language**: Python 3.8+
- **Database**: PostgreSQL
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **AI Models**: OpenAI GPT-4o (질문 생성 및 평가), Whisper (STT)

## 3. 프로그램 실행 방법
1. **데이터베이스 실행**: PostgreSQL 서비스가 실행 중이어야 합니다.
2. **가상환경 활성화 (선택 사항)**: `venv`가 있다면 활성화합니다.
3. **서버 실행**:
   ```bash
   python server.py
   ```
4. **접속**: 웹 브라우저가 자동으로 열리거나 `http://localhost:5000`으로 접속합니다.

## 4. 주요 기능 사용법

### [지원자 (Applicant)]
1. **회원가입/로그인**: 계정을 생성하고 로그인합니다.
2. **공고 확인**: '채용 공고' 탭에서 현재 진행 중인 공고를 확인합니다.
3. **면접 시작**:
   - 원하는 공고의 '확인하기' 버튼을 클릭합니다.
   - '지원하기' 버튼을 누른 후, PDF 형식의 이력서를 업로드합니다.
4. **면접 진행**:
   - AI 면접관이 질문을 제시합니다.
   - 마이크와 카메라가 켜진 상태에서 음성으로 답변합니다.
   - 답변이 끝나면 '답변 제출' 버튼을 클릭합니다.
   - 총 12개의 질문(자기소개, 직무 질문, 인성 질문 등)이 진행됩니다.
5. **결과 확인**: 면접 종료 후 '나의 기록'에서 합격 여부와 AI의 평가를 확인할 수 있습니다.
6. **내 정보 수정**: 비밀번호 확인 후 개인정보를 수정할 수 있습니다.

### [관리자 (Admin)]
1. **로그인**: 관리자 계정으로 로그인합니다.
2. **공고 관리**:
   - '채용 공고 등록' 버튼으로 새로운 공고를 작성합니다.
   - 본인이 작성한 공고는 수정 및 삭제가 가능합니다.
3. **지원자 현황**:
   - '지원자 현황' 탭에서 **본인이 올린 공고**에 지원한 지원자 목록을 볼 수 있습니다.
   - '상세보기'를 통해 지원자의 이력서, 면접 질의응답 내용, AI 분석 점수(기술, 문제해결, 소통, 태도)를 확인합니다.

## 5. 파일 구조 설명
- `server.py`: FastAPI 기반의 백엔드 서버 로직 (API, DB 연동, AI 호출).
- `app.js`: 프론트엔드 로직 (SPA 라우팅, API 호출, 녹음 및 타이머 처리).
- `index.html`: 메인 웹 페이지 구조.
- `styles.css`: 스타일 시트.
- `create_table.py`: 데이터베이스 테이블 초기화 스크립트.
- `migrate_rename_column.py`: DB 스키마 마이그레이션 스크립트 (announcement_title -> title).
- `requirements.txt`: Python 의존성 라이브러리 목록.

## 6. 사용된 라이브러리 및 모델
- **Backend Framework**: `FastAPI`, `Uvicorn`
- **Database Driver**: `psycopg2-binary`
- **AI Integration**: `openai` (GPT-4o, Whisper)
- **PDF Processing**: `pypdf`
- **Environment Management**: `python-dotenv`

## 7. 주의사항
- 카메라와 마이크 권한이 허용되어야 면접을 진행할 수 있습니다.
- `.env` 파일에 데이터베이스 접속 정보와 OpenAI API Key가 올바르게 설정되어 있어야 합니다.
