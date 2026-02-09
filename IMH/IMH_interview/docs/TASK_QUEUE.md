# TASK_QUEUE
(IMH AI 면접 시스템 – 에이전트 작업 통제 큐)

본 문서는 AI 코딩 에이전트가 **현재 시점에 수행해도 되는 작업만을 명시**한다.  
에이전트는 ACTIVE 상태의 TASK만 수행 가능하며,  
그 외 작업은 절대 착수해서는 안 된다.

---

## 상태 정의
- BACKLOG : 대기 (착수 금지)
- ACTIVE  : 현재 허용
- DONE    : 완료

---

## DONE

### TASK-001 로깅 기반 구축 (Phase 0)
- **Goal**
  - 개발/테스트/런타임 중 발생하는 모든 에러가
    반드시 **파일 로그(.log)** 로 남는 기반을 구축한다.

- **Scope (포함)**
  - `IMH/IMH_Interview/logs/agent/` 폴더 생성
  - `IMH/IMH_Interview/logs/runtime/` 폴더 생성
  - 공통 로거 유틸 설계 (Rotating / Error 분리)
  - `logger.exception()` 사용 규칙 정립

- **Verification**
  - `python scripts/check_logging.py` 실행 시 성공


---

### TASK-002 imh_core 최소 패키지 구성 (Phase 1)
- **Goal**: config / errors / dto 최소 코어 확정 및 구현
- **Scope**: `packages/imh_core/{config.py, errors.py, dto.py}`
- **Verification**: `scripts/verify_task_002.py` Pass

---

### TASK-003 Provider 인터페이스 + Mock 구현
- STT / LLM / Emotion / Visual / Voice 인터페이스 정의
- Mock 구현체 작성 (테스트 용도)
- **Verification**: `scripts/verify_task_003.py` Pass

---

### TASK-004 FastAPI 최소 엔트리 + healthcheck
- `/health` 단일 엔드포인트
- **Verification**: `IMH/api/health.py` 구현 및 `scripts/verify_task_004.py` Pass

---

### TASK-005 Playground STT (파일 업로드)
- **Goal**: Mock STT Provider 기반 파일 업로드 및 분석 API 구현
- **Scope**: `POST /api/v1/playground/stt`
- **Verification**: `python scripts/verify_task_005.py` Pass

---

## ACTIVE

(없음 - 에이전트 대기 중)

## BACKLOG

### TASK-006 Playground PDF → Text (문서 업로드)
- PDF 업로드 → 텍스트 추출
- 저장 정책 준수(원본 파일 장기 저장 금지)
- (선택) 텍스트 결과를 LLM 입력으로 연결 가능한 형태로 반환

### TASK-007 Voice 분석 (Parselmouth)
- Parselmouth 기반

### TASK-008 Emotion 분석 (DeepFace, 1fps)
- DeepFace (1fps)

### TASK-009 Visual 분석 (MediaPipe)
- MediaPipe

### TASK-010 정량 평가 엔진 (루브릭 기반)
- 정량 평가 루브릭(JSON 스키마) 기반 점수 산출
- 분석 결과를 평가 입력으로 변환

### TASK-011 평가 근거 데이터 구조 (Evidence)
- 평가 점수 산출 근거 데이터 구조 정의
- 결과 리포트/감사용 Evidence JSON 설계


## HOLD

### TASK-012 TTS Provider (Text → Speech)
- 면접관 음성 출력(TTS) Provider 인터페이스 및 Mock
- 실시간 면접/세션 단계에서만 착수