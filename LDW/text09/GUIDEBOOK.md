# AI 면접 프로그램 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로그램은 웹 기반의 **AI 면접 시뮬레이션**입니다. 사용자는 웹 브라우저를 통해 실제 면접과 유사한 환경에서 모의 면접을 진행할 수 있습니다. 회원가입 및 로그인 기능을 제공하며, 면접 진행 시 카메라와 마이크를 활용하여 사용자의 답변을 입력받고(시뮬레이션), 면접 결과를 시각적으로 피드백해줍니다.

## 2. 개발 환경 (Environment)
본 프로젝트는 다음과 같은 환경에서 개발 및 테스트되었습니다.

*   **OS**: Windows
*   **Language**: Python 3.x, HTML5, CSS3, JavaScript (ES6+)
*   **Database**: SQLite3
*   **Framework**: Flask (Web Framework)

## 3. 프로그램 실행 방법 (How to Run)
1.  **필수 라이브러리 설치**:
    Python이 설치되어 있어야 하며, `Flask` 라이브러리가 필요합니다.
    ```bash
    pip install flask
    ```
2.  **서버 실행**:
    명령 프롬프트(CMD) 또는 터미널에서 `server.py` 파일이 있는 경로로 이동한 후 다음 명령어를 실행합니다.
    ```bash
    python server.py
    ```
3.  **접속**:
    프로그램이 실행되면 자동으로 기본 웹 브라우저가 열리며 `http://localhost:5000`으로 접속됩니다.
    (브라우저가 열리지 않을 경우 주소창에 직접 입력하여 접속 가능합니다.)

## 4. 사용 라이브러리 (Libraries Used)
### Python (Backend)
*   **Flask**: 웹 서버 구동 및 API 라우팅 처리 (`pip install flask`)
*   **sqlite3**: 사용자 데이터(회원정보) 저장을 위한 내장 데이터베이스 라이브러리 (Python 내장)
*   **os**: 파일 경로 및 디렉토리 제어 (Python 내장)
*   **webbrowser**: 서버 실행 시 웹 브라우저 자동 실행 (Python 내장)
*   **threading**: 브라우저 실행 타이머 제어 (Python 내장)

### Frontend
*   **HTML5 / CSS3 / JavaScript**: 웹 페이지 구조 및 스타일링, 동적 기능 구현
*   **Google Fonts**: Noto Sans KR 폰트 사용

## 5. 주요 기능 사용법 (Key Features)
1.  **회원가입/로그인 (Auth)**
    *   아이디, 비밀번호, 이름 등을 입력하여 회원가입을 할 수 있습니다. (데이터는 `db/membership_information.db`에 저장됨)
    *   가입한 정보로 로그인하여 대시보드로 진입합니다.

2.  **대시보드 (Dashboard)**
    *   지원 가능한 공고 목록을 확인할 수 있습니다.
    *   '내 정보' 메뉴에서 개인정보를 수정할 수 있습니다.

3.  **면접 준비 (Interview Setup)**
    *   이력서를 업로드하고, 카메라 및 마이크 작동 여부를 테스트합니다.
    *   모든 준비가 완료되면 '면접 시작' 버튼이 활성화됩니다.

4.  **AI 면접 진행 (Interview Simulation)**
    *   **Phase 1~N**: 단계별로 AI 면접관의 질문이 제시됩니다.
    *   **답변**: 사용자는 음성(시뮬레이션) 또는 텍스트로 답변을 입력합니다.
    *   **타이머**: 각 질문에 대한 제한 시간이 표시됩니다.

5.  **결과 확인 (Result)**
    *   면접 종료 후 기술 역량, 문제 해결, 의사 소통, 태도 등 영역별 점수와 합격 여부를 그래프로 확인할 수 있습니다.

## 6. 파일 구조 설명 (File Structure)
```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
│
├── server.py        # [Main] Flask 웹 서버 실행 파일
├── index.html       # 웹 페이지의 메인 구조 (HTML)
├── styles.css       # 웹 페이지 스타일 정의 (CSS)
├── app.js           # 프론트엔드 로직 (페이지 전환, 이벤 처리 등)
│
└── db\
    └── membership_information.db  # (자동생성) 회원 정보 저장 DB 파일
```

---
*작성일: 2026. 02. 09.*
