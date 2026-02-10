# AI 면접 시뮬레이션 가이드북 (Guidebook)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션 프로그램**입니다. 사용자는 가상의 면접관(AI)과 함께 실제 면접과 유사한 환경에서 모의 면접을 진행할 수 있습니다.

### 주요 특징
- **사용자별 맞춤형 환경**: 지원자 및 관리자 모드 지원.
- **실전 같은 면접 진행**: 자기소개, 역량 검증, 기술 면접 단계별 진행.
- **음성 인식 및 TTS**: AI 질문 음성 출력 및 지원자 음성 답변 인식 (STT).
- **이력서 기반 맞춤 질문**: PDF 이력서 업로드를 통한 맞춤형 면접 준비 (기반 마련).
- **결과 피드백**: 면접 종료 후 영역별 점수 및 합격 여부 예측.

---

## 2. 개발 환경 (Environment)
본 프로젝트는 **Python Flask** 백엔드와 **Vanilla JavaScript** 프론트엔드로 구성되어 있습니다.

- **OS**: Windows, macOS, Linux (Cross-platform)
- **Language**:
  - Python 3.8+
  - JavaScript (ES6+)
  - HTML5 / CSS3
- **Database**: PostgreSQL (권장) 또는 SQLite (초기 개발용 호환 가능)
- **Libraries**:
  - `Flask`: 웹 서버 프레임워크
  - `psycopg2`: PostgreSQL 데이터베이스 어댑터
  - `werkzeug`: 파일 업로드 및 유틸리티
  - `python-dotenv`: 환경 변수 관리

---

## 3. 설치 및 실행 방법 (Installation & Execution)

### 3.1. 필수 요구사항 설치
Python이 설치되어 있어야 합니다. 프로젝트 루트 디렉토리에서 아래 명령어를 실행하여 필수 라이브러리를 설치하세요.

```bash
pip install flask psycopg2-binary werkzeug python-dotenv
```

### 3.2. 데이터베이스 설정 (.env)
프로젝트 루트에 `.env` 파일을 생성하고 데이터베이스 접속 정보를 설정해야 합니다. (기본적으로 `server.py` 내부에 폴백 설정이 있으나, 보안을 위해 `.env` 사용을 권장합니다.)

```env
DB_HOST=localhost
DB_NAME=interview_db
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_PORT=5432
```

### 3.3. 프로그램 실행
터미널에서 `server.py`가 있는 디렉토리로 이동 후 아래 명령어를 실행합니다.

```bash
python server.py
```

실행 후 웹 브라우저가 자동으로 열리며 `http://localhost:5000`으로 접속됩니다.
(자동으로 열리지 않을 경우 브라우저 주소창에 직접 입력하세요.)

---

## 4. 파일 구조 (File Structure)

```
big20_AI_Interview_simulation/
└── LDW/
    └── text09/
        ├── server.py              # 메인 백엔드 서버 (Flask)
        ├── app.js                 # 프론트엔드 로직 (SPA, API 통신)
        ├── index.html             # 메인 HTML 페이지 structure
        ├── styles.css             # 스타일시트 (UI 디자인)
        ├── GUIDEBOOK.md           # 본 가이드북 파일
        ├── check_table.py         # (유틸) DB 테이블 확인 스크립트
        ├── create_table.py        # (유틸) DB 테이블 생성 스크립트
        ├── uploads/               # 업로드된 이력서 저장소
        └── ...
```

---

## 5. 주요 기능 사용법 (User Manual)

### 5.1. 회원가입 및 로그인
- 초기 실행 시 로그인 화면이 나타납니다. 계정이 없다면 '회원가입'을 클릭하세요.
- **지원자**: 일반 면접 응시용 계정입니다.
- **관리자**: 채용 공고를 등록하고 지원자를 관리할 수 있는 계정입니다.

### 5.2. [지원자] 면접 진행
1. 로그인 후 대시보드에서 **지원 가능한 공고** 목록을 확인합니다.
2. 원하는 공고의 '확인하기' -> '지원하기' 버튼을 누릅니다.
3. **이력서 업로드**: PDF 형식의 이력서를 업로드합니다.
4. **환경 테스트**: 카메라 및 마이크 작동 여부를 확인하고 '면접 시작'을 누릅니다.
5. **면접 단계**: AI 면접관의 질문을 듣고(TTS) 음성으로 답변(STT)합니다.
   - Phase 1: 자기소개
   - Phase 2: 역량 검증
   - Phase 3: 기술/코딩 질문
6. 면접이 끝나면 결과 페이지에서 점수와 예측 결과를 확인할 수 있습니다.

### 5.3. [관리자] 공고 관리
1. 관리자 계정으로 로그인합니다.
2. **공고 등록**: '공고 등록' 버튼을 눌러 직무, 내용, 마감일을 입력합니다.
3. **공고 수정/삭제**: 본인이 작성한 공고에 한해 목록에 '수정' 및 '삭제' 버튼이 활성화됩니다.
4. **지원자 현황**: 지원자들의 면접 점수 및 합격 여부를 조회할 수 있습니다 (Mock Data 연동).

---

## 6. 문제 해결 (Troubleshooting)

- **DB 연결 오류 (`psycopg2.OperationalError`)**:
  - PostgreSQL 서버가 실행 중인지 확인하세요.
  - `.env` 파일 또는 `server.py` 상단의 DB 설정(`DB_HOST`, `DB_USER` 등)이 정확한지 확인하세요.
- **카메라/마이크 권한 오류**:
  - 브라우저 주소창 옆의 자물쇠 아이콘을 눌러 카메라/마이크 권한을 '허용'으로 설정하고 새로고침하세요.
  - `https` 가 아닌 `http` 환경에서는 일부 브라우저 보안 정책상 마이크 권한이 제한될 수 있습니다 (localhost 제외).

---
*Created by Antigravity*
