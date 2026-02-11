# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK.md)

## 1. 개요 (Overview)
본 프로그램은 **웹 기반 AI 면접 시뮬레이션** 플랫폼입니다. 사용자는 실제 면접과 유사한 환경에서 AI 면접관과 음성으로 대화하며 면접을 진행할 수 있습니다. OpenAI의 GPT-4o와 Whisper 모델을 활용하여 실시간 질문 생성, 답변 인식, 그리고 심층적인 결과 분석을 제공합니다.

## 2. 환경 (Environment)
본 프로그램은 다음 환경에서 개발 및 테스트되었습니다.

*   **OS**: Windows
*   **Backend Language**: Python 3.x
*   **Frontend Language**: HTML5, CSS3, Vanilla JavaScript (ES6+)
*   **Database**: PostgreSQL
*   **Browser**: Chrome, Edge 등 모던 브라우저

## 3. 프로그램 실행 방법 (How to Run)

1.  **데이터베이스 실행**: PostgreSQL 데이터베이스가 실행 중이어야 합니다.
2.  **가상 환경 진입 (선택 사항)**: 필요한 경우 Python 가상 환경을 활성화합니다.
3.  **필수 패키지 설치**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **서버 실행**:
    프로젝트 루트 디렉토리(`C:\big20\big20_AI_Interview_simulation\LDW\text09`)에서 터미널을 열고 다음 명령어를 입력합니다.
    ```bash
    python server.py
    ```
5.  **접속**:
    브라우저를 열고 `http://localhost:5000` 주소로 접속합니다.

## 4. 사용하는 모델 및 라이브러리 (Models & Libraries)

### Backend (Python)
*   **FastAPI**: 고성능 웹 프레임워크 (API 서버 역할)
*   **Uvicorn**: ASGI 웹 서버
*   **Psycopg2**: PostgreSQL 데이터베이스 어댑터
*   **OpenAI API**: AI 모델 연동
    *   **GPT-4o**: 면접 질문 생성, 답변 평가, 결과 분석
    *   **Whisper-1**: 음성 인식 (STT, Speech-to-Text)
*   **Pypdf**: 이력서(PDF) 텍스트 추출
*   **Python-dotenv**: 환경 변수 관리 (.env)

### Frontend
*   **Web Speech API**: 브라우저 내장 음성 인식 (실시간 피드백 용)
*   **MediaRecorder API**: 사용자 답변 음성 녹음
*   **Navigator MediaDevices**: 카메라 및 마이크 장치 제어

## 5. 주요 기능 사용법 (Key Features)

### 5.1 회원가입 및 로그인
*   **회원가입**: ID, 비밀번호, 이름, 생년월일, 연락처 등을 입력하여 계정을 생성합니다. '면접자'와 '관리자' 유형을 선택할 수 있습니다.
*   **로그인**: 생성한 계정으로 로그인합니다.

### 5.2 (면접자) 내 정보 수정
*   로그인 후 좌측 메뉴의 **내 정보**를 클릭합니다.
*   이메일, 주소, 전화번호를 수정하고 **정보 수정 완료** 버튼을 누르면 즉시 반영됩니다. (비밀번호 확인 절차 생략됨)
*   비밀번호 변경은 별도의 **비밀번호 변경** 버튼을 통해 가능합니다.

### 5.3 (면접자) 면접 진행
1.  **공고 확인**: 대시보드에서 지원할 공고를 확인하고 **확인하기** -> **지원하기**를 클릭합니다.
2.  **환경 설정**: 이력서(PDF)를 업로드하고 카메라/마이크 상태를 확인합니다.
3.  **면접 시작**: AI 면접관이 자기소개를 시작으로 질문을 합니다.
4.  **답변**: 질문을 듣고 마이크를 통해 답변합니다. 답변이 끝나면 **답변 제출** 버튼을 누릅니다.
5.  **결과 확인**: 모든 질문이 끝나면 면접 결과 페이지로 이동하며, 나중에 **내 면접 기록**에서도 결과를 확인할 수 있습니다.

### 5.4 (관리자) 공고 및 지원자 관리
*   **공고 관리**: 새로운 면접 공고를 등록, 수정, 삭제할 수 있습니다.
*   **지원자 현황**: 지원자들의 면접 진행 상황과 상세 결과(기술/인성 점수, 평가 내용)를 조회할 수 있습니다.

## 6. 파일 구조 설명 (File Structure)

```
C:\big20\big20_AI_Interview_simulation\LDW\text09
├── server.py               # 핵심 백엔드 서버 코드 (FastAPI)
├── app.js                  # 프론트엔드 로직 (SPA 라우팅, API 호출, 면접 로직)
├── index.html              # 메인 웹 페이지 구조
├── styles.css              # 스타일시트
├── requirements.txt        # 파이썬 의존성 패키지 목록
├── create_table.py         # 데이터베이스 테이블 초기화 스크립트
├── setup_interview_data.py # 기초 면접 데이터(면접 질문 등) 셋업
├── uploads/                # 업로드된 파일 저장소 (이력서, 음성 파일)
└── db/                     # 데이터베이스 관련 파일
```
