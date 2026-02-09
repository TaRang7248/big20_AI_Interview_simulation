# AI 면접 프로그램 가이드북 (GUIDEBOOK)

이 문서는 AI 면접 시뮬레이션 프로그램의 실행 방법과 파일 구조를 설명합니다.

## 1. 개요
이 프로그램은 웹 기반(HTML/JS) 프론트엔드와 Python Flask 백엔드로 구성되어 있습니다.
사용자가 입력한 회원 정보는 로컬 데이터베이스 파일(`db/membership_information.db`)에 안전하게 저장됩니다.

## 2. 실행 환경 준비
### 필수 요구 사항
- **Python 3.x**가 설치되어 있어야 합니다.
- **Flask** 라이브러리가 필요합니다.
  ```bash
  pip install flask
  ```

## 3. 프로그램 실행 방법
보안상의 이유로 브라우저에서 HTML 파일을 직접 여는 대신, Python 웹 서버를 통해 접속해야 합니다.

1. **터미널(CMD/PowerShell) 열기**
   - 프로젝트 폴더(`text09`)로 이동합니다.
     ```bash
     cd C:\big20\big20_AI_Interview_simulation\LDW\text09
     ```

2. **서버 실행**
   - 다음 명령어를 입력하여 서버를 실행합니다.
     ```bash
     python server.py
     ```
   - 실행 성공 시 다음과 같은 메시지가 나타납니다:
     ```
     Database initialized at db\membership_information.db
     Serving on http://localhost:5000
     ```

3. **웹 접속**
   - 웹 브라우저(Chrome, Edge 등)를 열고 주소창에 입력합니다:
     `http://localhost:5000`

## 4. 주요 기능 사용법
### 회원가입
1. 로그인 화면 하단의 **'회원가입'** 링크를 클릭합니다.
2. 아이디, 비밀번호, 이름 등 정보를 입력하고 **'가입하기'**를 클릭합니다.
3. 정보는 `db/membership_information.db`의 `users` 테이블에 저장됩니다.

### 로그인
1. 가입 시 입력한 아이디와 비밀번호를 입력합니다.
2. **'로그인'** 버튼을 클릭합니다.
3. DB에서 일치하는 정보를 찾으면 대시보드로 이동합니다.

## 5. 파일 구조 설명
- **server.py**: 웹 서버 및 데이터베이스(DB) 처리 로직 (Python Flask)
- **app.js**: 화면 동작 및 서버 통신 담당 (JavaScript)
- **index.html**: 메인 웹 페이지 구조
- **styles.css**: 디자인 스타일 시트
- **db/**: 데이터베이스 파일이 위치하는 폴더
  - **membership_information.db**: 회원 정보가 저장되는 SQLite DB 파일

> [!NOTE]
> `app.js`의 `MOCK_DB` 변수 내 사용자 데이터는 제거되었으며, 이제 실제 DB를 사용합니다.
