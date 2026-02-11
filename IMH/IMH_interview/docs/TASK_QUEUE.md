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

### TASK-009 Voice 분석 (Parselmouth)
- **Goal**: Playground 환경에서 **Parselmouth 기반 음성 분석 파이프라인**을 검증하고,
  실시간 면접 적용 전 음성 특성 분석 코어의 안정성을 확인
- **Scope**:
  - 오디오 파일 기반 음성 분석
  - Pitch / Intensity / Jitter / Shimmer / HNR 등 음향학적 지표 추출
  - 무음 / 비정상 파일 입력에 대한 예외 처리 정책 검증
  - Voice Provider 실구현체(Parselmouth) 기반 동작 확인
- **Verification**: `python scripts/verify_task_009.py` Pass

---

### TASK-010 Visual 분석 (MediaPipe)
- **Goal**: Playground 환경에서 **MediaPipe 기반 시각 분석 파이프라인**을 검증하고,
  실시간 면접 적용 전 비언어적 시각 정보 분석 코어의 안정성을 확인
- **Scope**:
  - 이미지 기반 얼굴 검출 및 존재 여부(Presence) 판단
  - 시선(Yaw) 및 자세(Pose) 정보 추출
  - 얼굴 미검출(No Face) 시 안전한 결과 반환 정책 검증
  - Visual Provider 실구현체(MediaPipe) 기반 동작 확인
- **Verification**: `python scripts/verify_task_010.py` Pass

---

### TASK-011 정량 평가 엔진 (루브릭 기반)
- **Goal**: Mock Provider / Analysis Result 기반 **정량 평가 로직(Eval Engine)** 검증
- **Scope**:
  - `packages/imh_eval` Rule-based 평가 로직
  - 직무/문제해결/의사소통/태도 영역별 점수 산출
  - `evidence_data` JSON 스키마 준수 및 직군별 가중치 적용
- **Verification**: `python scripts/verify_task_011.py` Pass

---

### TASK-012 평가 결과 리포팅 / 해석 계층 설계 (Reporting Layer)
- **Goal**: EvaluationResult(+Evidence)를 사용자 친화적 **InterviewReport(JSON)**로 변환하는 리포팅/해석 계층 구축
- **Scope**:
  - `packages/imh_report` 구현 (DTO / Mapping / Report Generator)
  - Score → Total Score(100점 환산) / Grade 매핑
  - `tag_code` 기반 Feedback/Insight 매핑
  - Mock 기반 Report 생성 및 구조 검증
- **Verification**: `python scripts/verify_task_012.py` Pass

### TASK-013 리포트 저장 / 이력 관리 (Persistence & History)
- **Goal**: 생성된 `InterviewReport`를 서비스 데이터로 보존하고, 면접 회차별 조회/리스트/상세 조회를 위한 Persistence 계층 구축
- **Scope**:
  - 파일 시스템 기반 `InterviewReport` 저장 구조 구현 (식별자/타임스탬프 기반)
  - Repository 인터페이스(`HistoryRepository`) 및 파일 기반 구현체(`FileHistoryRepository`) 구현
  - 메타데이터 파싱 기반 이력 조회(Find By ID / Find All) 기능 구현
  - 저장/조회 검증 스크립트(`scripts/verify_task_013.py`) 작성 및 검증 완료
- **Verification**: `python scripts/verify_task_013.py` Pass

---
## ACTIVE
### TASK-014 리포트 조회 API 노출 (Report API Contract)

- **Goal**:
  - 저장된 `InterviewReport`를 외부(UI/관리자/후속 서비스)에서 소비할 수 있도록
    **조회 전용 API 계약을 정의하고 노출**한다.

- **Scope**:
  - 단건 리포트 조회 API 계약 정의 (interview_id 기준)
  - 리포트 목록 조회 API 계약 정의 (타임스탬프 기준 정렬)
  - 응답 스키마 고정:
    - TASK-012에서 정의된 `InterviewReport` JSON 구조 재사용
  - API 응답 포맷 및 필드 의미 명세

- **Out of Scope**:
  - UI 화면 구현
  - 인증/권한 고도화
  - DB / 외부 저장소 연동
  - 실시간 세션 API

- **Dependencies**:
  - TASK-013 (리포트 저장 / 이력 관리) 완료
---

## HOLD

### TASK-015 리포트 소비 규격 정의 (UI / Client Contract)

- **Goal**:
  - 프론트엔드 및 클라이언트 관점에서
    `InterviewReport` JSON을 **어떻게 해석·표현·소비할지에 대한 규격을 확정**한다.

- **Scope**:
  - 리포트 주요 필드의 UI 표현 규칙 정의
    - 점수(Score), 등급(Grade), 요약(Summary), 피드백(Insight)
  - 시각화 요소 사용 규칙 정의
    - Radar Chart / Bar Chart 등에서 사용하는 필드 범위
  - 텍스트 길이 제한, 요약 우선순위 등 UI 친화 규칙 명시

- **Out of Scope**:
  - 실제 UI 컴포넌트 구현
  - 디자인 시안 작업
  - 사용자 인터랙션 로직

- **Dependencies**:
  - TASK-012 (Reporting Layer) 완료
  - TASK-014 (리포트 조회 API 계약) 완료
  
### TASK-016 TTS Provider (Text → Speech)
- **Goal**:
  - 면접 결과 또는 실시간 피드백을 음성으로 출력하기 위한 TTS Provider 계층 준비
- **Scope (예정)**:
  - TTS Provider 인터페이스 정의
  - Mock 기반 Text → Speech 변환 파이프라인
- **보류 사유**:
  - 현재 Phase에서는 리포트 저장/이력 및 리포트 소비 계약(API/UI) 확정이 우선
  - 출력 텍스트의 책임 경계(Reporting vs UI)가 아직 완전히 고정되지 않음
- **재개 조건**:
  - 리포트 저장 / 이력 관리 완료 (TASK-013)
  - 리포트 API 노출 계약 정의 (TASK-014)
  - UI 소비 규격 정의 완료 (TASK-015)