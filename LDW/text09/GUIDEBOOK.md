# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK.md)

## 1. 개요 (Overview)
이 프로젝트는 웹 기반의 **AI 면접 시뮬레이션** 프로그램입니다. 사용자는 웹 인터페이스를 통해 회원가입 및 로그인을 하고, AI 면접을 진행할 수 있습니다.
백엔드는 **Python Flask**를 사용하여 구현되었으며, 데이터베이스는 **PostgreSQL (Docker Container)**를 사용하여 안정적인 데이터 관리를 제공합니다.

## 2. 개발 및 실행 환경 (Environment)
이 프로젝트를 실행하기 위해서는 다음의 환경이 구성되어야 합니다.

- **운영체제**: Windows 10/11
- **언어**: Python 3.10 이상
- **데이터베이스**: PostgreSQL 16 (Docker Container 사용)
    - 이미지: `pgvector/pgvector:pg16`
- **웹 브라우저**: Google Chrome (권장), Microsoft Edge

## 3. 프로그램 실행 방법 (How to Run)

### 3.1. DB 컨테이너 실행
프로젝트 루트(`C:\big20\big20_AI_Interview_simulation`)에서 Docker Compose를 사용하여 DB를 실행합니다.
```cmd
docker-compose up -d
```
*주의: Docker Desktop이 설치 및 실행되어 있어야 합니다.*

### 3.2. 가상환경 활성화 및 패키지 설치
Python 가상환경을 활성화하고 필요한 라이브러리를 설치합니다.
```cmd
# 가상환경 활성화 (예: interview_env)
.\interview_env\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 3.3. 서버 실행
프로그램 디렉토리로 이동하여 서버를 실행합니다.
```cmd
cd LDW\text09
python server.py
```
서버가 정상적으로 실행되면 브라우저가 자동으로 열리거나 `http://localhost:5000`으로 접속하여 확인할 수 있습니다.

## 4. 사용 라이브러리 (Libraries)
주요 사용 라이브러리는 다음과 같습니다.

- **Flask**: 웹 서버 프레임워크
- **psycopg2-binary**: PostgreSQL 데이터베이스 연동 드라이버
- **python-dotenv**: 환경 변수 관리 (.env 파일 로드)
- **sqlite3**: (기존 레거시 코드, 현재는 PostgreSQL로 대체됨)

## 5. 주요 기능 사용법 (Features)

### 5.1. 회원가입
- 메인 화면에서 회원가입 버튼을 클릭합니다.
- 아이디, 비밀번호, 이름 등 필수 정보를 입력하여 가입합니다.
- 가입된 정보는 PostgreSQL DB의 `users` 테이블에 저장됩니다.

### 5.2. 로그인
- 가입한 아이디와 비밀번호로 로그인을 수행합니다.

### 5.3. 회원정보 수정
- 로그인 후 '정보수정' 메뉴로 이동합니다.
- 비밀번호 확인 후 이메일, 전화번호, 주소 등을 수정할 수 있습니다.
- 비밀번호 변경 기능도 제공됩니다.

## 6. 파일 구조 설명 (File Structure)
`C:\big20\big20_AI_Interview_simulation\LDW\text09` 폴더 기준입니다.

```
text09/
├── server.py        # 메인 백엔드 서버 파일 (Flask + DB 연동)
├── index.html       # 메인 프론트엔드 UI/UX
├── app.js           # 프론트엔드 로직 (API 호출 및 이벤트 처리)
├── styles.css       # 스타일 시트
├── GUIDEBOOK.md     # 프로그램 사용 가이드 (본 문서)
└── db/              # (구) SQLite 데이터 저장소 폴더
```
