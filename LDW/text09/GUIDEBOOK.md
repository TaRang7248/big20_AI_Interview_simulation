# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션**입니다. 사용자는 이력서를 등록하고 AI 면접관과 음성 및 화상으로 실시간 면접을 진행할 수 있으며, 면접 종료 후 AI가 분석한 평가 결과를 확인할 수 있습니다. 관리자는 채용 공고를 관리하고 지원자들의 면접 결과와 이력서를 검토할 수 있습니다.

## 2. 환경 설정 (Environment)
본 프로그램은 **Python (Backend)**과 **Vanilla JavaScript (Frontend)**로 구성되어 있습니다.

### 필수 요구 사항
- **Python 3.8 이상**
- **PostgreSQL 데이터베이스**
- **OpenAI API Key** (GPT-4o, Whisper 사용)

### 주요 라이브러리 및 모델
- **Backend Framework**: `FastAPI` (비동기 웹 서버)
- **Database**: `psycopg2` (PostgreSQL 연동)
- **AI Models**:
    - **OpenAI GPT-4o**: 면접 질문 생성, 답변 평가, 결과 분석
    - **OpenAI Whisper (whisper-1)**: 음성 인식 (STT)
    - **Web Speech API & SpeechSynthesis**: 브라우저 내장 TTS (음성 합성) 및 실시간 자막
- **Utilities**: `pypdf` (PDF 이력서 텍스트 추출), `python-dotenv` (환경 변수 관리)

## 3. 프로그램 실행 방법 (How to Run)

1. **데이터베이스 실행**: PostgreSQL 서버가 실행 중이어야 합니다.
2. **환경 변수 설정**: `.env` 파일에 DB 접속 정보와 `OPENAI_API_KEY`가 설정되어 있어야 합니다.
3. **가상 환경 활성화 (선택 사항)**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
4. **라이브러리 설치**:
   ```bash
   pip install -r requirements.txt
   ```
5. **서버 실행**:
   ```bash
   python server.py
   ```
   - 서버가 시작되면 자동으로 브라우저가 열립니다 (`http://localhost:5000`).
   - 수동으로 접속하려면 브라우저 주소창에 위 주소를 입력하세요.

## 4. 파일 구조 (File Structure)
```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── server.py                 # 메인 백엔드 서버 (FastAPI)
├── app.js                    # 프론트엔드 로직 (SPA, API 호출, 미디어 제어)
├── index.html                # 메인 UI 구조
├── styles.css                # 스타일 시트
├── create_table.py           # 초기 DB 테이블 생성 스크립트
├── migrate_add_email_column.py # DB 마이그레이션 (이메일 컬럼 추가)
├── verify_email_feature.py   # 이메일 기능 검증 스크립트
├── uploads/                  # 업로드된 이력서 및 오디오 파일 저장소
├── db/                       # (참고용) DB 관련 파일
└── requirements.txt          # 파이썬 의존성 패키지 목록
```

## 5. 주요 기능 사용법 (Key Features)

### [지원자 (Applicant)]
1. **회원가입 및 로그인**: 계정을 생성하고 로그인합니다.
2. **채용 공고 확인**: 현재 진행 중인 채용 공고를 확인하고 '확인하기'를 눌러 상세 내용을 봅니다.
3. **면접 시작**:
    - 이력서(PDF)를 업로드합니다.
    - 카메라와 마이크 권한을 허용하고 테스트합니다.
    - '면접 시작하기' 버튼을 누릅니다.
4. **면접 진행**:
    - AI 면접관의 질문을 듣고 답변을 말합니다.
    - 답변이 끝나면 자동으로 다음 질문으로 넘어갑니다. (약 2분 제한)
5. **결과 확인**: 면접이 종료되면 합격/불합격 여부와 상세 피드백을 확인할 수 있습니다.

### [관리자 (Admin)]
1. **공고 관리**: 채용 공고를 등록, 수정, 삭제할 수 있습니다.
2. **지원자 현황**:
    - 면접을 완료한 지원자 목록을 볼 수 있습니다.
    - **지원자 이름과 이메일 주소**가 표시됩니다.
    - '상세보기'를 통해 지원자의 이력서, 면접 질의응답 내용, AI 평가 점수(기술, 문제해결, 소통, 태도)를 확인할 수 있습니다.
3. **내 정보 수정**: 관리자 정보를 수정할 수 있습니다.

## 6. 문제 해결 (Troubleshooting)
- **(undefined) 표시 문제**: 지원자 현황에서 이름 옆에 `(undefined)`가 뜨는 현상은 `app.js`와 `server.py` 업데이트를 통해 해결되었습니다. 이제 정상적으로 **이메일 주소**가 표시됩니다.
- **마이크/카메라 오류**: 브라우저 주소창 옆의 권한 설정에서 마이크와 카메라 사용을 '허용'으로 설정했는지 확인하세요.
- **DB 연결 오류**: `.env` 파일의 DB 설정 정보가 정확한지 확인하세요.
