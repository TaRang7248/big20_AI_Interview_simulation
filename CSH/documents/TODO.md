
## 📋 CSH/docs 설계서 vs 실제 구현 점검 결과

---

### 소프트웨어 아키텍처 설계서 (SAD) 대비

| # | SAD 설계 항목 | 설계 기술 | 실제 구현 | 판정 |
|---|---|---|---|---|
| 1 | 이벤트 기반 마이크로서비스 | FastAPI 마이크로서비스 | FastAPI 사용하지만 **단일 모놀리스** (4965줄) | 🟡 부분 |
| 2 | 프론트엔드 | React, Next.js, Recharts | 순수 **Vanilla HTML/CSS/JS** | ❌ 불일치 |
| 3 | API Gateway | NGINX / Traefik | **없음** — FastAPI 직접 서빙 | ❌ 미구현 |
| 4 | WebSocket 시그널링 + WebRTC | FastAPI WebSockets + SDP/ICE | SDP offer/answer + 오디오/비디오 트랙 수신 ✔ | ✅ 구현 |
| 5 | 미디어 서버 | aiortc / GStreamer | aiortc만 사용, **녹화·트랜스코딩 없음** | 🟡 부분 |
| 6 | STT | Deepgram / Whisper 이중 엔진 | **Deepgram만** 사용 (Whisper 미구현) | 🟡 부분 |
| 7 | LLM 오케스트레이션 | LangChain + LangGraph | LangChain ✔, **LangGraph 미구현** (주석 처리) | 🟡 부분 |
| 8 | 감정 분석 엔진 | DeepFace + Hume AI | DeepFace ✔, **Hume는 TTS 전용** (감정분석 아님) | 🟡 부분 |
| 9 | 비동기 태스크 큐 | Celery | 6개 큐, 14개 태스크, Beat 스케줄 ✔ | ✅ 구현 |
| 10 | 관계형 DB | **Oracle** | **PostgreSQL**로 대체 | ❌ 불일치 |
| 11 | 벡터 DB | Pinecone / pgvector | **pgvector만** 사용 (Pinecone 없음) | 🟡 부분 |
| 12 | 캐시/브로커 | Redis | Redis ✔ (Celery 브로커 + 세션 + TimeSeries) | ✅ 구현 |
| 13 | 객체 저장소 | GCP Cloud Storage | **없음** — 로컬 파일시스템 | ❌ 미구현 |
| 14 | SFU 아키텍처 | 서버 사이드 미디어 포킹 | 오디오→STT, 비디오→DeepFace 포크 ✔, **다자간 포워딩 없음** | 🟡 부분 |
| 15 | 비동기 파이프라인 태스크 | 리포트·비디오 인코딩·배치 | 리포트·배치 ✔, **비디오 인코딩 없음** | ✅ 구현 |

---

### 시스템 요구사항 명세서 (SRS) 대비

| ID | 요구사항 | 실제 구현 | 판정 | 핵심 근거 |
|---|---|---|---|---|
| **F-001** | 적응형 질문 생성 (꼬리 질문 + RAG) | `AIInterviewer.generate_response()` — 토픽당 최대 2회 꼬리질문, RAG 컨텍스트 주입, 대화 메모리 | ✅ 구현 | LangChain Memory + ResumeRAG 연동 |
| **F-002** | 멀티모달 인터랙션 (비언어적 지표) | 음성·화상·텍스트·코딩·화이트보드 ✔, DeepFace 7종 감정 ✔ | 🟡 부분 | **감정 결과가 면접 흐름에 피드백 안 됨** (저장·표시만). 자신감/당황 등 복합 지표 미추출 |
| **F-003** | 실시간 개입 (VAD + Turn-taking) | `InterviewInterventionManager` — 침묵·길이·시간·주제이탈 5가지 개입 | ✅ 구현 | `/api/intervention/` API, 프론트엔드 연동 |
| **F-004** | 라이브 코딩 (샌드박스 + AI 분석) | Python/JS/Java/C/C++ 실행 ✔, LLM 코드 분석 ✔, Monaco Editor ✔ | 🟡 부분 | **테스트케이스 자동 채점 없음** (LLM 의견만), 샌드박스가 모듈차단 수준 (컨테이너 격리 아님) |
| **F-005** | 시스템 설계 화이트보드 | `DiagramAnalyzer` (Claude → Qwen3-VL 폴백), `ArchitectureProblemGenerator` | ✅ 구현 | 비전 AI 다이어그램 인식, 4차원 평가 |
| **F-006** | 상세 피드백 리포트 (STAR + 발화속도 + 시선) | STAR 분석 ✔, 키워드 추출 ✔, 등급 산출 ✔ | 🟡 부분 | **speech_rate, pronunciation_clarity, gaze tracking 미구현** — 필드는 존재하나 측정 로직 없음. PDF 내보내기 없음 |
| **F-007** | 채용 적합도 스코어링 (루브릭 1-5점) | 5개 역량 × 1-5점 = 25점, 등급(S/A/B/C/D), LLM 합불 판정 | 🟡 부분 | **루브릭 정의가 프롬프트에 하드코딩** — 기업별/직무별 커스터마이징 불가 |
| **N-001** | 초저지연 (1.5초 이내) | ThreadPoolExecutor 병렬 ✔, Celery 오프로딩 ✔ | 🟡 부분 | **지연 시간 측정·모니터링 없음**, 1.5초 SLA 검증 불가 |
| **N-002** | 동시 접속 / 수평 확장 (K8s) | docker-compose에 DB만 포함 | ❌ 미구현 | Dockerfile·K8s manifest·HPA 없음 |
| **N-003** | 생체 데이터 보호 (TLS/AES) | SHA-256 비밀번호 해싱만 존재 | ❌ 미구현 | TLS 없음, AES 없음, 무인증 API, 데이터 삭제 없음 |
| **N-004** | 공정성 / 편향 방지 | 없음 | ❌ 미구현 | 편향 검증·설명가능성·감사 로깅 없음 |

---

### 📊 종합 대시보드

| 판정 | SAD (15개) | SRS (11개) | **합계 (26개)** |
|---|:-:|:-:|:-:|
| ✅ 구현 완료 | 4 | 3 | **7 (27%)** |
| 🟡 부분 구현 | 7 | 5 | **12 (46%)** |
| ❌ 미구현/불일치 | 4 | 3 | **7 (27%)** |

---

### 🔴 우선순위별 Gap 정리

| 우선순위 | 항목 | 설명 |
|---|---|---|
| 🔴 **Major** | SAD-2 프론트엔드 | 설계서(React/Next.js) vs 실제(Vanilla HTML) 완전 불일치 |
| 🔴 **Major** | SAD-3 API Gateway | NGINX/Traefik/SSL 없음 |
| 🟠 **High** | REQ-N-002 확장성 | Dockerfile·K8s 없음, 수평 확장 불가 |
| 🟠 **High** | REQ-F-006 리포트 | 발화속도·시선추적·PDF 미구현 |
| 🟡 **Medium** | SAD-10 Oracle→PostgreSQL | 의도적 변경 가능, 설계서 업데이트 필요 |
| 🟡 **Medium** | SAD-6 Whisper STT | Deepgram만 구현, 오프라인 폴백 없음 |
| 🟡 **Medium** | SAD-7 LangGraph | 워크플로우 상태머신 미구현 |
| 🟢 **Low** | REQ-F-002 감정 피드백 | 감정 데이터는 수집되나 면접 흐름 피드백 미연동 |
| 🟢 **Low** | REQ-N-004 공정성 | 학술 프로젝트 단계에서는 후순위 |

> **총평**: 핵심 기능(면접 엔진, 코딩 테스트, 화이트보드, 평가)은 **모두 동작 수준으로 구현**되어 있습니다. 주요 Gap은 인프라/보안/프론트엔드 기술 스택 등 **비기능적 영역**에 집중되어 있으며, 이는 프로토타입→프로덕션 전환 시 해결할 항목입니다. DB 엔진(Oracle→PostgreSQL) 등 의도적 변경 사항은 설계서를 현행화하는 것을 권장합니다.