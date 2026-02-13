# PROJECT_STATUS
(IMH AI 모의면접 프로젝트 – ChatGPT 협업 기준 상태 문서)

본 문서는 IMH AI 모의면접 프로젝트의
**현재 상태, 전체 계획, 진행 이력**을
ChatGPT와 사용자(프로젝트 오너)가 공유하기 위한
단일 기준 문서이다.

- 이 문서는 코딩에이전트와 코딩 프로젝트의 내부 문서가 아니다.
- 코딩에이전트와 코딩 프로젝트의 단일 기준 문서는 IMH/IMH_Interview/docs/ 폴더 문서들이다.
- 따라서 코딩에이전트 프롬프트에는 ‘PROJECT_STATUS를 확인하라’는 문구를 넣지 않는다.
- 이 문서는 ChatGPT 협업에서 “기억의 기준점” 역할을 한다.
- 이후 모든 판단은 이 문서를 기준으로 한다.
- 사용자가 이 문서를 수시로 업데이트하며,
  ChatGPT는 항상 최신 버전을 진실로 간주한다.

---

## 1. 프로젝트 개요

### 1.1 프로젝트 목적
- AI 기반 모의면접 시스템 구축
- 단순 Q&A가 아닌,
  **정량 평가 + 근거 제시 + 피드백 제공**이 가능한 면접 시스템

### 1.2 개발 전략 (확정, PROJECT_STATUS 기준)

- **Phase 0**: 운영·기반 고정 (로깅, 규칙, 문서)
- **Phase 1**: Core 구조/표준 확립
- **Phase 2**: API 최소 골격 + Playground
- **Phase 3**: 분석 모듈 (STT / Emotion / Visual / Voice)
- **Phase 4**: 평가 엔진 + 리포팅 + 조회 API 계층 확정
- **Phase 5**: 실시간 면접 플로우 통합 (계약 확정 단계)
  - Session Engine 확정
  - 실전/연습 모드 정책 분리
  - 공고 정책 엔진 고정
  - Snapshot Double Lock 구조 확정
  - 상태 전이(State Contract) 고정
  - 관리자 조회/중단 처리 규격 확정

- **Phase 6**: Service Layer & API Boundary 확정
  - API ↔ Domain 격리(DTO / Mapper)
  - Command / Query 분리
  - Fail-Fast 동시성 정책 적용
  - Runtime Entry 확정
  - API Guardrail(AST 기반) 적용

- **Phase 7**: 질문은행 및 RAG 통합
  - 질문 출처 계층 분리
  - RAG Fallback 전략 정의
  - Snapshot 계약 침범 금지

- **Phase 8**: DB 정식 전환 (PostgreSQL / Redis)
  - 파일 기반 저장소 → RDB 전환
  - 세션 상태 관리 Redis 도입

- **Phase 9**: 운영 통계 및 고도화
  - 관리자 통계 대시보드
  - Query 전용 확장



### 1.3 기본 원칙
- API 기반으로 빠르게 구현 후 on-premise 모델로 교체 가능
- 모든 모델은 교체 가능한 추상화 구조
- 저장은 “분석 결과” 위주, 원본 영상/음성 장기 저장 금지

---

## 2. 협업 규칙 (ChatGPT 기준)

### 2.1 역할 분리
- 사용자: 프로젝트 오너, 승인 권한자
- ChatGPT:  
  - 코드를 직접 작성하지 않음
  - **코딩에이전트에게 전달할 명령/프롬프트를 설계**
- 코딩에이전트(안티그래비티):
  - 실제 코드/문서/구현 수행 주체

### 2.2 작업 진행 규칙
- 모든 작업은 **Plan → 승인 → 구현** 순서
- 승인 전 코드 수정 절대 금지
- TASK 단위로 진행 상태 관리

### 2.3 문서/언어 규칙
- 사람이 읽는 문서(MD): **한국어**
- 코드/로그/에러 메시지: 영어

---

## 3. 단일 기준 문서(Single Source of Truth)

### 3.1 프로젝트 기준 문서 위치

- 실행/구현 판단 기준 문서:
  - `IMH/IMH_Interview/docs/`
    - 00_AGENT_PLAYBOOK.md
    - CURRENT_STATE.md
    - TASK_QUEUE.md
    - (각 TASK_PLAN.md, CONTRACT.md 등 구현 관련 문서 포함)

- 정책/설계 상위 계약 문서:
  - `IMH/IMH_Interview/_refs/`
    - 인터뷰 정책 스펙.md
    - ERD 설계 문서
    - 질문 태그 설계 문서
    - 정량 평가 루브릭 가이드
    - UI 설계 초안

설명:
- docs/ 는 코딩에이전트의 직접 판단 및 구현 기준 문서이다.
- _refs/ 는 시스템 동작 정책 및 상위 설계 계약 문서이다.
- 정책 관련 TASK 설계 시 _refs 문서를 근거로 한다.
- 단, 코딩에이전트는 반드시 docs에 반영된 내용만을 기준으로 구현한다.

---

### 3.2 중요 규칙

- ChatGPT는 다음을 근거로 설계 판단을 수행한다:
  1. PROJECT_STATUS.md
  2. IMH/IMH_Interview/docs/
  3. IMH/IMH_Interview/_refs/ (정책/설계 계약 문서)

- 코딩에이전트는 오직 `IMH/IMH_Interview/docs/` 폴더 문서만을
  구현 기준으로 사용한다.

- 정책(_refs)은 상위 계약 문서이며,
  실제 구현은 반드시 docs에 반영된 이후 수행되어야 한다.

- 과거 대화 기억에 의존하지 않는다.


---

## 4. 전체 TASK 로드맵 및 진행 상태

> 상태 표기:
- DONE : 완료
- ACTIVE : 현재 승인/진행 대상
- BACKLOG : 대기
- HOLD : 보류

---

### Phase 0. 운영·기반 고정

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-001 | 로깅 기반 구축 (agent/runtime 로그, 로테이션, 검증) | DONE |

**TASK-001 요약**
- 공통 로깅 유틸 구현
- 로그 디렉토리 구조 확정
- 스택트레이스 포함 에러 로그 검증 완료

---

### Phase 1. Core 구조·표준

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-002 | imh_core 최소 패키지 구성 (config / errors / dto) | DONE |
| TASK-003 | Provider 인터페이스 정의 + Mock | DONE |

---

### Phase 2. API 최소 골격 / Playground

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-004 | FastAPI 엔트리 + healthcheck | DONE |
| TASK-005 | Playground STT (파일 업로드) | DONE |
| TASK-006 | Playground PDF → Text (문서 업로드) | DONE |
| TASK-007 | Playground Embedding → Query Focus | DONE |

---

### Phase 3. 분석 모듈

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-008 | Emotion 분석 (DeepFace, 1fps) | DONE |
| TASK-009 | Voice 분석 (Parselmouth) | DONE |
| TASK-010 | Visual 분석 (MediaPipe) | DONE |

---

### Phase 4. 평가 / 리포팅 계층

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-011 | 정량 평가 엔진(루브릭 기반) | DONE |
| TASK-012 | 평가 결과 리포팅 / 해석 계층 | DONE |
| TASK-013 | 리포트 저장 / 이력 관리 | DONE |
| TASK-014 | 리포트 API 노출 (BFF Endpoint) | DONE |
| TASK-015 | UI 계약 및 소비 규격 정의 | DONE |

---

### Phase 5. 실시간 면접 플로우 통합

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-016 | TTS Provider (Text → Speech) | HOLD |
| TASK-017 | Interview Session Engine | DONE |
| TASK-018 | Interview Mode Policy Split | DONE |
| TASK-019 | 공고(채용) 정책 엔진 | DONE |
| TASK-020 | 관리자 지원자 조회/필터 규격 | DONE |
| TASK-021 | Interview Session 통합 실행 및 계약 고정 | DONE |

---

---

### Phase 6. Service & API Boundary 확정 (완료)

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-022 | Service Layer 및 DTO 구현 | DONE |
| TASK-023 | API Layer & Runtime Entry 확정 | DONE |

---

### Phase 7. 질문은행 및 RAG 통합

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-024 | 질문은행 구조 정비 | ACTIVE |
| TASK-025 | RAG Fallback 엔진 통합 | BACKLOG |

---

### Phase 8. DB 정식 전환 (PostgreSQL / Redis)

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-026 | PostgreSQL 도입 (공고/세션/평가 영속화) | BACKLOG |
| TASK-027 | Redis 세션 상태 도입 | BACKLOG |

---

### Phase 9. 운영 통계 및 고도화

| TASK ID | 내용 | 상태 |
|------|------|------|
| TASK-028 | 관리자 통계 대시보드 | BACKLOG |


---
## 5. 현재 진행 상태 요약 (최신)

- 완료된 TASK:
  - TASK-001 ~ TASK-015
  - TASK-017
  - TASK-018
  - TASK-019
  - TASK-020
  - TASK-021
  - TASK-022
  - TASK-023
  - (Phase 0 ~ Phase 5 완료)
  - Phase 6 (Service & API Boundary 확정) 완료

- 현재 승인/진행 대상:
  - 없음 (Phase 7 신규 TASK 정의 단계)

- 보류 중:
  - TASK-016 (TTS Provider) – HOLD

- 현재 단계:
  - **Phase 7 진입 준비 단계 (질문은행 및 RAG 통합 설계 단계)**

    - End-to-End 인터뷰 실행 아키텍처 통합 구현 완료 (TASK-021)
    - Interview Session Engine 구현 완료
    - Interview Mode Policy 분리 완료
    - Job Policy Engine (Immutable AI Evaluation Schema) 구현 완료
    - 관리자 조회 규격(Admin Query Layer) 계약 고정 완료
    - 공고 게시 이후 AI-Sensitive Fields 불변 계약 확정
    - DRAFT → PUBLISHED → CLOSED 상태 전이 및 Irreversible Transition 확정
    - 세션 생성 시 정책 스냅샷(Double Lock) 구조 확정
    - Snapshot 기반 Evaluation 및 Admin Query 정합성 확보
    - Result는 EVALUATED 상태에만 적용되는 계약 확정
    - weakness 필터는 Phase 7 이후로 Deferred

    - Service Layer 구축 완료 (TASK-022)
      - API ↔ Domain 완전 격리 (DTO / 명시적 Mapper)
      - Command(Lock) / Query(Bypass) 분리 구조 확정
      - session_id 단위 Fail-Fast 동시성 제어 적용
      - 상태 변경은 반드시 Engine 메서드를 통해서만 수행

    - API Layer & Runtime Entry 확정 완료 (TASK-023)
      - API는 Service Layer의 Facade 역할만 수행
      - Domain/Engine 직접 접근 금지 구조 확정
      - 실제 병렬 API 경쟁 기반 Fail-Fast 검증 완료
      - AST 기반 Router Guardrail 적용 완료
      - Runtime Bootstrap(main) 확정

    - 모든 TASK는 Python 3.10.11 + interview_env 환경에서 검증 완료

  - 다음 단계 (Phase 7 작업 범위):
    - 질문은행 구조 정비
    - RAG Fallback 엔진 통합
    - LLM 기반 질문 생성 로직을 Engine 경계 내에서 통합
    - 질문 출처(Source) 계층 분리 설계
    - Snapshot 계약 침범 방지 하에 RAG 연결



## 6. 업데이트 규칙 (중요)

- 이 문서는 **사용자가 직접 업데이트**한다.
- ChatGPT는 항상 최신 내용을 사실로 간주한다.
- TASK 상태 변경 시:
  - 상태(DONE / ACTIVE / BACKLOG 등)만 갱신
  - 세부 구현 내용은 docs/DEV_LOG.md에 기록

---

## 7. 이 문서의 사용법

새 채팅 시작 시, 사용자는 다음과 같이 말하면 된다:

> “PROJECT_STATUS.md를 기준으로 현재 프로젝트 상태를 파악하고,
> 다음 TASK에 대한 코딩에이전트용 프롬프트를 설계해 달라.”

이 문서 하나로:
- 프로젝트 맥락 복원
- 현재 위치 판단
- 다음 행동 결정
이 모두 가능하다.
