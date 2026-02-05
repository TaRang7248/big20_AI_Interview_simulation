# AI 면접 시뮬레이션 가이드북 (AI Interview Simulation Guidebook)

본 문서는 Python 기반 AI 면접 시뮬레이션 프로그램의 사용법, 시스템 구조, 기능, 및 Vision AI 통합에 대한 안내를 담고 있습니다.

---

## 1. 프로그램 개요 (Overview)

이 프로그램은 실제 면접 상황을 시뮬레이션하여 사용자가 면접 역량을 강화할 수 있도록 돕는 도구입니다. 
생성형 AI (LLM)가 면접관 역할을 수행하며, 면접자의 음성을 인식(STT)하고, 표정을 분석(Vision AI)하여 종합적인 피드백을 제공합니다.

### 주요 기능
- **실시간 음성 인터뷰**: 마이크를 통해 실제 말하듯이 답변합니다.
- **DeepFace Vision AI**: 웹캠을 통해 면접자의 표정(감정)을 실시간으로 분석합니다.
- **꼬리물기 질문 (Follow-up)**: LLM이 답변 내용을 분석하여 심층 질문을 던집니다.
- **나만의 질문 데이터베이스**: 직무별 예상 질문과 RAG(검색 증강 생성)를 통해 맞춤형 질문을 생성합니다.

---

## 2. 설치 및 실행 (Installation & Run)

### 필수 요구사항
- Python 3.10 이상
- 웹캠 및 마이크
- OpenAI API Key (또는 호환되는 LLM Key)

### 설치 단계
1. **가상환경 생성 및 활성화** (권장)
   ```bash
   python -m venv venv
   source venv/bin/activate  # Mac/Linux
   venv\Scripts\activate     # Windows
   ```

2. **의존성 패키지 설치**
   ```bash
   pip install -r requirements.txt
   ```
   > **주의**: `deepface` 라이브러리는 최초 실행 시 얼굴 분석 모델(weights)을 다운로드하므로 인터넷 연결이 필요하며 시간이 소요될 수 있습니다.

3. **환경 변수 설정**
   `.env` 파일을 생성하고 API 키를 입력하세요.
   ```ini
   OPENAI_API_KEY=sk-proj-...
   ```

### 실행 방법
```bash
python main.py
```
실행 후 브라우저가 자동으로 열리며 `http://127.0.0.1:8000`으로 접속됩니다.

---

## 3. 시스템 구조 (Vertical Slice Architecture)

본 프로그램은 기능별로 독립적인 모듈로 분리된 "Vertical Slice" 아키텍처를 따릅니다.

### 디렉토리 구조
```
C:\big20\big20_AI_Interview_simulation\LDW\text08\
│
├── api/                  # API 엔드포인트 (Router)
│   ├── interview.py      # 면접 진행 및 Vision AI API
│   └── schemas.py        # 데이터 모델 (Pydantic)
│
├── services/             # 핵심 비즈니스 로직
│   ├── interview_service.py # 면접 흐름 관리 (Orchestrator)
│   ├── vision_service.py    # [NEW] Vision AI (표정 분석)
│   ├── llm_service.py       # LLM 통신 (질문 생성, 평가)
│   └── stt_service.py       # 음성 인식 (Speech-to-Text)
│
├── db/                   # 데이터베이스 로직
│   ├── sqlite.py         # 면접 로그 저장 (Local)
│   └── postgres.py       # 벡터 DB (PGVector) - RAG용
│
├── templates/            # 화면 (HTML)
│   └── index.html        # 메인 인터페이스 (카메라/마이크 UI 포함)
│
├── static/               # 정적 파일 (JS, CSS)
│   └── js/main.js        # 프론트엔드 로직 (카메라/녹음 제어)
│
└── main.py               # 서버 진입점 (FastAPI App)
```

---

## 4. Vision AI (DeepFace) 기능

면접 중 웹캠을 통해 사용자의 얼굴을 분석합니다.

- **작동 방식**: 3초 간격으로 프레임을 캡처하여 서버로 전송합니다.
- **분석 내용**: 7가지 감정 (행복, 슬픔, 분노, 놀람, 공포, 혐오, 평온) 중 지배적인 감정을 추출합니다.
- **피드백**: 화면 좌측 상단 카메라 미리보기 창에 현재 감정 상태가 실시간으로 표시됩니다. (예: "평온", "긴장(공포)")
- **활용 팁**: 면접 중 너무 경직되지 않도록 "평온" 또는 "행복(미소)" 상태를 유지하는 연습을 하세요.

---

## 5. 문제 해결 (Troubleshooting)

- **마이크/카메라 작동 안 함**: 브라우저의 주소창 옆 '자물쇠' 아이콘을 눌러 권한을 허용했는지 확인하세요.
- **DeepFace 오류**: `weights` 다운로드 중 실패했을 수 있습니다. 인터넷 연결을 확인하고 다시 실행하세요.
- **속도 저하**: CPU 기반으로 Vision AI가 동작하므로 저사양 PC에서는 분석 주기가 늦어질 수 있습니다.

---
**제작**: 2026 Big20 AI Interview Integration Team
