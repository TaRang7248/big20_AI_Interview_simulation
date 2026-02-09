# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로그램은 웹 기반의 **AI 면접 시뮬레이션**입니다. 사용자는 면접자로서 회원가입 및 로그인을 수행하고, 가상의 AI 면접관과 음성으로 대화하며 면접을 진행할 수 있습니다. 또한, 자신의 회원 정보를 수정하고 관리할 수 있는 기능을 제공합니다.

## 2. 환경 설정 (Environment)
본 프로그램은 다음 환경에서 실행을 권장합니다.
- **OS**: Windows 10/11
- **Language**: Python 3.8 이상
- **Browser**: Google Chrome 또는 Microsoft Edge (최신 버전 권장 - 음성 인식/합성 API 지원 필요)

## 3. 프로그램 실행 방법 (How to Run)
1.  **필수 라이브러리 설치**:
    터미널(PowerShell 또는 CMD)에서 다음 명령어를 실행하여 필요한 Python 패키지를 설치합니다.
    ```bash
    pip install flask
    ```
    (*`sqlite3`는 Python 표준 라이브러리이므로 별도 설치 불필요*)

2.  **서버 실행**:
    프로젝트 폴더(`C:\big20\big20_AI_Interview_simulation\LDW\text09`)로 이동 후 다음 명령어를 실행합니다.
    ```bash
    python server.py
    ```

3.  **접속**:
    서버가 실행되면 자동으로 웹 브라우저가 열리거나, 주소창에 `http://localhost:5000`을 입력하여 접속합니다.

## 4. 사용 라이브러리 (Libraries)
- **Backend**:
    - `Flask`: 웹 서버 프레임워크
    - `sqlite3`: 내장 데이터베이스 (회원 정보 관리)
    - `webbrowser`: 서버 실행 시 브라우저 자동 오픈
- **Frontend**:
    - `HTML5/CSS3`: UI 구조 및 스타일링
    - `Vanilla JavaScript`: 클라이언트 로직 (SPA 구현)
    - `Web Speech API`: 음성 인식(STT) 및 음성 합성(TTS)

## 5. 주요 기능 사용법 (Key Features)
### 5.1 회원 관리
- **회원가입**: 아이디, 비밀번호, 이름, 생년월일, 이메일, 전화번호 등을 입력하여 가입합니다.
- **로그인**: 가입한 아이디와 비밀번호로 로그인합니다.
- **내 정보 수정**:
    1.  로그인 후 네비게이션 바의 '내 정보'를 클릭합니다. (또는 대시보드 메뉴 이용)
    2.  현재 비밀번호를 입력하여 본인 확인을 합니다.
    3.  수정할 이메일 및 전화번호를 입력하고 '정보 수정' 버튼을 누릅니다.
    4.  변경된 정보는 데이터베이스(`db/membership_information.db`)에 즉시 반영됩니다.

### 5.2 AI 면접 진행
- **대시보드**: 지원 가능한 공고 목록을 확인하고 '지원하기' 버튼을 누릅니다.
- **환경 점검**: 카메라 및 마이크 권한을 허용하고 연결 상태를 테스트합니다.
- **면접 시작**: AI 면접관의 질문을 듣고(TTS), 사용자의 음성으로 답변(STT)합니다.
- **결과 확인**: 면접 종료 후 영역별 점수와 합격/불합격 예측 결과를 확인합니다.

## 6. 파일 구조 설명 (File Structure)
```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
│
├── server.py              # [메인] Flask 웹 서버 및 DB API 처리 로직
├── app.js                 # [메인] 클라이언트 로직 (라우팅, API 호출, 면접 진행)
├── index.html             # 웹 페이지 구조 (SPA 형태)
├── styles.css             # 스타일 시트
├── GUIDEBOOK.md           # 프로그램 사용 설명서
└── db\
    └── membership_information.db  # SQLite 데이터베이스 파일 (회원 정보 저장)
```
