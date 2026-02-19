# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 시뮬레이션 개요
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션**으로, 사용자가 실제 면접과 유사한 환경에서 AI 면접관과 대화하며 면접 역량을 키울 수 있도록 돕습니다.
면접이 종료되면 AI가 지원자의 답변 내용, 태도 등을 종합적으로 분석하여 **루브릭(Rubric)** 기준에 따른 상세한 평가 리포트를 제공합니다.

### 주요 특징
- **실시간 대화**: STT(음성 인식)와 TTS(음성 합성) 기술을 활용하여 실제 사람과 대화하듯 면접을 진행합니다.
- **맞춤형 질문**: 지원한 직무와 자기소개서 내용을 바탕으로 생성형 AI가 심층 질문을 생성합니다.
- **루브릭 기반 평가**: 기술/직무, 문제해결, 의사소통, 태도/인성 4가지 영역을 5단계 척도로 정밀하게 평가합니다.
- **웹 인터페이스**: 직관적인 웹 UI를 통해 누구나 쉽게 이용할 수 있습니다.

---

## 2. 시뮬레이션 환경
본 시뮬레이션은 다음과 같은 환경에서 실행되도록 개발되었습니다.

- **OS**: Windows (권장)
- **Python 버전**: Python 3.10 이상 권장
- **브라우저**: Chrome, Edge 등 최신 웹 브라우저

---

## 3. 실행 방법
### 1단계: 가상환경 설정 및 패키지 설치
(최초 1회 실행)
```bash
# 가상환경 생성 (예시)
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 필수 패키지 설치
pip install -r requirements.txt
```

### 2단계: 서버 실행
`server.py` 파일을 실행하면 서버가 구동되고 자동으로 웹 브라우저가 열립니다.
```bash
python server.py
```
- 서버는 기본적으로 `http://localhost:5000` 에서 동작합니다.
- 브라우저가 자동으로 열리지 않을 경우, 주소창에 위 주소를 직접 입력하세요.

### 3단계: Docker를 이용한 실행 방법 (권장)
Docker가 설치되어 있다면, 다음 명령어로 간편하게 실행할 수 있습니다.

1. **컨테이너 빌드 및 실행**:
   ```bash
   docker-compose up --build
   ```
   > **주의사항**: 상위 폴더(`.../big20/`)에 `.env` 파일이 존재해야 정상적으로 실행됩니다. (API Key 등 필수 설정 포함)

2. **접속**:
   웹 브라우저를 열고 `http://localhost:5000`으로 접속합니다.
   (Docker 환경에서는 브라우저가 자동으로 실행되지 않을 수 있습니다.)
3. **종료**:
   `Ctrl + C`를 눌러 서버를 중지하거나, 다른 터미널에서 `docker-compose down`을 실행합니다.

---

## 4. 사용 모델 및 라이브러리 목록

### 핵심 기술 (AI & Backend)
- **FastAPI**: 고성능 비동기 웹 프레임워크 (백엔드 서버)
- **OpenAI GPT-4o**: 면접 질문 생성 및 답변 분석, 평가 (LLM)
- **LangChain**: LLM 오케스트레이션 및 프롬프트 관리
- **Uvicorn**: ASGI 웹 서버

### 음성 및 멀티미디어
- **Deepgram**: 고성능 음성 인식 (STT)
- **Edge-TTS**: 자연스러운 음성 합성 (TTS)
- **PyAudio**: 오디오 입출력 처리
- **MoveNet Thunder (Google)**: 실시간 자세(Pose) 분석
- **DeepFace (Facebook) / OpenCV**: 표정 기반 감정 분석


### 데이터베이스 및 저장소
- **PostgreSQL / SQLite**: (설정에 따라) 면접 데이터 및 결과 저장
- **SQLAlchemy**: ORM(Object Relational Mapping) 데이터베이스 연동

---

## 5. 주요 기능 사용법

### [1] 로그인 및 직무 선택
1. 회원가입 후 로그인을 진행합니다.
2. 면접을 진행할 **직무(예: 웹 개발자, 마케팅 등)**를 선택하거나 입력합니다.
3. 자기소개서 파일을 업로드하거나 텍스트로 입력합니다.

### [2] 면접 진행
1. '면접 시작' 버튼을 누르면 AI 면접관이 첫 인사를 건넵니다.
2. 마이크를 통해 답변을 말하면 AI가 이를 인식하고 꼬리물기 질문을 이어갑니다.
3. 설정된 질문 개수만큼 면접이 진행됩니다.

### [3] 결과 확인
1. 면접이 종료되면 잠시 후 **분석 결과 페이지**로 이동합니다.
2. **평가 루브릭**에 따라 4가지 항목(기술, 문제해결, 의사소통, 태도)에 대한 점수와 상세 피드백을 확인합니다.
3. **비디오 태도 분석**: 면접 도중 촬영된 지원자의 표정, 시선 처리, 자세, 손 움직임 등을 분석하여 '태도/인성' 평가에 반영합니다.
4. '합격/불합격' 여부와 개선점을 파악합니다.

---

## 6. 파일 구조 설명
```
C:\big20\big20_AI_Interview_simulation\LDW\text09\
├── app/
│   ├── main.py              # FastAPI 애플리케이션 진입점
│   ├── config.py            # 환경 변수 및 설정 관리
│   ├── database.py          # 데이터베이스 연결 설정
│   ├── models.py            # Pydantic/SQLAlchemy 데이터 모델 정의
│   └── services/            # 핵심 비즈니스 로직
│       ├── analysis_service.py  # 면접 결과 분석 및 루브릭 평가 로직 ★
│       ├── llm_service.py       # LLM 연동 (GPT-4)
│       ├── stt_service.py       # 음성 인식
│       └── tts_service.py       # 음성 합성
├── static/                  # CSS, JS, 이미지 등 정적 파일
├── templates/               # HTML 템플릿 파일
├── requirements.txt         # 프로젝트 의존성 패키지 목록
├── server.py                # 서버 실행 및 브라우저 자동 실행 스크립트
├── scripts/                 # 유틸리티 스크립트 (모델 다운로드 등)
├── models/                  # AI 모델 저장소

├── Dockerfile               # 도커 이미지 빌드 설정 파일
└── docker-compose.yml       # 도커 컨테이너 실행 설정 파일
```

---

## 7. 데이터베이스 이관 및 설정 가이드 (Migration Guide)

이 섹션은 현재 실행 중인 데이터베이스 컨테이너(`interview_db_container`)의 데이터와 설정을 다른 컴퓨터로 그대로 옮겨 실행하는 방법을 설명합니다.

### 1단계: 데이터 백업 (기존 컴퓨터)
기존 컴퓨터에서 다음 스크립트를 실행하여 데이터베이스의 **스키마(구조)**와 **데이터**를 추출합니다.

1. `migration_package` 폴더로 이동합니다.
   ```bash
   cd C:\big20\big20_AI_Interview_simulation\LDW\text09\migration_package
   ```
2. 스키마 추출 실행:
   ```bash
   python export_schema.py
   ```
   - 결과물: `../data/schema.sql` 생성됨
3. 데이터 추출 실행 (기존 `export_db.py` 위치에서 실행 권장):
   ```bash
   cd ..
   python export_db.py
   ```
   - 결과물: `data/interview_db_backup.json` 생성됨

### 2단계: 파일 복사 (이관)
다음 파일 및 폴더를 압축하여 **새로운 컴퓨터**로 복사합니다.

- **전체 프로젝트 폴더**: `C:\big20\big20_AI_Interview_simulation\LDW\text09` (하위 폴더 포함)
  - 특히 `data/` 폴더 내의 `schema.sql`과 `interview_db_backup.json`이 반드시 포함되어야 합니다.
  - `.env` 파일 (상위 폴더에 위치)도 함께 복사하거나, 새 컴퓨터에 동일한 내용으로 생성해야 합니다.

### 3단계: 데이터베이스 복원 (새로운 컴퓨터)
새로운 컴퓨터에서 다음 절차를 따릅니다.

1. **Docker 환경 실행**:
   `migration_package` 폴더 내의 `docker-compose.yml`을 사용하여 DB와 앱을 실행합니다.
   ```bash
   cd migration_package
   docker-compose up -d --build
   ```
   - `-d`: 백그라운드 실행
2. **데이터 복원 실행**:
   데이터베이스가 실행된 상태에서 복원 스크립트를 실행합니다.
   ```bash
   # (필요시 가상환경 활성화 후)
   python import_data.py
   ```
   - 이 스크립트는 `data/schema.sql`로 테이블을 생성하고, `data/interview_db_backup.json`의 데이터를 입력합니다.

3. **확인**:
   웹 브라우저에서 `http://localhost:5000`에 접속하여 데이터가 정상적으로 조회되는지 확인합니다.
