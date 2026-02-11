# 프로젝트 페르소나 및 규칙

## 기술 스택 및 아키텍처 (Tech Stack & Architecture)

본 프로젝트는 **계층형 아키텍처(Layered Architecture)**를 따르며, 각 레이어별 역할과 기술 스택은 다음과 같습니다. 코드를 생성하거나 수정할 때 반드시 해당 레이어의 기술 스택을 준수하십시오.

### Presentation Layer (Frontend)
- **Candidate App**: React, Next.js, WebRTC API
- **Recruiter Dashboard**: React, Recharts (통계 및 리포트 시각화)
- **Guideline**: 모든 UI 컴포넌트는 재사용성을 고려하여 작성하고, 시각화는 Recharts를 활용함.

### Application & Gateway Layer (Backend)
- **Gateway**: NGINX / Traefik (라우팅 및 로드 밸런싱)
- **Core API**: FastAPI (Python) - 비즈니스 로직 및 세션 관리
- **Signaling Server**: FastAPI WebSockets (WebRTC 연결 수립)
- **Guideline**: Python 코드는 FastAPI의 비동기(`async/await`) 패턴을 기본으로 하며, Pydantic을 이용해 엄격한 스키마 검증을 수행함.

### AI & Real-time Processing Layer
- **Media Server**: Python (aiortc/GStreamer) - 스트림 수신 및 녹화
- **AI Services**: 
  - **STT**: Deepgram / Whisper
  - **LLM**: LangChain, LangGraph (RAG 기반 대화 제어)
  - **Emotion**: DeepFace, Hume AI (감정 분석)
- **Guideline**: AI 로직은 LangChain/LangGraph의 흐름에 맞춰 작성하고, 실시간성 유지를 위해 최적화된 로직을 우선함.

### Data & Async Layer
- **Databases**: PostgreSQL + pgvector (Vector DB)
- **Cache/Broker**: Redis (세션 및 메시지 브로커)
- **Storage**: GCP Object Storage
- **Task Queue**: Celery (비동기 리포트 생성 및 인코딩)
- **Guideline**: 데이터베이스 쿼리는 PostgreSQL 문법을 준수하며, 벡터 검색은 RAG 패턴을 활용함. 비동기 작업은 Celery 워커로 위임함.

## 응답 가이드 (Response Guide)
- 코드를 수정할 때는 변경된 부분뿐만 아니라 전체 컨텍스트를 이해할 수 있도록 주석을 달아줘.
- 한국어로 설명하되, 기술 용어는 영어로 병기해줘.
- 주석은 최대한 자세히 작성해서 초보자도 이해하기 쉽도록 해줘.

## 필수 참조 문서 (Mandatory Documents)
모든 코드 생성은 반드시 CSH\documents에 있는 다음 문서들을 기준으로 합니다:
1. `소프트웨어 아키텍처 설계서 (SAD).md`: 전체 시스템 구조 가이드를 준수할 것.
2. `시스템 요구사항 명세서 (SRS).md`: 정의된 기능적/비기능적 요구사항 및 제약 사항을 엄격히 따를 것.

## 코딩 원칙
- 코드를 작성하기 전, 해당 기능이 `시스템 요구사항 명세서 (SRS).md`의 어느 항목에 해당하는지 먼저 확인하고 관련 로직을 설계해줘.
- 아키텍처 패턴은 `소프트웨어 아키텍처 설계서 (SAD).md`에 정의된 구조를 벗어나지 마.
- 만약 구현하려는 내용이 두 문서의 내용과 충돌할 경우, 나에게 먼저 질문하고 확인을 받아.
