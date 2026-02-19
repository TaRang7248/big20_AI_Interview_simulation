# CURRENT_STATE
(IMH AI 면접 시스템 – 현재 개발 상태 스냅샷)

본 문서는 AI 코딩 에이전트가 **작업을 시작할 때 반드시 먼저 읽어야 하는 문서**이다.  
에이전트는 이 문서에 적힌 내용만을 근거로 현재 상태를 판단하며,
기억·추측·자율적 확장을 해서는 안 된다.

## 개발 실행 환경 (강제)

- Python: **3.10.11**
- Virtual Environment: **interview_env (venv)**
- 모든 python 실행 / pip install / 검증은
  반드시 `interview_env` 활성화 상태에서 수행한다.
- 글로벌(시스템) Python 환경에 패키지 설치는 금지한다.

# 검증 상태 요약 (Phase 1 ~ Phase 10, TASK-004 ~ TASK-028)

# Phase 1 ~ Phase 4. Core Processing & Report Layer

## 1. Core Processing Layer (TASK-004 ~ TASK-011)

- 파일 검증, 텍스트 추출, 임베딩 파이프라인 정상 동작 검증 완료
- 음성 분석(Pitch/Intensity/Jitter/Shimmer/HNR) 정책 계약 동작 확인
- 얼굴 분석(MediaPipe) 및 No Face 정책 계약 동작 확인
- 루브릭 기반 점수 산출 및 직군 가중치 로직 정상 동작 확인
- 모든 검증은 Python 3.10.11 + `interview_env` 환경에서 수행됨

---

## 2. Report & Persistence Layer (TASK-013 ~ TASK-014)

- InterviewReport 파일 저장/조회/정렬 계약 동작 검증 완료
- `/reports` API 목록/상세 조회 정상 동작 확인
- DTO 직렬화 및 404 처리 계약 동작 검증 완료
- 파일 기반 메타데이터 구성 정책 유지 확인
- 저장 단위 원자성 및 정렬 기준 계약 유지 확인

---

# Phase 5. Session & Policy Engine Architecture 고정

## 3. Session & Policy Engine Layer (TASK-017 ~ TASK-019, TASK-021)

- 세션 상태 전이(APPLIED → IN_PROGRESS → COMPLETED/INTERRUPTED → EVALUATED) 계약 동작 검증 완료
- 최소 질문 수 10개 규칙 및 침묵 처리 규칙 계약 동작 검증 완료
- Actual / Practice 모드 분리 및 Resume 정책 계약 동작 검증 완료
- 공고 상태 전이(DRAFT → PUBLISHED → CLOSED) 및 Immutable Policy 계약 동작 검증 완료
- AI-Sensitive Fields 불변 계약 유지 확인

### End-to-End 통합 실행 (TASK-021)

- Job Policy Freeze at Publish 적용 확인
- Snapshot Double Lock(Job/Session) 계약 동작 검증 완료
- Snapshot 기반 질문/평가/조회 흐름 정합성 확인
- Phase 5 핵심 계약(Freeze / Snapshot / State Contract) 보호 상태 확인

📌 **Phase 5 기준선**
- 상태 전이 계약 고정
- Snapshot 불변성 고정
- Freeze at Publish 계약 고정
- Engine이 유일한 상태 변경 권한 보유

---

# Phase 6. Service Layer & API Boundary 확정 (TASK-022 ~ TASK-023)

## 4. Service Layer (TASK-022)

- API → Service → Engine 단일 Command 경로 강제
- 상태 변경은 반드시 Engine 메서드를 통해서만 수행됨
- DTO ↔ Domain 완전 분리 (명시적 Mapper 적용)
- Command / Query 분리(CQRS) 구조 고정
- session_id 단위 Fail-Fast 동시성 정책 적용
- Admin Query는 Read-Only Query Service 경로로 분리

## 5. API Layer & Runtime Entry (TASK-023)

- API Layer는 Service Layer의 Entry Adapter로만 동작
- Engine/Repository 직접 접근 없음 (AST Guardrail 검증 완료)
- 상태 전이 / Lock 정의 / Freeze 해석을 API에서 수행하지 않음
- 병렬 요청 경쟁 시 1건 423 즉시 반환 검증 완료

📌 **Phase 6 기준선**
- API ↔ Service ↔ Engine 경계 고정
- Fail-Fast 동시성 정책 확정
- 외부 런타임 진입점 안정화 완료

---

# Phase 7. Question Bank & RAG Fallback Integration

## 6. Question Bank Layer (TASK-024)

- `packages/imh_qbank` 구조 확정 (Domain / Repository / Service)
- Source 계층 정의 (STATIC / GENERATED ORIGIN)
- Soft Delete 정책 도입 (status=DELETED → 신규 세션 자동 제외)
- Snapshot과 완전 독립(Value Object) 구조 검증 완료
- Hard Delete 경로 없음 확인

## 7. RAG Fallback Engine 통합 (TASK-025)

- SessionEngine 단일 판단 주체(Fallback Authority) 고정
- 3-Tier 전략 검증 완료:
  1) RAG 생성
  2) Static QBank Fallback
  3) Emergency Safe Fallback
- Generated 질문은 Snapshot에 Value로 고정
- Snapshot Independence 검증 완료
- Freeze / Snapshot / State Contract 침해 없음 확인

📌 **Phase 7 기준선**
- Question Source 이중 구조 안정화
- Engine 권한 단일화 유지
- Snapshot 오염 없음

---

# Phase 8. PostgreSQL 영속화 전환 완료 (TASK-026)

- Primary Data Store: PostgreSQL
- Memory는 Secondary / Rollback Safety 용도로만 유지
- Write Path: PostgreSQL → Secondary 구조 유지
- Restart Replay / Rollback Safety 검증 완료
- Snapshot 영속화 전략 확정

📌 **Phase 8 기준선**
- PostgreSQL 단일 권위 저장소 확정
- Authority 구조 명확화 완료

---

# Phase 9. Redis Runtime & Control Layer 고정 (TASK-027)

## 8. Redis Baseline (TASK-027 CP0 ~ CP4)

- Runtime Mirror (PG → Redis 복제)
- Distributed Lock (interview_id 단위)
- Idempotency Guard (request_id 기반)
- Write Order: PG Commit → Redis Mirror
- No Write-Back 계약 유지
- Redis Down 시 Fail-Fast Reject
- Hydration = Mirror 복원 (상태 변경 아님)
- Pause는 Operational Flag (State Transition 아님)

📌 **Phase 9 기준선**
- Redis는 Authority가 아니다.
- Redis는 Control + Runtime Layer 전용이다.
- Snapshot / Freeze / State Contract 침해 없음.

---

# Phase 10. Operational Statistics & Observability Layer (TASK-028)

## 9. Business Statistics Layer (CP0) — LOCKED

- Track A: PostgreSQL Snapshot 기반 통계
- Type 1: Real-Time Status
- Type 2: 기간 집계 / 평균 점수
- Redis는 Result Cache Only
- TTL / as_of 일관성 검증 완료
- PostgreSQL Authority 유지

## 10. Operational Observability Layer (CP1) — LOCKED

- Track B: Informational Only (비즈니스 지표와 혼합 금지)
- Reason / Span / Layer 3축 메타 모델 확정
- Log 기반 Latency / Failure Rate / Cache Hit 관측 구현
- 상태 전이 실패율: 기존 로그/PG 실패 이벤트 기반 집계
- Type 3: MView 격리 전략 + 쿼리 레벨 증명 완료
- Type 4: DISABLED (실시간 실행 금지, 영속 저장 없음)
- Track A / Track B 물리적 분리 검증 완료
- 신규 Write Path 없음
- Engine/Command 수정 없음

📌 **Phase 10 기준선**
- 통계와 관측 계층 분리 완료
- Authority 구조 유지
- Heavy Query 격리 전략 확정
- 운영 관측 계층 안정화

---

# 📌 현재 시스템 상태 (Phase 1 ~ Phase 10 완료)

- 상태 전이 / Snapshot / Freeze 계약 고정
- PostgreSQL 단일 권위 저장소 확정
- Redis는 Runtime/Cache 전용
- Business Stats와 Observability 완전 분리
- Heavy Query 격리 전략 확정
- 신규 영속 Write Path 없음
- 핵심 계약 침해 없음

---

> 시스템은 실행 엔진 + 영속화 + 런타임 제어 + 통계 + 관측까지 완성된 상태이다.
> 운영 가능한 아키텍처로 안정화되었다.

---

## 1. 프로젝트 목적 (확정)

- 목적: **AI 모의면접 시스템**
- 전략:
  - 1단계: **API 기반 모델로 핵심 기능을 빠르게 구현**
  - 2단계: **on-premise 모델로 교체하여 성능/비용 최적화**
- 모든 모델은 **API / Local(on-prem)** 방식으로 언제든 교체 가능하도록 추상화한다.
- 질문 생성(RAG/LLM) 또한 Provider 추상화를 통해 교체 가능하도록 설계한다.
- Engine은 정책 판단의 단일 주체이며, 외부 모델은 수동적 공급자 역할만 수행한다.

---
## 2. 현재 개발 단계

- 상태: Phase 10 COMPLETE → Phase 11 정의 대기

---

### Phase 5 완료: End-to-End 실행 아키텍처 고정 (TASK-021)

- 세션 엔진 통합 완료
- Job Policy Freeze at Publish 계약 고정
- Snapshot Double Lock (Job / Session) 구조 확정
- 상태 전이(State Contract) 기반 실행 흐름 고정
- 관리자 조회 계층(Admin Query Layer) 통합 완료
- Snapshot 기반 Evaluation / Admin Query 정합성 확보

---

### Phase 6 완료: Service Layer & API Boundary 확정 (TASK-022 ~ TASK-023)

- DTO / Mapper 완전 분리
- Command / Query 분리(CQRS) 계약 고정
- Fail-Fast 동시성 정책 적용
- API → Service → Engine 단일 Command 경로 고정
- Engine 외부 정책 판단 경로 차단
- AST 기반 Guardrail 적용 완료
- Runtime Entry 경계 확정

---

### Phase 7 완료: Question Bank & RAG Fallback Integration (TASK-024 ~ TASK-025)

#### Question Bank 정비
- Source 계층 정의 (Static Origin / Generated Origin)
- Soft Delete 정책 도입
- Snapshot과 완전 독립(Value Object) 구조 확정
- Engine/Service 경계 침범 없음 검증 완료

#### RAG Fallback 통합
- SessionEngine 단일 판단 주체(Fallback Authority) 고정
- 3-Tier 전략 구현:
  1) RAG 생성
  2) Static QBank Fallback
  3) Emergency Safe Fallback
- Fallback은 상태 전이를 유발하지 않음
- Snapshot Value Object 불변성 유지
- Freeze 계약 침범 없음 확인
- Snapshot Independence 검증 완료
- Contract Stability 재검증 완료

---

### Phase 8 완료: PostgreSQL 영속화 전환 (TASK-026)

- Primary Data Store: PostgreSQL (Read / Write)
- Write Path Switch 완료 (`WRITE_PATH_PRIMARY=POSTGRES`)
- Dual Write 유지 (Postgres Primary + Memory Secondary)
- Restart Replay / Rollback Safety 검증 완료
- Snapshot 영속화 전략 확정
- 기존 File 기반 저장소 전환 완료

📌 **Phase 8 기준선**
- PostgreSQL이 단일 권위 저장소
- Memory는 Secondary / Rollback Safety 용도로만 유지
- 핵심 계약(Freeze / Snapshot / State Contract) 유지

---

# Phase 9. Redis Runtime & Cache Architecture (COMPLETE)

## TASK-027 / CP0 ~ CP4 (🔒 LOCKED)

---

## TASK-027 / CP0 (Baseline Runtime Layer)

- **Status**: VERIFIED → 🔒 LOCKED
- **Scope**:
  - Runtime Mirror (PG → Redis 단순 복제)
  - Distributed Lock (`interview_id` 단위)
  - Idempotency Guard (`request_id` 기반)

- **Immutable Contracts**:
  - PostgreSQL Only Source of Truth
  - Write Order: PG Commit → Redis Mirror
  - No Write-Back (Redis → PG 금지)
  - Redis Down 시 Fail-Fast Reject
  - Hydration = Mirror 복원 (상태 변경 아님)
  - Pause는 Operational Flag (State Transition 아님)

---

## TASK-027 / CP1 (Projection Cache)

- **Status**: VERIFIED → 🔒 LOCKED
- **Scope**:
  - SessionProjectionDTO
  - RedisProjectionRepository
  - Read-Through Strategy
  - Invalidate-First Policy
  - Redis Down Fallback

---

## TASK-027 / CP2 (RAG Cache)

- **Status**: VERIFIED → 🔒 LOCKED
- **Scope**:
  - RAGCacheDTO / RedisRAGRepository
  - CachedQuestionGenerator Decorator
  - Async Save
  - Versioned Key Strategy
  - Authority 기반 TTL 제어

---

## TASK-027 / CP3 (Candidate Cache)

- **Status**: VERIFIED → 🔒 LOCKED
- **Scope**:
  - Candidate Entity Cache
  - Candidate List Cache
  - Read Optimization 전용 설계
  - Invalidate-on Save/Delete
  - Stale Data Protection (`is_active=true` 보장)
  - Redis Down Soft Fallback

---

## TASK-027 / CP4 (Prompt Composition Cache)

- **Status**: VERIFIED → 🔒 LOCKED
- **Scope**:
  - RedisPromptRepository
  - CachedPromptComposer (Read-Through Pattern)
  - Logical Prompt Version Identifier
  - Versioned Key Strategy
  - Max Size Limit
  - Stampede Protection (Leader/Follower 최소 완화 전략)
  - Fail-Open Strategy

---

# Phase 9 최종 기준선 (LOCKED BASELINE)

- PostgreSQL = Single Source of Truth
- Redis = Read Optimization Only
- Write Order = PG → Redis
- No Write-Back
- Snapshot Immutable 유지
- Job Policy Freeze 유지
- Deterministic Evaluation 보장
- Restart Replay / Rollback Safety 유지

📌 Redis는 Authority가 아니다.
📌 모든 Cache는 Derived Data이다.
📌 Redis Down은 시스템 장애가 아니다.
📌 Dual Write 제거 조건 충족 상태.

---

# Phase 9의 목적 (완료)

- Redis Control Layer 안정화
- Runtime Mirror 신뢰성 확보
- Cache 확장(CP1~CP4) 안전성 검증 완료
- Dual Write 제거 준비 완료
- Phase 10 확장을 위한 안정적 아키텍처 기반 확보

---
# Phase 10

## TASK-028 관리자 통계 및 운영 관측 계층 (Phase 10) — ✅ DONE / LOCKED

> Phase 10 (Operational Statistics & Observability Layer) 완료.  
> CP0 (Track A) 및 CP1 (Track B) 모두 LOCKED 상태로 전환되었다.

### TASK-028 / CP0 (Business Statistics MVP) — 🔒 LOCKED
- **Status**: 🔒 LOCKED
  - Authority / Caching / Isolation (verify_task_028_cp0.py): PASS
  - TTL 만료/복귀 및 as_of 일관성 (verify_task_028_cp0_ttl.py): PASS
- **Scope**:
  - Track A (Business Stats) Only
  - Query Type 1 (Real-time) & Type 2 (Period Aggregated)
  - `packages/imh_stats` Package
- **Contracts** (불변):
  - PostgreSQL Authority (Source of Truth)
  - Redis Read-Through Cache Only (No Authority)
  - Read-Only Query Layer (No Side-effects)

---

### TASK-028 / CP1 (Operational Observability & Heavy Query Isolation) — 🔒 LOCKED
- **Status**: 🔒 LOCKED
  - Code Level Separation (Track A/B): PASS
  - Type 4 DISABLED Guard: PASS
  - informational_only=True enforced: PASS
  - Log-based Latency/FailureRate/CacheHitRate: PASS
  - Redis as_of preservation (Miss→Hit): PASS
  - PG State Transition Failures (No Engine Mod): PASS
  - Type 3 MView Isolation (query-level: TYPE3_MVIEW_NAME, SQL template, banned table check): PASS
  - TTS_SYNTHESIS excluded from active Spans: PASS
- **Scope**:
  - Track B (Operational Observability) — Informational Only
  - `obs_enums.py`, `obs_dtos.py`, `obs_repository.py`, `obs_service.py`
  - Type 3 MView strategy (DB-level, repo routes to MView if exists)
  - Type 4 DISABLED (no endpoint, no storage)
- **Contracts** (불변):
  - Track B NEVER called by Track A Services/Repos
  - Redis = Result Cache Only (setex, TTL, as_of preserved)
  - No Engine/Command modification
  - No Write-Back, No new persistent paths
  - TTS_SYNTHESIS = Reserved (excluded from CP1)

---

### TASK-028 최종 계약 재확인 (Immutable)

다음 계약은 TASK-028 완료 이후에도 절대 변경되지 않는다:

| 계약 | 상태 |
|---|---|
| PostgreSQL Authority는 유지된다 | ✅ 확인 |
| Redis는 Result Cache Only이다 | ✅ 확인 |
| Observability는 Informational Only이다 | ✅ 확인 |
| Business Stats(Track A)와 Observability(Track B)는 물리적으로 분리되어 있다 | ✅ 확인 |
| Engine / Command / State Contract는 변경되지 않았다 | ✅ 확인 |
| 신규 영속 Write Path는 생성되지 않았다 | ✅ 확인 |
| Snapshot / Freeze 계약은 유지된다 | ✅ 확인 |

---

## 3. 확정된 핵심 방향 (변경 금지)

### 3.1 기능 우선순위 (Phase 9 완료 기준)

1. **Phase 2 Playground 기반 정적 파일 분석은 유지 (독립 테스트 하네스)**

- 오디오/영상 업로드 → STT / 감정 / 시선 / 음성 분석 검증
- 문서(PDF) 업로드 → Text 추출(PDF → Text)
- 목적: 개발/검증/Regression 테스트 환경 유지
- Session Engine / Snapshot 구조와 완전히 분리 유지
- Redis / Runtime / Cache 계층과도 독립
- Engine 상태 전이(State Contract)와 무관
- Business Statistics / Observability 계층과도 독립

> Playground는 운영 흐름이 아닌 실험/검증 전용 영역이다.

---

2. **Phase 7 완료: 질문은행 + RAG Fallback 통합 구조 (LOCKED)**

- Session Engine 단일 정책 판단 구조 유지
- Question Source 분리 구조 확정:
  - STATIC (Question Bank)
  - GENERATED (RAG/LLM)
- RAG 실패 시 3-Tier 전략 고정:
  1) RAG 생성 시도
  2) Static QBank Fallback
  3) Emergency Safe Fallback
- Fallback은 상태 전이를 유발하지 않음 (State Contract 불변)
- Generated 질문은 Snapshot에 Value Object로 고정
- Freeze / Snapshot / State Contract 계약 침범 금지
- Engine 외부에서 Question Source 변경 경로 금지
- Redis Cache 계층은 Read Optimization Only
- Snapshot Immutable 계약 유지
- Business Statistics / Observability 계층은 Question Source에 영향 없음

> Engine이 유일한 질문 정책 결정 권한을 가진다.

---

3. **TTS (Text → Speech)**

- 실시간 면접 단계의 구성요소
- 현재 HOLD 유지
- Prompt Cache / Snapshot 안정화 이후 재개 예정
- Provider 패턴 기반 통합 예정
- Engine 경계 침범 금지
- Redis Authority와 무관
- Observability Span은 Reserved 처리 (현재 구현 범위 제외)

> TTS는 현재 시스템 계약에 영향을 주지 않는 보류 기능이다.

---

4. **RAG / 질문은행 / 임베딩 (Phase 7~9 안정화 완료)**

- 온프레미스 저성능 모델 보정 목적
- 질문 품질 안정화 및 직무/공고 기반 보강
- Fallback 구조 LOCKED
- 향후 확장 가능성:
  - PGVector 도입
  - 외부 RAG 엔진 교체
- Engine 경계 불변 유지
- Snapshot 계약과 충돌 금지
- metadata 최소 집합 유지 (Snapshot 오염 방지)
- Redis RAG Cache는 Derived Data이며 Authority가 아님
- Business Stats 및 Observability는 RAG 내부 상태에 의존하지 않음

> RAG는 품질 보강 계층이며 상태 권한을 가지지 않는다.

---

5. **Business Statistics & Observability (Phase 10 완료 — LOCKED)**

### Track A: Business Statistics
- PostgreSQL Snapshot 기반 통계
- Type 1: Real-Time Status
- Type 2: 기간 집계 / 평균 점수
- Redis는 Result Cache Only
- TTL / as_of 계약 유지
- PostgreSQL Authority 유지

### Track B: Operational Observability
- Informational Only (비즈니스 지표와 혼합 금지)
- Reason / Span / Layer 3축 메타 모델 확정
- Log 기반 Latency / Failure Rate / Cache Hit 관측
- 상태 전이 실패율은 기존 로그/PG 실패 이벤트 기반
- Track A / Track B 물리적 분리 유지
- 신규 Write Path 없음
- Type 3: MView 격리 전략 확정
- Type 4: DISABLED 유지

> 통계는 권위 데이터 기반, 관측은 참고용이다.
> 두 계층은 절대 혼합되지 않는다.

---

6. **UI / 프론트 연동 (Phase 11 이후 확장 예정)**

- API → Service → Engine 단일 Command 경로 유지
- Command / Query 분리 원칙 유지
- 상태 전이(State Contract) API 우회 금지
- 질문 Source 조작 API 금지
- Redis Cache 직접 접근 API 금지
- Snapshot Freeze 이후 수정 경로 금지
- Track A / Track B 분리 구조 유지
- Observability는 UI에 노출 가능하나 Informational임을 명시

> UI는 계약을 소비하는 계층이며 계약을 변경할 수 없다.
---

## 세션 상태 (변경 금지)

- APPLIED  
- IN_PROGRESS  
- COMPLETED  
- INTERRUPTED  
- EVALUATED  

→ 기준 상태값으로 유지 (변경 금지)  
→ Fallback은 해당 상태에 영향을 주지 않음  
→ Redis Runtime / Cache는 상태 전이를 발생시키지 않음  
→ Evaluation은 EVALUATED 상태에서만 결과 확정  

---

### 3.2 모델 구성 (현재 기준)

| 분석 항목 | 모델 | 실행 환경 |
|----------|------|-----------|
| STT | Faster-Whisper | GPU (VRAM ~1GB) |
| LLM | GPT-4o / Qwen3-4B / A.X-4.0-Light / EXAONE 7.8B / Llama3.1-KO | GPU (~4.5GB) |
| Emotion | DeepFace | CPU (1fps) |
| Visual | MediaPipe | CPU |
| Voice | Parselmouth | CPU |

※ 모델 교체 가능 (Provider 인터페이스 고정)
※ Engine은 모델에 의존하지 않음 (정책 판단 분리 유지)
※ RAG/LLM은 동기 Request/Response 방식 기준으로 통합 완료
※ Streaming 방식은 별도 Phase에서 구조 검토 후 도입

---
## 4. 저장 정책 (확정)

- ❌ 서버는 **원본 영상/오디오 파일을 장기 저장하지 않는다**
- ⭕ 저장 대상:
  - 텍스트 (STT 결과)
  - 분석 결과 요약
  - 평가 점수 및 근거 (JSONB)
- 목적:
  - 보안 리스크 최소화
  - 저장 비용 최소화
  - 법적 책임 범위 최소화

---

### 4.1 현재 저장소 상태 (Phase 9 완료 기준)

- PostgreSQL = **Single Source of Truth**
  - users / job_postings / interviews / evaluations 기반 영속화
  - chat_history는 `INTERVIEWS.chat_history (jsonb)`로 통합
  - 평가 결과는 JSONB 기반 구조로 저장

- Redis = **Read Optimization Only**
  - Runtime Mirror
  - Projection / RAG / Candidate / Prompt Cache
  - Authority 없음
  - No Write-Back 유지

- PGVector:
  - 현재 필수 구성 아님
  - 향후 RAG 고도화 시 선택적 도입 가능

- 파일 기반 저장소(FileHistoryRepository):
  - Phase 2~3 개발 단계에서 사용
  - 현재는 운영 영속 저장소로 사용하지 않음

---

## 5. 데이터 / 설계 기준 문서 (읽기 전용, 계약 기준)

아래 문서들은 `_refs/` 폴더에 있으며,  
구현 시 반드시 **무손실 반영**해야 한다.

### 5.1 ERD / 데이터 아키텍쳐
- `26.02.05(목)데이터 아키텍쳐,ERD 가이드.md`
- 핵심:
  - `MESSAGES` 테이블 제거
  - `INTERVIEWS.chat_history (jsonb)` 통합
  - PostgreSQL Authority 유지

---

### 5.2 UI 설계 (최신본)
- `26.02.06(금)AI 면접 프로그램 UI 설계 초안.md`
- 포함:
  - 면접 진행도(phase)
  - 답변 완료 버튼
  - 관리자 UI
- 상태 전이(State Contract) 우회 금지

---

### 5.3 질문 태그 설계
- `26.02.05(목)질문태그설계.md`
- tag_code는 문자열 식별자
- 변경/삭제 금지
- 평가 JSON과 1:1 대응

---

### 5.4 정량 평가 루브릭
- `26.02.09(월)정량평가 루브릭 가이드.md`
- 평가 JSON 스키마 고정
- Deterministic Evaluation 보장
- Redis Cache는 평가 근거가 아님

---

### 5.5 인터뷰 정책 스펙
- `26.02.11(수)인터뷰 정책 스펙.md`

고정 정책:

- 최소 질문 10개 보장
- 침묵 2케이스 처리 정책
  - 무응답
  - 답변 후 침묵
- 세션 상태 ENUM:
  - APPLIED
  - IN_PROGRESS
  - COMPLETED
  - INTERRUPTED
  - EVALUATED
- 결과 공개 정책:
  - 2주 이내 합/불합 자동 통지 보장
- Job Policy Freeze at Publish 계약 유지
- Snapshot Double Lock 유지


## 6. 확정된 폴더 / 모듈 구조

IMH/IMH_Interview/
├── IMH/                  # (app 대체) FastAPI 엔트리 / Router 조립
│   ├── api/
│   └── main.py
├── packages/             # 공유 가능한 핵심 로직
│   ├── imh_core/
│   ├── imh_providers/
│   ├── imh_analysis/
│   ├── imh_eval/
│   ├── imh_history/
│   ├── imh_job/
│   ├── imh_session/
│   ├── imh_service/
│   └── imh_qbank/
├── docs/                 # 운영 문서 (사람/에이전트용)
├── logs/                 # 실제 로그 파일 (.log)
│   ├── agent/
│   └── runtime/
├── _refs/                # 스펙/기준 문서 (읽기 전용)
└── scripts/


- packages/는 팀원과 공유 가능한 단위로 설계한다.
- IMH/는 실행 진입점만 담당하며 비즈니스 로직을 가지지 않는다.
### 진행 상태

- `packages/imh_core/`: ✅ DONE  
  - TASK-002 완료 (config / errors / dto)
  - 공통 로깅 기반 포함 (TASK-001)
  - TASK-026: PostgreSQL Repository 구현 및 Primary Write Path 전환 완료
  - TASK-027: Redis Control Layer 및 Runtime Mirror 도입 완료 (CP0~CP4 🔒 LOCKED)

- `packages/imh_providers/`: ✅ DONE
  - TASK-003: Provider 인터페이스 + Mock 구조 확정
  - TASK-006: PDF Local Provider 추가
  - TASK-007: Embedding Provider (Interface / Mock) 추가

- `packages/imh_analysis/`: ✅ DONE
  - TASK-008: Emotion 분석 모듈 구현 완료
  - TASK-009: Voice Provider (Parselmouth 기반 실제 구현) 추가
  - TASK-010: Visual Provider (MediaPipe 기반 실제 구현) 추가

- `packages/imh_eval/`: ✅ DONE
  - TASK-011: 정량 평가 엔진 (RubricEvaluator) 구현 완료
  - 영역별 점수 산출 로직 및 가중치 적용 검증 완료

- `packages/imh_history/`: ✅ DONE
  - TASK-013: 리포트 저장소(FileHistoryRepository) 구현 완료
  - JSON 파일 기반 저장은 개발 초기 단계 용도
  - 운영 영속 저장은 PostgreSQL 기반으로 전환 완료 (TASK-026 이후)

- `packages/imh_job/`: ✅ DONE
  - TASK-019: 공고 정책 엔진(Job Policy Engine) 구현 완료
  - JobStatus(DRAFT/PUBLISHED/CLOSED) 전이 및 AI-Sensitive Fields 불변성 강제 검증 완료
  - Job Policy Freeze at Publish 계약 고정
  - Session Snapshot 생성 로직 구현 완료

- `packages/imh_session/`: ✅ DONE
  - TASK-017: Interview Session Engine 구현 완료
    - 상태(APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED) 정의
    - 최소 질문 수(10) 및 조기 종료 정책 구현
    - 침묵 2케이스(Post-Answer / No-Answer) 처리 로직 구현
    - Redis / PostgreSQL 추상화 인터페이스 설계
    - Strict Verification Script(`verify_task_017.py`) Pass

  - TASK-018: Interview Mode Policy Split 구현 완료
    - InterviewPolicy 인터페이스 및 모드별(Actual / Practice) 구현체 정의
    - SessionConfig에 mode 추가 및 Engine 주입 로직 구현
    - 조기 종료 / 중단 / 재진입 정책 분리 검증 완료 (`verify_task_018.py`)

  - TASK-020: 관리자 지원자 조회/필터 규격 및 구현 완료
    - `ApplicantQueryService` 구현 (Active Session + History Federated Search)
    - `MemorySessionRepository` 인프라 구현 (`find_by_job_id` 지원)
    - 관리자 조회 규격(필터/정렬/페이징) 및 정책 준수 검증 완료 (`verify_task_020.py`)

  - TASK-021: End-to-End 인터뷰 실행 아키텍처 통합 구현 완료
    - Job Policy Freeze at Publish 계약 적용
    - Snapshot Double Lock 구조 구현
    - Session Engine ↔ Job Policy Engine ↔ Evaluation ↔ Admin Query 통합 흐름 구현
    - 상태 전이(State Contract) 기반 실행 흐름 검증 완료
    - Snapshot 기반 Evaluation 및 Admin Query 정합성 검증 완료 (`verify_task_021.py`)

  - TASK-022: Service Layer 및 외부 경계 통합 구현 완료
    - `SessionService` 구현 (Command 전용 유스케이스 오케스트레이션)
    - `AdminQueryService` 구현 (Read-Only Query 경로 분리)
    - API ↔ Domain 완전 격리 (DTO / 명시적 Mapper 적용)
    - Command(Lock) / Query(Bypass) 구조 분리 확정
    - Fail-Fast 동시성 제어 적용
    - Phase 5 계약 훼손 없음 검증 완료 (`verify_task_022.py`)

- `packages/imh_qbank/`: ✅ DONE
  - TASK-024: 질문은행 구조 정비 완료
  - TASK-025: RAG Fallback 엔진 통합 완료
    - Snapshot 불변성 보장
    - Engine 단일 판단 주체 유지
    - Contract Stability 재검증 완료 (`verify_task_025.py`)

- `packages/imh_stats/`: ✅ DONE
  - TASK-028 CP0: Business Statistics Layer 구현 완료
    - Type1 (Real-Time Status)
    - Type2 (기간 집계 / 평균 점수)
    - Redis Result Cache Only 적용
    - TTL / as_of 일관성 검증 완료

  - TASK-028 CP1: Operational Observability Layer 구현 완료
    - Track B Informational Only 분리
    - Reason / Span / Layer 메타 모델 확정
    - Log 기반 Latency / Failure Rate / Cache Hit 관측 구현
    - 상태 전이 실패율 집계 (Engine 수정 없음)
    - Type3 MView 격리 전략 확정 및 쿼리 레벨 검증 완료
    - Type4 DISABLED 유지 (영속 저장 없음)
    - Track A/B 물리적 분리 검증 완료
    - 신규 Write Path 없음

- `IMH/api/`: ✅ DONE
  - TASK-014: 리포트 조회 API 노출
  - TASK-023: API Layer 및 Runtime Entry 경계 확정 완료
    - API → Service → Engine 단일 Command 경로 유지
    - AST 기반 Guardrail 확보
    - 병렬 요청 Fail-Fast 검증 완료 (`verify_task_023.py`)

- `IMH/IMH_Interview/_refs/`: ✅ DONE
  - TASK-015: UI / Client 리포트 소비 규격 정의
  - 인터뷰 정책 스펙 확정 및 Phase 5 계약 고정

---

📌 현재 상태 요약:

- Phase 1 ~ Phase 10 완료 (TASK-028 🔒 LOCKED)
- PostgreSQL = Single Source of Truth
- Redis = Read Optimization Only (Authority 아님)
- API / Service / Engine 경계 고정
- Snapshot / Freeze / State Contract 보호 상태 유지
- Business Stats / Observability 완전 분리
- Heavy Query 격리 전략 확정
- 신규 영속 Write Path 없음
- 운영 가능한 아키텍처 완성


## 7. 로깅 / 기록 규칙 (중요)

### 7.1 에러 로그는 “진짜 로그파일(.log)”로 남긴다
- 에이전트가 개발/테스트/실행 중 발견하는 모든 에러는 **MD가 아니라 로그파일(.log)** 로 기록한다.
- 로그 위치:
  - `IMH/IMH_Interview/logs/agent/` (에이전트/개발/테스트)
  - `IMH/IMH_Interview/logs/runtime/` (API 서버 런타임)

### 7.2 MD 문서는 “사람이 읽는 요약”만 남긴다
- `docs/DEV_LOG.md`에는 아래만 남긴다.
  - 변경 요약(무엇을/왜)
  - 테스트 방법(재현 커맨드)
  - 에러 요약 + **해당 로그파일 경로**
- 상세 스택트레이스/긴 로그는 **항상 .log 파일**에 남긴다.

### 7.3 로그에 포함되어야 할 필드(권장)
- timestamp, level, logger_name, file:line, message
- (가능하면) request_id, user_id(또는 session_id), latency_ms

### 7.4 로그에 절대 포함하면 안 되는 것(금지)
- 사용자 개인정보(PII)
- 인증 토큰/키/API Key
- 원문 대화 전체(민감정보/용량/정책 이슈)
- 업로드 파일의 원문 전체(필요 시 요약/해시/메타데이터만)

---

## 8. 변경 승인 규칙 (강제)

### 8.1 Plan → Approval → Implement
에이전트는 아래 순서를 반드시 지킨다.

1) **Plan(변경 제안서) 작성**
- 어떤 파일을 만들거나 수정할지
- 왜 필요한지
- 무엇을 추가/변경/삭제하는지
- 영향 범위(API/패키지/테스트/환경)
- 롤백 방법

2) **사용자(프로젝트 오너) 허락을 받은 뒤에만 구현**
- 허락 전에는 코드 생성/수정/대규모 diff 출력 금지

3) **구현 후 기록**
- `docs/DEV_LOG.md` 업데이트(요약/테스트/로그 경로)

---
## 9. 지금 당장 하면 안 되는 것 (중요)

아래 항목은 현재 단계(Phase 10 완료 이후 안정화 단계)에서 **명시적으로 금지**한다.

- PostgreSQL Authority 변경 또는 우회
  → PostgreSQL = Single Source of Truth 계약 유지
- Redis를 Authority로 사용하는 구조 도입
  → Redis는 Read Optimization Only
  → No Write-Back 유지
  → Write Order (PG → Redis) 변경 금지
- 실시간 면접의 네트워크/스트리밍 인프라 구현 (WebRTC / 저지연 스트리밍 파이프라인)
  → Playground 기반 정적 분석 우선
- LLM 평가 엔진의 대규모 재구현 (루브릭/스코어링 로직 재설계)
  → 정량 평가 루브릭 스키마 고정
- Streaming 기반 LLM 구조 전환 (Async/WebSocket 전환 포함)
  → Engine 경계 불변 유지
- Phase 5에서 확정된 상태 ENUM 변경
  (APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED)
- Snapshot 계약 / Job Policy Freeze 계약 변경
- TASK-022에서 확정된 Service Layer 구조 변경
  (Command/Query 분리, DTO 격리, Lock 정책)
- Engine 단일 정책 판단 구조 변경
- Question Source 구조(STATIC / GENERATED) 변경
- Generated 질문의 Session-local 자산 정책 변경
- Fallback 3-Tier 전략 변경
- Redis Cache를 직접 조작하는 API 노출
- Snapshot 외부 수정 경로 추가
- Business Statistics(Track A)와 Observability(Track B) 혼합 집계

> 현재는 “Redis 아키텍처 LOCKED + 통계/관측 계층 LOCKED 상태”이며,
> 핵심 정책/상태/스냅샷/엔진/Authority 계약은 절대 변경하지 않는다.

---

## 10. 현재 기준 상태

## Phase 9 (COMPLETE)

- TASK-027 (CP0~CP4) LOCKED
- Redis = Read Optimization Only
- PostgreSQL = Single Source of Truth
- Write Order = PG → Redis
- No Write-Back 유지
- Snapshot / Freeze / State Contract 침해 없음

---

## Phase 10 (COMPLETE)

### TASK-028 관리자 통계 및 운영 관측 계층

- CP0: Business Statistics LOCKED
- CP1: Operational Observability LOCKED
- Track A / Track B 완전 분리
- Type 3 MView 격리 전략 확정
- Type 4 DISABLED 유지
- 신규 영속 Write Path 없음
- Engine / Snapshot / State 계약 침해 없음

---

## ACTIVE

- 없음 (다음 Phase 정의 대기 상태)

---

## HOLD

### TASK-016 TTS Provider (Text → Speech)

- Goal:
  - AI 면접 질문을 음성(TTS)으로 출력하기 위한 Provider 계층 준비
- 보류 사유:
  - Engine 경계 및 Snapshot 계약 안정성 유지 필요
  - Streaming 아키텍처 별도 승인 필요
- 재개 조건:
  - 별도 Phase로 분리 승인
  - Streaming 계약 수립
  - Engine 경계 불변 유지 조건 명시
