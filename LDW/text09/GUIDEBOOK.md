# 웹 기반 AI 면접 시뮬레이션 가이드북

## 1. 개요
본 프로젝트는 사용자가 이력서를 업로드하고, AI 면접관과 실시간으로 대화하며 면접을 진행할 수 있는 웹 애플리케이션입니다. LLM(Large Language Model)을 활용하여 직무와 이력서에 맞는 맞춤형 질문을 생성하고, 답변을 분석하여 피드백을 제공합니다.

## 2. 개발 환경
- **OS**: Windows / Mac / Linux
- **Language**: Python 3.9+, JavaScript (ES6+)
- **Database**: PostgreSQL
- **Frontend**: HTML5, CSS3, Vanilla JS
- **Backend**: Flask (Python)

## 3. 프로그램 실행 방법

### 3.1. 환경 설정
1. Python 및 PostgreSQL이 설치되어 있어야 합니다.
2. PostgreSQL 데이터베이스 생성:
   ```sql
   CREATE DATABASE interview_db;
   ```
3. `.env` 파일 설정:
   프로젝트 루트에 `.env` 파일을 생성하고 데이터베이스 비밀번호를 설정하세요.
   ```
   POSTGRES_PASSWORD=your_password
   ```

### 3.2. 패키지 설치
터미널에서 다음 명령어를 실행하여 필요한 라이브러리를 설치합니다.
```bash
pip install flask psycopg2-binary python-dotenv pypdf
```

### 3.3. 서버 실행
```bash
python server.py
```
서버가 정상적으로 실행되면 브라우저에서 `http://localhost:5000`으로 접속합니다.

## 4. 사용 라이브러리 (Dependencies)
- **Flask**: 웹 서버 프레임워크
- **psycopg2-binary**: PostgreSQL 데이터베이스 연동
- **python-dotenv**: 환경 변수 관리
- **pypdf**: PDF 이력서 텍스트 추출
- **werkzeug**: 파일 업로드 및 보안 유틸리티

## 5. 주요 기능 사용법

### 5.1. 회원가입 및 로그인
- **지원자**: 일반 회원가입을 통해 계정을 생성하고 로그인합니다.
- **관리자**: 관리자 계정으로 로그인하여 채용 공고를 관리합니다.

### 5.2. 채용 공고 관리 (관리자)
- **공고 등록**: 직무, 제목, 내용, 마감일을 입력하여 새 공고를 등록합니다.
- **공고 수정/삭제**: 등록된 공고를 수정하거나 삭제할 수 있습니다.

### 5.3. 이력서 업로드 및 면접 시작 (지원자)
1. 원하는 공고를 선택하여 '확인하기'를 클릭합니다.
2. '면접 응시하기' 버튼을 누릅니다.
3. 카메라와 마이크 상태를 확인합니다.
4. PDF 형식의 이력서를 업로드합니다.
5. '면접 시작하기'를 눌러 AI 면접을 시작합니다.

### 5.4. 실시간 AI 면접
- AI가 이력서와 직무를 분석하여 질문을 제시합니다.
- 사용자는 음성(STT 예정) 또는 텍스트로 답변을 입력합니다.
- 답변을 제출하면 AI가 내용을 분석하고 다음 질문을 이어갑니다.

### 5.5. 결과 확인
- 면접이 종료되면 종합 분석 결과를 리포트 형태로 확인할 수 있습니다.

## 6. 파일 구조 설명
```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── app.js               # 프론트엔드 로직 (SPA 라우팅, API 호출)
├── data.json            # (구버전) 목업 데이터 파일
├── db/                  # 데이터베이스 관련 파일
├── diagnose_db.py       # DB 상태 진단 스크립트
├── GUIDEBOOK.md         # 프로젝트 가이드북 (본 파일)
├── index.html           # 메인 웹 페이지
├── server.py            # 메인 백엔드 서버 (API, DB 연결, AI 로직)
├── styles.css           # 웹 페이지 스타일 시트
└── uploads/             # 업로드된 이력서 저장 폴더
```
