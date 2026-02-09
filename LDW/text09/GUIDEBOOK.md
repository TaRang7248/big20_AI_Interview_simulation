# 웹 기반 AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

본 문서는 웹 기반 AI 면접 시뮬레이션 프로그램의 설치, 실행 및 사용 방법에 대한 상세 가이드를 제공합니다.

## 1. 개요 (Overview)
이 프로젝트는 **Flask** 기반의 웹 애플리케이션으로, 사용자가 온라인 환경에서 모의 면접을 진행하고 AI를 통해 면접 준비를 할 수 있도록 돕는 시뮬레이션 프로그램입니다. 관리자는 채용 공고를 관리하고, 지원자는 이력서를 등록하거나 면접 질문을 학습할 수 있습니다.

## 2. 환경 설정 (Environment Setup)

### 2.1 필수 요구 사항
- **Python 3.8 이상**
- **Git** (소스 코드 관리용)
- **PostgreSQL** (데이터베이스)

### 2.2 설치 방법
1. **저장소 클론 (Clone Repository)**
   ```bash
   git clone [레포지토리 주소]
   cd C:\big20\big20_AI_Interview_simulation\LDW\text09
   ```

2. **가상 환경 생성 및 활성화 (선택 사항)**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```

3. **필수 라이브러리 설치**
   아래 명령어로 필요한 패키지를 설치합니다.
   ```bash
   pip install flask psycopg2-binary werkzeug python-dotenv
   ```

4. **환경 변수 설정 (.env)**
   프로젝트 루트 디렉토리 또는 상위 디렉토리에 `.env` 파일을 생성하고 데이터베이스 비밀번호를 설정합니다. (기본값: `013579`)
   ```env
   POSTGRES_PASSWORD=your_password
   ```

## 3. 프로그램 실행 방법 (Execution)

### 3.1 데이터베이스 초기화 및 데이터 로드
최초 실행 시, 면접 질문 데이터를 데이터베이스에 적재해야 합니다.
```bash
python setup_interview_data.py
```
* 위 스크립트는 `data.json` 파일을 읽어 `interview_answer` 테이블에 데이터를 삽입합니다.

### 3.2 서버 실행
다음 명령어로 웹 서버를 실행합니다.
```bash
python server.py
```
* 서버가 시작되면 브라우저가 자동으로 열립니다. (http://localhost:5000)
* 만약 열리지 않는다면 브라우저 주소창에 직접 입력하여 접속하세요.

## 4. 사용 라이브러리 (Libraries Used)

| 라이브러리 | 용도 |
| --- | --- |
| **Flask** | 웹 프레임워크 (서버 구축) |
| **psycopg2** | PostgreSQL 데이터베이스 어댑터 |
| **Werkzeug** | 파일 업로드 보안 및 유틸리티 |
| **python-dotenv** | 환경 변수 관리 |

## 5. 주요 기능 사용법 (Key Features)

### 5.1 회원가입 및 로그인
- **회원가입**: ID, 비밀번호, 이름, 생년월일 등을 입력하여 계정을 생성합니다.
- **로그인**: 생성한 계정으로 로그인하여 서비스를 이용합니다.

### 5.2 채용 공고 관리 (관리자 기능)
- **공고 등록**: 제목, 직무, 마감일, 내용을 입력하여 새로운 채용 공고를 게시합니다.
- **공고 수정/삭제**: 등록된 공고를 수정하거나 삭제할 수 있습니다.
- **작성자 표시**: 공고 목록에서 해당 공고를 작성한 관리자의 ID를 확인할 수 있습니다.

### 5.3 면접 준비 및 시뮬레이션
- **이력서 업로드**: 지원하고자 하는 공고에 맞춰 PDF 형식의 이력서를 업로드할 수 있습니다.
- **면접 질문 학습**: `interview_answer` 테이블에 저장된 방대한 면접 질문과 모범 답안 데이터를 통해 학습할 수 있습니다.

## 6. 파일 구조 설명 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
│
├── server.py                # 메인 Flask 서버 파일 (API 및 라우팅 처리)
├── setup_interview_data.py  # 데이터베이스 초기화 및 데이터 로드 스크립트
├── data.json                # 면접 질문/답변 원본 데이터
├── index.html               # 메인 프론트엔드 HTML 파일
├── app.js                   # 프론트엔드 로직 (API 호출, UI 제어)
├── styles.css               # 스타일 시트
├── GUIDEBOOK.md             # 프로젝트 가이드북 (본 문서)
└── uploads/                 # 업로드된 파일 저장소
    └── resumes/             # 이력서 파일 저장 폴더
```

## 7. 문제 해결 (Troubleshooting)
- **DB 연결 오류**: `server.py` 내의 `DB_NAME`, `DB_USER`, `DB_PASS` 설정이 로컬 PostgreSQL 설정과 일치하는지 확인하세요.
- **포트 충돌**: 5000번 포트가 이미 사용 중이라면 `server.py` 하단의 `app.run(port=5000)`에서 포트 번호를 변경하세요.

---
**작성일**: 2026년 2월 9일
**버전**: 1.0.0
