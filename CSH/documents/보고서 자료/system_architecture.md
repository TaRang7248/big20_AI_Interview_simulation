# 3. 시스템 아키텍처 설계

본 장에서는 AI 모의면접 시뮬레이션 시스템의 전체 소프트웨어 아키텍처를 체계적으로 기술한다. 아키텍처 설계는 2장에서 도출된 기능적·비기능적 요구사항을 기술적으로 구현하기 위한 구조적 결정(Architectural Decision)의 집합으로서, 시스템의 품질 속성(Quality Attributes)인 응답 지연(Latency), 확장성(Scalability), 가용성(Availability), 보안성(Security)을 동시에 만족하는 설계를 지향하였다. 본 시스템은 전통적인 계층형 아키텍처(Layered Architecture)에 이벤트 기반 아키텍처(Event-Driven Architecture, EDA)를 결합한 하이브리드(Hybrid) 설계 패턴을 채택하여, 다양한 AI 서비스의 실시간 통합이라는 고유한 기술적 도전을 해결하고자 하였다.

---

## 3.1 전체 아키텍처 개요 (계층형 + 이벤트 기반 하이브리드)

### 3.1.1 아키텍처 설계 철학

본 시스템의 아키텍처 설계는 다음의 세 가지 근본 원칙을 기반으로 구성되었다.

**첫째, 관심사의 분리(Separation of Concerns)이다.** 시스템의 각 구성 계층은 명확히 구분된 단일 책임(Single Responsibility)을 가지며, 계층 간의 통신은 잘 정의된 인터페이스를 통해서만 이루어진다. 프레젠테이션 계층은 사용자 인터랙션의 렌더링에, 애플리케이션 계층은 비즈니스 로직의 처리에, 데이터 계층은 상태 영속성(State Persistence)에 각각 전념함으로써 계층 간 결합도(Coupling)를 최소화하고 각 계층의 독립적 진화(Independent Evolution)를 가능케 한다.

**둘째, 느슨한 결합(Loose Coupling)과 높은 응집도(High Cohesion)이다.** 특히 다수의 AI 서비스(LLM, STT, TTS, DeepFace, Hume Prosody, Claude Vision)가 동시에 동작하는 환경에서, 개별 서비스의 장애가 전체 시스템으로 전파되지 않도록 격리(Isolation) 설계가 적용되었다. 이벤트 버스(EventBus)를 통한 비동기 통신 패턴과 Celery 워커를 통한 태스크 오프로딩(Task Offloading)은 각 서비스 간의 직접 의존성을 제거하여 느슨한 결합을 실현하는 핵심 메커니즘이다.

**셋째, 방어적 설계(Defensive Design)이다.** 현실적인 운영 환경에서 외부 API의 일시적 장애, 로컬 GPU 메모리 부족으로 인한 LLM 타임아웃, 네트워크 불안정 등 다양한 예외 상황이 발생할 수 있음을 상정하고, 2장에서 정의한 REQ-N-006(Graceful Degradation) 요구사항을 모든 계층에 걸쳐 일관되게 적용하였다. 이는 단순한 예외 처리(Exception Handling)를 넘어, 각 서비스의 폴백 경로(Fallback Path)를 사전에 명확히 설계하는 수준의 방어적 아키텍처를 의미한다.

### 3.1.2 6계층 아키텍처 구성

본 시스템은 클라이언트 측에서 서버 측으로 수직적으로 배치된 6개의 기능 계층(Layer)으로 구성된다. 각 계층은 하위 계층에만 의존하며, 상위 계층으로의 역방향 의존성은 이벤트 발행(Event Publishing)을 통한 비동기 알림 방식으로 처리된다.

- **제1계층: Presentation Layer (Next.js 16 프론트엔드)** — 사용자와 직접 상호작용하는 웹 프론트엔드 계층. React 19.2.3 기반의 Next.js 16.1.6으로 구현된 SPA이다.
- **제2계층: Gateway Layer (NGINX API Gateway)** — 모든 외부 트래픽의 단일 진입점(Single Entry Point). SSL 종단, 라우팅, Rate Limiting을 담당한다.
- **제3계층: Application Layer (FastAPI Core API)** — 비즈니스 로직 처리, REST API 및 WebSocket 서빙, LangGraph 상태머신 오케스트레이션을 담당한다.
- **제4계층: AI & Real-time Processing Layer** — WebRTC 미디어 처리, STT/TTS 파이프라인, DeepFace 감정 분석, 시선 추적 등 실시간 AI 처리를 담당한다.
- **제5계층: Async Task Layer (Celery 워커)** — LLM 답변 평가, 리포트 생성, 이력서 RAG 처리 등 지연 허용(Latency-tolerant) 작업을 비동기적으로 처리한다.
- **제6계층: Data Layer (PostgreSQL + pgvector + Redis)** — 관계형 데이터 영속성, 벡터 임베딩 저장, 세션 캐싱 및 Pub/Sub 메시징을 담당한다.

이 6개 계층은 수직적 요청 처리 경로(Request Path)와 수평적 이벤트 전파 경로(Event Path)의 두 가지 데이터 흐름으로 연결된다. 수직적 경로는 사용자의 요청이 Presentation → Gateway → Application 계층을 거쳐 처리되고 응답이 반환되는 동기적(Synchronous) 흐름이며, 수평적 경로는 이벤트 버스와 Redis Pub/Sub를 통해 Application ↔ Async Task 계층 간의 상태 변화가 비동기적으로 전파되는 흐름이다.

---

## 3.2 계층별 설계 상세

### 3.2.1 Presentation Layer — Next.js 16 프론트엔드

프레젠테이션 계층은 지원자와 AI 면접관 간의 실시간 인터랙션을 가능케 하는 웹 기반 사용자 인터페이스를 제공한다. 기술 스택은 Next.js 16.1.6(App Router), React 19.2.3, TypeScript, Tailwind CSS의 조합으로 구성되며, 웹 표준 프레임워크를 통한 SSR(Server-Side Rendering) 및 클라이언트 측 상호작용을 지원한다.

**페이지 구성 (10개 라우트):** 시스템의 주요 페이지는 메인 랜딩 페이지(landing page), 로그인/회원가입 페이지(auth), 이력서 및 채용공고 관리 페이지(dashboard), 면접 준비 설정 페이지(interview/setup), 실시간 화상 면접 페이지(interview/session), 코딩 테스트 페이지(interview/coding), 화이트보드 설계 페이지(interview/whiteboard), 면접 결과 리포트 페이지(report), 사용자 프로필 페이지(profile)로 구성된다.

**컴포넌트 아키텍처:** 컴포넌트는 공통 UI 컴포넌트(Button, Modal, Toast, Spinner 등), 인증 관련 컴포넌트(LoginForm, RegisterForm, SocialLoginButtons), 면접 특화 컴포넌트(VideoCanvas, ChatBubble, EmotionIndicator, VADStatus), 리포트 시각화 컴포넌트(RadarChart, BarChart, EmotionPieChart, GazeChart, SpeedAreaChart)의 4개 그룹으로 분류된다. 각 컴포넌트는 단일 책임 원칙에 따라 설계되어 재사용성과 테스트 용이성을 확보하였다.

**상태 관리 (3개 Context):** 전역 상태 관리는 React Context API를 통해 구현된다. AuthContext는 로그인 상태, JWT 토큰, 사용자 정보를 관리하며, ToastContext는 시스템 알림 메시지의 표시 큐를 관리하고, EventBusContext는 WebSocket 연결 상태와 실시간 이벤트 구독(Subscription)을 관리한다. 이 세 Context는 최상위 레이아웃(layout.tsx)에서 프로바이더(Provider)로 래핑되어 하위 모든 컴포넌트에서 접근 가능하다.

**실시간 이벤트 알림 시스템:** 면접 진행 중 발생하는 모든 실시간 이벤트(STT 중간 결과, AI 면접관 응답 텍스트 스트리밍, 감정 분석 결과, 이력서 처리 완료, 리포트 생성 완료 등)는 WebSocket 연결을 통해 수신되며, EventBusContext의 핸들러가 이를 적절한 UI 컴포넌트 상태 업데이트 및 Toast 알림으로 변환하여 사용자에게 전달한다.

### 3.2.2 Gateway Layer — NGINX API Gateway

NGINX는 시스템의 모든 외부 트래픽이 통과하는 단일 진입점(Single Entry Point)으로서 다음의 기능을 담당한다.

**SSL/TLS 종단(Termination):** 포트 80(HTTP)으로 수신된 모든 요청을 포트 443(HTTPS)으로 301 영구 리다이렉트하며, TLS 1.2 및 TLS 1.3 프로토콜만을 허용한다. 사용 가능한 암호 스위트는 ECDHE-ECDSA-AES128-GCM-SHA256, ECDHE-RSA-AES128-GCM-SHA256, ECDHE-ECDSA-AES256-GCM-SHA384, ECDHE-RSA-AES256-GCM-SHA384로 한정되어 OWASP 권장 기준을 충족한다. SSL 세션 캐싱(10MB 공유 캐시, TTL 10분)을 통해 반복 연결의 TLS 핸드셰이크 비용을 절감한다. HTTP/2 프로토콜이 활성화되어 요청 멀티플렉싱(Multiplexing)과 헤더 압축(Header Compression)을 지원한다.

**라우팅 정책:** URL 경로 기반으로 트래픽을 두 개의 업스트림(Upstream)으로 분기한다. `/api/**` 및 `/ws/**` 경로의 요청은 FastAPI 백엔드(포트 8000)로, 그 외 모든 요청은 Next.js 프론트엔드(포트 3000)로 프록시된다. WebSocket 업그레이드 헤더(Upgrade: websocket, Connection: upgrade)는 `/ws/` 경로에서 자동으로 처리되며, WebSocket 연결의 유지 타임아웃은 면접 세션 최대 지속 시간(120분)을 고려하여 7,200초로 설정되었다. LLM 추론 등 장시간 소요 요청에 대비하여 `/api/` 경로의 프록시 읽기(read) 및 전송(send) 타임아웃은 각 120초로 설정되었다.

**Rate Limiting:** 3개의 독립된 Rate Limit 존(Zone)이 설정된다. 일반 API 요청은 IP당 초당 20개(버스트 40개), 인증 관련 엔드포인트(`/api/auth/`)는 IP당 초당 5개(버스트 10개), WebSocket 연결은 IP당 초당 5개(버스트 10개)로 제한되며, 초과 요청은 즉시 HTTP 429 Too Many Requests 응답으로 처리된다.

**보안 헤더 설정:** X-Frame-Options: SAMEORIGIN(클릭재킹 방지), X-Content-Type-Options: nosniff(MIME 스니핑 방지), X-XSS-Protection: 1; mode=block(XSS 필터 활성화), Referrer-Policy: strict-origin-when-cross-origin, Strict-Transport-Security: max-age=31536000; includeSubDomains(HSTS 강제)가 모든 응답에 자동으로 추가된다. 서버 버전 정보는 `server_tokens off` 설정으로 외부에 노출되지 않는다.

**업스트림 부하 분산:** FastAPI 업스트림은 `least_conn` 알고리즘(최소 연결 수 우선 라우팅)을 사용하여 복수의 FastAPI 인스턴스 간 트래픽을 분산할 수 있는 구조로 설계되었다. 현재 단일 인스턴스가 기본 설정이나, 업스트림 서버 목록에 인스턴스를 추가하는 것만으로 수평적 확장이 가능하다.

**정적 자산 캐싱:** Next.js가 빌드한 정적 자산(`_next/static/`)은 NGINX 레벨에서 365일 장기 캐시(Cache-Control: public, max-age=31536000, immutable)가 적용되어, 반복 방문 시 불필요한 서버 요청 없이 클라이언트 캐시에서 즉시 제공된다.

### 3.2.3 Application Layer — FastAPI Core API

애플리케이션 계층은 `integrated_interview_server.py` 단일 모듈에 구현된 FastAPI 서버가 담당한다. 이 서버는 REST API, WebSocket, SSE의 세 가지 엔드포인트 유형을 모두 서빙하며, LangGraph 상태머신 오케스트레이션, WebRTC 시그널링, 이벤트 버스 관리, 보안 미들웨어 적용 등 시스템의 핵심 비즈니스 로직을 포함한다.

**API 엔드포인트 구성 (100개 이상):** 본 서버는 사용자 인증(로그인, 회원가입, 소셜 OAuth2), 이력서 업로드 및 RAG 처리, 면접 세션 생성·조회·종료, 채팅(면접 답변 수신 및 AI 질문 응답), WebRTC 시그널링(offer/answer/ICE 교환), STT 스트리밍 수신, 감정 분석 결과 폴링, 코딩 테스트 문제 조회 및 제출, 화이트보드 캡처 분석, 평가 리포트 조회, PDF 다운로드, 모니터링(`/api/monitoring/latency`), GDPR 데이터 삭제 등 100개 이상의 REST 및 WebSocket 엔드포인트를 제공한다.

**비동기 처리 아키텍처:** Python asyncio를 기반으로 한 완전 비동기(Fully Asynchronous) 요청 처리가 구현된다. CPU 바운드(CPU-bound) 및 I/O 블로킹 작업(DeepFace 추론, LLM 호출, RAG 임베딩)은 각각 용도에 특화된 ThreadPoolExecutor를 통해 이벤트 루프 블로킹 없이 처리된다. LLM_EXECUTOR(max_workers=2)와 VISION_EXECUTOR(max_workers=2), RAG_EXECUTOR(max_workers=2)의 세 개 전용 실행기가 독립적으로 운용되어, 특정 작업의 병목이 다른 작업의 처리를 지연시키지 않도록 격리된다. max_workers=2로 제한한 것은 GTX 1660(VRAM 6GB) 환경에서 GPU 메모리 경합을 방지하기 위한 의도적 제약으로, VRAM 압박 시 발생하는 전체 파이프라인 지연을 억제한다.

**미들웨어 스택:** 요청 처리 파이프라인은 CORS 미들웨어(CORSMiddleware, 허용 오리진 설정), 지연 시간 측정 미들웨어(LatencyMonitor, SLA 1.5초 자동 감시), JWT 인증 미들웨어(FastAPI Depends 패턴)의 순서로 구성된다.

**uvicorn 실행 설정:** 프로덕션 환경에서는 Docker 컨테이너 내에서 uvicorn이 `--workers 2` 옵션으로 2개의 워커 프로세스를 생성하여, 다중 CPU 코어의 활용과 동시 요청 처리 용량을 높인다. `--forwarded-allow-ips '*'` 옵션으로 NGINX 프록시 헤더(X-Forwarded-*)를 신뢰하여 실제 클라이언트 IP 정보를 정확하게 로깅한다.

### 3.2.4 AI & Real-time Processing Layer

AI 및 실시간 처리 계층은 WebRTC 미디어 파이프라인과 다수의 AI 서비스가 협력하여 동작하는 복합 계층으로, 본 시스템에서 가장 기술적으로 복잡한 구성을 갖는다.

**WebRTC 미디어 파이프라인 (aiortc SFU):** 지원자의 웹 브라우저와 서버 간의 실시간 미디어 통신은 WebRTC 표준을 준수하는 aiortc 라이브러리를 통해 구현된다. 서버는 SFU(Selective Forwarding Unit) 아키텍처를 채택하여, 클라이언트의 비디오/오디오 스트림을 서버에서 직접 수신하고 AI 분석 파이프라인으로 전달한다. SDP(Session Description Protocol) offer/answer 교환과 ICE(Interactive Connectivity Establishment) 후보 협상은 FastAPI WebSocket 엔드포인트를 통한 시그널링으로 처리된다. 수신된 미디어 트랙은 비디오 트랙과 오디오 트랙으로 분기되어 각각 DeepFace 감정 분석(비디오)과 STT/Prosody 분석(오디오) 파이프라인으로 전달된다. GStreamer와 FFmpeg를 활용한 미디어 녹화 및 트랜스코딩 기능은 `media_recording_service.py` 모듈이 담당한다.

**실시간 음성 인식(STT) 파이프라인:** WebRTC 오디오 트랙에서 추출된 실시간 오디오 데이터는 Deepgram Nova-3 API로 스트리밍되어 한국어 음성 인식이 수행된다. Deepgram은 중간 결과(Interim Result)와 최종 결과(Final Result), 발화 종료(UtteranceEnd) 이벤트를 구분하여 반환하며, 이 중 UtteranceEnd 이벤트가 VAD 기반 Turn-taking 시스템의 트리거로 활용된다. STT 결과에는 띄어쓰기 보정 파이프라인(STT_SPACING_MODE: off/safe/full의 3단계 정책)이 적용되며, 한국어 기술 토큰(Redis, JWT, Node.js 등)은 보정 전 플레이스홀더로 보호되어 과도한 보정으로 인한 왜곡을 방지한다. word-level confidence 통계(평균, 표준편차)를 기반으로 low confidence 발화에 대해서는 보정을 보수적으로 적용하는 safe 정책이 기본값이다. Deepgram 장애 시에는 `stt_engine.py`의 Whisper 폴백 엔진이 자동으로 활성화된다.

**AI 음성 합성(TTS) 파이프라인:** LLM이 생성한 면접 질문 텍스트는 Hume AI EVI(Empathic Voice Interface) API를 통해 음성으로 합성된다. Hume AI EVI는 단순 음성 합성을 넘어 텍스트의 감정적 맥락을 분석하여 억양과 강세를 동적으로 조절하는 감정 인식(Emotion-aware) TTS 기능을 제공한다. 생성된 음성 파일(MP3)은 서버에 로컬 저장되며, 클라이언트는 HTTP 파일 엔드포인트를 통해 해당 파일을 수신하여 재생한다. `hume_tts_service.py` 모듈이 이 파이프라인을 담당한다.

**표정 감정 분석 파이프라인:** 수신된 비디오 스트림에서 1초 간격으로 프레임을 추출하고, DeepFace.analyze()를 VISION_EXECUTOR를 통해 비동기적으로 호출하여 7가지 기본 감정을 분류한다. 분석 결과는 GazeTrackingService에도 전달되어 얼굴 영역(Face Region) 정보를 통한 시선 방향 추정에 활용된다. 실시간 분석 결과는 LangGraph 상태머신의 WorkflowState에 last_emotion으로 저장되어 다음 질문 생성의 감정 적응 모드 결정에 반영된다.

**음성 감정 분석(Prosody) 파이프라인:** 발화 구간의 오디오는 `hume_prosody_service.py`를 통해 Hume AI Prosody API에 별도로 전송되어 심층 음성 감정 분석이 수행된다. 분석된 48개 감정 지표 중 면접 평가에 유의미한 10개 핵심 지표가 추출되어 interview_indicators 딕셔너리로 정리된다. Prosody와 DeepFace 분석 결과의 멀티모달 융합은 `merge_with_deepface()` 함수를 통해 수행되며, 최종 감정 적응 모드(normal/encouraging/challenging)를 산출한다.

### 3.2.5 Async Task Layer — Celery 워커 (6큐, 16태스크)

비동기 태스크 계층은 Celery 분산 태스크 큐를 통해 지연 허용 가능한(Latency-tolerant) AI 처리 작업을 메인 API 서버에서 분리하여 백그라운드에서 처리한다. 이 분리는 LLM 추론, 이력서 RAG 처리, 리포트 생성 등 수 초에서 수 분의 처리 시간이 소요될 수 있는 작업이 메인 이벤트 루프를 블로킹하지 않도록 보장한다.

**6개 전용 큐 구성:**

- **llm_evaluation 큐**: 답변 평가 태스크(evaluate_answer_task, batch_evaluate_task, pre_generate_coding_problem_task)를 처리한다.
- **emotion_analysis 큐**: 감정 분석 태스크(analyze_emotion_task, batch_emotion_analysis_task)를 처리한다.
- **report_generation 큐**: 리포트 생성 태스크(generate_report_task, complete_interview_workflow_task)를 처리한다.
- **tts_generation 큐**: TTS 합성 태스크(generate_tts_task, prefetch_tts_task)를 처리한다.
- **rag_processing 큐**: 이력서 RAG 처리 태스크(process_resume_task)를 처리한다.
- **media_processing 큐**: 녹화 파일 트랜스코딩 및 정리 태스크(transcode_recording_task, cleanup_recording_task)를 처리한다.

**16개 태스크 명세:** 각 태스크는 soft_time_limit과 hard time_limit을 이중으로 설정하여 응답 없는 태스크의 무기한 대기를 방지한다. 핵심 평가 태스크인 evaluate_answer_task는 soft_time_limit=60초, time_limit=90초로 설정되며, 최대 3회 자동 재시도(retry)가 가능하다. 리포트 생성 태스크(generate_report_task)는 STAR 키워드 분석, 기술 키워드 추출, 강점/개선점 집계, 점수 통계 계산, 개선 권고사항 생성의 5단계 처리를 순차적으로 수행하며 soft_time_limit=120초이다.

**주기적 태스크 (Celery Beat):** 5분 간격으로 만료된 세션 정리(cleanup_sessions_task)가 실행되며, 1시간 간격으로 시스템 전반의 통계 집계(aggregate_statistics_task)가 수행된다.

**이벤트 기반 연동:** 각 태스크가 완료될 때마다 `_publish_event()` 헬퍼 함수를 통해 Redis Pub/Sub 채널에 완료 이벤트(예: evaluation.completed, report.generated, emotion.analyzed)를 발행한다. FastAPI 서버의 EventBus가 이 이벤트를 수신하여 해당 세션의 WebSocket 연결을 통해 프론트엔드에 실시간 알림을 전달한다. 이 메커니즘은 Celery 워커와 FastAPI 서버 간의 직접적인 동기 호출 없이, Redis를 중간 메시지 브로커로 활용하는 완전한 이벤트 기반 비동기 통신 패턴을 구현한다.

### 3.2.6 Data Layer — PostgreSQL + pgvector + Redis

데이터 계층은 관계형 데이터 영속성, 벡터 임베딩 저장, 세션 상태 캐싱, 이벤트 메시징의 네 가지 기능을 PostgreSQL과 Redis의 두 데이터 저장소가 분담하여 처리한다.

**PostgreSQL (+ pgvector 확장):** 주 관계형 데이터베이스로서 사용자 계정 정보(Users), 채용공고(JobPostings), 면접 세션(InterviewSessions), 답변 평가 결과(EvaluationResults), 이력서 메타데이터(Resumes)의 영속적 저장을 담당한다. pgvector 확장을 통해 nomic-embed-text 모델이 생성한 768차원의 이력서 임베딩 벡터를 직접 저장하고, 코사인 유사도(Cosine Similarity) 기반의 근사 최근접 이웃(Approximate Nearest Neighbor, ANN) 검색을 수행한다. SQLAlchemy ORM을 통한 데이터 접근 계층이 구현되어 있으며, 연결 풀링(Connection Pooling)을 통해 동시 데이터베이스 연결을 효율적으로 관리한다.

**Redis:** Redis는 네 가지 독립적인 용도로 활용된다. 첫째, Celery 브로커(Broker) 및 결과 백엔드(Result Backend)로서 태스크 큐 메시지 및 실행 결과를 저장한다. 둘째, EventBus의 Pub/Sub 채널로서 Celery 워커와 FastAPI 서버 간의 이벤트 메시징을 담당한다. 채널 네이밍은 `interview_events:{event_type}`의 패턴을 따르며, 30종 이상의 이벤트 타입이 관리된다. 셋째, RAG 검색 결과 캐시(TTL: 30분)로서 반복적인 임베딩 조회의 GPU 부하를 절감한다. 넷째, 세션 데이터의 임시 저장소로서 면접 진행 중의 상태 정보를 고속 메모리 저장소에서 관리하여 데이터베이스 부하를 경감한다.

**데이터 보안:** PostgreSQL에 저장되는 사용자 비밀번호는 bcrypt(rounds=12)로 단방향 해싱되어 저장된다. 업로드된 파일(이력서, 녹화 파일, PDF 리포트)은 AES-256-GCM으로 암호화되어 파일 시스템에 저장되며, 데이터베이스에는 암호화된 파일 경로만 기록된다.

---

## 3.3 핵심 아키텍처 패턴

### 3.3.1 LangGraph 면접 상태머신 (10 Phase, 조건부 분기)

LangGraph 상태머신은 본 시스템에서 가장 핵심적인 아키텍처 패턴으로, 복잡한 면접 대화 흐름을 수학적으로 엄밀한 유한 상태 기계(FSM)로 모델링하여 결정론적이고 추적 가능한 면접 진행을 보장한다.

**그래프 구조 설계:** LangGraph의 StateGraph 인터페이스를 사용하여 10개의 노드(Node)와 이벤트 조건에 따라 분기하는 엣지(Edge)로 구성된 유향 그래프(Directed Graph)가 정의된다. 각 노드는 InterviewNodes 클래스의 메서드(greeting, process_answer, evaluate, route_next, generate_question, follow_up, complete, error_recovery)로 구현되며, 순수 함수(Pure Function) 또는 코루틴(Coroutine)의 형태로 WorkflowState를 수신하여 갱신된 상태를 반환한다.

**조건부 엣지(Conditional Edge):** `add_conditional_edges()` API를 통해 정의된 조건부 분기는 route_after_evaluate와 route_after_route_next의 두 라우팅 함수를 통해 구현된다. route_after_route_next 함수는 (1) question_count가 max_questions(기본 10)에 도달하면 complete 노드로, (2) needs_follow_up이 True이면 follow_up 노드로, (3) 그 외에는 generate_question 노드로 전이하는 세 갈래의 조건 분기를 수행한다. 이 분기 결정에 emotion_adaptive_mode가 영향을 미치며, 격려 모드에서는 꼬리질문 분기가 억제되어 더 우호적인 면접 환경이 조성된다.

**체크포인트(Checkpoint) 메커니즘:** MemorySaver를 활용한 체크포인트 기능이 활성화되어, 각 노드 실행 후의 WorkflowState가 자동으로 스냅샷(Snapshot)으로 저장된다. 세션 중단 후 재개 시, 마지막 체크포인트에서 워크플로우를 재시작할 수 있어 면접의 연속성을 보장한다. 체크포인트는 세션 ID를 키로 인메모리(In-memory) 딕셔너리에 저장된다.

**병렬 처리:** evaluate 노드에서는 `asyncio.gather()`를 사용하여 답변 평가 태스크 오프로딩(_run_evaluation), DeepFace 감정 결과 수집(_run_emotion), Hume Prosody 결과 수집(_run_prosody)의 세 비동기 작업이 병렬로 실행된다. RAG 컨텍스트 사전 조회는 이들보다 먼저 직렬로 실행되어 Ollama 임베딩 모델과 LLM의 GPU 동시 사용으로 인한 경합을 방지한다.

**감사 추적(Audit Trail):** 각 노드 실행 시 `_trace_entry()` 함수를 통해 노드 이름, 타임스탬프, 실행 시간(밀리초), 주요 판단 근거가 trace 리스트에 누적된다. 면접 종료 후 이 trace 데이터를 통해 전체 면접의 진행 과정과 각 결정의 근거를 사후에 완전히 재현하고 검증할 수 있는 감사 추적(Audit Trail) 기능이 제공된다.

### 3.3.2 이벤트 기반 아키텍처 (EventBus — Redis Pub/Sub + WebSocket)

이벤트 기반 아키텍처는 시스템의 다수 비동기 서비스 간의 느슨한 결합을 유지하면서도 일관된 상태 전파를 보장하는 핵심 설계 패턴이다.

**EventBus 싱글톤 구조:** EventBus 클래스는 스레드 안전한 싱글톤(Thread-safe Singleton) 패턴으로 구현되어, 시스템 전체에서 단 하나의 인스턴스가 존재한다. 내부적으로 이벤트 타입별 핸들러 레지스트리(EventType → [handler, ...])와 글로벌 핸들러 목록, Redis Pub/Sub 연결, WebSocket 연결 관리 맵(session_id → {websocket connections})을 관리한다.

**이벤트 발행 3단계 전파:** `publish()` 비동기 메서드를 통해 이벤트가 발행되면, 세 단계의 전파가 순차적으로 수행된다. 첫째, 로컬 핸들러 디스패치: 같은 프로세스 내에 등록된 이벤트 핸들러가 즉시 실행된다. 둘째, Redis Pub/Sub 전파: `interview_events:{event_type}` 채널에 이벤트 JSON을 발행하여 Celery 워커 등 다른 프로세스에 전파한다. 셋째, WebSocket 브로드캐스트: 해당 세션의 모든 WebSocket 연결에 이벤트 페이로드를 전송하여 프론트엔드에 실시간 알림을 전달한다.

**Self-echo 방지:** Redis Pub/Sub 특성상 발행자 프로세스도 자신이 발행한 메시지를 수신하게 되는 self-echo 문제가 발생한다. 이를 방지하기 위해 `_published_event_ids` 집합(Set)에 자신이 발행한 이벤트의 UUID를 기록하고, Redis에서 수신한 메시지 중 자신의 이벤트 ID와 일치하는 것은 무시한다.

**Celery 워커 동기 발행:** Celery 워커는 동기(Synchronous) 컨텍스트에서 실행되므로 비동기 `publish()` 메서드를 직접 호출할 수 없다. 이를 위해 동기 이벤트 발행 전용 `_publish_event()` 헬퍼 함수가 구현되어, 동기 Redis 클라이언트를 통해 직접 Pub/Sub 채널에 발행하는 방식을 사용한다.

**30종 이상의 이벤트 타입:** 시스템에서 관리되는 이벤트 타입은 `events.py`의 EventType 열거형에 정의되며, 세션 라이프사이클(SESSION_CREATED, SESSION_STARTED, SESSION_ENDED), 면접 진행(QUESTION_GENERATED, ANSWER_RECEIVED, EVALUATION_COMPLETED), AI 처리(EMOTION_ANALYZED, PROSODY_ANALYZED, STT_RESULT, TTS_READY), 데이터 처리(RESUME_PROCESSED, REPORT_GENERATED, PDF_READY), 시스템 상태(SYSTEM_ERROR, CELERY_TASK_COMPLETED) 등 30개 이상의 타입을 포함한다.

### 3.3.3 Graceful Degradation (점진적 성능 저하)

점진적 성능 저하 패턴은 본 시스템의 모든 계층에 걸쳐 일관되게 적용되는 방어적 설계 원칙으로, 부분적 장애가 전체 서비스 중단으로 이어지지 않도록 보장한다.

**계층별 폴백 체계:** AI 서비스 계층에서 STT가 실패할 경우 Whisper 로컬 모델로 자동 전환되며, LLM이 타임아웃될 경우 사전 정의된 폴백 질문이 즉시 반환된다. AES 암호화 라이브러리 오류 시 암호화 없이 원본 파일을 저장하여 서비스의 핵심 기능(면접 진행)이 유지된다.

인프라 계층에서 Redis 연결 실패 시 EventBus가 로컬 핸들러만 동작하는 인프로세스 모드로 전환된다. Celery 워커 장애 시 평가 작업이 deferred 마크와 함께 세션에 저장되었다가 면접 종료 후 일괄 처리된다.

**폴백 평가 데이터:** `_default_evaluation()` 함수는 모든 평가 점수를 중간값(3.0)으로 설정하고 `fallback: True` 플래그를 포함하는 기본 평가 결과를 반환한다. 이 폴백 결과는 실제 LLM 평가 실패 시에도 리포트 생성 파이프라인이 계속 진행될 수 있도록 하여, 면접 전체의 완결성(Completeness)을 유지한다.

---

## 3.4 배포 아키텍처 (Docker Compose + NGINX)

### 3.4.1 컨테이너화 설계

본 시스템은 Docker를 통한 컨테이너화(Containerization) 배포를 기본 전략으로 채택하여, 개발 환경과 프로덕션 환경의 일관성(Environmental Consistency)을 보장하고 의존성 충돌 문제를 원천 차단한다.

**FastAPI 백엔드 컨테이너(Dockerfile):** 기반 이미지는 Python 3.11-slim으로, 용량을 최소화하면서도 모든 필수 시스템 의존성을 포함한다. 주요 시스템 패키지로는 psycopg2 빌드를 위한 gcc와 libpq-dev, 미디어 처리를 위한 ffmpeg, 실시간 오디오 처리를 위한 portaudio19-dev가 설치된다. Docker 가이드라인에 따라 requirements.txt를 먼저 복사하여 pip install을 수행한 후 소스 코드를 복사함으로써, 소스 코드 변경 시 의존성 레이어를 재빌드하지 않아도 되는 레이어 캐싱(Layer Caching) 최적화가 적용된다. 헬스 체크는 `/health` 엔드포인트를 30초 간격으로 호출하며, 3회 연속 실패 시 컨테이너가 비정상으로 판정된다.

**Next.js 프론트엔드 컨테이너:** Node.js 기반의 Next.js 애플리케이션이 컨테이너화되어 포트 3000에서 서빙된다.

**NGINX 컨테이너:** `nginx.conf` 설정 파일과 SSL 인증서가 마운트되어 포트 80 및 443에서 리버스 프록시로 동작한다.

**Celery 워커 컨테이너:** FastAPI 백엔드와 동일한 이미지를 기반으로, 진입점(Entrypoint)만 `celery -A celery_app worker`로 변경하여 실행한다. 별도의 컨테이너로 분리됨으로써 워커 프로세스의 독립적 확장과 재시작이 가능하다.

### 3.4.2 Docker Compose 서비스 구성

Docker Compose를 통해 정의된 서비스 의존성은 다음의 순서로 기동된다. Redis 및 PostgreSQL이 먼저 기동되어 인프라가 준비된 후, FastAPI 백엔드와 Celery 워커가 기동되고, 마지막으로 Next.js 프론트엔드와 NGINX가 기동된다. 각 서비스 간에는 depends_on과 healthcheck 조건을 통한 순서 제어가 적용되어, 의존 서비스가 완전히 준비된 후에만 후속 서비스가 기동되는 안정적인 초기화 순서를 보장한다.

내부 서비스 통신은 Docker 내부 네트워크(bridge network)를 통해 이루어지며, 서비스 이름(fastapi, nextjs, redis, postgres)을 DNS 호스트명으로 활용한다. 외부에 노출되는 포트는 NGINX의 80번과 443번뿐이며, 내부 서비스 포트(8000, 3000, 6379, 5432)는 외부에서 직접 접근 불가능하다.

### 3.4.3 로컬 개발 환경 (start_all.ps1)

Windows 환경의 로컬 개발을 위해 `start_all.ps1` PowerShell 스크립트가 제공된다. 이 스크립트는 Redis, PostgreSQL, Ollama(LLM 서빙), FastAPI 서버, Celery 워커, Next.js 개발 서버를 순서에 맞게 기동하며, 각 서비스의 의존성 체크와 건강 상태 확인을 자동으로 수행한다.

---

## 3.5 아키텍처 설계 타당성 검토

### 3.5.1 설계 결정 근거

**계층형 아키텍처 채택 이유:** 계층형 아키텍처는 각 계층의 책임이 명확히 분리되어 유지보수성(Maintainability)과 테스트 용이성(Testability)이 뛰어나다. 특히 Presentation 계층(Next.js)과 Application 계층(FastAPI)의 분리는 프론트엔드와 백엔드의 독립적 개발 및 배포를 가능케 하며, NGINX API Gateway를 중간에 배치함으로써 보안 정책과 라우팅 로직을 중앙화하여 일관성을 확보한다.

**이벤트 기반 패턴 도입 이유:** 실시간 AI 처리라는 특성상, 각 AI 서비스(STT, TTS, DeepFace, Hume, LLM)의 처리 시간이 가변적이고 일부는 외부 API 호출에 의존한다. 이벤트 기반 아키텍처는 이러한 비동기적 처리 결과를 시스템 전체에 전파하는 데 있어 폴링(Polling) 방식 대비 실시간성이 높고 서버 부하가 낮다. 또한 서비스 추가 및 제거 시 기존 서비스를 변경하지 않고 이벤트 구독만 조정하면 되는 개방-폐쇄 원칙(Open-Closed Principle)에 부합하는 확장 구조를 제공한다.

**LangGraph 선택 이유:** 전통적인 조건문 기반 면접 흐름 제어는 상태 수가 증가할수록 코드 복잡도가 지수적으로 증가하는 문제를 갖는다. LangGraph는 상태머신의 각 노드를 독립적인 함수로 정의하고 그래프 구조로 연결함으로써, 새로운 Phase 추가나 분기 조건 변경이 전체 코드를 수정하지 않고 로컬 변경(Local Change)으로 처리 가능하다. 체크포인트 기능, 감사 추적(Audit Trail), 시각화(Mermaid 다이어그램 자동 생성) 등 면접 시스템에 직접 활용 가능한 부가 기능도 선택의 근거가 되었다.

### 3.5.2 기술적 트레이드오프

**단일 모노리스 vs. 마이크로서비스:** 본 시스템은 FastAPI 단일 서버에 다수의 기능(REST API, WebSocket, WebRTC 시그널링, AI 파이프라인 오케스트레이션)을 통합한 모노리스(Monolith) 구조에 가깝다. 이 구조는 배포 단순성, 서비스 간 통신 오버헤드의 부재, 개발 초기의 생산성 측면에서 유리하다. 다만 특정 기능의 독립적 확장이 어렵다는 단점이 있으며, 향후 트래픽이 증가하면 WebRTC 처리, LLM 오케스트레이션, API 서빙의 세 영역으로 분리하는 마이크로서비스화를 고려할 수 있다.

**로컬 LLM vs. 클라우드 LLM:** EXAONE, Qwen3-Coder 등 로컬 LLM을 Ollama를 통해 자체 서빙하는 방식은 데이터의 외부 유출 없이 이력서 등 민감 정보를 LLM에 직접 주입할 수 있고, API 비용이 발생하지 않는 장점이 있다. 반면 GTX 1660(VRAM 6GB)의 제한된 GPU 메모리 환경에서 복수 LLM 동시 호출이 어렵고, 클라우드 LLM 대비 처리 속도가 낮을 수 있다. 이를 보완하기 위해 ThreadPoolExecutor 병렬화 제한, RAG 캐싱, LLM 타임아웃 및 폴백 전략이 도입되었다.

---

본 장에서 기술된 6계층 아키텍처, LangGraph 상태머신, 이벤트 기반 아키텍처, Docker Compose 배포 구조는 2장의 요구사항을 기술적으로 실현하는 구조적 결정의 집합이다. 특히 SLA 1.5초(REQ-N-001)와 Graceful Degradation(REQ-N-006) 요구사항이 아키텍처 전체에 걸쳐 관통하는 설계 제약으로 작용하여, 비동기 처리 분리, 폴백 체계, 이벤트 기반 통신이라는 세 가지 핵심 아키텍처 결정을 필연적으로 도출하였음을 확인할 수 있다. 4장 이하에서는 이 아키텍처를 구현하는 데 사용된 구체적 기술 스택과, 각 핵심 기능의 설계·구현 세부사항을 상세히 기술한다.
