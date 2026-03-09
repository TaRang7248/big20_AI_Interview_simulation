📋 AI 모의면접 시뮬레이션 시스템 — 보고서 목차(안)

1. 서론
   1.1 프로젝트 개요 및 배경
   1.2 프로젝트 목적 및 필요성
   1.3 프로젝트 범위 (Scope)
   1.4 용어 정의 (Glossary)

2. 시스템 요구사항 분석
   2.1 기능적 요구사항
       2.1.1 AI 면접 수행 (적응형 질문 생성, 꼬리질문, RAG 기반 맞춤화)
       2.1.2 비언어 행동 분석 (감정·시선·발화속도·Prosody)
       2.1.3 기술 역량 평가 (코딩 테스트, 시스템 설계 화이트보드)
       2.1.4 종합 평가 리포팅 (5축 언어 + 비언어 통합, 합격/불합격 판정)
       2.1.5 사용자 관리 (인증, 채용공고, 이력서 업로드)
   2.2 비기능적 요구사항
       2.2.1 응답 시간 (SLA 1.5초 이내)
       2.2.2 보안 (암호화, 인증, GDPR)
       2.2.3 확장성 및 가용성
       2.2.4 실시간성 (WebRTC, WebSocket, SSE)
   2.3 유스케이스 다이어그램

3. 시스템 아키텍처 설계
   3.1 전체 아키텍처 개요 (계층형 + 이벤트 기반)
   3.2 계층별 설계
       3.2.1 Presentation Layer — Next.js 16 프론트엔드
       3.2.2 Gateway Layer — NGINX API Gateway
       3.2.3 Application Layer — FastAPI Core API
       3.2.4 AI & Real-time Processing Layer
       3.2.5 Async Task Layer — Celery 워커 (6큐, 16태스크)
       3.2.6 Data Layer — PostgreSQL + pgvector + Redis
   3.3 핵심 아키텍처 패턴
       3.3.1 LangGraph 면접 상태머신 (10 Phase, 조건부 분기)
       3.3.2 이벤트 기반 아키텍처 (EventBus — Redis Pub/Sub + WebSocket)
       3.3.3 Graceful Degradation (점진적 성능 저하)
   3.4 배포 아키텍처 (Docker Compose, NGINX)
   3.5 시스템 아키텍처 다이어그램

4. 기술 스택
   4.1 백엔드 (Python 3.11, FastAPI, SQLAlchemy, Celery)
   4.2 프론트엔드 (Next.js 16.1.6, React 19.2.3, TypeScript, Tailwind CSS)
   4.3 AI/ML 모델
       4.3.1 LLM — EXAONE 3.5 7.8B (Ollama, 면접 질문/평가)
       4.3.2 코딩 LLM — Qwen3-Coder-30B-A3B (코드 분석)
       4.3.3 STT — Deepgram Nova-3 (실시간 한국어 음성 인식)
       4.3.4 TTS — Hume AI EVI (음성 합성)
       4.3.5 감정 분석 — DeepFace + Hume Prosody
       4.3.6 Vision — Claude 3.5 Sonnet (화이트보드)
       4.3.7 임베딩 — nomic-embed-text (RAG, 768차원)
   4.4 인프라 (Docker, NGINX, Redis, PostgreSQL, aiortc)

5. 핵심 기능 설계 및 구현
   5.1 AI 면접 흐름
       5.1.1 면접 세션 라이프사이클
       5.1.2 LangGraph 상태머신 설계 (10 Phase 전이)
       5.1.3 적응형 질문 생성 (RAG 컨텍스트 + 프롬프트 엔지니어링)
       5.1.4 SSE 기반 실시간 답변 스트리밍
       5.1.5 면접 개입 시스템 (VAD 기반 Turn-taking)
   5.2 답변 평가 시스템
       5.2.1 5축 언어 평가 (문제해결력/논리성/기술이해도/STAR/전달력)
       5.2.2 비언어 평가 (발화속도/시선추적/감정안정성/Prosody)
       5.2.3 통합 점수 산출 (언어 60% + 비언어 40%)
       5.2.4 합격/불합격 이진 판정 로직
   5.3 이력서 RAG (Retrieval-Augmented Generation)
       5.3.1 PDF 파싱 및 청킹
       5.3.2 PGVector 벡터 저장 및 유사도 검색
       5.3.3 면접 질문 맞춤화 흐름
   5.4 실시간 비언어 분석
       5.4.1 WebRTC 미디어 파이프라인 (비디오/오디오 분기)
       5.4.2 DeepFace 표정 감정 분석 (7가지, 1초 간격)
       5.4.3 발화 속도 분석 (SPM, 등급 판정)
       5.4.4 시선 추적 분석 (OpenCV, 눈 접촉 비율)
       5.4.5 Hume AI Prosody 감정 분석 (10개 지표)
   5.5 코딩 테스트
       5.5.1 다국어 코드 실행 (Python/JS/Java/C/C++, Docker 샌드박스)
       5.5.2 AI 코드 분석 (Qwen3-Coder-30B 기반)
       5.5.3 동적 문제 생성 (난이도별)
   5.6 화이트보드 시스템 설계
       5.6.1 Claude 3.5 Sonnet Vision 다이어그램 분석
       5.6.2 아키텍처 평가 기준 및 피드백
   5.7 종합 리포팅
       5.7.1 Recharts 인터랙티브 대시보드 (7종 차트)
       5.7.2 PDF 리포트 생성 (ReportLab)
       5.7.3 STAR 기법 분석 결과

6. 프론트엔드 설계 및 구현
   6.1 페이지 구성 (10개 페이지)
   6.2 컴포넌트 아키텍처 (공통/인증/리포트/감정)
   6.3 상태 관리 (AuthContext, ToastContext, EventBusContext)
   6.4 실시간 이벤트 알림 시스템 (WebSocket + Toast)
   6.5 반응형 디자인 및 접근성 (a11y)
   6.6 데이터 시각화 (Recharts + Chart.js)

7. 보안 설계 및 구현
   7.1 인증·인가 (bcrypt, JWT HS256, 소셜 로그인)
   7.2 데이터 암호화 (AES-256-GCM, TLS)
   7.3 API 보안 (CORS, 보호 엔드포인트 16개, Rate Limiting)
   7.4 코드 실행 보안 (Docker 샌드박스, 타임아웃)
   7.5 개인정보 보호 (GDPR 전체 데이터 삭제)
   7.6 종합 평가 - 5계층 Defense in Depth, 보안 설정 요약표(11개 통제)

8. 비동기 처리 및 인프라
   8.1 Celery 태스크 아키텍처 (6큐, 16태스크)
   8.2 이벤트 버스 설계 (Redis Pub/Sub, 30+ 이벤트 타입)
   8.3 미디어 녹화/트랜스코딩 (aiortc + GStreamer/FFmpeg)
   8.4 SLA 지연 시간 모니터링 (1.5초 임계값)
   8.5 Docker 컨테이너화 및 NGINX 배포

9. 테스트 및 품질 관리
   9.1 테스트 전략
   9.2 성능 테스트 결과 (STT 응답, LLM 추론 지연)
   9.3 알려진 한계 및 개선 방향

10. 프로젝트 수행 결과
    10.1 구현 완료 기능 요약
    10.2 주요 정량 지표
         - 백엔드: Python 23개 모듈, ~19,800 Lines
         - 프론트엔드: 10개 페이지, 9개 컴포넌트, 3개 Context
         - API: 100+ 엔드포인트 (REST + WebSocket + SSE)
         - AI 모델: 7종 (LLM, STT, TTS, 감정, Vision, 임베딩, 코딩)
    10.3 미구현 항목 및 향후 계획
         - D-ID AI 아바타, Kubernetes, CI/CD, Sentry/ELK

11. 결론
    11.1 프로젝트 의의 및 기대 효과
    11.2 기술적 기여
    11.3 향후 발전 방향

부록
   A. 시스템 구조도 (아키텍처 다이어그램)
   B. API 엔드포인트 전체 목록
   C. 데이터베이스 ERD
   D. 환경변수 설정 가이드 (.env.example)
   E. 변경 이력 (Changelog)
   F. 참고 문헌

### 목차 설계 근거

| 설계 원칙 | 반영 내용 |
| :--- | :--- |
| **기술 깊이** | **5장:** LangGraph 상태머신, RAG 파이프라인, 평가 수식($\text{Faithfulness}$, $\text{Relevance}$ 등) 핵심 알고리즘 상세 기술 |
| **정량 지표** | **10.2절:** 코드 라인 수, API 수, 모델 종류 등 객관적 수치 제시 |
| **아키텍처 중심** | **3장:** 독립 장으로 분리하여 계층/패턴/배포 뷰를 체계적으로 설명 |
| **보안 독립 장** | **7장:** OWASP 기준 보안 조치(암호화, 인증, GDPR)를 별도 기술 |
| **AI 모델 명세** | **4.3절:** 7종 AI 모델을 각각 분리하여 용도·버전·선정 이유 기술 |
| **프론트/백 분리** | **5장(백엔드 기능)** 및 **6장(프론트엔드)**으로 구분하여 각각의 설계 의도 설명 |