# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK.md)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션**입니다. 지원자는 원하는 직무에 지원하고, 이력서(PDF)를 업로드한 뒤, AI와 실시간으로 면접을 진행할 수 있습니다. LLM(Large Language Model) 기술을 활용하여 지원자의 이력서와 직무에 맞는 맞춤형 질문을 생성하고, 답변을 평가합니다.

## 2. 환경 설정 (Environment Setup)
본 프로그램은 Python Flask 서버와 Vanilla JS 프론트엔드로 구성되어 있습니다.

### 필수 요구 사항
- **Python 3.8+**
- **Node.js** (선택 사항, 개발 편의용)
- **PostgreSQL** (데이터베이스)

### 설치 방법
1. **필수 라이브러리 설치**:
   ```bash
   pip install flask psycopg2-binary python-dotenv pypdf werkzeug
   ```
2. **데이터베이스 설정**:
   - PostgreSQL이 설치되어 있어야 하며, `interview_db` 데이터베이스를 생성해야 합니다.
   - `.env` 파일 또는 환경 변수에 `POSTGRES_PASSWORD`를 설정하세요. (기본값: server.py 참조)

## 3. 프로그램 실행 방법 (Execution)
1. 터미널(PowerShell 또는 CMD)을 엽니다.
2. 프로젝트 디렉토리로 이동합니다.
   ```bash
   cd C:\big20\big20_AI_Interview_simulation\LDW\text09
   ```
3. 서버를 실행합니다.
   ```bash
   python server.py
   ```
4. 웹 브라우저가 자동으로 열리며 `http://localhost:5000`에 접속됩니다.

## 4. 주요 기능 사용법 (Features)

### [지원자] 면접 진행
1. **로그인/회원가입**: 계정이 없다면 회원가입 후 로그인합니다.
2. **공고 확인**: '지원 가능한 공고' 목록에서 원하는 공고의 '확인하기' 버튼을 클릭합니다.
3. **상세 정보 및 지원**: 공고 내용을 확인하고 '지원하기' 버튼을 클릭합니다.
4. **이력서 업로드**: PDF 형식의 이력서를 업로드합니다.
5. **장치 테스트**: 카메라와 마이크가 정상 작동하는지 테스트합니다.
6. **면접 시작**: '면접 시작' 버튼을 누르면 AI 면접관이 질문을 시작합니다.
7. **답변 하기**: 질문을 듣고(또는 읽고) 답변을 입력하거나 말한 뒤 '답변 완료'를 누릅니다.
8. **결과 확인**: 모든 질문이 끝나면 면접 결과(합격/불합격 예측 등)를 봅니다.

### [관리자] 공고 및 지원자 관리
1. **관리자 로그인**: 관리자 계정으로 로그인합니다.
2. **공고 등록**: '공고 관리' 메뉴에서 새 채용 공고를 등록합니다.
3. **지원자 현황**: 지원자들의 면접 진행 상황과 점수를 확인합니다.

## 5. 파일 구조 설명 (File Structure)
```
C:\big20\big20_AI_Interview_simulation\LDW\text09
├── server.py           # Backend 서버 (Flask, DB 연결, API, Mock LLM)
├── app.js              # Frontend 로직 (UI 제어, API 호출, 면접 흐름)
├── index.html          # 메인 웹 페이지 (SPA 구조)
├── styles.css          # 스타일시트
├── GUIDEBOOK.md        # 사용자 가이드북 (본 파일)
└── uploads/            # 업로드된 이력서 저장 폴더
```

## 6. 사용 라이브러리 (Libraries)
- **Flask**: 웹 서버 프레임워크
- **psycopg2**: PostgreSQL 데이터베이스 연동
- **pypdf**: PDF 이력서 텍스트 추출
- **werkzeug**: 파일 업로드 및 보안 유틸리티

---
© 2026 AI Interview Simulation Project.
