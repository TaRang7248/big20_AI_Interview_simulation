# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK.md)

## 1. 개요 (Overview)
본 프로그램은 **웹 기반 AI 면접 시뮬레이션**입니다.
사용자는 웹 브라우저를 통해 가상의 면접관(AI)과 상호작용하며, 면접 질문에 답변하고 실시간 피드백을 받을 수 있습니다.
또한, Python Flask 서버를 통해 회원가입 정보를 로컬 데이터베이스(SQLite)에 저장하고 관리합니다.

---

## 2. 개발 환경 (Environment)
본 프로젝트는 다음과 같은 환경에서 개발 및 테스트되었습니다.
*   **OS**: Windows
*   **Language**:
    *   **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES6+)
    *   **Backend**: Python 3.x
*   **Framework/Library**:
    *   Flask (Web Server)
    *   SQLite3 (Database)

---

## 3. 프로그램 실행 방법 (How to Run)
**중요**: `index.html` 파일을 직접 더블 클릭하여 실행하면 데이터베이스 기능이 작동하지 않습니다. 반드시 아래 순서대로 실행해주세요.

1.  **터미널 열기**: `C:\big20\big20_AI_Interview_simulation\LDW\text09` 폴더에서 명령 프롬프트(CMD) 또는 PowerShell을 엽니다.
2.  **서버 실행**:
    ```bash
    python server.py
    ```
3.  **브라우저 자동 실행**:
    *   서버가 정상적으로 실행되면, 잠시 후 **기본 웹 브라우저가 자동으로 열리며** 프로그램(`http://localhost:5000`)에 접속됩니다.
4.  **프로그램 사용**:
    *   회원가입 및 로그인을 진행하고 면접 시뮬레이션을 시작합니다.

---

## 4. 사용 라이브러리 (Libraries)
*   **Backend**:
    *   `flask`: 웹 서버 구동 및 API 제공
    *   `sqlite3`: 사용자 데이터 저장 (Python 내장)
    *   `webbrowser`: 서버 실행 시 브라우저 자동 실행 (Python 내장)
    *   `threading`: 브라우저 실행 타이머 제어 (Python 내장)
*   **Frontend**:
    *   Google Fonts (Noto Sans KR): 폰트 적용
    *   SpeechRecognition API (Web API): 음성 인식 (STT) 지원 브라우저 필요 (Chrome 권장)
    *   SpeechSynthesis API (Web API): 음성 안내 (TTS)

---

## 5. 주요 기능 사용법 (Features)

### 5.1 회원가입 및 로그인
*   **회원가입**: ID, 비밀번호, 이름, 생년월일, 성별, 이메일, 주소, 전화번호를 입력하여 계정을 생성합니다.
*   **로그인**: 생성한 계정으로 접속합니다. (관리자/면접자 구분)

### 5.2 면접 진행 (Applicant)
1.  **대시보드**: 지원 가능한 공고 목록을 확인하고 '지원하기' 버튼을 클릭합니다.
2.  **환경 점검**: 카메라와 마이크 권한을 허용하고 연결 상태를 확인합니다.
3.  **면접 시작**:
    *   AI 면접관이 질문을 읽어줍니다 (TTS).
    *   질문이 끝난 후 타이머가 작동하며, 사용자는 마이크를 통해 답변합니다 (STT).
    *   '답변 완료' 버튼을 누르거나 시간이 종료되면 다음 질문으로 넘어갑니다.
4.  **결과 확인**: 면접 종료 후 영역별 점수와 합격 여부 예측 결과를 확인합니다.

### 5.3 관리자 기능 (Admin)
*   **공고 관리**: 새로운 면접 공고를 등록하거나 기존 공고를 수정합니다.
*   **지원자 현황**: 지원자들의 면접 점수와 합격 여부를 조회합니다.

---

## 6. 파일 구조 설명 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
│
├── server.py           # [Backend] Flask 웹 서버 및 DB 관리 메인 파일
├── index.html          # [Frontend] 웹 어플리케이션의 메인 HTML 구조
├── styles.css          # [Frontend] UI 디자인 스타일시트
├── app.js              # [Frontend] 클라이언트 로직 (라우팅, 면접 진행, API 통신)
├── GUIDEBOOK.md        # [Docs] 프로그램 사용 설명서 (현재 파일)
│
└── db\
    └── membership_information.db  # [Database] SQLite 사용자 정보 저장소
```

---

## 7. 문제 해결 (Troubleshooting)
*   **브라우저가 열리지 않을 때**: 주소창에 `http://localhost:5000` 또는 `http://127.0.0.1:5000`을 직접 입력하세요.
*   **데이터베이스 오류**: `db` 폴더가 존재하는지 확인하십시오. 없으면 `server.py` 실행 시 자동으로 생성됩니다.
*   **카메라/마이크 오류**: 브라우저 주소창 왼쪽의 '사이트 설정'에서 카메라와 마이크 권한이 '허용'되어 있는지 확인하세요.
