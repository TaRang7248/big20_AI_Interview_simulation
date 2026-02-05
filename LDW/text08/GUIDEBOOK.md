# 📘 AI Interview Simulation - GUIDEBOOK

## 소개 (Introduction)
이 프로그램은 **GPT-4o** 기반의 AI 면접 시뮬레이터입니다.
사용자가 지원한 직무(Job Title)에 맞춰, **20년차 전문가 페르소나**를 가진 AI 면접관이 실제 면접처럼 깊이 있는 질문을 던지고 피드백을 제공합니다.

---

## 🚀 실행 방법 (How to Run)

### 1. 환경 설정 (Prerequisites)
- **Python 3.9+** 설치 필요
- `.env` 파일에 `OPENAI_API_KEY` 설정 필수

### 2. 설치 (Installation)
프로젝트 루트(`text08`)에서 라이브러리를 설치합니다.
```bash
pip install -r requirements.txt
```

### 3. 서버 실행 (Run Server)
```bash
python start_app.py
```
서버가 시작되면 콘솔에 접속 주소가 표시됩니다 (기본: `http://127.0.0.1:8000`).

---

## 📝 API 사용법 (API Usage)

### 1. 면접 시작 (`POST /api/interview/start`)
새로운 면접 세션을 시작하고 첫 번째 질문(자기소개)을 받습니다.

- **URL**: `/api/interview/start`
- **Body (`multipart/form-data`)**:
    - `candidate_name`: 지원자 이름 (예: 김철수)
    - `job_role`: 지원 직무 (예: Python 백엔드 개발자)
    - `user_id`: 사용자 ID (숫자, 예: 1)
- **Response**:
    ```json
    {
        "status": "started",
        "session_id": "uuid-string",
        "question": "자기소개를 부탁드립니다...",
        "step": 1,
        "total_steps": 10
    }
    ```

### 2. 답변 제출 및 피드백 (`POST /api/interview/submit`)
음성 또는 텍스트로 답변을 제출하면, AI가 평가 후 다음 질문을 제공합니다.

- **URL**: `/api/interview/submit`
- **Body (`multipart/form-data`)**:
    - `session_id`: 시작 시 발급받은 세션 ID
    - `answer_text`: (옵션) 텍스트 답변
    - `audio`: (옵션) 음성 파일 (.webm 등)
    - `image`: (옵션) 아키텍처 다이어그램 등 이미지 파일
- **Response**:
    ```json
    {
        "status": "success",
        "next_question": "다음 질문 내용...",
        "evaluation": {
            "score": 85,
            "feedback": "구체적인 사례가 좋아...",
            "is_follow_up": false
        },
        "step": 2,
        "is_completed": false
    }
    ```

---

## ⚠️ 트러블슈팅 (Troubleshooting)

### Q1. "AttributeError: module 'services.llm_service' has no attribute..."
- **원인**: 구형 코드와 신규 `LLMService` 클래스 간의 불일치.
- **해결**: 최신 코드로 업데이트되었는지 확인하고 서버를 재시작하세요.

### Q2. "OpenAI Rate Limit Error"
- **원인**: API 키 쿼터 초과.
- **해결**: `.env`의 API 키를 확인하거나 충전하세요.

### Q3. 음성 인식이 안 돼요.
- **원인**: `stt_service` 설정 또는 마이크 권한 문제.
- **해결**: 우선 텍스트 답변(`answer_text`)을 사용하여 면접을 진행할 수 있습니다.
