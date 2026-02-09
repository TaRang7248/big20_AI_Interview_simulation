# 소프트웨어 아키텍처 설계서 (SAD)

프로젝트의 아키텍처는 고성능 실시간 처리를 위한 이벤트** **기반** **

마이크로서비스**(Event-Driven Microservices)** 패턴을 채택합니다. 파이썬의 비동기 처리 능력을 극대화하기 위해 FastAPI를 핵심 프레임워크로 사용하며, 무거운 AI 연산은 별도의 워커(Worker)로 분리하여 처리합니다. 

## 시스템 논리 아키텍처 (Logical Architecture)

시스템은 크게 클라이언트(Frontend), API 게이트웨이, 실시간 통신 서버, AI 처리 서비스, 데이터 스토리지로 구성됩니다. 

| 계층 (Layer) | 구성 요소 (Component) | 기술 스택 (Tech  Stack) | 역할 및 책임 |
| --- | --- | --- | --- |
| Presentation | Candidate App | React, Next.js,  WebRTC API | 면접 진행,  영상/음성 캡처, IDE 제공 |
|  | Recruiter Dashboard | React, Recharts | 지원자 관리, 리포트 조회, 통계 시각화 |
| Gateway | API Gateway | NGINX / Traefik | 로드 밸런싱, SSL 종단, 라우팅 |
| Application | Core API Service | FastAPI (Python) | 사용자 인증, 세션 관리, 비즈니스 로직 |
|  | Signaling Server | FastAPI  (WebSockets) | WebRTC 연결 수립  (SDP/ICE 교환) |
| Real-time | Media Server | Python (aiortc or GStreamer) | 미디어 스트림 수신,  분기(Splitting),  녹화 |
| AI Services | STT Service | Deepgram SDK / Whisper | 실시간 음성 인식 |
|  | LLM Orchestrator | LangChain, LangGraph | 대화 흐름 제어, 질문 생성, 답변 |
|  |  |  | 평가 |
|  | Emotion Engine | DeepFace, Hume AI | 표정 및 음성 감정 분석 |
| Async Tasks | Task Queue | Celery | 리포트 생성, 비디오 인코딩, 배치 분석 |
| Data | Main DB | Oracle | 사용자 정보, 면접 기록, 루브릭 데이터 |
|  | Vector DB | Pinecone / pgvector | 질문 임베딩, RAG용 지식 베이스 |
|  | Cache/Broker | Redis | 세션 상태 저장, 메시지 브로커 |
|  | Object Storage | Google Cloud Platform(GCP) | 녹화 영상, 로그 파일 저장 |

## 상세 기술 선정 및 근거 (Technology Rationale)

웹** **프레임워크**: ****FastAPI**** vs Django **본 프로젝트에서는 **FastAPI**를 선정합니다. 

비동기** **처리**(Asynchronous I/O):** WebRTC 시그널링과 수많은 AI API 호출(OpenAI, Deepgram 등)은 I/O 바운드 작업입니다. FastAPI는 Python의 asyncio를 네이티브로 지원하여, Django(WSGI 기반) 대비 높은 동시성 처리 성능을 보장합니다. 

데이터** **검증**:** Pydantic을 이용한 강력한 타입 힌팅과 유효성 검사는 복잡한 AI 모델의 입출력 데이터(JSON)를 안정적으로 처리하는 데 필수적입니다. 

**AI **친화성**:** 파이썬 기반의 AI 라이브러리(PyTorch, TensorFlow)와의 통합이 매끄러워, 별도의 모델 서빙 서버 없이도 경량화된 추론을 백엔드 내에서 수행하기 용이합니다. 

### 실시간 통신: WebRTC 아키텍처

브라우저 간 직접 연결(P2P) 방식보다는 **SFU(Selective Forwarding Unit)** 또는 서버 사이드 프로세싱 구조를 채택합니다. 

이유**:** AI가 면접관으로서 영상과 음성을 실시간으로 분석해야 하므로, 미디어 스트림이 서버를 거쳐야 합니다. 

구현**:** 클라이언트의 WebRTC 스트림을 서버(Python aiortc 또는 GStreamer 파이프라인)에서 수신합니다. 수신된 오디오 스트림은 STT 엔진으로, 비디오 스트림은 컴퓨터 비전 모델(DeepFace)로 분기(Forking)되어 병렬 처리됩니다. 

### 비동기 작업 처리: Celery + Redis

실시간성이 덜 중요한 작업(예: 면접 종료 후 종합 리포트 생성, 고해상도 영상 저장)은 Celery를 통해 비동기로 처리하여 API 서버의 부하를 줄입니다. Redis는 Celery의 브로커 역할뿐만 아니라, LLM의 대화 맥락(Context)을 저장하는 단기 메모리로도 활용됩니다. 

