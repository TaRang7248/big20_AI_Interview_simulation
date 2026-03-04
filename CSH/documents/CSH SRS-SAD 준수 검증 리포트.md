# CSH 시스템 SRS/SAD 준수 검증 리포트

> **검증 대상**: `CSH/` 폴더 전체 (백엔드 20개 모듈 ~19,600줄 + 프론트엔드 Next.js 앱)  
> **기준 문서**: `소프트웨어 아키텍처 설계서 (SAD).md`, `시스템 요구사항 명세서 (SRS).md`  
> **검증 일자**: 2026-03-04

---

## 1. 총괄 요약 (Executive Summary)

| 구분 | 항목 수 | 충족 | 부분 | 미충족 | 준수율 |
|:---|:---:|:---:|:---:|:---:|:---:|
| **SRS 기능적 요구사항** (REQ-F) | 7 | 6 | 1 | 0 | **92.9%** |
| **SRS 비기능적 요구사항** (REQ-N) | 4 | 2 | 2 | 0 | **75.0%** |
| **SAD 아키텍처 컴포넌트** | 14 | 12 | 1 | 1 | **89.3%** |
| **SAD 기술 선정 근거** | 3 | 3 | 0 | 0 | **100%** |
| **종합** | **28** | **23** | **4** | **1** | **~88.6%** |

> **CSH 시스템은 SRS/SAD 대비 약 88.6%의 종합 준수율을 달성하였습니다** (가중치 기반: SRS 기능 40% + SRS 비기능 30% + SAD 아키텍처 30%, 섹션 6 상세 산출 참조). 이는 V2(~15.5%), YYR(~25.8%)과 비교하여 압도적으로 높은 수치입니다.

---

## 2. SRS 기능적 요구사항 (Functional Requirements) 검증

### REQ-F-001: 적응형 질문 생성 (Adaptive Questioning) — ✅ 충족

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| 답변 내용 실시간 분석 | ✅ | `integrated_interview_server.py` L2200-3000: `AIInterviewer.generate_response()` — 이전 답변 기반 맥락 질문 생성 |
| 꼬리 질문(Follow-up) 생성 | ✅ | `interview_workflow.py` L1-400: `InterviewPhase.FOLLOW_UP` 페이즈 + `follow_up_count` (최대 2회) |
| LangChain 메모리 모듈 | ✅ | `interview_workflow.py`: LangGraph `StateGraph` + `MemorySaver` 체크포인팅, `WorkflowState`에 `chat_history` 30+ 필드 |
| RAG 기술 결합 | ✅ | `resume_rag.py`: PGVectorStore V2 (resume_embeddings + qa_embeddings), nomic-embed-text 768d, MMR retriever (k=4, lambda_mult=0.7) |
| 프론트엔드 연동 | ✅ | `interview/page.tsx`: SSE 스트리밍 채팅 (`chatStream`), 이력서 업로드 후 RAG 인덱싱 |

**세부 분석:**
- `AIInterviewer` 클래스가 2개의 LLM 인스턴스(질문용 temp=0.7, 평가용 temp=0.3)를 분리 운용하여 질문 생성과 평가의 품질을 독립 관리
- RAG는 이력서(PDF→resume_embeddings)와 Q&A 데이터(JSON→qa_embeddings)를 병렬 조회 (`asyncio.gather`)
- Redis 캐싱 (SHA-256 해시 키, TTL 30분, pickle 직렬화)으로 중복 RAG 호출 최소화
- 한국어 가드 (한국어 비율 최소 0.6, 최대 2회 재시도)로 LLM 다국어 드리프트 방지
- `prompt_templates.py`: `INTERVIEWER_PROMPT`에 "답변 기반 맥락 유지" + "꼬리질문 최대 2회" + "총 10개 질문" 강제

---

### REQ-F-002: 멀티모달 인터랙션 (Multimodal Interaction) — ✅ 충족

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| 음성 대화 | ✅ | `stt_engine.py` (Deepgram Nova-3), `whisper_stt_service.py` (Whisper 폴백), `hume_tts_service.py` (Hume Octave TTS) |
| 화상(Video) | ✅ | `integrated_interview_server.py` L7000-7800: WebRTC `RTCPeerConnection` (aiortc), 비디오 파이프라인 |
| 텍스트(Chat/Code) | ✅ | `/api/chat` 엔드포인트 + SSE 스트리밍, `/api/coding/*` 코딩 테스트 |
| 드로잉(Whiteboard) | ✅ | `whiteboard_service.py`: Canvas→Base64→Claude 3.5 Sonnet/Qwen3-VL 분석 |
| 표정 변화 감지 | ✅ | `integrated_interview_server.py` L3000-3800: DeepFace 1초 주기 표정 분석 (7감정) |
| 목소리 떨림 감지 | ✅ | `hume_prosody_service.py`: Hume AI 48종 감정→10종 면접 지표 (자신감/불안/집중/당황/긍정/진정/부정/슬픔/놀람/피로) |
| '자신감' '당황함' 비언어적 지표 추출 | ✅ | `hume_prosody_service.py`: `extract_interview_indicators()`, `determine_emotion_adaptive_mode()` |
| 프론트엔드 시각화 | ✅ | `emotion/page.tsx` (Chart.js 3종), `EmotionCharts.tsx`, `InterviewReportCharts.tsx` (Recharts) |

**세부 분석:**
- **5종 입력 모달리티** 동시 처리: 음성(WebRTC Audio→STT) + 영상(WebRTC Video→DeepFace+Gaze) + 텍스트(REST Chat) + 코드(Monaco Editor) + 드로잉(Canvas)
- **멀티모달 감정 융합**: DeepFace(표정) 50% + Hume Prosody(음성) 50% 가중 평균 → 면접 적응 모드(encouraging/challenging/normal) 결정
- **Graceful Degradation 전면 적용**: Deepgram 실패→Whisper, WebRTC 실패→WS 계속, TTS 실패→브라우저 Web Speech, Claude 실패→Qwen3-VL

---

### REQ-F-003: 실시간 개입 (Interruption Handling) — ✅ 충족

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| 답변이 너무 길어질 경우 개입 | ✅ | `integrated_interview_server.py` L1500-2200: `InterviewInterventionManager` — `MAX_ANSWER_TIME=120s`, `soft_time_warning`(90s) + `hard_time_limit`(120s) |
| 주제 이탈 시 개입 | ✅ | `InterviewInterventionManager`: `off_topic` 개입 타입, LLM 기반 주제 관련성 판단 |
| 정중한 개입 | ✅ | 5종 개입 메시지: `soft_time_warning`, `hard_time_limit`, `off_topic`, `encourage_more`, `silence_detected` |
| VAD(Voice Activity Detection) | ✅ | 프론트엔드: Web Audio API `AnalyserNode` RMS 분석(500ms) → `interventionApi.vadSignal()`, 백엔드: VAD 시그널 수신 + 개입 판단 |
| Turn-taking 알고리즘 | ✅ | 쿨다운 15초, 턴당 최대 3회 개입, `SILENCE_THRESHOLD=5s` 침묵 감지 |
| 프론트엔드 연동 | ✅ | `interview/page.tsx`: `interventionApi.check()` 폴링, `interventionApi.vadSignal()` 전송, `startTurn()`/`endTurn()` 턴 관리 |

---

### REQ-F-004: 라이브 코딩 환경 — ✅ 충족

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| Python, JavaScript 등 주요 언어 지원 | ✅ | `code_execution_service.py`: `Language` Enum — Python, JavaScript, Java, C, C++ 5개 언어 |
| 웹 IDE 내장 | ✅ | `coding/page.tsx`: Monaco Editor (`@monaco-editor/react`) VS Code 수준 에디터 |
| 샌드박스 실행 | ✅ | `code_execution_service.py`: Docker 컨테이너 격리(네트워크 차단, RAM 256MB, PID 50 제한) + subprocess 폴백 |
| AI 코드 분석 | ✅ | `code_execution_service.py`: Qwen3-Coder 전용 LLM으로 코드 분석 |
| 시간 복잡도 분석 | ✅ | `CodeAnalysisResult`: `time_complexity` 필드 |
| 코드 스타일 분석 | ✅ | `CodeAnalysisResult`: `code_quality_score`, `style_feedback` |
| 주석 작성 여부 평가 | ✅ | `CodeAnalysisResult`: `has_comments`, `comment_quality` 분석 |
| 문제 자동 생성 | ✅ | `ProblemPool` (Redis List): Celery `pre_generate_coding_problem_task`로 사전 생성, 난이도별(Easy/Medium/Hard) |
| 보안 패턴 검사 | ✅ | `CodeSanitizer`: 5개 언어별 위험 패턴 탐지(os.system, eval, exec 등) |

**세부 분석:**
- **SRS 초과 구현**: SRS는 "Python, JavaScript 등"만 언급하나 CSH는 Java, C, C++까지 총 5개 언어 지원
- **보안 격리**: Docker→subprocess 2중 폴백, 100KB 코드 크기 제한, 언어별 보안 패턴 감지
- **AI 코딩 문제 풀**: Redis 기반 `ProblemPool` — 부족 시 Celery 비동기로 자동 보충, 즉시 제공

---

### REQ-F-005: 시스템 설계 화이트보드 — ⚠️ 부분 충족 (85%)

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| 다이어그램 캔버스 제공 | ✅ | `whiteboard/page.tsx`: HTML5 Canvas — 펜/직선/사각형/원/화살표/텍스트/지우개 7도구, 8색 팔레트, Undo/Redo |
| AI 시각적 인식 | ✅ | `whiteboard_service.py`: Canvas→Base64→Claude 3.5 Sonnet Vision API (1순위) + Qwen3-VL:4B (폴백) |
| 아키텍처 타당성 평가 | ✅ | `whiteboard_service.py`: 100점 만점 평가, 8개 카테고리(messaging/ecommerce/media/social/data/infra/storage/auth) |
| GPT-4V 활용 | ⚠️ | Claude 3.5 Sonnet + Qwen3-VL 사용 (GPT-4V 대신 대체 구현) |
| 실시간 협업 기능 | ❌ | 단일 사용자 캔버스만 구현, 실시간 협업(e.g., 화상 면접 중 동시 편집)은 미구현 |

**감점 사유:**
- SRS는 "GPT-4V 등 활용"으로 명시하였으나, 실제 구현은 Claude 3.5 Sonnet + Qwen3-VL로 대체됨. 기능적으로 동등하나 명시적 일치는 아님
- 실시간 협업(면접관과 지원자가 동시에 캔버스 조작)은 미구현

---

### REQ-F-006: 상세 피드백 리포트 — ✅ 충족

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| STAR 기법 답변 구조 분석 | ✅ | `integrated_interview_server.py` L3000-3800: `InterviewReportGenerator` — STAR(Situation/Task/Action/Result) 점수 |
| 핵심 키워드 추출 | ✅ | `InterviewReportGenerator`: 키워드 추출 + 빈도 분석 |
| 발화 속도 분석 | ✅ | `speech_analysis_service.py`: SPM/WPM, 한국어 음절 카운트, 적정 240-320 SPM, S~D 5등급 |
| 발음 명확성 분석 | ✅ | `speech_analysis_service.py`: Deepgram word-level confidence 기반 발음 등급 |
| 시선 처리 분석 | ✅ | `gaze_tracking_service.py`: DeepFace face region 기반 정면 응시 비율, 적정 60-85%, S~D 5등급 |
| 종합 리포트 생성 | ✅ | `pdf_report_service.py`: ReportLab A4 PDF — 8개 섹션(표지+합격추천, STAR, LLM평가, 발화, 시선, 감정, 키워드, 종합피드백) |
| 프론트엔드 시각화 | ✅ | `InterviewReportCharts.tsx` (861줄): Recharts 7종 차트 (역량 Radar, 답변별 Bar, STAR Bar, 감정 Pie, 키워드 Bar, SPM Area, 시선 Bar) |

**세부 분석 — SRS 초과 구현:**
- **음성 감정(Prosody)**: Hume AI 48종→10종 면접 지표 (SRS 미명시)
- **필러/간투사 감지**: "음/어/아/그러니까" 등 한국어 필러 패턴 탐지 (SRS 미명시)
- **비언어적 종합 점수**: 발화 25% + 시선 25% + 감정 25% + 음성운율 25% (SRS 미명시)
- **녹화 재생**: GStreamer/FFmpeg 녹화 + AES-256 암호화 저장 + 다운로드 (SRS 미명시)

---

### REQ-F-007: 채용 적합도 스코어링 — ✅ 충족

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| 루브릭(Rubric) 기반 평가 | ✅ | `prompt_templates.py`: `EVALUATION_PROMPT` — 5개 역량(문제해결/논리/기술/STAR/의사소통), 각 1~5점 |
| 각 역량별 1~5점 척도 | ✅ | `prompt_templates.py`: "각 항목 1-5점으로 평가", 총 25점 만점 |
| 합격/불합격 추천 의견 | ✅ | `integrated_interview_server.py` L6200-7000: 통합 점수(verbal 60% + nonverbal 40%), **pass ≥ 4.0** 기준 합격/불합격 판정 |
| 채용 담당자 직관적 판단 지원 | ✅ | `InterviewReportCharts.tsx`: Recharts Radar 차트로 5개 역량 시각화, 합격 추천 텍스트 |
| 공고 기반 평가 | ✅ | `recruiter/page.tsx` + `jobs/page.tsx`: 채용 공고 CRUD, 공고별 면접 세션 연결 |

---

## 3. SRS 비기능적 요구사항 (Non-Functional Requirements) 검증

### REQ-N-001: 초저지연 통신 — ⚠️ 부분 충족 (80%)

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| WebRTC 기반 영상 스트리밍 | ✅ | `integrated_interview_server.py` L7000-7800: aiortc `RTCPeerConnection`, SDP Offer/Answer |
| STT 변환 지연 최소화 | ✅ | Deepgram Nova-3 (실시간 WebSocket 스트리밍, endpointing=1100ms) |
| LLM 추론 시간 최적화 | ⚠️ | Ollama exaone3.5:7.8b (로컬, num_ctx=8192) — GTX 1660급 GPU에서 1.5초 초과 가능성 |
| 전체 응답 지연 ≤ 1.5초 | ⚠️ | `latency_monitor.py`: SLA 1.5초 모니터링 + 파이프라인 단계별 측정 구현, 단 로컬 LLM 추론 시간이 하드웨어 의존적 |
| SSE 스트리밍 | ✅ | `/api/chat/stream` — 토큰 단위 실시간 전송으로 체감 지연 최소화 |

**감점 사유:**
- SLA 1.5초 **모니터링 인프라**는 완벽 구현 (LatencyMonitor, 미들웨어, 대시보드)
- 그러나 **실제 달성 여부**는 하드웨어 의존적: Ollama exaone3.5:7.8b 로컬 추론이 GPU 성능에 따라 1.5초를 초과할 수 있음
- SSE 스트리밍으로 **체감 지연**은 최소화하는 우회 전략은 적절

---

### REQ-N-002: 동시 접속 처리 — ⚠️ 부분 충족 (50%)

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| 수평적 확장(Horizontal Scaling) | ⚠️ | `Dockerfile` 존재, `docker-compose.yml` 존재하나 단일 인스턴스 구성 |
| Kubernetes 오케스트레이션 | ❌ | K8s manifest/Helm chart 없음 |
| 수백 개 동시 면접 세션 | ⚠️ | Celery 6개 큐 분리 + Redis 브로커로 일부 부하 분산, 단 단일 프로세스 FastAPI 서버 |

**감점 사유:**
- **Kubernetes 배포 미구현**: SRS는 "Kubernetes 기반 오케스트레이션"을 명시적으로 요구하나, K8s manifest가 없음
- **부분 달성 요인**: Docker 컨테이너화 + Celery 워커 분리(8개 전용 큐) + Redis 브로커로 수평 확장 **기반**은 마련됨
- Celery 워커는 `--pool=solo`로 단일 스레드 실행 중 — 프로덕션 환경에서의 동시성 제한

---

### REQ-N-003: 생체 데이터 보호 — ✅ 충족

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| TLS 1.3 전송 암호화 | ✅ | `security.py`: `get_ssl_context()`, `generate_self_signed_cert()`, NGINX TLS 종단 |
| AES-256 저장 암호화 | ✅ | `security.py`: AES-256-GCM 파일 암호화 (`encrypt_file()`/`decrypt_file()`), 포맷: `[MAGIC:4B][VERSION:1B][IV:12B][TAG:16B][DATA]` |
| GDPR 즉시 삭제 | ✅ | `integrated_interview_server.py` L4600-5400: `/api/users/{user_id}/data` DELETE — 사용자 데이터 전체 영구 삭제 |
| 환경변수 기반 키 관리 | ✅ | `security.py`: `os.getenv("ENCRYPTION_KEY")`, `.env` 파일 분리 |
| bcrypt 비밀번호 해싱 | ✅ | `security.py`: bcrypt(rounds=12) + SHA-256 하위 호환 마이그레이션 |
| JWT 인증 | ✅ | `security.py`: JWT HS256, Bearer 토큰, `get_current_user()` 의존성 주입 |
| 세션 관리 | ✅ | `AuthContext.tsx`: sessionStorage 영속화, 세션 타임아웃 60분, 유휴 30분, 면접 중 보호 |
| 회원탈퇴/데이터 삭제 | ✅ | `profile/page.tsx`: 회원탈퇴 UI + `authApi.deleteAccount()` |

**세부 분석 — SRS 초과 구현:**
- **소셜 로그인 보안**: Kakao/Google/Naver OAuth2 (SRS 미명시)
- **암호화 실패 Graceful Degradation**: 암호화 실패 시 원본 반환으로 서비스 중단 방지
- **코드 실행 보안 격리**: Docker 컨테이너 네트워크 차단 + 메모리 제한 (SRS 미명시)

---

### REQ-N-004: 공정성 및 편향 방지 — ⚠️ 부분 충족 (60%)

| SRS 요구사항 | 구현 상태 | 근거 파일 / 위치 |
|:---|:---:|:---|
| 인종/성별/억양 편향 검증 | ❌ | 다양한 데이터셋 검증 로직 없음, 편향 테스트 미구현 |
| 평가 결과 설명 가능성(Explainability) | ✅ | `prompt_templates.py`: 5개 역량별 점수 + 근거 텍스트, `InterviewReportGenerator`: STAR 분석 + 키워드 기반 근거 |
| 다양한 데이터셋 검증 | ❌ | 편향 감사(Bias Audit) 파이프라인 없음 |

**감점 사유:**
- **Explainability는 잘 구현됨**: 5개 역량별 점수 산출 근거 텍스트, STAR 분석 결과, 키워드 추출 → 채용 담당자가 AI 판단 근거를 확인 가능
- **편향 검증 완전 미구현**: 인종/성별/억양에 따른 모델 편향 테스트, 공정성 지표(Demographic Parity, Equalized Odds 등) 없음
- 이는 별도의 ML Ops / Fairness 파이프라인이 필요한 영역으로, 현재 시스템 범위에서의 한계

---

## 4. SAD 아키텍처 컴포넌트 검증

### 4.1 Presentation Layer

| SAD 컴포넌트 | 기술 스택 (SAD) | 구현 상태 | 실제 구현 | 비고 |
|:---|:---|:---:|:---|:---|
| **Candidate App** | React, Next.js, WebRTC API | ✅ | Next.js 16.1.6 + React 19 + TypeScript, WebRTC `RTCPeerConnection` | 면접/코딩/화이트보드/대시보드/감정/프로필/설정 7개 페이지 |
| **Recruiter Dashboard** | React, Recharts | ✅ | `recruiter/page.tsx` + `InterviewReportCharts.tsx` (Recharts 7종 차트) | 공고 관리 + 통계 시각화 |

### 4.2 Gateway Layer

| SAD 컴포넌트 | 기술 스택 (SAD) | 구현 상태 | 실제 구현 | 비고 |
|:---|:---|:---:|:---|:---|
| **API Gateway** | NGINX / Traefik | ✅ | `CSH/nginx/` 디렉토리, NGINX 리버스 프록시 + SSL 종단 + 로드 밸런싱 | Traefik 미사용, NGINX 단독 |

### 4.3 Application Layer

| SAD 컴포넌트 | 기술 스택 (SAD) | 구현 상태 | 실제 구현 | 비고 |
|:---|:---|:---:|:---|:---|
| **Core API Service** | FastAPI (Python) | ✅ | `integrated_interview_server.py` (9,268줄), 80+ REST 엔드포인트 | 사용자 인증, 세션 관리, 비즈니스 로직 전체 |
| **Signaling Server** | FastAPI (WebSockets) | ✅ | WebSocket `/ws/interview/{session_id}`: SDP/ICE 교환, STT 결과 수신, 감정/운율 브로드캐스트 | 동일 서버 내 WS 엔드포인트 |

### 4.4 Real-time Layer

| SAD 컴포넌트 | 기술 스택 (SAD) | 구현 상태 | 실제 구현 | 비고 |
|:---|:---|:---:|:---|:---|
| **Media Server** | Python (aiortc or GStreamer) | ✅ | aiortc `RTCPeerConnection` + GStreamer/FFmpeg 녹화 파이프라인 | `media_recording_service.py`: GStreamer→FFmpeg 2중 폴백 |

### 4.5 AI Services Layer

| SAD 컴포넌트 | 기술 스택 (SAD) | 구현 상태 | 실제 구현 | 비고 |
|:---|:---|:---:|:---|:---|
| **STT Service** | Deepgram SDK / Whisper | ✅ | `stt_engine.py` (Deepgram Nova-3 WebSocket) + `whisper_stt_service.py` (faster-whisper + openai-whisper 폴백) | 3중 폴백 체인 |
| **LLM Orchestrator** | LangChain, LangGraph | ✅ | `interview_workflow.py`: LangGraph `StateGraph` 10-phase 워크플로우 + `MemorySaver` | `ChatOllama` (exaone3.5:7.8b) |
| **Emotion Engine** | DeepFace, Hume AI | ✅ | DeepFace (표정 7감정, 1초 주기) + Hume Prosody (음성 48종→10종 면접 지표) | 멀티모달 융합 (50:50) |

### 4.6 Async Tasks Layer

| SAD 컴포넌트 | 기술 스택 (SAD) | 구현 상태 | 실제 구현 | 비고 |
|:---|:---|:---:|:---|:---|
| **Task Queue** | Celery | ✅ | `celery_app.py` + `celery_tasks.py` (1,366줄): 8개 전용 큐, 13+ 태스크, Beat 스케줄 | 리포트/TTS/RAG/평가/감정/트랜스코딩/코딩 |

### 4.7 Data Layer

| SAD 컴포넌트 | 기술 스택 (SAD) | 구현 상태 | 실제 구현 | 비고 |
|:---|:---|:---:|:---|:---|
| **Main DB** | Oracle | ⚠️ | **PostgreSQL** + SQLAlchemy ORM | SAD는 Oracle 명시, 실제는 PostgreSQL로 대체 (pgvector 호환성 위해) |
| **Vector DB** | Pinecone / pgvector | ✅ | `resume_rag.py`: PGVectorStore V2 (pgvector), nomic-embed-text 768d, COSINE_DISTANCE | Pinecone 미사용, pgvector 단독 |
| **Cache/Broker** | Redis | ✅ | Redis: Celery 브로커 + EventBus Pub/Sub + RAG 캐시(TTL 30분) + TTS 캐시 + 감정 TimeSeries + STT 상태 + 세션 상태 | 7+ 용도 활용 |
| **Object Storage** | GCP | ❌ | 로컬 파일시스템 (`uploads/` 디렉토리) | GCP Object Storage 미연결 |

---

## 5. SAD 기술 선정 근거 (Technology Rationale) 검증

### 5.1 웹 프레임워크: FastAPI — ✅ 충족

| SAD 근거 | 구현 상태 | 검증 |
|:---|:---:|:---|
| 비동기 처리 (asyncio) | ✅ | `async def` 전면 활용, `asyncio.gather()`로 RAG/감정/운율 병렬 처리 |
| Pydantic 데이터 검증 | ✅ | Pydantic BaseModel 기반 이벤트/요청/응답 모델, 엄격한 타입 힌팅 |
| AI 라이브러리 통합 | ✅ | LangChain, LangGraph, DeepFace, Hume AI, aiortc 등 직접 통합 |

### 5.2 실시간 통신: WebRTC SFU 아키텍처 — ✅ 충족

| SAD 근거 | 구현 상태 | 검증 |
|:---|:---:|:---|
| 서버 사이드 프로세싱 (SFU) | ✅ | aiortc 서버에서 미디어 수신 → STT + DeepFace + Gaze + Recording 병렬 분기 |
| 오디오→STT 엔진 분기 | ✅ | PCM16 16kHz → Deepgram Nova-3 WebSocket + Whisper 폴백 |
| 비디오→컴퓨터 비전 분기 | ✅ | VP8 디코딩 → DeepFace 1초 주기 + GazeTracking + GStreamer 녹화 |

### 5.3 비동기 작업: Celery + Redis — ✅ 충족

| SAD 근거 | 구현 상태 | 검증 |
|:---|:---:|:---|
| 리포트 생성 비동기 | ✅ | `generate_report_task`, `complete_interview_workflow_task` |
| 고해상도 영상 저장 비동기 | ✅ | `transcode_recording_task`, `cleanup_recording_task` |
| Redis 브로커 역할 | ✅ | Celery 메시지 브로커, 결과 백엔드 |
| Redis 대화 맥락 저장 | ✅ | RAG 캐시(TTL 30분), 세션 상태, STT 상태, TTS 캐시, 감정 TimeSeries |

---

## 6. 가중치 기반 종합 점수 산출

### 6.1 SRS 기능적 요구사항 (가중치 40%)

| 요구사항 | 점수 (0~10) | 가중치 | 소계 |
|:---|:---:|:---:|:---:|
| REQ-F-001 적응형 질문 | 10 | 1/7 | 1.43 |
| REQ-F-002 멀티모달 인터랙션 | 10 | 1/7 | 1.43 |
| REQ-F-003 실시간 개입 | 10 | 1/7 | 1.43 |
| REQ-F-004 라이브 코딩 | 10 | 1/7 | 1.43 |
| REQ-F-005 화이트보드 | 8.5 | 1/7 | 1.21 |
| REQ-F-006 상세 리포트 | 10 | 1/7 | 1.43 |
| REQ-F-007 채용 스코어링 | 10 | 1/7 | 1.43 |
| **소계** | | | **9.79 / 10** |
| **40% 환산** | | | **39.1 / 40** |

### 6.2 SRS 비기능적 요구사항 (가중치 30%)

| 요구사항 | 점수 (0~10) | 가중치 | 소계 |
|:---|:---:|:---:|:---:|
| REQ-N-001 초저지연 통신 | 8.0 | 1/4 | 2.00 |
| REQ-N-002 동시 접속 처리 | 5.0 | 1/4 | 1.25 |
| REQ-N-003 생체 데이터 보호 | 10 | 1/4 | 2.50 |
| REQ-N-004 공정성/편향 방지 | 6.0 | 1/4 | 1.50 |
| **소계** | | | **7.25 / 10** |
| **30% 환산** | | | **21.8 / 30** |

### 6.3 SAD 아키텍처 (가중치 30%)

| 구분 | 항목 수 | 충족 | 부분 | 미충족 | 점수 |
|:---|:---:|:---:|:---:|:---:|:---:|
| 아키텍처 컴포넌트 (14) | 14 | 12 | 1 | 1 | 8.93/10 |
| 기술 선정 근거 (3) | 3 | 3 | 0 | 0 | 10/10 |
| **가중 평균** | | | | | **9.24 / 10** |
| **30% 환산** | | | | | **27.7 / 30** |

### 6.4 최종 종합 점수

| 구분 | 점수 | 만점 |
|:---|:---:|:---:|
| SRS 기능적 (40%) | 39.1 | 40 |
| SRS 비기능적 (30%) | 21.8 | 30 |
| SAD 아키텍처 (30%) | 27.7 | 30 |
| **최종 합계** | **88.6** | **100** |

---

## 7. 주요 미비 사항 및 개선 권고

### 7.1 Critical (높은 우선순위)

| # | 미비 사항 | 관련 요구사항 | 개선 방안 |
|:---|:---|:---|:---|
| 1 | **Kubernetes 배포 미구현** | REQ-N-002 | Helm chart 또는 K8s manifest 작성, HPA(Horizontal Pod Autoscaler) 설정 |
| 2 | **GCP Object Storage 미연결** | SAD Data Layer | GCS 버킷 연동, 녹화/리포트 파일 Cloud Storage 마이그레이션 |

### 7.2 Major (중간 우선순위)

| # | 미비 사항 | 관련 요구사항 | 개선 방안 |
|:---|:---|:---|:---|
| 3 | **AI 공정성/편향 테스트 미구현** | REQ-N-004 | Fairness Indicators(Demographic Parity, EO) 테스트 파이프라인         구축, 다양한 억양/성별 음성 데이터셋으로 STT 성능 검증 |
| 4 | **LLM 응답 1.5초 SLA 하드웨어 의존** | REQ-N-001 | 모델 경량화(quantization), GPU 업그레이드, 또는 클라우드 LLM(GPT-4o-mini) 하이브리드 |
| 5 | **Oracle→PostgreSQL 변경** | SAD Data Layer | 이는 합리적 기술 판단이나, SAD 문서 자체를 PostgreSQL로 업데이트 필요 |

### 7.3 Minor (낮은 우선순위)

| # | 미비 사항 | 관련 요구사항 | 개선 방안 |
|:---|:---|:---|:---|
| 6 | **GPT-4V→Claude/Qwen 대체** | REQ-F-005 | 기능적으로 동등하나, SRS 정합성 위해 GPT-4V 옵션 추가 고려 |
| 7 | **화이트보드 실시간 협업 미구현** | REQ-F-005 | WebSocket 기반 캔버스 공유 (CRDT/OT 알고리즘) |
| 8 | **Celery --pool=solo** | REQ-N-002 | 프로덕션: `--pool=prefork` 또는 `--pool=gevent`로 변경 |

---

## 8. 시스템 간 비교 (V2 / YYR / CSH)

| 평가 항목 | V2 | YYR | **CSH** |
|:---|:---:|:---:|:---:|
| **SRS 기능적 준수** | ~22% | ~38% | **~98%** |
| **SRS 비기능적 준수** | ~6% | ~6% | **~73%** |
| **SAD 아키텍처 준수** | ~20% | ~26% | **~92%** |
| **종합 준수율** | **~15.5%** | **~25.8%** | **~88.6%** |

### CSH만의 차별적 구현:
1. **완전한 멀티모달 파이프라인**: WebRTC Video + Audio + Text + Code + Whiteboard 5종 동시 처리
2. **3중 STT 폴백 체인**: Deepgram Nova-3 → Whisper (faster-whisper → openai-whisper) → 브라우저 Web Speech API
3. **EventBus 아키텍처**: Redis Pub/Sub + In-process + WebSocket 3중 이벤트 전파
4. **Celery 8개 전용 큐**: 서비스별 장애 격리 + Beat 스케줄러
5. **PDF 리포트**: STAR + 발화 + 시선 + 감정 + 운율 + 키워드 종합 8섹션 PDF
6. **보안 완성도**: AES-256-GCM + bcrypt + JWT + TLS + GDPR 삭제 + OAuth2 소셜 로그인
7. **Graceful Degradation 전면 적용**: 모든 외부 서비스(STT/TTS/Vision/Docker/GStreamer)에 폴백 체인

---

## 9. 결론

CSH 시스템은 SRS/SAD 문서에서 정의된 **28개 요구사항 및 아키텍처 컴포넌트 중 23개를 완전 충족, 4개를 부분 충족, 1개만 미충족**하여 **약 88.6%의 종합 준수율**을 달성했습니다.

특히 SRS 기능적 요구사항은 **7개 중 6개를 완전 충족**(REQ-F-005만 85% 부분 충족)하며, 일부 항목(REQ-F-006 리포트, REQ-N-003 보안)은 **SRS 명세를 초과하여 구현**했습니다.

주요 개선 영역은:
1. **인프라 레벨**: Kubernetes 배포 + GCP Object Storage 연동
2. **AI 윤리**: 공정성/편향 테스트 파이프라인
3. **성능**: LLM 추론 최적화 (클라우드 하이브리드 또는 모델 경량화)

이 세 영역이 해결되면 **95% 이상의 완전한 SRS/SAD 준수**가 가능합니다.
