
## 2026-02-09

### TASK-001 로깅 기반 구축 (Logging Infrastructure)
- **요약**: `imh_core/logging` 패키지 구현 및 프로젝트 로그 디렉토리 구조 확정.
- **변경 사항**:
    - `packages/imh_core/logging/config.py` 생성: `TimedRotatingFileHandler` 적용 (매일 자정 로테이션).
    - `logs/agent/` 디렉토리 생성: 에이전트 및 로컬 개발용 로그 저장.
    - `logs/runtime/` 디렉토리 생성: 향후 API 서버 런타임 로그 저장용.
    - `scripts/check_logging.py` 추가: 로깅 동작 검증용 스크립트.
- **검증 증거**:
    - **생성된 로그 파일**:
        1. `IMH/IMH_Interview/logs/agent/agent.log`
        2. `IMH/IMH_Interview/logs/agent/agent.error.log`
        3. *(Runtime 로그 폴더 생성됨, 파일은 런타임 시 생성)*
    - **로테이션 설정**: `interval=1` (매일), `backupCount=30` (30일 보관)
    - **스택트레이스 기록 확인** (`agent.error.log` 발췌):
      ```text
      [2026-02-09 11:13:32] [ERROR] [verification_script] [check_logging.py:26] This is an INTENTIONAL EXCEPTION
      Traceback (most recent call last):
        File "...\scripts\check_logging.py", line 24, in verify_logging
          1 / 0
      ZeroDivisionError: division by zero
      ```
- **디렉토리 구조**:
  ```text
  IMH/IMH_Interview/packages
  ├── imh_core
  │   ├── logging
  │   │   ├── config.py
  │   │   └── __init__.py
  │   └── __init__.py
  └── __init__.py
  ```

### TASK-002 imh_core 최소 패키지 구성 (Core Infrastructure)
- **요약**: `imh_core` 패키지 내 `config`, `errors`, `dto` 모듈 구현 및 표준화
- **변경 사항**:
    - `packages/imh_core/config.py`: `pydantic-settings` 기반 단일 설정 클래스(`IMHConfig`) 구현. `.env` 로딩 지원.
    - `packages/imh_core/errors.py`: 공통 예외 클래스(`IMHBaseError`) 및 에러 코드 체계 정의.
    - `packages/imh_core/dto.py`: `pydantic.BaseModel` 기반 `BaseDTO` 정의 (ORM 모드, 공백 제거 자동화).
    - `scripts/verify_task_002.py`: 모듈 동작 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_002.py` -> `ALL PASS`
    - **Config**: `.env` 파일 로드 및 기본값 동작 확인.
    - **Errors**: 사용자 정의 에러 raise/catch 및 에러 코드 확인.
    - **DTO**: Pydantic 기능(공백 제거 등) 동작 확인.
- **디렉토리 구조**:
  ```text
  packages/imh_core
  ├── config.py
  ├── dto.py
  ├── errors.py
  └── logging/ (기존 유지)
  ```

### TASK-003 Provider 인터페이스 + Mock 구현 (Provider Layer)
- **요약**: STT, LLM, Emotion, Visual, Voice 5개 도메인의 Provider 인터페이스 정의 및 Async Mock 구현체 작성.
- **변경 사항**:
    - `packages/imh_core/dto.py`: 각 Provider별 입출력 DTO 추가 (`TranscriptDTO`, `LLMMessageDTO` 등).
    - `packages/imh_providers/`: 도메인별 패키지 구조 생성.
    - `packages/imh_providers/{domain}/base.py`: `abc.ABC` 기반 Async 인터페이스 정의 (`ISTTProvider` 등).
    - `packages/imh_providers/{domain}/mock.py`: `asyncio.sleep` 기반 Latency 시뮬레이션이 가능한 Mock 구현체 작성.
    - `scripts/verify_task_003.py`: 5개 Mock Provider 통합 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_003.py` -> `ALL MOCK PROVIDERS VERIFIED SUCCESSFULLY!`
    - **DTO**: Pydantic 모델을 통한 입출력 타입 강제 확인.
    - **Async**: `async def` 인터페이스 및 `await` 호출 정상 동작 확인.
- **디렉토리 구조**:
  ```text
  packages/imh_providers/
  ├── stt/ (base.py, mock.py)
  ├── llm/ (base.py, mock.py)
  ├── emotion/ (base.py, mock.py)
  ├── visual/ (base.py, mock.py)
  └── voice/ (base.py, mock.py)
  ```

### TASK-004 FastAPI 최소 엔트리 + Healthcheck (Application Entry)
- **요약**: `IMH/main.py` 진입점 생성 및 `/health` 라우터 구현. `imh_core` 로깅 연동.
- **변경 사항**:
    - `IMH/main.py`: FastAPI 앱 생성, `lifespan` 이벤트를 통한 런타임 로깅 초기화.
    - `IMH/api/health.py`: Liveness Probe용 `/health` 엔드포인트.
    - `logs/runtime/runtime.log`: 서버 실행 로그가 기록될 파일 생성 확인.
    - `scripts/verify_task_004.py`: 서버 구동 및 Healthcheck 응답 검증 스크립트.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_004.py` -> `[PASS] Healthcheck response is valid.`
    - **Health Response**: `{"status": "ok", "version": "0.1.0", "timestamp": "..."}`
    - **Runtime Log**: `Starting IMH AI Interview v0.1.0...` 기록 확인.
- **디렉토리 구조**:
  ```text
  IMH/IMH_Interview/IMH
  ├── api/
  │   ├── health.py
  │   └── __init__.py
  └── main.py
  ```
- **환경 검증 보완 (2026-02-09 Supplementary)**:
    - **실행 환경**: `interview_env` (venv) 활성화 상태에서 `scripts/verify_task_004.py` 재검증 완료.
    - **패키지 확인**: `fastapi`, `uvicorn`, `httpx` 등 필수 패키지가 `interview_env`에 설치되어 있음을 확인.

### TASK-005 Playground STT (파일 업로드)
- **요약**: `dependencies.py`를 통한 Mock STT Provider 연동 및 파일 업로드 분석 API 구현.
- **변경 사항**:
    - `IMH/api/playground.py`: Playground STT Router 구현 (임시 파일 처리, Validation).
    - `IMH/api/dependencies.py`: Provider Dependency Injection (`get_stt_provider`) 추가.
    - `IMH/main.py`: Playground Router 등록 (`/api/v1/playground`).
    - `python-multipart` 패키지 설치: `UploadFile` 처리를 위한 의존성 추가.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_005.py`
        - 정상 `.wav` 파일 -> 200 OK (Mock Data).
        - 비정상 `.txt` 파일 -> 400 Bad Request.
    - **로그 확인**: `logs/agent/agent.log`에 요청 정보(UUID 파일명, 사이즈) 및 처리 결과 기록 확인.
- **로그 파일**:
    - 런타임 로그: `logs/runtime/runtime.log`

### TASK-006 Playground PDF → Text (문서 업로드)
- **요약**: `pypdf` 기반 PDF 텍스트 추출 API 구현 (`/pdf-text`). 안정성 제약(페이지 수, 용량) 적용.
- **변경 사항**:
    - `packages/imh_core/dto.py`: `PDFExtractionResultDTO`, `PDFPageDTO` 추가.
    - `packages/imh_providers/pdf/`: `IPDFProvider` 인터페이스 및 `LocalPDFProvider` 구현.
    - `IMH/api/dependencies.py`: `get_pdf_provider` 추가.
    - `IMH/api/playground.py`: `POST /pdf-text` 엔드포인트 구현 (50페이지/10MB 제한).
    - `requirements.txt`: `pypdf` 의존성 확인.
    - `scripts/verify_task_006.py`: 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_006.py` (Verify Environment: interview_env)
        - Invalid Ext (.txt) -> 400 OK
        - Page Limit (51 pages) -> 400 OK
        - No Text (Blank PDF) -> 422 OK
    - **로그 확인**: `logs/agent/agent.log`에 페이지 수, 글자 수, Latency 기록 확인.

### TASK-007 Playground Embedding → Query Focus
- **요약**: 검색(RAG) 용도로 사용되는 **Query Text**를 임베딩 벡터로 변환하는 Playground 파이프라인 구현. 대화 전체/STT 결과 임베딩은 제외하고, Mock Provider 기반으로 변환 흐름만 검증.
- **변경 사항**:
    - `packages/imh_providers/embedding/`: Embedding Provider 패키지 신설 (`Interface`, `MockEmbeddingProvider`).
    - `packages/imh_core/dto.py`: `EmbeddingRequestDTO`, `EmbeddingResponseDTO` 추가.
    - `IMH/api/playground.py`: `POST /embedding` 엔드포인트 추가.
    - `scripts/verify_task_007.py`: Query Text → Embedding 변환 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_007.py` (Verify Environment: `interview_env`)
        - Valid Query Text -> Vector 반환 성공
        - Empty / Invalid Input -> Validation Error 처리 확인
        - 전체 테스트 통과 시 `"ALL TESTS PASSED"` 출력
    - **로그 확인**: `IMH/IMH_Interview/logs/runtime/runtime.log`에 API 요청/응답 및 처리 결과 기록 확인.

### TASK-008 Emotion 분석 (DeepFace Implementation)
- **요약**: DeepFace 모델을 활용한 **영상(1fps)/이미지 감정 분석** 파이프라인 구현. `playground` API에 통합 및 DTO 구조화.
- **변경 사항**:
    - `packages/imh_providers/emotion/dto.py`: 시계열 분석 결과(`VideoEmotionAnalysisResultDTO`) 및 프레임 DTO 정의.
    - `packages/imh_providers/emotion/deepface_impl.py`: `DeepFaceEmotionProvider` 구현 (OpenCV Backend, 1fps 샘플링, Face Detection Fail 처리).
    - `packages/imh_providers/emotion/base.py`, `mock.py`: `analyze_video` 인터페이스 추가 및 Mock 구현 업데이트.
    - `IMH/api/dependencies.py`: `get_emotion_provider` 의존성 주입 추가 (DeepFaceImpl 사용).
    - `IMH/api/playground.py`: `POST /emotion` 엔드포인트 구현 (이미지/비디오 분기 처리).
    - `scripts/verify_task_008.py`: `TestClient` 기반 통합 검증 스크립트 작성 (Dummy 영상/이미지 생성 및 업로드).
    - **환경 변경**: `tf-keras` 패키지 설치 (DeepFace + TF 2.20 호환성 이슈 해결).
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_008.py` (Verify Environment: `interview_env`)
        - Image Upload -> 200 OK (DeepFace/Image Result).
        - Video Upload (3s, 10fps) -> 200 OK. 3 Frames Analyzed (1fps Sampling 동작 확인).
        - JSON 구조(`metadata`, `results`) 및 `timestamp` 정합성 확인.
    - **로그 확인**: `IMH/IMH_Interview/logs/runtime/runtime.log`에 분석 프레임 수 및 처리 시간 기록 확인.


### TASK-009 Voice 분석 (Parselmouth)
- **요약**: `praat-parselmouth` 라이브러리를 활용한 음성 분석 Provider(`ParselmouthVoiceProvider`) 구현 및 Playground API 연동.
- **변경 사항**:
    - `packages/imh_providers/voice/parselmouth_impl.py`: `analyze_audio` 구현 (Pitch, Intensity, Jitter, Shimmer, HNR 추출).
    - `packages/imh_core/dto.py`: `VoiceResultDTO` 확장 (Intensity 및 Min/Max 필드 추가).
    - `IMH/api/playground.py`: `POST /voice` 엔드포인트 추가.
    - `IMH/api/dependencies.py`: `get_voice_provider` 의존성 주입 추가.
    - `scripts/verify_task_009.py`: 검증 스크립트 작성 (Sine Wave, Silence, Invalid File 테스트).
    - **환경 변경**: `praat-parselmouth` 패키지 설치.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_009.py` (Verify Environment: `interview_env`)
        - Sine Wave (440Hz) -> 200 OK. Feature Extraction (Pitch ~440Hz, Jitter/Shimmer/HNR Valid).
        - Silence File -> 200 OK. Null/Zero Values Returned (Graceful Handling).
        - Invalid File (.txt) -> 500 Internal Server Error (Provider Exception Raised).
    - **로그 확인**: `logs/runtime/runtime.log`에 분석 지표 요약 및 예외 스택트레이스 기록.

#### TASK-009 Hotfix (2026-02-10)
- **요약**: Voice 분석 시 잘못된 파일 입력에 대해 500 대신 422 에러를 반환하도록 수정.
- **변경 사항**:
    - `packages/imh_providers/voice/parselmouth_impl.py`: `parselmouth.Sound` 생성 실패 시 `ValueError`로 래핑하여 raise.
    - `IMH/api/playground.py`: `analyze_voice`에서 `ValueError` 포착 시 `HTTP 422` 반환.
    - `scripts/verify_task_009.py`: Invalid File 테스트 기대치를 500 -> 422로 수정.
- **재검증 결과**:
    - Invalid File (.txt) -> 422 Unprocessable Entity 확인.
    - 정상/무음 파일 기존 테스트 통과 유지.

### PRE_TASK-010 선행 안정화 (Stabilization)
- **요약**: TASK-010 착수 전, 기존 Emotion 엔드포인트의 리소스 누수 및 Mock Provider 정합성 버그 수정.
- **변경 사항**:
    - `IMH/api/playground.py`: `analyze_emotion` 내 `UnboundLocalError`(예외 변수 미정의 참조) 및 임시 파일 삭제 누락 수정.
    - `packages/imh_providers/emotion/mock.py`: `EmotionResultDTO` 필수 필드(`scores`) 누락분 보완.
- **검증 증거**:
    - `scripts/verify_task_008.py` 실행 시 임시 파일 삭제 로그(`Temporary Emotion file deleted`) 확인 및 Regression Test (001~009) All Pass.

## 2026-02-10: TASK-010 Visual 분석 (MediaPipe) 구현
Plan 수립
- **요약**: MediaPipe 기반 시각 분석(시선, 포즈, 제스처) 모듈을 프로젝트 표준으로 흡수하기 위한 계획 문서 작성.
- **변경 사항**:
    - `docs/TASK-010_PLAN.md` 작성: "성공했던 구현의 재현 및 표준화"를 골자로 한 Phase 2 최종 분석 모듈 설계 방향 확정.
- **주요 전략**:
    - **재현 기반(Reproduction)**: 과거 성공한 MediaPipe 연동 구조를 Phase 2 기준선으로 고정.
    - **안전 출력 중심**: 얼굴/신체 미검출(No Face) 시에도 안정적인 DTO 반환 보장.
    - **관리형 리스크**: 의존성 충돌 이슈를 재설계가 아닌 환경 관리 대상으로 정의하여 안정성 확보.

### TASK-010 Visual 분석 (MediaPipe) Implementation
- **요약**: MediaPipe 기반 시각 분석(시선, 포즈) Provider(`MediaPipeVisualProvider`) 구현 및 Playground API 연동. Phase 2 기준선(Reproduction Baseline) 준수.
- **변경 사항**:
    - `packages/imh_providers/visual/dto.py`: `VisualResultDTO` 정의 (Presence, Attention, Pose Score 및 Metadata).
    - `packages/imh_providers/visual/mediapipe_impl.py`: `analyze` 메서드 구현. 얼굴 검출, 시선(Yaw), 어깨 기울기(Pose) 분석 로직 적용.
    - `IMH/api/dependencies.py`: `get_visual_provider` 의존성 주입 추가.
    - `IMH/api/playground.py`: `POST /visual` 엔드포인트 구현 (이미지 업로드).
    - `scripts/verify_task_010.py`: 검증 스크립트 작성 (No Face 시나리오 검증).
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_010.py` (Verify Environment: `interview_env`)
        - No Face Image (Black) -> `has_face=False`, `presence_score=0.0` 확인.
        - API Router Import -> 성공.
        - Provider Initialization -> 성공 (MediaPipe Spec: 0.10.5 확인).
    - **로그 확인**: `logs/agent/agent.log`에 `Visual Analysis succeeded. Has Face: False` 기록 확인.

## 2026-02-11: TASK-011 정량 평가 엔진 구현 (Phase 2 Evaluation)
- **변경 요약**: 
  - `packages/imh_eval` 패키지 신규 생성 (Rule-based Scoring Engine)
  - 루브릭 가이드 기반 4대 영역(직무/문제해결/의사소통/태도) 평가 로직 구현
  - `EvaluationContext` -> `RubricEvaluator` -> `EvaluationResult` 파이프라인 구축
  - `schema.py`를 통해 `evidence_data` 및 `tag_code` 계약 준수
  - TASK-011은 Rule-based Engine이며, 모델 품질은 평가 대상이 아님
- **테스트 방법**: 
  - `python scripts/verify_task_011.py` 실행
- **검증 결과**:
  - 만점 시나리오(DEV Profile) -> 5.0점 확인
  - 복합 시나리오(NON_TECH Profile) -> 가중치 적용 점수(2.7점) 정합성 확인
  - JSON Schema output 필드 존재여부 확인 완료
- **로그 파일**: `logs/agent/verify_task_011.log`


### TASK-012 평가 결과 리포팅 / 해석 계층 설계 (Reporting Layer)
- **요약**: `packages/imh_report` 패키지 구현. Evaluation Result를 입력받아 사용자 친화적인 리포트(JSON)를 생성하는 Logic 구현.
- **변경 사항**:
  - `packages/imh_report/dto.py`: `InterviewReport`, `ReportHeader`, `ReportDetail` 등 DTO 정의.
  - `packages/imh_report/mapping.py`: `tag_code` -> Feedback/Insight 매핑 및 등급 산출 로직 구현.
  - `packages/imh_report/engine.py`: `ReportGenerator.generate()` 구현 (5점 척도 -> 100점 환산, 등급 부여, Insight 결합).
  - `scripts/verify_task_012.py`: Mock Data 기반 리포트 생성 및 필드 검증 스크립트 작성.
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_012.py`
    - Mock Evaluation Result (3.5점) -> Report Total Score 70.0점, Grade "B" 확인.
    - 직무 역량(4점) -> "우수합니다" 피드백, Strength 추가 확인.
    - 태도(2점) -> "보완이 필요합니다" 피드백, Weakness 및 Actionable Insight 추가 확인.
    - JSON Output 구조(`header`, `details`, `footer`) 정합성 확인.
- **로그 및 산출물**:
  - `packages/imh_report/__init__.py` 포함 패키지 구조화.

### TASK-013 리포트 저장 / 이력 관리 (Persistence & History)
- **요약**: `packages/imh_history` 구현. `InterviewReport`(JSON)를 파일 시스템에 저장하고, 메타데이터 기반으로 이력을 조회하는 Repository 계층 구축.
- **변경 사항**:
  - `packages/imh_history/dto.py`: 리스트 조회용 메타데이터 `HistoryMetadata` DTO 정의.
  - `packages/imh_history/repository.py`: `HistoryRepository` 인터페이스 및 `FileHistoryRepository` 구현 (파일 시스템 기반 JSON 저장소).
  - `IMH/IMH_Interview/data/reports/`: 리포트 저장소 디렉토리 생성 및 `.gitignore` 설정.
  - `scripts/verify_task_013.py`: 저장(Save), 단건 조회(Find By ID), 목록 조회(Find All) 기능 검증 스크립트 작성.
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_013.py`
    - Save -> `data/reports/{timestamp}_{uuid}.json` 파일 생성 확인.
    - Find By ID -> 저장된 데이터와 조회된 DTO 일치 확인.
    - Find All -> 파일 리스트 파싱 및 타임스탬프 기준 정렬 확인.
    - 메타데이터 정합성(Score, Grade 등) 확인 완료.
- **로그 및 산출물**:
  - `packages/imh_history/` 패키지 구조화.

### TASK-014 리포트 조회 API 노출 (Report API)
- **요약**: 저장(TASK-013)된 리포트 데이터를 조회하기 위한 API Contract 구현 (BFF Endpoint).
- **변경 사항**:
  - `IMH/api/reports.py`: `GET /api/v1/reports` (목록) 및 `/{id}` (상세) 구현.
  - `IMH/api/dependencies.py`: `get_history_repository` 추가.
  - `IMH/main.py`: Report Router 등록.
  - `scripts/verify_task_014.py`: 통합 검증 스크립트 작성 (생성 -> 저장 -> 조회 -> 삭제 파이프라인).
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_014.py` -> `ALL TESTS PASSED`
    1. List API: 생성된 리포트가 목록에 포함됨 확인.
    2. Detail API: 상세 필드(점수, 등급 등)가 원본과 일치함 확인.
    3. Error Handling: 존재하지 않는 ID 요청 시 404 정상 반환 확인.
  - **참고**
    -  Windows 환경에서 테스트 로그 로테이션 시 `PermissionError` 발생 가능하나 로직 무관함.
    - 검증 스크립트(scripts/verify_task_014.py)는 Plan에 명시되진 않았으나, 
      구현 검증 목적의 보조 도구로 사용되었으며 Contract에는 영향을 주지 않는다.”
- **로그 및 산출물**:
  - `packages/imh_history/` 및 `packages/imh_report/` 기존 코드 활용.
  - API Layer 추가.

### TASK-015 리포트 소비 규격 정의 (Consumer Contract)
- **요약**: UI 및 외부 Client가 리포트 데이터를 올바르게 해석하기 위한 소비 규격(`TASK-015_CONTRACT.md`) 작성.
- **변경 사항**:
    - `docs/TASK-015_CONTRACT.md`: 리포트 소비 주체, 목적, 데이터 렌더링 가이드, 책임 경계 정의.
    - 구현 코드 없음 (Plan Only Task).
- **산출물**:
    - [TASK-015_CONTRACT.md](TASK-015_CONTRACT.md)

### TASK-017 Interview Session Engine (Phase 5 Core)
- **요약**: 실시간 면접 세션의 동작 정책을 관장하는 Session Engine (`packages/imh_session`) 구현 완료.
- **변경 사항**:
  - `packages/imh_session/` 패키지 구조화.
  - `state.py`: 5대 세션 상태(APPLIED, IN_PROGRESS, COMPLETED, INTERRUPTED, EVALUATED) 정의.
  - `dto.py`: `SessionConfig` (최소 10질문 기본값), `SessionContext` (Redis-like Hot State) 정의.
  - `repository.py`: Hot State(Redis) / Cold Storage(PostgreSQL) 인터페이스 분리 설계.
  - `engine.py`: Strict State Machine 및 Policy Enforcement 구현.
    - 최소 질문 수(10) 미달 시 조기 종료 차단 로직.
    - 침묵 2케이스(Post-Answer / No-Answer) 분기 처리 및 SILENCE_WARNING 이벤트 구조.
    - 조기 종료 신호(`early_exit_signaled`) 수신 시 종료 처리 로직.
  - `scripts/verify_task_017.py`: Mock Repository 기반 정책 검증 스크립트.
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_017.py` -> `Ran 7 tests in 0.003s OK`
    1. **State Machine**: APPLIED -> IN_PROGRESS -> COMPLETED 전이 확인.
    2. **Min Question Policy**: 10문제 미만에서 조기 종료 신호 무시 확인.
    3. **Early Exit**: 10문제 이상 + 신호 발생 시만 COMPLETED 전이 확인.
    4. **Silence Handling**: 
       - `is_no_answer=True` (무응답) -> 완료 카운트 증가, 다음 질문 진행.
       - `is_no_answer=False` (답변 후 침묵) -> 완료 카운트 증가.
    5. **Interruption**: USER_ABORT 시 INTERRUPTED 상태 확정 확인.
- **로그 및 산출물**:
  - `packages/imh_session/` 패키지 사용.

## 2026-02-13: TASK-018 실전/연습 모드 정책 분리 구현 (Interview Mode Policy Split)

- **작업 내용**:
  - `packages/imh_session/policy.py`: 정책 인터페이스(`InterviewPolicy`) 및 모드 구현체(`ActualModePolicy`, `PracticeModePolicy`) 정의.
  - `packages/imh_session/dto.py`: `SessionConfig`에 `mode: InterviewMode` 필드 추가 (기본값 ACTUAL).
  - `packages/imh_session/engine.py`: 
    - 엔진 초기화 시 정책 주입 로직 추가.
    - 조기 종료(`_complete_current_step`) 및 중단(`interrupt_session`) 로직에 정책 검사(`policy.requires_min_questions_for_early_exit`) 반영.
    - `resume_session` 메서드 추가 (정책 허용 시에만 동작).
  - `scripts/verify_task_018.py`: 실전/연습 모드별 정책 차이(재진입, 조기 종료 시점) 검증 스크립트 작성.

- **검증 결과**:
  - `python scripts/verify_task_018.py`: **Pass**
    1. **실전 모드**: 
       - 중단 시 `INTERRUPTED` 상태로 종료됨을 확인.
       - 재진입(`resume_session`) 시도 시 정책 위반 로그 발생 및 상태 유지 확인.
       - 최소 질문 수(5개) 미만에서 조기 종료 신호 무시(IN_PROGRESS 유지) 확인.
       - 최소 질문 수 충족 후 조기 종료 신호 시 `COMPLETED` 전이 확인.
    2. **연습 모드**: 
       - 중단 후 재진입(`resume_session`) 시 `IN_PROGRESS`로 복구됨을 확인.
       - 최소 질문 수 미만에서도 조기 종료 신호 시 즉시 `COMPLETED` 전이 확인.
  - `python scripts/verify_task_017.py`: **Pass**
    - 기존 엔진 로직(기본값 Actual Mode)에 회귀 없음을 확인.

### TASK-018 기술적 제약 및 향후 요구사항 (2026-02-13 보강)

**A. 런타임 진입점 부재 명시**
- 현재 프로젝트에는 SessionConfig를 생성하고 InterviewSessionEngine을 초기화하는 실제 런타임 경로(API Endpoint / Service Layer)가 아직 존재하지 않는다.
- TASK-017 및 TASK-018은 엔진 코어 로직과 정책 분리, 그리고 단위 검증 스크립트(scripts/verify_task_*.py) 수준까지만 포함한다.
- 따라서 Practice 모드(mode=InterviewMode.PRACTICE) 설정은 verify_task_018.py에서 수동으로 Config를 생성하여 주입하는 방식으로만 검증되었다.

**B. Mode 주입은 통합 단계에서 강제해야 함**
- 향후 Phase 5 후반부(실시간 면접 플로우 통합)에서 "연습 모드 시작" API 또는 "공고 기반 면접 시작" API가 구현될 예정이다.
- 해당 진입점에서 SessionConfig 생성 시 반드시 mode 값을 명시적으로 강제 주입해야 한다.
  - 연습 시작 → mode=InterviewMode.PRACTICE
  - 공고 기반 면접 → mode=InterviewMode.ACTUAL
- mode 값을 요청에 의존하지 말고, 서버 로직에서 강제 설정하도록 구현해야 한다.
- 이 항목은 통합 단계 DoD에 포함되어야 한다.

**C. 상태 전이 중앙 검증 관련 기술 부채 기록**
- `_update_status`는 상태 전이 유효성을 중앙에서 강제 검증하지 않으며, 호출자 책임 구조로 설계되어 있다.
- 현재 `resume_session`은 (1) status==INTERRUPTED 가드 + (2) policy 가드 이후 `_update_status`를 호출하여 문제없이 동작한다.
- 향후 엔진 안정화 단계에서 상태 전이 중앙 검증(guard/validator) 도입을 고려할 수 있다.
- 단, 본 TASK-018 범위에서는 구조 리팩터링이 금지되었으므로 변경하지 않았다.


### TASK-019 공고 정책 엔진 구현 (Job Policy Engine)
- **요약**: 공고(Job Posting)를 "불변의 AI 평가 스키마"로 정의하고, 상태(DRAFT/PUBLISHED/CLOSED)에 따른 엄격한 수정 통제 및 정책 스냅샷 로직을 구현.
- **변경 사항**:
    - `packages/imh_job/` 패키지 신설.
    - `enums.py`: `JobStatus` 정의.
    - `models.py`: `Job`, `JobPolicy` 모델 구현.
        - `JobPolicy`: AI-Sensitive Fields(Time limits, Weights, Requirements 등) 정의 및 유효성 검사.
        - `Job`: `publish()`, `close()`, `update_policy()` 메서드를 통한 상태 전이 및 불변성 강제.
        - `create_session_config()`: `SessionConfig` 스냅샷 생성 로직 구현.
    - `errors.py`: `JobStateError`, `PolicyValidationError` 정의.
    - `scripts/verify_task_019.py`: 상태 전이 및 정책 불변성 검증 스크립트 작성.
- **검증 결과**:
    - `python scripts/verify_task_019.py`: **Pass**
        - DRAFT 상태에서 정책 수정 가능 확인.
        - PUBLISHED 전환 후 정책 수정 시도 시 `PolicyValidationError` 발생 확인 (AI-Sensitive Fields 보호).
        - Session Snapshot 생성 시 값이 정확히 매핑됨을 확인.
        - CLOSED 상태에서 메타데이터 수정 차단 확인.
- **주요 정책 반영**:
    - **Irreversible Transition**: PUBLISHED 상태 이후 되돌리기 불가.
    - **Minimum Questions**: 최소 질문 수 10개 강제 (System Policy).
    - **Result Exposure**: 14일 자동 통지 규칙을 상위 제약으로 명시.

### TASK-019 결함 수정 (Bug Fix)
- **이슈**: Pydantic 모델의 `job.policy = ...` 직접 대입 허용으로 인한 불변성 우회 가능성 확인.
- **수정**: `Job` 모델의 `policy` 필드를 `_policy` (PrivateAttr)로 변경하고, `@property` setter를 통해 상태 기반 쓰기 권한을 강제함.
- **검증**: `verify_task_019.py`에 직접 대입 시도 테스트 케이스 추가 -> `PolicyValidationError` 발생 확인.
