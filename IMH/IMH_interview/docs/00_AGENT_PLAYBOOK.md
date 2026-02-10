# 00_AGENT_PLAYBOOK_1 (보완판) — 프로젝트 누락 점검 반영본 (2026-02-09)

> 목적: **IMH AI 면접 시스템** 코딩 에이전트가 *프로젝트 문서와 실제 구현 사이의 불일치*로 인해 기능을 빠뜨리거나 잘못 구현하는 것을 방지한다.  
> 본 문서는 **“에이전트 실행 지침 + 문서 인벤토리 + 불일치 해결 규칙 + 개발 계획(로드맵) + Task Queue 작성 규격”**을 하나로 묶는다.

---

## 0. 이번 보완에서 확인된 핵심 포인트 (무손실 반영 체크)

### 0.1 UI 설계 최신본 우선
- UI 문서는 **`26.02.06(금)AI 면접 프로그램 UI 설계 초안.md`**가 최신이며, 동일 파일명의 구버전이 존재할 수 있다.  
- 에이전트는 **항상 날짜가 포함된 최신본(26.02.06)**을 우선 기준으로 삼는다.  
  - 면접자 UI에는 “면접 진행도(phase 표시)”, “답변 완료 버튼”, “코딩테스트/화이트보드”가 명시되어 있다.  

### 0.2 ERD: messages 테이블 제거 → interviews.chat_history(jsonb) 통합이 ‘현 설계’
- 최신 ERD 가이드에서는 **`MESSAGES` 테이블을 삭제**하고 **`INTERVIEWS.chat_history(jsonb)`**로 통합한다.  
- 이유: 면접 이력 조회 시 대량 Join 제거로 성능 최적화.  

### 0.3 루브릭/태그: tag_code는 문자열 식별자 기반이 ‘현 설계’
- 질문 태그는 **시스템 식별자(identifier)**로 유지하며, 변경/삭제 금지(추가만 허용).  
- 평가 결과는 **`evaluation_scores.tag_code(varchar)` + evidence_data(jsonb)** 형태로 저장한다.  
- 루브릭 가이드가 요구하는 LLM 평가 JSON 스키마( category/score/tag_code/rationale/evidence_data/improvement_feedback )를 준수한다.

---

## 1. 에이전트 필수 규칙 (Mandatory Protocols)

### 1.1 변경 승인 게이트 (Plan-Only First)
- 코드 수정 전 반드시 **변경 제안서(Proposal)** 작성 → 사용자 승인 후 구현.
- 승인 전에는 **실제 코드 변경, 커밋, 대규모 diff 출력 금지**.

### 1.2 로깅 규약 (Runtime Observation)
- 에이전트가 발견한 에러/런타임 관측은 **MD가 아니라 `logs/*.log`** 파일에 남긴다.
- 스택트레이스 포함을 위해 `logger.exception()` 사용.
- 로그에 절대 포함 금지: **RAW 답변 원문**, 개인정보, 비밀번호, 인증 토큰. (보안 규정)

### 1.3 모듈/폴더 구조 원칙 (공유 가능 구조)
- **Package-Centric**: 재사용 가능한 로직은 `packages/` 아래에만 둔다.
- 실행 진입점은 최소화하고(Thin), 비즈니스 로직은 packages로 이동한다.

### 1.4 폴더 네이밍 규칙 (중요)
- 프로젝트 규칙: **`app/` 폴더 대신 `IMH/`를 사용**한다.  
  - 신규 생성/수정 시 `app.*` import가 나타나면 **`IMH.*`로 정리**한다.

### 1.5 문서 접근 범위 및 단일 기준 규칙 (Single Source of Truth)

- 에이전트는 **PROJECT_STATUS.md를 참조하지 않는다.**
  - 해당 문서는 ChatGPT 협업을 위한 “메모리/세이브 포인트” 문서이며,
    에이전트가 접근하거나 존재를 가정해서는 안 된다.

- 에이전트의 판단 근거는 **오직 `IMH/IMH_Interview/docs/` 폴더 내 문서**로 한정한다.
  - 허용 문서 예:
    - `00_AGENT_PLAYBOOK.md`
    - `CURRENT_STATE.md`
    - `TASK_QUEUE.md`
    - `DEV_LOG.md`
    - 개별 TASK의 Plan 문서 (`TASK-XXX_PLAN.md`)
  - `_refs/` 폴더의 문서는 **설계 스펙 참조용**으로만 사용한다.

- 사용자 또는 ChatGPT가 대화 중 PROJECT_STATUS.md의 내용을 언급하더라도,
  에이전트는 이를 **참고 정보로만 인식**하며,
  실제 판단 및 행동은 반드시 docs 문서에 반영된 내용만을 따른다.

- 에이전트 프롬프트에 “PROJECT_STATUS를 확인하라”는 문구가 포함되어 있더라도,
  이는 **무시 규칙**에 해당한다.
  - 에이전트는 해당 지시를 문서 범위 오류로 판단하고,
    docs 기준으로만 작업을 수행한다.

> 본 규칙은 에이전트의 자율 추론보다 **문서 기반 통제**를 우선하며,  
> 위반 시 작업 결과는 무효로 간주될 수 있다.
---

## 2. 프로젝트 폴더 및 문서 체계 (Inventory)

> 기준 루트: `IMH/IMH_Interview/`

```text
IMH/IMH_Interview/
├── IMH/                  # (기존 app 대체) FastAPI 엔트리/라우터/DI 조립
├── packages/             # 핵심 비즈니스 로직 (공유 가능)
│   ├── imh_core/         # config, logging, errors, dto, utils
│   ├── imh_providers/    # STT/LLM/Emotion/Visual/Voice 추상화 + 구현체
│   ├── imh_analysis/     # 파일 기반 분석(감정/시선/음성)
│   └── imh_eval/         # 루브릭 정량 평가 엔진 + 집계
├── docs/                 # 운영 문서(사람용): CURRENT_STATE, DEV_LOG, DECISIONS, TASK_QUEUE
├── logs/                 # 실제 로그 파일
│   ├── agent/
│   └── runtime/
├── _refs/                # “정의” 문서(원본 스펙): ERD, UI, 태그, 루브릭
└── scripts/              # 유틸/인프라 스크립트(alembic, seed, etc.)
```

---

## 3. 참조 문서 관리 (Technical Context)

에이전트는 구현 시 아래 문서를 **무손실(Zero Omission)** 반영해야 한다.

### 3.1 _refs/ 문서(스펙) — 우선순위
1) **ERD/데이터 아키텍쳐**  
   - `26.02.05(목)데이터 아키텍쳐,ERD 가이드.md`  
   - 핵심: `INTERVIEWS.chat_history(jsonb)` 통합, PGVector, Redis Key 규약, 로그 필드, 인증 전략

2) **UI 설계(최신본 기준)**  
   - `26.02.06(금)AI 면접 프로그램 UI 설계 초안.md`  
   - 핵심: 공통(로그인/회원가입/정보수정), 면접자(시작전/진행중/결과), 관리자(공고/지원자현황/결과조회)

3) **질문 태그 설계**
   - `26.02.05(목)질문태그설계.md`  
   - 핵심: tag_code 체계(capability/problem_solving/communication/character), 변경/삭제 금지

4) **정량 평가 루브릭**
   - `26.02.09(월)정량평가 루브릭 가이드.md`  
   - 핵심: 평가 항목별 구현 로직(코사인 유사도, AST 분석, STAR 구조, Gaze/Emotion), 직군별 가중치, 평가 JSON 응답 스키마

---

## 4. “프로젝트 누락 가능성” 점검 결과 & PLAYBOOK에 추가해야 하는 문서들

현재 PLAYBOOK_1에는 **스펙 참조는 존재하지만**, 에이전트가 “어디에 무엇을 기록/결정/추적”해야 하는지 운영 문서가 부족해 누락 위험이 있다.
따라서 아래 4개 문서를 **docs/**에 “프로젝트 운영 표준”으로 추가한다.

### 4.1 docs/CURRENT_STATE.md (현 상태 스냅샷)
- 목적: 에이전트가 작업 시작 시 “지금까지 구현된 것 / 미구현 / 깨진 것”을 1페이지로 파악.
- 최소 포함:
  - 현재 활성 브랜치/커밋(선택)
  - 실행 방법(venv, docker 여부)
  - 동작 확인된 API 목록
  - 미해결 이슈 Top 5
  - 다음 Task Queue 링크

### 4.2 docs/DECISIONS.md (설계 의사결정 로그)
- 목적: “왜 이렇게 했는지”를 남겨서 재논의 비용을 줄인다.
- 반드시 기록할 결정 예시:
  - `MESSAGES` 제거 → `INTERVIEWS.chat_history(jsonb)` 통합(Join 감소 목적)
  - 서버는 영상 원본 저장 안 함(결과만 저장)
  - Redis 세션 vs JWT 선택
  - provider(api/local) 토글 정책, stream/batch 정책

### 4.3 docs/DATA_CONTRACTS.md (JSONB/DTO 계약서)
- 목적: **jsonb(chat_history, evidence_data)** 가 많아질수록 “형식 붕괴”가 가장 큰 위험.
- 최소 포함:
  - `interviews.chat_history` JSON 스키마(필수 키, 타입, timestamp 표준)
  - `evaluation_scores.evidence_data` JSON 스키마(루브릭 가이드와 일치)
  - “호환성 규칙”(필드 추가는 가능, 이름 변경/삭제 금지)

### 4.4 docs/API_SPEC.md (FastAPI 라우트 계약서)
- 목적: UI/프론트/테스트가 붙기 전에 API가 흔들리지 않도록 고정.
- 최소 포함:
  - Auth: login/register/me
  - Posting: list/detail/apply(지원)
  - Interview: create/start/next_turn/finish/result
  - Admin: postings CRUD, applicants list, applicant detail
  - Playground: stt/emotion/visual/voice/run (파일 업로드 기반)

> 위 4개 문서는 “스펙(_refs)”이 아니라 “운영 표준(docs)”이다.  
> 에이전트는 작업 시작 시 **PLAYBOOK + CURRENT_STATE + DECISIONS**를 먼저 읽어야 한다.

---

## 5. 구현 우선순위 로드맵 (UI → 데이터 → API 순으로 누락 방지)

### [Phase 1] 운영 기반 고정
- 로깅/예외/환경설정(Provider 선택, MODE_STREAM, fps 등) in `imh_core`
- `docs/DEV_LOG.md` + `logs/` 파일 기록 루틴 정착

### [Phase 2] 데이터 계층(ERD) 고정 + 마이그레이션
- ERD 가이드 기반 테이블/컬럼/인덱스 물리화
- 특히 `interviews.chat_history(jsonb)` / `evaluation_scores.evidence_data(jsonb)` 형식 확정

### [Phase 3] UI 여정 최소 기능 API
- 면접자:
  - 공고 목록/선택 → 이력서 업로드 → 환경 테스트(메타) → 면접 시작/진행/종료 → 결과 조회
- 관리자:
  - 공고 관리 → 지원자 현황 → 합/불 결과 조회

### [Phase 4] 루브릭 정량 평가 엔진
- 루브릭 가이드의 구현 로직을 모듈화하여 점수 산출 + 근거(evidence_data) 저장

### [Phase 5] Playground (빠른 모델 비교/성능 검증)
- 업로드 기반 분석 API + 간단 UI(또는 Swagger 기반)로 모델 교체 테스트 속도 개선

---

## 6. Task Queue 작성 규격 (에이전트 지시용)

> 목표: Task를 “작게, 검증 가능하게, 스펙과 매핑 가능하게”

### 6.1 Task 1개 템플릿
- **Task ID**: T-YYYYMMDD-###  
- **Goal(한 줄)**: 무엇을 끝내면 완료인가
- **Scope**: 포함/제외(명시)
- **Spec Links(_refs/docs)**: 어떤 문서의 어떤 섹션을 따르는지
- **Acceptance Criteria**: curl 또는 pytest로 검증 가능한 체크리스트
- **Files**: 생성/수정 파일 목록
- **Logging**: 어떤 로그를 남겨야 하는지
- **Rollback**: 되돌리는 방법

### 6.2 Task 크기 가이드
- 1 Task는 “**1~2개 엔드포인트**” 또는 “**1개 데이터 계약(JSON 스키마) 확정**” 수준으로 쪼갠다.
- 긴 Task는 반드시 하위 Task로 분해하여 Queue에 등록한다.

---

## 7. (중요) 스펙 불일치 처리 규칙

스펙 문서끼리 충돌할 때, 에이전트는 아래 우선순위를 따른다.

1) 날짜가 포함된 최신 문서 > 구버전 문서  
   - UI: `26.02.06`이 우선
2) ERD 가이드의 “설계 변경 사항” 명시가 있으면 그 내용을 우선 적용  
   - messages 삭제 → chat_history 통합
3) 구현이 이미 존재한다면, **DECISIONS.md에 ‘왜 다르게 되었는지’ 기록** 후 정리

---

## 8. 빠진 기능/데이터 관점 체크리스트 (누락 방지용)

UI(26.02.06)에 있고 ERD/Playbook에 반영이 약할 수 있는 항목들:
- 면접자 “면접 진행도(phase)” 표시용 데이터(예: interviews.current_step / total_questions_planned 는 있으나, **phase 정의/매핑**은 별도 계약 필요)
- “답변 완료 버튼” → 서버에선 **turn 종료 이벤트**를 명확히 처리해야 함(Interview next_turn endpoint)
- “코딩테스트/화이트보드” → `whiteboard_notes.content_json` 저장 + 평가 대상화(옵션)

ERD(26.02.05)에 있고 API 스펙에 빠지기 쉬운 항목들:
- Redis: `interview:{id}:state`, `lock`, `rag:cache:{hash}` 키 규약
- 로그 공통 필드(timestamp/level/request_id/user_id/latency_ms/status)

루브릭(26.02.09)에 있고 구현에서 빠지기 쉬운 항목들:
- 평가 결과 JSON 스키마 고정( tag_code / evidence_data 포함 )
- 직군별 가중치 적용

---

## 9. 에이전트 출력 형식(강제)

### 9.1 작업 시작(승인 전)
1) 변경 제안서(파일/이유/내용/영향/롤백)  
2) 사용자 허락 요청

### 9.2 구현 완료 후(승인 후)
1) 변경 요약  
2) 생성/수정 파일 목록  
3) 로컬 테스트 방법(curl 예시 포함)  
4) logs 파일 경로(에러/주요 런타임 로그)  
5) docs/DEV_LOG 업데이트 요약  
6) 다음 작업 제안 1~2개

---

## 10. 부록: 핵심 스펙 요약(참조용)

### 10.1 interviews.chat_history(jsonb) 최소 권장 형태
- `{role, content, timestamp, question_id?}` 배열 형태(ERD 예시)

### 10.2 evaluation_scores.evidence_data(jsonb) 최소 권장 형태
- `cosine_similarity`, `keyword_match`, `star_structure` 등 루브릭 가이드가 명시한 근거를 포함

---

### 참고 문서(필수)
- ERD 가이드: `26.02.05(목)데이터 아키텍쳐,ERD 가이드.md`
- UI 최신본: `26.02.06(금)AI 면접 프로그램 UI 설계 초안.md`
- 태그 설계: `26.02.05(목)질문태그설계.md`
- 루브릭 가이드: `26.02.09(월)정량평가 루브릭 가이드.md`

### 문서 언어 규칙 (Mandatory)

- `docs/` 폴더 내 모든 Markdown 문서는 **한국어로 작성한다**.
- DEV_LOG, CURRENT_STATE, TASK_QUEUE, DECISIONS 등 운영 문서는
  사람이 읽는 것을 목적으로 하므로 영어 사용을 금지한다.
- 단, 코드 블록, 파일명, 클래스명, 함수명, 에러 메시지,
  로그 파일(.log)의 내용은 영어를 유지한다.
  
### Python 실행 환경 규칙 (Mandatory – 강화)

- 본 프로젝트는 단일 Python 가상환경(venv)만을 사용한다.
- 가상환경 이름: interview_env

- interview_env는 이미 다음 경로에 **존재하는 것으로 고정**한다.
  - C:\big20\big20_AI_Interview_simulation\interview_env

- 에이전트는 다음 행위를 **절대 수행해서는 안 된다**.
  - interview_env를 새로 생성하는 행위
  - 다른 이름의 venv를 생성하거나 사용하는 행위
  - IMH/IMH_Interview 하위 또는 그 외 위치에 venv를 추가 생성하는 행위
  - 전역 Python / 전역 pip 사용

- 모든 python / pip / uvicorn 실행은
  반드시 아래 실행 파일을 기준으로 수행한다.
  - C:\big20\big20_AI_Interview_simulation\interview_env\Scripts\python.exe

- pip 명령은 반드시 다음 형식만 허용된다.
  - python -m pip ...

- 위 규칙을 위반한 작업 결과는
  **사전 경고 없이 무효 처리**될 수 있다.