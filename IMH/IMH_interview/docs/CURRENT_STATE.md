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

## 검증 상태 요약 (Phase 1 ~ Phase 5)

### 1. Core Processing Layer (TASK-004 ~ 011)

- 파일 검증, 텍스트 추출, 임베딩 파이프라인 정상 동작 확인
- 음성 분석(Pitch/Intensity/Jitter/Shimmer/HNR) 정책 검증 완료
- 얼굴 분석(MediaPipe) 및 No Face 정책 검증 완료
- 루브릭 기반 점수 산출 및 직군 가중치 로직 정상 동작 확인
- 모든 검증은 Python 3.10.11 + interview_env 환경에서 수행됨

---

### 2. Report & Persistence Layer (TASK-013 ~ 014)

- InterviewReport 파일 저장/조회/정렬 정책 검증 완료
- `/reports` API 목록/상세 조회 정상 동작 확인
- DTO 직렬화 및 404 처리 정책 검증 완료
- 파일 기반 메타데이터 구성 정책 유지 확인

---

### 3. Session & Policy Engine Layer (TASK-017 ~ 019)

- 세션 상태 전이(APPLIED → IN_PROGRESS → COMPLETED/INTERRUPTED → EVALUATED) 정상 동작
- 최소 질문 수 10개 정책 및 침묵 처리 정책 검증 완료
- Actual / Practice 모드 분리 정책 검증 완료
- 공고 상태 전이(DRAFT → PUBLISHED → CLOSED) 및 Immutable Policy 계약 검증 완료
- AI-Sensitive Fields 불변 계약 유지 확인

---

### 4. Admin Query Layer (TASK-020)

- Active + History 통합 조회(Federated Search) 정상 동작
- 필수 필터(job_id, status, result, date) 계약 준수 확인
- Result는 EVALUATED 상태에만 적용됨 검증 완료
- is_interrupted alias 합집합 처리 확인
- search_keyword 계약(2자 이상, email exact, name partial) 준수 확인
- weakness 필터는 Deferred 처리(Phase 7 이후)
- Scope Lock 위반 없음 확인

---

모든 TASK는 verify_task_xxx.py 스크립트를 통해 검증되었으며,
검증 스크립트는 계약 동작 확인을 위한 보조 도구로 사용된다.



## 1. 프로젝트 목적 (확정)

- 목적: **AI 모의면접 시스템**
- 전략:
  - 1단계: **API 기반 모델로 핵심 기능을 빠르게 구현**
  - 2단계: **on-premise 모델로 교체하여 성능/비용 최적화**
- 모든 모델은 **API / Local(on-prem)** 방식으로 언제든 교체 가능하도록 추상화한다.

---
## 2. 현재 개발 단계

- 상태: Phase 5 진행 중
  - 전반부 완료: 리포트 API 노출 및 UI 소비 규격 확정 (TASK-014, TASK-015)
  - 후반부 착수: 실시간 면접 플로우 통합(세션 엔진/공고 정책/중단 처리/관리자 조회) 설계 단계 진입
  - (설계 기준) 인터뷰 정책 스펙(INTERVIEW_POLICY_SPEC) 확정 및 기준 문서로 고정

- 완료 항목:
  - Analysis 결과를 입력으로 받아 정량 점수 및 평가 근거(Evidence)를 산출하는 Rule-based Evaluation Engine 구현 및 검증 완료 (TASK-011)
  - 평가 결과를 사용자 친화적 리포트(JSON)로 변환하는 Reporting Layer 구현 완료 (TASK-012)
  - 리포트의 저장 및 이력 관리 계층 구현 완료 (TASK-013)
    - FileHistoryRepository 기반(파일 저장)으로 검증 완료
  - 리포트 조회 API 노출 및 검증 완료 (TASK-014)
  - UI / Client 관점의 리포트 소비 규격(Contract) 정의 완료 (TASK-015)

- 미포함 항목(향후 단계):
  - 실제 LLM / RAG 연동(질문은행 활용, 임베딩/벡터 검색 포함)
  - UI 화면 구현(면접자/관리자)
  - 외부 사용자 인증/권한 체계
  - 실시간 면접 세션 오케스트레이션(스트림/비동기 플로우) 구현
    - ※ 단, 현재는 “설계/정의 단계”로 진입한 상태이며 구현은 아직 착수하지 않음

- 현재 Phase의 목적:
  - 리포트 데이터 구조(JSON) 확정 ✅
  - 해석(Interpretation) 로직 1차 구현 완료 ✅
  - 리포트 저장 · 조회 · 이력 관리 흐름 완성 ✅
  - UI / Client 소비 규격(Contract) 확정 완료 ✅
  - 다음 단계: 실시간 면접 진행 플로우 설계 및 통합(Phase 5 후반부)로 확장 진행


---

## 3. 확정된 핵심 방향 (변경 금지)

- (세션 상태) APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED 를 기준 상태값으로 사용

### 3.1 기능 우선순위

1. **Phase 2 Playground 기반 정적 파일 분석은 유지**
   - 오디오/영상 업로드 → STT / 감정 / 시선 / 음성 분석 검증
   - 문서(PDF) 업로드 → Text 추출(PDF→Text)
   - 목적: 개발/검증/테스트 하네스(Regression) 역할

2. **현재 최우선: Phase 5 후반부 “실시간 면접 플로우 통합”**
   - 인터뷰 정책 스펙 기준으로
     세션 엔진 / 공고 정책 / 중단 처리 / 관리자 조회 흐름을 설계 및 통합

3. **TTS(Text→Speech)**
   - 실시간 면접 단계에서 핵심 구성요소로 취급
   - (현 상태) TASK-016은 HOLD이며, 실시간 플로우 설계가 안정화된 뒤 재개

4. **RAG / 질문은행 / 임베딩**
   - 온프레미스 저성능 모델 보정 및 질문 품질 안정화 목적
   - Phase 5 후반부 이후(Phase 6)로 계획

5. **UI/프론트 연동**
   - API 안정화 및 실시간 플로우 최소 통합 이후 확장
- (세션 상태) APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED 를 기준 상태값으로 사용

---

### 3.2 모델 구성 (현재 기준)

| 분석 항목 | 모델 | 실행 환경 |
|---------|------|-----------|
| STT | Faster-Whisper | GPU (VRAM ~1GB) |
| LLM | GPT-4o / Qwen3-4B / A.X-4.0-Light / EXAONE 7.8B / Llama3.1-KO | GPU (~4.5GB) |
| Emotion | DeepFace | CPU (1fps) |
| Visual | MediaPipe | CPU |
| Voice | Parselmouth | CPU |

※ 모델 교체 가능, 인터페이스 고정

---

## 4. 저장 정책 (확정)

- ❌ 서버는 **원본 영상/오디오 파일을 장기 저장하지 않는다**
- ⭕ 저장 대상:
  - 텍스트(STT 결과)
  - 분석 결과 요약
  - 평가 점수 및 근거(JSONB)
- 목적: 보안, 비용, 법적 리스크 최소화

### 4.1 현재 저장소 상태(현행)
- 현재 활성 DB(PostgreSQL/Redis/PGVector)는 도입하지 않는다.
- 리포트/이력 저장은 파일 기반(FileHistoryRepository)으로 운영한다.
- DB 도입은 리포트 구조 및 실시간 플로우 정책이 안정화된 이후 단계에서 진행한다.
---

## 5. 데이터/설계 기준 문서 (읽기 전용)

아래 문서들은 **_refs/** 폴더에 있으며,  
구현 시 반드시 **무손실 반영**해야 한다.

1. ERD / 데이터 아키텍쳐  
   - `26.02.05(목)데이터 아키텍쳐,ERD 가이드.md`
   - 핵심:
     - `MESSAGES` 테이블 제거
     - `INTERVIEWS.chat_history (jsonb)` 통합

2. UI 설계 (최신본)
   - `26.02.06(금)AI 면접 프로그램 UI 설계 초안.md`
   - 면접 진행도(phase), 답변 완료 버튼, 관리자 UI 포함

3. 질문 태그 설계
   - `26.02.05(목)질문태그설계.md`
   - tag_code는 **문자열 식별자**, 변경/삭제 금지

4. 정량 평가 루브릭
   - `26.02.09(월)정량평가 루브릭 가이드.md`
   - 평가 JSON 스키마 고정

5. 인터뷰 정책 스펙
   - `26.02.11(수)인터뷰 정책 스펙.md`
   - 최소 질문 10개 보장
   - 침묵 2케이스 처리 정책(무응답/답변 후 침묵 구분)
   - 세션 상태 ENUM(APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED)
   - 결과 공개 정책(2주 이내 합/불합 자동 통지 보장)
---

## 6. 확정된 폴더 / 모듈 구조

IMH/IMH_Interview/
├── IMH/                  # (app 대체) FastAPI 엔트리
├── packages/             # 공유 가능한 핵심 로직
│   ├── imh_core/
│   ├── imh_providers/
│   ├── imh_analysis/
│   ├── imh_analysis/
│   ├── imh_eval/
│   └── imh_session/
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
  - 영역별 점수 산출 로직 및 가중치 적용 검증됨

- `packages/imh_history/`: ✅ DONE
  - TASK-013: 리포트 저장소(FileHistoryRepository) 구현 완료
  - JSON 파일 기반 영구 저장 및 이력 조회 검증됨

- `packages/imh_job/`: ✅ DONE
  - TASK-019: 공고 정책 엔진(Job Policy Engine) 구현 완료
  - JobStatus(DRAFT/PUBLISHED/CLOSED) 전이 및 AI-Sensitive Fields 불변성 강제 검증됨
  - Session Snapshot 생성 로직 구현됨


- `IMH/api/`: ✅ DONE
  - TASK-014: 리포트 조회 API 노출
    - 리포트 목록(List) / 상세(Detail) 조회 API 구현
    - 저장된 리포트(JSON)를 외부 소비 계층에서 조회 가능하도록 노출
    - List / Detail 데이터 노출 정책 분리
    - Read-only API 동작 검증 스크립트 기반 검증 완료

- `IMH/IMH_Interview/_refs/`: ✅ DONE
  - TASK-015: UI / Client 리포트 소비 규격 정의
    - `TASK-015_CONTRACT.md` 문서를 통해
      리포트 해석, 표현, Null 처리, 책임 경계 규칙 확정
  - 인터뷰 정책 스펙(INTERVIEW_POLICY_SPEC) 확정
    - 최소 질문 10개 보장
    - 침묵 2케이스 처리 정책
    - 세션 상태 ENUM(APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED)
    - 결과 공개 정책(2주 내 합/불합 자동 통지 보장)
    - 실전/연습 모드 정책 분리
    
- `packages/imh_session/`: ✅ DONE
  - TASK-017: Interview Session Engine 구현 완료
    - 상태(APPLIED, IN_PROGRESS, COMPLETED, INTERRUPTED, EVALUATED) 정의
    - 최소 질문 수(10) 및 조기 종료 정책 구현
    - 침묵 2케이스(Post-Answer / No-Answer) 처리 로직 구현
    - Redis / PostgreSQL 추상화 인터페이스 설계
    - Strict Verification Script(`verify_task_017.py`) Pass
  - TASK-018: Interview Mode Policy Split 구현 완료
    - InterviewPolicy 인터페이스 및 모드별(Actual/Practice) 구현체 정의
    - SessionConfig에 mode 추가 및 Engine 주입 로직 구현
    - 조기 종료/중단/재진입 정책 분리 검증 완료 (`verify_task_018.py`)
    - ※ 실전/연습 모드 진입점(API) 구현 시 mode 강제 주입 필요 (Phase 5 통합 단계)
  - TASK-020: 관리자 지원자 조회/필터 규격 및 구현 완료
    - `ApplicantQueryService` 구현 (Active Session + History Federated Search)
    - `MemorySessionRepository` 인프라 구현 (`find_by_job_id` 지원)
    - 관리자 조회 규격(필터/정렬/페이징) 및 정책 준수 검증 완료 (`verify_task_020.py`)





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

아래 항목은 현재 단계에서 **명시적으로 금지**한다.

- DB 마이그레이션/스키마 확정(ERD 반영 구현 포함)
- 실시간 면접의 네트워크/스트리밍 인프라 구현(WebRTC/저지연 스트리밍 파이프라인)
- LLM 평가 엔진의 대규모 재구현(루브릭/스코어링 로직 재설계)
- 엔드포인트를 대량으로 생성(Playground 다중 엔드포인트 확장 포함)
- 프론트/UI 개발(대시보드/관리자 화면 포함)

> 현재는 “실시간 면접 기능의 구현”이 아니라  
> “정책 기반 설계와 구조 확정”을 우선한다.


---
## 10. 현재 최우선 목표

## ACTIVE
- Phase 5 후반부: 실시간 면접 플로우 통합 설계
  - 인터뷰 정책 스펙(INTERVIEW_POLICY_SPEC)을 기준으로 구조 설계
  - 세션 엔진 상태 전이 정의
  - 공고 정책 기반 동작 규칙 구조화
  - 실전/연습 모드 분리 아키텍처 설계
  - 관리자 조회 및 필터 정책 반영 설계
- 다음 승인 대상 TASK는 TASK_QUEUE에 등록 예정

---

## HOLD

### TASK-016 TTS Provider (Text → Speech)
- **Goal**:
  - AI 면접 질문을 음성(TTS)으로 출력하기 위한 Provider 계층 준비
- **보류 사유**:
  - TTS는 실시간 면접 세션 엔진의 질문 출력 구조가
    명확히 정의된 이후에 통합하는 것이 적절함
- **재개 조건**:
  - 세션 엔진(TASK-017) 구조 확정
  - 질문 출력 타이밍 및 책임 경계 정의 완료