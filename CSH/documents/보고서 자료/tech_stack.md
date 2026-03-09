# 4. 기술 스택

본 장에서는 AI 모의면접 시뮬레이션 시스템의 구현에 활용된 기술 스택(Technology Stack)의 전체 구성을 체계적으로 기술한다. 기술 스택의 선정은 3장에서 정의된 6계층 아키텍처의 각 계층이 요구하는 기술적 특성과, 2장의 비기능적 요구사항(실시간 응답 1.5초 이내, 수평적 확장성, 점진적 성능 저하)을 만족하는 것을 기본 기준으로 삼았다. 본 시스템의 기술 스택은 크게 백엔드(Backend), 프론트엔드(Frontend), AI/ML 모델(AI/ML Models), 인프라(Infrastructure)의 네 영역으로 분류되며, 각 영역 내에서 채택된 기술의 선정 이유, 버전 정보, 역할, 그리고 기술 간 상호의존성을 상세히 서술한다.

---

## 4.1 백엔드 (Backend)

### 4.1.1 Python 3.11

본 시스템의 백엔드 전체는 Python 3.11을 기반으로 구현되었다. Python 3.11은 CPython 인터프리터의 Specializing Adaptive Interpreter 도입을 통해 이전 버전(3.10) 대비 평균 25%의 실행 속도 향상을 달성한 버전으로, I/O 바운드 및 CPU 바운드 작업이 혼재하는 AI 서비스 백엔드에 적합한 성능 특성을 제공한다. 또한 Exception Groups와 TaskGroups 등 향상된 비동기 프로그래밍 지원 기능이 도입되어, asyncio 기반의 비동기 요청 처리에서 예외 관리의 정밀성이 개선되었다.

Python의 선택은 LangChain, LangGraph, DeepFace, Celery 등 본 시스템의 핵심 라이브러리 생태계가 모두 Python을 주 언어로 지원하며, 특히 AI/ML 분야에서 NumPy, TensorFlow, PyTorch 등과의 원활한 상호운용성(Interoperability)을 제공한다는 점에서 불가피한 선택이었다. Docker 컨테이너 이미지는 Python 3.11-slim을 기반으로 하여 불필요한 시스템 패키지를 배제함으로써 이미지 용량을 최소화하였다.

### 4.1.2 FastAPI (≥ 0.104.0)

FastAPI는 본 시스템의 Application Layer(제3계층)를 구성하는 핵심 웹 프레임워크이다. Starlette 기반의 ASGI(Asynchronous Server Gateway Interface) 프레임워크로서, 동기·비동기(async/await) 처리를 모두 지원하며, Pydantic v2(≥ 2.0.0) 기반의 요청/응답 데이터 검증 및 자동 직렬화를 제공한다.

FastAPI를 선택한 핵심 이유는 다음과 같다. 첫째, REST API, WebSocket, SSE(Server-Sent Events)의 세 가지 엔드포인트 유형을 단일 프레임워크 내에서 통합적으로 지원한다. 본 시스템은 100개 이상의 REST 엔드포인트, WebSocket 기반 실시간 이벤트 통신, SSE 기반 LLM 토큰 스트리밍을 동시에 서빙해야 하므로, 이 세 프로토콜의 통합 지원은 아키텍처적으로 필수적이다. 둘째, Depends() 의존성 주입(Dependency Injection) 시스템을 통해 JWT 인증, 데이터베이스 세션 관리, Rate Limiting 등의 횡단 관심사(Cross-cutting Concern)를 선언적으로 처리할 수 있어, 보안 로직의 누락 없이 일관된 적용이 가능하다. 셋째, OpenAPI(Swagger) 문서 자동 생성 기능을 통해 프론트엔드 개발팀과의 API 계약(API Contract)이 자동으로 동기화된다.

서빙 런타임으로는 uvicorn(≥ 0.24.0)이 사용되며, 프로덕션 환경에서는 --workers 2 옵션으로 멀티 프로세스 모드가 적용된다. python-multipart(≥ 0.0.6) 패키지는 이력서 PDF 파일 업로드 시 multipart/form-data 파싱을 담당한다.

### 4.1.3 SQLAlchemy (≥ 2.0.0)

SQLAlchemy 2.0은 PostgreSQL 데이터베이스와의 상호작용을 위한 ORM(Object-Relational Mapping) 계층을 제공한다. 2.0 버전에서 도입된 새로운 쿼리 인터페이스(select() 스타일)와 타입 힌트(Type Hint) 지원을 통해 코드의 가독성과 타입 안전성이 향상되었다. psycopg(≥ 3.1.0, psycopg3 드라이버)를 데이터베이스 어댑터로 사용하며, 연결 문자열 포맷은 postgresql+psycopg://로 최신 psycopg3 비동기 드라이버를 활용한다. 연결 풀링(Connection Pooling)을 통해 동시 데이터베이스 접근의 효율성을 확보하며, SQLAlchemy의 세션 관리(Session Management)는 FastAPI의 Depends() 패턴과 결합하여 요청 단위 세션 라이프사이클이 자동으로 관리된다.

### 4.1.4 Celery (≥ 5.3.0) + Redis (≥ 5.0.0) + Kombu (≥ 5.3.0)

Celery는 분산 태스크 큐 프레임워크로서, 본 시스템의 Async Task Layer(제5계층)를 구성한다. Redis를 메시지 브로커(Broker) 및 결과 백엔드(Result Backend)로 사용하며, Kombu 메시징 라이브러리를 통해 6개의 전용 큐(llm_evaluation, emotion_analysis, report_generation, tts_generation, rag_processing, media_processing)를 정의하고 태스크 라우팅을 수행한다. JSON 직렬화, Asia/Seoul 시간대, soft_time_limit/time_limit 이중 타임아웃, task_acks_late(완료 후 ACK), worker_prefetch_multiplier=1(한 번에 하나의 태스크만 가져옴) 등의 설정이 적용된다.

선택적으로 Flower(≥ 2.0.0) 모니터링 대시보드를 통해 워커 상태, 태스크 진행 현황, 큐별 적재량을 웹 UI로 실시간 확인할 수 있다.

### 4.1.5 인증 및 보안 패키지

python-jose[cryptography](≥ 3.3.0)은 JWT(JSON Web Token) 생성 및 검증을 담당한다. HS256 알고리즘으로 액세스 토큰을 서명하며, 토큰 유효 기간은 기본 120분으로 설정된다. bcrypt(≥ 4.0.0)는 사용자 비밀번호의 단방향 해싱을 수행하며, work factor를 rounds=12로 설정하여 무차별 대입 공격에 대한 충분한 계산 비용을 부과한다. cryptography(≥ 41.0.0)는 AES-256-GCM 파일 암호화와 RSA-2048 자체 서명 SSL 인증서 생성 기능을 제공한다.

### 4.1.6 PDF 리포트 생성

ReportLab(≥ 4.0.0)은 면접 종합 평가 리포트의 PDF 생성을 담당한다. 한국어 폰트(NanumGothic 등)를 지원하며, 표, 차트, 텍스트 블록을 포함하는 다단(Multi-column) 리포트 레이아웃을 프로그래밍 방식으로 구성한다. 생성된 PDF 파일은 AES-256-GCM으로 암호화하여 파일 시스템에 저장됨으로써, 지원자의 면접 결과가 무보호 상태로 노출되지 않도록 한다.

---

## 4.2 프론트엔드 (Frontend)

### 4.2.1 Next.js 16.1.6

Next.js 16.1.6은 Presentation Layer(제1계층)를 구성하는 React 기반 풀스택(Full-stack) 웹 프레임워크이다. App Router 아키텍처를 채택하여 파일 기반 라우팅(File-based Routing), 레이아웃 중첩(Nested Layouts), 서버 컴포넌트(Server Components)와 클라이언트 컴포넌트(Client Components)의 분리를 지원한다. SSR(Server-Side Rendering)을 통해 초기 페이지 로딩 시간(Time to First Contentful Paint)을 최소화하고, 정적 자산은 NGINX에서 365일 장기 캐싱되어 반복 방문 시 즉각적인 로딩을 보장한다.

### 4.2.2 React 19.2.3

React 19.2.3은 본 시스템의 UI 컴포넌트 렌더링 엔진이다. Server Components를 통한 서버 측 데이터 페칭과 Client Components를 통한 클라이언트 측 상호작용의 명확한 분리가 가능하며, Concurrent Mode를 통해 대규모 상태 업데이트 시에도 UI 응답성이 유지된다. 전역 상태 관리는 React Context API를 통해 AuthContext(인증), ToastContext(알림), EventBusContext(실시간 이벤트)의 세 Context Provider로 구현되어, 외부 상태 관리 라이브러리(Redux 등)에 대한 의존성 없이 경량 상태 관리가 달성된다.

### 4.2.3 TypeScript (≥ 5.0)

TypeScript는 프론트엔드 코드 전체에 정적 타입 시스템을 적용하여, 컴파일 시점에서 타입 오류를 검출함으로써 런타임 에러의 발생 가능성을 현저히 줄인다. API 응답 타입의 인터페이스(Interface) 정의를 통해 백엔드와 프론트엔드 간의 데이터 계약(Data Contract)을 코드 레벨에서 강제하며, IDE(통합 개발 환경)의 자동 완성(IntelliSense) 지원을 극대화하여 개발 생산성을 향상시킨다.

### 4.2.4 Tailwind CSS (v4)

Tailwind CSS v4는 유틸리티 퍼스트(Utility-First) CSS 프레임워크로서, HTML 마크업 내에 직접 스타일 클래스를 적용하는 방식으로 사용자 인터페이스를 구성한다. 디자인 토큰(Design Token) 기반의 일관된 간격(Spacing), 색상(Color), 타이포그래피(Typography) 시스템을 통해 시각적 일관성을 보장하며, JIT(Just-in-Time) 컴파일러를 통해 사용되지 않는 CSS 클래스를 자동으로 제거하여 최종 번들 크기를 최소화한다. @tailwindcss/postcss(≥ 4) PostCSS 플러그인을 통해 빌드 파이프라인에 통합된다.

### 4.2.5 데이터 시각화 라이브러리

Recharts(≥ 3.7.0)는 면접 평가 결과의 인터랙티브 차트 시각화를 담당하는 주 시각화 라이브러리이다. React 네이티브 컴포넌트로 설계되어 선언적(Declarative) API를 통해 레이더 차트(RadarChart), 바 차트(BarChart), 영역 차트(AreaChart), 방사형 차트(RadialBarChart) 등을 구현한다. 각 차트는 마우스 오버 툴팁(Tooltip)과 범례(Legend)를 포함하는 인터랙티브 방식으로 제공되어, 지원자가 평가 데이터를 직관적으로 탐색할 수 있다.

Chart.js(≥ 4.5.1)와 react-chartjs-2(≥ 5.3.1)는 감정 분포 파이 차트 등 Recharts가 직접 지원하지 않는 특수 차트 유형에 대한 보완적 시각화 라이브러리로 활용된다. Canvas 기반 렌더링을 통해 대규모 데이터 포인트의 고성능 시각화를 제공한다.

### 4.2.6 특수 목적 프론트엔드 패키지

Monaco Editor(@monaco-editor/react ≥ 4.7.0)는 코딩 테스트 페이지에서 지원자가 코드를 작성하는 웹 기반 코드 에디터를 제공한다. Visual Studio Code와 동일한 편집 엔진을 사용하며, Python, JavaScript, Java, C, C++ 등 5개 언어에 대한 구문 강조(Syntax Highlighting), 자동 들여쓰기(Auto-Indentation), 괄호 매칭(Bracket Matching)을 지원한다. Lucide React(≥ 0.563.0)는 시스템 전반에서 사용되는 UI 아이콘 컴포넌트를 제공하며, clsx(≥ 2.1.1)는 조건부 CSS 클래스 결합 유틸리티로 활용된다.

---

## 4.3 AI/ML 모델

본 시스템은 총 7종의 AI/ML 모델을 통합 운용한다. 이 중 3종(EXAONE, Qwen3-Coder, nomic-embed-text)은 Ollama를 통해 로컬 GPU에서 자체 서빙되며, 4종(Deepgram STT, Hume AI TTS/Prosody, Claude Vision)은 외부 클라우드 API를 통해 호출된다. 로컬 모델과 클라우드 API의 하이브리드 구성은 데이터 보안(이력서 등 민감 정보의 외부 유출 방지)과 서비스 가용성(외부 API 장애 시 로컬 폴백)의 두 가지 요구사항을 동시에 만족시키기 위한 설계적 선택이다.

### 4.3.1 LLM — EXAONE 3.5 7.8B (Ollama 로컬 서빙)

EXAONE 3.5는 LG AI Research에서 개발한 한국어 특화 대규모 언어 모델로, 7.8B(78억) 파라미터 규모의 모델이 Ollama 런타임을 통해 로컬 GPU(GTX 1660, VRAM 6GB)에서 서빙된다. 본 시스템에서 EXAONE 3.5는 면접 질문 생성, 꼬리질문 생성, 답변 평가의 세 핵심 기능에 활용된다.

LangChain(≥ 0.1.0)의 ChatOllama 인터페이스를 통해 호출되며, 주요 생성 파라미터는 temperature=0.3(창의성보다 일관성 우선), num_ctx=8192(컨텍스트 윈도우 크기)으로 설정된다. 한국어 면접이라는 특수한 도메인에서 EXAONE 3.5는 GPT 계열 모델 대비 한국어 문장 생성의 자연스러움과 비용 효율성에서 우위를 보이며, 로컬 서빙을 통해 이력서 정보를 포함한 프롬프트가 외부 서버로 전송되지 않아 데이터 주권(Data Sovereignty)이 보장된다.

LLM 출력의 후처리에는 사고 토큰 제거(EXAONE Deep의 <thought> 태그 및 Qwen3의 <think> 태그 자동 제거), 복수 질문 분리(extract_single_question), 한국어 품질 가드(한글 비율 60% 이상 강제) 등의 방어적 필터가 적용된다. LLM 추론 타임아웃(LLM_TIMEOUT_SEC=60초) 초과 시 사전 정의된 폴백 질문이 반환되어 면접 흐름의 연속성이 보장된다.

### 4.3.2 코딩 LLM — Qwen3-Coder-30B-A3B (Ollama 로컬 서빙)

Qwen3-Coder-30B-A3B는 Alibaba Cloud에서 개발한 코드 특화 대규모 언어 모델로, 30B 파라미터 중 3B만 활성화되는 MoE(Mixture of Experts) 아키텍처를 채택하여 제한된 GPU 메모리 환경에서도 대규모 모델의 코드 이해력을 활용할 수 있다.

본 시스템에서 Qwen3-Coder는 두 가지 기능에 활용된다. 첫째, 코딩 테스트 문제의 동적 생성(pre_generate_coding_problem_task)으로, 지정된 난이도(easy/medium/hard)에 따라 문제 설명, 입출력 예시, 테스트 케이스를 포함하는 코딩 문제를 자동 생성한다. 둘째, 지원자가 제출한 코드에 대한 심층 AI 코드 분석으로, 알고리즘 정확성, 시간/공간 복잡도, 코드 품질, 엣지 케이스 처리에 대한 다차원적 피드백을 생성한다. Qwen3-Coder는 Python, JavaScript, Java, C, C++의 5개 프로그래밍 언어를 지원한다.

### 4.3.3 STT — Deepgram Nova-3 (클라우드 API)

Deepgram Nova-3는 실시간 한국어 음성 인식(Real-time Korean ASR)을 위한 클라우드 STT 서비스이다. deepgram-sdk(≥ 3.0.0)를 통해 WebSocket 프로토콜 기반의 실시간 스트리밍 인식이 구현되며, 중간 결과(Interim Result), 최종 결과(Final Result), 발화 종료(UtteranceEnd) 이벤트를 구분하여 반환한다. word-level confidence 점수를 제공하여 STT 결과의 신뢰도 기반 후처리가 가능하며, VAD(Voice Activity Detection) 내장 기능을 통해 면접 대화의 자연스러운 Turn-taking을 지원한다.

STT 후처리 파이프라인에서는 pykospacing 라이브러리를 통한 한국어 띄어쓰기 보정이 적용된다. 보정 정책은 STT_SPACING_MODE 환경변수를 통해 off(보정 없음), safe(low confidence 발화만 보수적 보정), full(전체 보정)의 3단계로 조절 가능하며, 기본값은 safe로 설정되어 과도한 보정으로 인한 기술 용어 왜곡을 방지한다 .

Deepgram 서비스 장애 시에는 faster-whisper(≥ 1.0.0, CTranslate2 기반 고속 로컬 STT 엔진)가 자동으로 활성화되어 오프라인 환경에서도 음성 인식 기능이 유지된다. 이 폴백 메커니즘은 REQ-N-006(Graceful Degradation)을 실현하는 대표적 사례이다.

### 4.3.4 TTS — Hume AI EVI (클라우드 API)

Hume AI EVI(Empathic Voice Interface)는 AI 면접관의 음성 합성을 담당하는 감정 인식형(Emotion-aware) TTS 서비스이다. hume(≥ 0.5.0) SDK를 통해 호출되며, 일반적인 TTS 서비스와 달리 텍스트의 감정적 맥락을 분석하여 억양, 강세, 속도를 동적으로 조절하는 감정 인식 음성 합성 기능을 제공한다. 이를 통해 AI 면접관의 질문 음성이 기계적이고 단조로운 느낌이 아닌, 자연스러운 면접관의 어조로 전달되어 지원자의 면접 몰입도를 높인다.

생성된 음성은 MP3 형식으로 서버에 로컬 저장되며, 클라이언트는 HTTP 파일 서빙 엔드포인트를 통해 수신하여 재생한다. hume_tts_service.py 모듈이 전체 TTS 파이프라인을 캡슐화한다.

### 4.3.5 감정 분석 — DeepFace + Hume Prosody (로컬 + 클라우드 하이브리드)

표정 감정 분석은 DeepFace(≥ 0.0.79) 라이브러리를 통해 로컬에서 수행된다. DeepFace는 OpenCV(≥ 4.8.0)와 tf-keras(≥ 2.15.0)를 기반으로 동작하며, VGG-Face, FaceNet, ArcFace 등 다양한 깊이 학습(Deep Learning) 모델을 백엔드로 활용한다. 본 시스템에서는 얼굴 검출(Face Detection)과 감정 분류(Emotion Classification)에 초점을 두며, 7가지 기본 감정(happy, sad, angry, surprise, fear, disgust, neutral)에 대한 확률 분포를 실시간으로 출력한다. NumPy(≥ 1.24.0)는 영상 프레임의 배열 처리 및 수치 연산에 필수적으로 활용된다.

음성 감정 분석은 Hume AI Prosody API를 통해 수행된다. 48개의 감정 차원(Emotion Dimensions) 중 면접 맥락에서 유의미한 10개 핵심 지표(자신감, 흥미, 집중, 편안함, 불안, 열정, 망설임, 명확성, 스트레스, 전반적 긍정성)가 추출되며, httpx(≥ 0.25.0) 비동기 HTTP 클라이언트를 통해 API 호출이 처리된다. aiohttp(≥ 3.9.0)도 비동기 HTTP 통신에 활용된다.

DeepFace(표정)와 Hume Prosody(음성)의 두 채널 감정 분석 결과는 50:50 가중 융합(Weighted Fusion)을 통해 최종 감정 적응 모드(normal/encouraging/challenging)로 통합된다. 이 멀티모달 융합 접근법은 단일 채널 분석 대비 감정 판별의 견고성(Robustness)을 크게 향상시킨다.

### 4.3.6 Vision — Claude 3.5 Sonnet (클라우드 API)

Anthropic Claude 3.5 Sonnet은 화이트보드 시스템 설계 평가에 활용되는 비전-언어 멀티모달(Vision-Language Multimodal) 모델이다. anthropic(≥ 0.18.0) SDK를 통해 호출되며, 지원자가 화이트보드 인터페이스에서 그린 시스템 설계 다이어그램의 캡처 이미지를 입력으로 받아, 확장성, 가용성, 데이터 일관성, 보안, 성능의 5개 차원에서 아키텍처 평가 피드백을 생성한다.

Claude 3.5 Sonnet의 시각적 이해(Visual Understanding) 능력은 손으로 그린 다이어그램에서 노드(서버, 데이터베이스, 캐시 등), 엣지(데이터 흐름, API 호출 등), 텍스트 레이블(서비스명, 프로토콜명 등)을 인식하고, 이를 시스템 설계 원칙에 기반하여 비판적으로 분석하는 수준으로 구현된다. 이는 기존 텍스트 기반 LLM으로는 불가능한, 시각적 아키텍처 도면에 대한 직접적 평가를 가능케 하는 혁신적 기능이다.

### 4.3.7 임베딩 — nomic-embed-text (Ollama 로컬 서빙)

nomic-embed-text는 이력서 RAG 파이프라인에서 텍스트 임베딩 생성을 담당하는 문장 임베딩(Sentence Embedding) 모델이다. Ollama 런타임을 통해 로컬 GPU에서 서빙되어, 이력서 텍스트가 외부로 전송되지 않는 데이터 보안을 보장한다. 768차원의 밀집 벡터(Dense Vector)를 생성하며, 검색 쿼리에 "search_query:" 접두사를 추가하여 비대칭 검색(Asymmetric Search)에 최적화된 임베딩을 생성한다.

생성된 임베딩은 pgvector(≥ 0.2.0) 확장을 통해 PostgreSQL에 직접 저장되며, 코사인 유사도 기반의 Approximate Nearest Neighbor(ANN) 검색으로 면접 질문에 관련된 이력서 컨텍스트를 실시간으로 검색한다. langchain-postgres(≥ 0.0.1) 통합을 통해 LangChain의 VectorStore 인터페이스와 원활하게 연동되며, pypdf(≥ 3.17.0)는 PDF 이력서의 텍스트 추출에, langchain-text-splitters(≥ 0.0.1)는 추출된 텍스트의 청킹(Chunking)에 활용된다.

---

## 4.4 인프라 (Infrastructure)

### 4.4.1 Docker + Docker Compose

Docker는 시스템의 모든 서비스(FastAPI, Next.js, Celery Worker, NGINX, Redis, PostgreSQL)를 컨테이너화하여 배포 환경의 일관성을 보장한다. FastAPI 컨테이너는 Python 3.11-slim 이미지를 기반으로, gcc, libpq-dev(psycopg2 빌드), ffmpeg(미디어 처리), portaudio19-dev(실시간 오디오), curl(헬스 체크) 등의 시스템 의존성이 설치된다. Docker 레이어 캐싱 최적화를 위해 requirements.txt 복사 및 pip install이 소스 코드 복사보다 선행하는 빌드 순서가 적용된다.

Docker Compose는 전체 서비스 스택의 오케스트레이션을 담당하며, depends_on 및 healthcheck 조건을 통해 서비스 기동 순서를 제어한다. 서비스 간 통신은 Docker 내부 브릿지 네트워크를 통해 이루어지며, 외부 노출 포트는 NGINX의 80번(HTTP → HTTPS 리다이렉트)과 443번(HTTPS)으로 한정된다.

### 4.4.2 NGINX

NGINX는 API Gateway(제2계층)로서, SSL/TLS 종단(TLS 1.2/1.3, OWASP 권장 암호 스위트), 라우팅(/api/** → FastAPI, /* → Next.js), 3단 Rate Limiting(일반 API 20r/s, 인증 5r/s, WebSocket 5r/s), 보안 헤더 주입(HSTS, X-Frame-Options, X-XSS-Protection 등), Gzip 압축(레벨 6, 10종 MIME 타입), 정적 자산 365일 장기 캐싱을 수행한다. 워커 프로세스 수는 auto(CPU 코어 수 자동 조절)로 설정되며, 워커당 최대 동시 연결은 1,024개이다.

### 4.4.3 Redis

Redis는 시스템 전체에서 네 가지 역할을 수행한다. 첫째, Celery 메시지 브로커 및 결과 백엔드(CELERY_BROKER_URL 환경변수)로서 비동기 태스크 큐잉을 지원한다. 둘째, EventBus의 Pub/Sub 메시징 채널(interview_events:* 패턴)로서 프로세스 간 이벤트 전파를 담당한다. 셋째, RAG 검색 결과 캐시(TTL: 30분)로서 반복적인 벡터 검색의 GPU 부하를 절감한다. 넷째, 면접 세션 상태의 고속 임시 저장소로서 활용된다.

### 4.4.4 PostgreSQL + pgvector

PostgreSQL은 주 관계형 데이터베이스로서 사용자, 채용공고, 면접 세션, 평가 결과 등의 영속 데이터를 관리한다. pgvector 확장을 통해 768차원 벡터의 네이티브 저장 및 코사인 유사도 검색을 지원하여, 별도의 벡터 데이터베이스(Pinecone, Weaviate 등) 없이 단일 데이터베이스에서 관계형 데이터와 벡터 데이터를 통합 관리한다. 이는 인프라 복잡도를 줄이면서도 RAG 파이프라인의 핵심 기능을 완전히 지원하는 실용적 설계이다.

### 4.4.5 aiortc (≥ 1.6.0)

aiortc는 Python asyncio 기반의 WebRTC 구현 라이브러리로, 본 시스템의 실시간 미디어 통신(RTC) 계층을 제공한다. SFU(Selective Forwarding Unit) 아키텍처로 동작하여 클라이언트의 비디오/오디오 스트림을 서버에서 직접 수신하고, 비디오 트랙은 DeepFace 표정 분석 및 시선 추적 파이프라인으로, 오디오 트랙은 Deepgram STT 및 Hume Prosody 파이프라인으로 분기 전달한다. DTLS(Datagram TLS) 암호화를 통한 미디어 전송 구간 보안이 자동으로 적용된다.

### 4.4.6 Ollama

Ollama는 로컬 LLM 서빙 런타임으로, EXAONE 3.5 7.8B, Qwen3-Coder-30B-A3B, nomic-embed-text의 세 로컬 모델을 GPU 가속 환경에서 서빙한다. LangChain의 langchain-ollama(≥ 0.0.1) 통합을 통해 ChatOllama 및 OllamaEmbeddings 인터페이스로 접근되며, REST API 형식(http://localhost:11434)으로 로컬 통신한다. GTX 1660(VRAM 6GB) 환경에서 복수 모델의 동시 로드로 인한 GPU 메모리 경합을 방지하기 위해, ThreadPoolExecutor(max_workers=2) 기반의 동시성 제어가 적용된다.

---

## 4.5 기술 스택 요약표

| 영역 | 기술 | 버전 | 역할 |
|------|------|------|------|
| 백엔드 | Python | 3.11 | 전체 백엔드 런타임 |
| 백엔드 | FastAPI | ≥ 0.104.0 | REST API, WebSocket, SSE 서빙 |
| 백엔드 | uvicorn | ≥ 0.24.0 | ASGI 서버 |
| 백엔드 | Pydantic | ≥ 2.0.0 | 데이터 검증 및 직렬화 |
| 백엔드 | SQLAlchemy | ≥ 2.0.0 | ORM, 데이터베이스 접근 |
| 백엔드 | psycopg | ≥ 3.1.0 | PostgreSQL 드라이버 (psycopg3) |
| 백엔드 | Celery | ≥ 5.3.0 | 분산 비동기 태스크 큐 |
| 백엔드 | Kombu | ≥ 5.3.0 | Celery 메시징 라이브러리 |
| 백엔드 | python-jose | ≥ 3.3.0 | JWT 토큰 생성/검증 |
| 백엔드 | bcrypt | ≥ 4.0.0 | 비밀번호 해싱 |
| 백엔드 | cryptography | ≥ 41.0.0 | AES-256-GCM, SSL 인증서 |
| 백엔드 | ReportLab | ≥ 4.0.0 | PDF 리포트 생성 |
| 프론트엔드 | Next.js | 16.1.6 | React 풀스택 웹 프레임워크 |
| 프론트엔드 | React | 19.2.3 | UI 컴포넌트 렌더링 |
| 프론트엔드 | TypeScript | ≥ 5.0 | 정적 타입 시스템 |
| 프론트엔드 | Tailwind CSS | v4 | 유틸리티 퍼스트 CSS |
| 프론트엔드 | Recharts | ≥ 3.7.0 | 인터랙티브 차트 시각화 |
| 프론트엔드 | Chart.js | ≥ 4.5.1 | Canvas 기반 차트 |
| 프론트엔드 | Monaco Editor | ≥ 4.7.0 | 웹 코드 에디터 (VS Code 엔진) |
| AI/ML | EXAONE 3.5 | 7.8B | 면접 질문 생성, 답변 평가 (로컬) |
| AI/ML | Qwen3-Coder | 30B-A3B (MoE) | 코딩 문제 생성, 코드 분석 (로컬) |
| AI/ML | Deepgram Nova-3 | SDK ≥ 3.0.0 | 실시간 한국어 STT (클라우드) |
| AI/ML | faster-whisper | ≥ 1.0.0 | STT 오프라인 폴백 (로컬) |
| AI/ML | Hume AI EVI | SDK ≥ 0.5.0 | 감정 인식형 TTS (클라우드) |
| AI/ML | Hume Prosody | SDK ≥ 0.5.0 | 음성 감정 분석 (클라우드) |
| AI/ML | DeepFace | ≥ 0.0.79 | 표정 감정 분석 (로컬) |
| AI/ML | Claude 3.5 Sonnet | SDK ≥ 0.18.0 | 화이트보드 다이어그램 분석 (클라우드) |
| AI/ML | nomic-embed-text | 768차원 | 이력서 RAG 임베딩 (로컬) |
| AI/ML | LangChain | ≥ 0.1.0 | LLM 오케스트레이션 프레임워크 |
| AI/ML | LangGraph | ≥ 0.2.0 | 면접 워크플로우 상태머신 |
| 인프라 | Docker | — | 컨테이너화 배포 |
| 인프라 | Docker Compose | — | 멀티 서비스 오케스트레이션 |
| 인프라 | NGINX | — | API Gateway, SSL 종단, Rate Limiting |
| 인프라 | Redis | ≥ 5.0.0 | 태스크 큐, Pub/Sub, 캐시 |
| 인프라 | PostgreSQL | — | RDBMS, pgvector 벡터 저장 |
| 인프라 | pgvector | ≥ 0.2.0 | 벡터 검색 확장 |
| 인프라 | aiortc | ≥ 1.6.0 | Python WebRTC (SFU) |
| 인프라 | Ollama | — | 로컬 LLM 서빙 런타임 |

---

본 장에서 기술된 기술 스택은 총 40개 이상의 패키지와 서비스로 구성되며, 백엔드 12개, 프론트엔드 8개, AI/ML 모델 7종(+ LangChain/LangGraph 통합 프레임워크), 인프라 8개의 구성 요소가 유기적으로 결합되어 AI 모의면접 시뮬레이션 시스템을 형성한다. 특히 로컬 모델(EXAONE, Qwen3-Coder, nomic-embed-text, DeepFace)과 클라우드 API(Deepgram, Hume, Claude)의 하이브리드 배치 전략은, 데이터 보안과 서비스 가용성이라는 상충할 수 있는 두 요구사항을 동시에 만족시키는 핵심 기술 전략이다. 5장에서는 이 기술 스택을 기반으로 구현된 핵심 기능의 설계 및 구현 세부사항을 상세히 기술한다.
