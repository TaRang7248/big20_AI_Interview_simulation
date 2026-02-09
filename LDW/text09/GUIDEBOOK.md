# AI 면접 시뮬레이션 가이드북 (AI Interview Simulation Guidebook)

## 1. 개요 (Overview)
본 프로젝트는 웹 기반의 **AI 면접 시뮬레이션 프로그램**입니다. 사용자는 모의 면접을 통해 자기소개, 역량 검증, 기술 면접(코딩 테스트) 과정을 체험할 수 있으며, 관리자는 면접 공고를 등록하고 지원자의 결과를 확인할 수 있습니다.

**주요 특징:**
- **SPA (Single Page Application)**: 페이지 새로고침 없이 부드러운 사용자 경험 제공
- **AI 면접관**: TTS(Text-to-Speech)를 활용한 음성 질문 및 답변 시간 제한 기능
- **관리자 기능**: 면접 공고 생성 및 지원자 현황 대시보드 제공
- **데이터베이스 연동**: PostgreSQL을 사용하여 회원 정보 및 공고 데이터 관리

---

## 2. 환경 설정 (Environment Setup)

### 필수 요구 사항
- **OS**: Windows (본 가이드 기준)
- **Python**: 3.8 이상
- **PostgreSQL**: 13 이상 (로컬 또는 원격 DB)
- **Web Browser**: Chrome, Edge 등 최신 브라우저

### 설치 및 설정
1. **Python 패키지 설치**:
   ```bash
   pip install flask psycopg2-binary python-dotenv
   ```
2. **데이터베이스 설정**:
   - PostgreSQL 서버가 실행 중이어야 합니다.
   - 데이터베이스 이름: `interview_db` (기본값)
   - `.env` 파일 또는 `server.py` 내의 DB 접속 정보를 본인의 환경에 맞게 수정해야 합니다.

---

## 3. 프로그램 실행 방법 (How to Run)

1. **서버 실행**:
   프로젝트 폴더 (`C:\big20\big20_AI_Interview_simulation\LDW\text09`)에서 터미널을 열고 아래 명령어를 입력합니다.
   ```bash
   python server.py
   ```
2. **접속**:
   서버가 정상적으로 실행되면 브라우저가 자동으로 열리거나, 수동으로 주소창에 `http://localhost:5000`을 입력하여 접속합니다.

---

## 4. 사용 라이브러리 (Libraries Used)

### Backend (Python)
- **Flask**: 경량 웹 프레임워크로 서버 구축 및 API 제공
- **psycopg2**: PostgreSQL 데이터베이스 연동 어댑터
- **python-dotenv**: 환경 변수 관리
- **webbrowser**: 서버 실행 시 브라우저 자동 실행

### Frontend (JavaScript/HTML/CSS)
- **Vanilla JS (ES6+)**: 별도의 프레임워크 없이 순수 자바스크립트로 SPA 및 로직 구현
- **HTML5/CSS3**: 구조 및 스타일링 (Flexbox, Grid 활용)
- **Web Speech API**: TTS(음성 합성) 기능 구현 (브라우저 내장 API)

---

## 5. 주요 기능 사용법 (Key Features)

### [지원자 모드]
- **회원가입/로그인**: 계정을 생성하고 로그인합니다.
- **마이페이지**: 개인정보 수정 및 비밀번호 변경이 가능합니다.
- **채용 공고 확인**: 현재 등록된 면접 공고 목록을 보고 '지원하기'를 클릭합니다.
- **면접 진행**:
    1. **환경 점검**: 카메라와 마이크 권한을 확인합니다.
    2. **면접 시작**: AI 면접관의 질문을 듣고 제한 시간 내에 대답합니다.
    3. **단계별 진행**: 자기소개 -> 역량 검증 -> 기술 면접 순으로 진행됩니다.
- **결과 확인**: 면접 종료 후 AI가 분석한(Mock Data) 점수와 합격 여부를 확인합니다.

### [관리자 모드] (ID: admin 권한 필요)
- **공고 관리**:
    - '면접 공고 관리' 메뉴에서 현재 진행 중인 공고를 확인합니다.
    - '공고 등록' 버튼을 눌러 새로운 채용 공고를 생성합니다. (제목, 마감일, 내용 입력)
- **지원자 현황**: 면접에 응시한 지원자들의 점수와 합격 여부를 목록으로 확인합니다.

---

## 6. 파일 구조 설명 (File Structure)

```
text09/
├── server.py           # [메인] Flask 웹 서버 및 API 엔드포인트 정의
├── app.js              # [핵심] 프론트엔드 로직, 라우팅, API 호출, 면접 진행 로직
├── index.html          # 메인 웹 페이지 구조 (Single Page)
├── styles.css          # 웹 페이지 스타일링 (CSS)
├── db/                 # (구) SQLite DB 파일 저장소
├── create_table.py     # DB 테이블 생성 유틸리티 스크립트
├── check_table.py      # DB 데이터 확인 유틸리티 스크립트
├── GUIDEBOOK.md        # [문서] 사용자 가이드북 (본 파일)
└── ...
```

---
*작성일: 2026년 2월 9일*
