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

### TASK-006 Playground PDF → Text (문서 업로드)
- **Goal**: PDF 업로드 → 텍스트 추출 Playground 파이프라인 검증
- **Scope**:
  - PDF 파일 업로드
  - 텍스트 추출 결과 반환
  - 저장 정책 준수(원본 파일 장기 저장 금지)
- **Verification**: `python scripts/verify_task_006.py` Pass

---

### TASK-007 Playground Embedding → Query Focus
- **Goal**: 검색(RAG) 용도로 사용되는 **Query Text**를 임베딩 벡터로 변환하는 Playground 파이프라인 검증
- **Scope**:
  - Query Text → Embedding 변환
  - Embedding Provider (Mock) 기반 검증
  - 대화 전체 / STT 결과 임베딩 제외
- **Verification**: `python scripts/verify_task_007.py` Pass

---

### TASK-008 Emotion 분석 (DeepFace, 1fps)
- **Goal**: Playground 환경에서 **DeepFace 기반 감정 분석 파이프라인**을 검증하고,
  실시간 면접 적용 전 저주기(1fps) Emotion 분석 코어의 안정성을 확인
- **Scope**:
  - 이미지 / 비디오 파일 기반 Emotion 분석
  - 1fps 프레임 샘플링 기반 DeepFace 추론
  - 얼굴 미검출 / 다중 얼굴 처리 정책 검증
  - 시계열 DTO 구조화 및 Playground API 연동
- **Verification**: `python scripts/verify_task_008.py` Pass

---
## ACTIVE

### TASK-009 Voice 분석 (Parselmouth)
- Parselmouth 기반 음성 분석
- 발화 특성, pitch, intensity 등 음성 지표 추출
- Playground 환경에서 파일 기반 검증

---
## BACKLOG

### TASK-010 Visual 분석 (MediaPipe)
- MediaPipe 기반 시선/포즈/제스처 분석

---

### TASK-011 정량 평가 엔진 (루브릭 기반)
- 정량 평가 루브릭(JSON 스키마) 기반 점수 산출
- 분석 결과를 평가 입력으로 변환

---

### TASK-012 평가 근거 데이터 구조 (Evidence)
- 평가 점수 산출 근거 데이터 구조 정의
- 결과 리포트/감사용 Evidence JSON 설계

---

## HOLD

### TASK-013 TTS Provider (Text → Speech)
- 면접관 음성 출력(TTS) Provider 인터페이스 및 Mock
- 실시간 면접/세션 단계에서만 착수