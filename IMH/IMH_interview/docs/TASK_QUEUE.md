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

## ACTIVE

### TASK-004 FastAPI 최소 엔트리 + healthcheck
- `/health` 단일 엔드포인트

### TASK-005 Playground STT (파일 업로드)
- Mock STT Provider 기반

### TASK-006 Playground Voice 분석
- Parselmouth 기반

### TASK-007 Playground Emotion 분석
- DeepFace (1fps)

### TASK-008 Playground Visual 분석
- MediaPipe
