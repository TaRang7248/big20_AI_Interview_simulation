# 8. 비동기 처리 및 인프라

본 장에서는 AI 모의면접 시뮬레이션 시스템의 비동기 처리 아키텍처와 인프라 계층의 설계·구현을 상세히 기술한다. 실시간 AI 서비스를 다수 통합 운용하는 본 시스템에서, 비동기 처리와 인프라 구성은 SLA 1.5초(REQ-N-001), 확장성(REQ-N-005), 점진적 성능 저하(REQ-N-006) 요구사항을 충족하는 핵심 기술 기반이다.

---

## 8.1 Celery 태스크 아키텍처 (6큐, 16태스크)

### 8.1.1 Celery 애플리케이션 설정

Celery 분산 태스크 큐 시스템의 핵심 설정은 celery_app.py 모듈(126줄)에 정의된다. Redis를 메시지 브로커(Broker)와 결과 백엔드(Result Backend)로 동시에 사용하며, CELERY_BROKER_URL 및 CELERY_RESULT_BACKEND 환경변수를 통해 연결 문자열이 구성된다.

주요 설정 항목은 다음과 같다. 직렬화 형식은 task_serializer="json"과 result_serializer="json"으로 설정되어, 태스크 인자와 결과가 JSON 형식으로 직렬화된다. 이는 바이너리 직렬화(pickle) 대비 디버깅 용이성과 보안성(Pickle 역직렬화 공격 방지)에서 유리하다. 시간대는 timezone="Asia/Seoul"로 한국 표준시가 적용되며, enable_utc=False로 설정되어 모든 타임스탬프가 로컬 시간으로 기록된다.

worker_prefetch_multiplier=1로 설정되어, 각 워커가 한 번에 하나의 태스크만 큐에서 가져온다(Prefetch). 이 설정은 LLM 추론, 리포트 생성 등 처리 시간이 긴 태스크가 특정 워커에 편중되어 다른 태스크의 대기 시간이 증가하는 문제를 방지한다. task_acks_late=True로 설정되어, 태스크가 완료된 후에야 ACK(Acknowledgment)가 브로커에 전송된다. 이를 통해 워커가 태스크 처리 중 비정상 종료되더라도 해당 태스크가 다른 워커에 의해 재처리될 수 있는 at-least-once 전달 보장이 구현된다.

result_expires=3600(1시간)으로 설정되어, 태스크 실행 결과가 Redis에 1시간 동안 보관된 후 자동 삭제된다. 이를 통해 Redis 메모리의 무한 증가를 방지한다.

### 8.1.2 6개 전용 큐 설계

태스크는 기능적 특성에 따라 6개의 전용 큐(Queue)로 분리되어 라우팅된다. 큐별 분리의 설계 의도는 다음과 같다. 첫째, 서로 다른 리소스 프로파일(GPU 집약, I/O 집약, CPU 집약)의 태스크가 동일 큐에서 경합하는 것을 방지한다. 둘째, 특정 유형의 태스크 적체가 다른 유형의 태스크 처리에 영향을 미치지 않도록 격리한다. 셋째, 큐별 독립적인 워커 스케일링이 가능하여, 병목이 발생하는 큐에만 선택적으로 워커를 추가할 수 있다.

llm_evaluation 큐는 LLM 기반 태스크를 전담한다. evaluate_answer_task(답변 평가), batch_evaluate_task(일괄 평가), pre_generate_coding_problem_task(코딩 문제 사전 생성)의 3개 태스크가 라우팅된다. 이 큐의 태스크는 Ollama LLM 호출을 포함하므로 GPU 리소스를 집중적으로 사용하며, 워커 동시성(concurrency)이 제한적으로 설정된다.

emotion_analysis 큐는 감정 분석 태스크를 전담한다. analyze_emotion_task(단건 감정 분석)와 batch_emotion_analysis_task(일괄 감정 분석)의 2개 태스크가 라우팅된다.

report_generation 큐는 리포트 생성 태스크를 전담한다. generate_report_task(종합 리포트 생성)와 complete_interview_workflow_task(면접 워크플로우 완료 처리)의 2개 태스크가 라우팅된다.

tts_generation 큐는 TTS 합성 태스크를 전담한다. generate_tts_task(단건 TTS 합성)와 prefetch_tts_task(TTS 사전 생성)의 2개 태스크가 라우팅된다. 이 큐의 태스크는 Hume AI 외부 API 호출을 포함하므로 I/O 바운드 특성을 갖는다.

rag_processing 큐는 이력서 RAG 처리 태스크를 전담한다. process_resume_task(이력서 PDF 파싱, 청킹, 임베딩, 벡터 저장)가 라우팅된다.

media_processing 큐는 미디어 관련 태스크를 전담한다. transcode_recording_task(녹화 파일 트랜스코딩)와 cleanup_recording_task(녹화 파일 정리)의 2개 태스크가 라우팅된다.

태스크 라우팅은 celery_app.py의 task_routes 딕셔너리에서 태스크 이름과 큐 이름의 매핑으로 정의되며, 새로운 태스크를 추가할 때 해당 딕셔너리에 매핑만 추가하면 되는 설정 기반 라우팅(Configuration-based Routing) 패턴을 채택하였다.

### 8.1.3 16개 태스크 명세

celery_tasks.py 모듈(800줄 이상)에 정의된 16개 Celery 태스크의 주요 명세는 다음과 같다.

evaluate_answer_task는 핵심 평가 태스크로서, LLM(EXAONE 3.5)을 호출하여 지원자의 답변을 5축(문제해결력, 논리성, 기술이해도, STAR, 전달력)으로 평가한다. soft_time_limit=60초, time_limit=90초, max_retries=3으로 설정된다. RAG 폴백 메커니즘이 구현되어, 호출 측에서 resume_context를 전달하지 않은 경우 태스크 내부에서 직접 RAG 검색을 수행한다. 완료 시 _publish_event()를 통해 evaluation.completed 이벤트를 Redis Pub/Sub에 발행한다.

generate_report_task는 면접 종합 리포트를 생성하는 태스크로서, 5단계 처리 파이프라인으로 구성된다. 제1단계는 _analyze_star_structure() 함수를 통한 STAR 키워드 분석이다. 제2단계는 _extract_keywords() 함수를 통한 기술 키워드 추출로, 40개 이상의 사전 정의된 기술 키워드(Python, React, Docker, AWS 등)의 출현 빈도를 카운트한다. 제3단계는 전체 평가의 강점/개선점 집계이다. 제4단계는 각 평가 점수의 평균, 최솟값, 최댓값 등의 통계 산출이다. 제5단계는 _generate_recommendations() 함수를 통한 맞춤형 개선 권고사항 생성이다. soft_time_limit=120초이며, 완료 시 report.generated 이벤트를 발행한다.

generate_tts_task는 Hume AI EVI API를 호출하여 AI 면접관의 질문 텍스트를 음성으로 합성하는 태스크이다. 생성된 MP3 파일을 서버에 저장하고, tts.ready 이벤트를 발행하여 프론트엔드에 오디오 URL을 전달한다.

process_resume_task는 업로드된 이력서 PDF를 파싱, 청킹, 임베딩하여 pgvector에 저장하는 태스크이다. 처리 완료 시 resume.processed 이벤트를 발행한다.

### 8.1.4 주기적 태스크 (Celery Beat)

Celery Beat 스케줄러를 통해 2개의 주기적 태스크가 자동 실행된다. cleanup_sessions_task는 5분 간격(schedule: 300초)으로 실행되어 만료된 면접 세션의 데이터(Redis 캐시, 임시 파일)를 정리한다. aggregate_statistics_task는 1시간 간격(schedule: 3600초)으로 실행되어 시스템 전반의 통계(총 면접 횟수, 평균 점수, 활성 세션 수 등)를 집계하여 모니터링에 활용한다.

### 8.1.5 Lazy Loading 패턴

celery_tasks.py는 LLM, RAG, TTS 인스턴스를 태스크 최초 호출 시에만 초기화하는 Lazy Loading 패턴을 적용한다. get_llm(), get_rag(), get_tts_service() 함수는 각각 전역 변수(_llm_instance, _rag_instance, _tts_instance)에 인스턴스를 캐싱하여, 동일 워커 프로세스 내에서 반복적인 모델 로딩을 방지한다. 이 패턴은 Celery 워커의 기동 시간을 단축하고(모든 모델을 워커 기동 시 로드하지 않음), 실제로 사용되지 않는 모델의 메모리 점유를 방지한다.

---

## 8.2 이벤트 버스 설계 (Redis Pub/Sub, 30+ 이벤트 타입)

### 8.2.1 EventBus 싱글톤 아키텍처

event_bus.py 모듈(411줄)에 구현된 EventBus는 시스템 전체의 이벤트 발행/구독을 중앙화하는 핵심 메시징 인프라이다. 스레드 안전한 싱글톤(Thread-safe Singleton) 패턴으로 구현되어, 시스템 전체에서 단 하나의 인스턴스만 존재한다.

EventBus의 내부 자료구조는 네 가지 핵심 컴포넌트로 구성된다. 이벤트 타입별 핸들러 레지스트리(Dict[EventType, List[Callable]])는 특정 이벤트 타입에 대해 등록된 비동기 핸들러 함수의 리스트를 관리한다. 글로벌 핸들러 목록(List[Callable])은 모든 이벤트 타입에 대해 호출되는 핸들러를 관리한다. Redis Pub/Sub 연결은 프로세스 간(Inter-process) 이벤트 전파를 담당한다. WebSocket 연결 관리 맵(Dict[str, Set[WebSocket]])은 세션 ID별 활성 WebSocket 연결을 추적한다.

### 8.2.2 이벤트 발행 3단계 전파 메커니즘

publish() 비동기 메서드를 통해 이벤트가 발행되면, 세 단계의 전파가 순차적으로 수행된다.

제1단계: 로컬 핸들러 디스패치이다. 동일 프로세스 내에 등록된 이벤트 핸들러가 asyncio.gather()를 통해 병렬적으로 즉시 실행된다. 각 핸들러의 예외는 독립적으로 캐치되어, 특정 핸들러의 오류가 다른 핸들러의 실행을 방해하지 않는다.

제2단계: Redis Pub/Sub 전파이다. 이벤트 페이로드(event_type, session_id, data, timestamp, event_id)가 JSON으로 직렬화되어 interview_events:{event_type} 채널에 발행된다. 채널 네이밍에 이벤트 타입을 포함함으로써, 구독자가 관심 있는 이벤트 타입만 선택적으로 구독할 수 있다.

제3단계: WebSocket 브로드캐스트이다. 이벤트의 session_id에 해당하는 모든 활성 WebSocket 연결에 이벤트 페이로드를 전송한다. 전송 실패한 연결(끊어진 WebSocket)은 자동으로 연결 관리 맵에서 제거된다.

### 8.2.3 Self-echo 방지 메커니즘

Redis Pub/Sub의 특성상, 메시지를 발행한 프로세스도 자신이 구독 중인 채널에서 해당 메시지를 수신하게 되는 self-echo 문제가 발생한다. EventBus는 _published_event_ids 집합(Set)에 자신이 발행한 이벤트의 UUID를 기록하고, Redis에서 수신한 메시지 중 자신의 이벤트 ID와 일치하는 것은 무시하는 방식으로 이 문제를 해결한다. 이벤트 ID 집합은 크기가 무한히 증가하지 않도록 주기적으로 정리(Purge)된다.

### 8.2.4 Celery 워커 동기 발행

Celery 워커는 동기(Synchronous) 실행 컨텍스트에서 동작하므로, EventBus의 비동기 publish() 메서드를 직접 사용할 수 없다. 이를 해결하기 위해 celery_tasks.py에 _publish_event() 동기 헬퍼 함수가 구현되었다. 이 함수는 동기 redis.Redis 클라이언트를 생성하여 직접 Pub/Sub 채널에 JSON 메시지를 발행하며, EventBus의 비동기 Pub/Sub 리스너가 이를 수신하여 WebSocket 브로드캐스트까지 수행하는 전체 전파 경로를 완성한다.

Redis 연결 실패 시에도 Celery 태스크 자체의 실행은 정상적으로 계속되며, 이벤트 발행 실패만 경고 로그로 기록되는 Graceful Degradation이 적용된다. 이 설계는 이벤트 메시징 인프라의 일시적 장애가 핵심 AI 처리 작업의 완료를 방해하지 않도록 보장한다.

### 8.2.5 30종 이상의 이벤트 타입 체계

events.py의 EventType 열거형에 정의된 이벤트 타입은 다음 5개 카테고리로 분류된다.

세션 라이프사이클 이벤트(6종)로는 SESSION_CREATED, SESSION_STARTED, SESSION_PAUSED, SESSION_RESUMED, SESSION_ENDED, SESSION_EXPIRED가 정의된다.

면접 진행 이벤트(6종)로는 QUESTION_GENERATED, ANSWER_RECEIVED, EVALUATION_COMPLETED, FOLLOW_UP_GENERATED, PHASE_CHANGED, INTERVIEW_COMPLETED가 정의된다.

AI 처리 이벤트(8종)로는 STT_INTERIM, STT_FINAL, STT_UTTERANCE_END, TTS_READY, EMOTION_ANALYZED, PROSODY_ANALYZED, GAZE_ANALYZED, CODING_ANALYZED가 정의된다.

데이터 처리 이벤트(5종)로는 RESUME_UPLOADED, RESUME_PROCESSED, REPORT_GENERATED, PDF_READY, RECORDING_COMPLETED가 정의된다.

시스템 상태 이벤트(5종 이상)로는 SYSTEM_ERROR, CELERY_TASK_COMPLETED, CELERY_TASK_FAILED, WORKER_HEARTBEAT, HEALTH_CHECK 등이 정의된다.

각 이벤트는 일관된 JSON 스키마(event_type, session_id, data, timestamp, event_id)를 따르며, data 필드에 이벤트 타입별 페이로드가 포함된다.

---

## 8.3 미디어 녹화/트랜스코딩 (aiortc + FFmpeg)

### 8.3.1 실시간 미디어 녹화

media_recording_service.py 모듈은 aiortc를 통해 수신되는 WebRTC 미디어 스트림의 실시간 녹화를 담당한다. 비디오 트랙과 오디오 트랙은 각각 독립적으로 녹화되며, 녹화 시작/중지가 면접 세션의 라이프사이클과 동기화된다.

녹화 파이프라인은 다음과 같이 구성된다. aiortc MediaStreamTrack에서 프레임을 수신하고, FFmpeg 서브프로세스(subprocess)를 통해 실시간으로 컨테이너 포맷(WebM 또는 MP4)에 기록한다. 비디오 코덱은 VP8 또는 H.264, 오디오 코덱은 Opus 또는 AAC가 사용된다. FFmpeg는 파이프(pipe) 방식으로 프레임 데이터를 수신하여, 메모리 효율적인 스트리밍 방식의 녹화가 구현된다.

### 8.3.2 비동기 트랜스코딩

면접 종료 후 녹화 파일의 트랜스코딩은 Celery의 transcode_recording_task를 통해 비동기적으로 처리된다. 원본 녹화 파일은 최적 압축 설정(CRF, 비트레이트 제어)으로 재인코딩되어 파일 크기가 절감되며, 트랜스코딩 완료 후 원본 파일은 자동 삭제된다. 최종 트랜스코딩된 파일은 security.py의 encrypt_file()을 통해 AES-256-GCM으로 암호화되어 저장된다.

cleanup_recording_task는 일정 기간이 경과한 녹화 파일을 자동 삭제하여 디스크 공간을 관리한다. 삭제 정책은 환경변수를 통해 설정 가능하다.

---

## 8.4 SLA 지연 시간 모니터링 (1.5초 임계값)

### 8.4.1 LatencyMonitor 미들웨어

latency_monitor.py 모듈(약 100줄)에 구현된 LatencyMonitor는 FastAPI 미들웨어로서 모든 HTTP 요청의 End-to-End 지연 시간을 자동 측정한다. 미들웨어는 요청 수신 시점과 응답 완료 시점의 타임스탬프 차이를 밀리초 단위로 기록하며, 이 측정값을 SLA 임계값(1.5초 = 1500ms)과 비교한다.

SLA 위반 감지 시 다음의 조치가 자동으로 수행된다. 경고 로그가 출력되어 위반 엔드포인트, 요청 메서드, 소요 시간, SLA 초과량이 기록된다. 연속 위반 횟수가 카운트되어, 특정 엔드포인트에서 반복적으로 SLA를 위반하는 경우 시스템 관리자에게 알림이 전송된다. 위반 통계는 /api/monitoring/latency 엔드포인트를 통해 실시간으로 조회 가능하다.

### 8.4.2 구간별 지연 시간 측정

LatencyMonitor는 전체 요청 지연뿐 아니라, 핵심 처리 구간별 지연 시간도 개별적으로 측정한다. 측정 구간은 STT 파이프라인 지연(Deepgram API 호출 포함), LLM 추론 지연(Ollama API 호출), RAG 검색 지연(pgvector 유사도 검색 + Redis 캐시 조회), WebRTC 시그널링 지연(SDP/ICE 교환), 이벤트 전파 지연(Redis Pub/Sub + WebSocket 브로드캐스트)으로 구분된다.

각 구간의 지연 통계(평균, P50, P95, P99, 최대값)가 슬라이딩 윈도우 방식으로 유지되며, 어떤 구간이 SLA 위반의 주 원인인지를 정량적으로 식별할 수 있다.

### 8.4.3 모니터링 엔드포인트

/api/monitoring/latency GET 엔드포인트는 다음의 모니터링 데이터를 JSON 형식으로 반환한다. 전체 요청 지연 통계(평균, P50, P95, P99), 구간별 지연 통계, SLA 준수율(SLA 이내 응답 비율), 최근 SLA 위반 이력(위반 시각, 엔드포인트, 소요 시간), 활성 세션 수 및 시스템 리소스 사용량이 포함된다. 이 엔드포인트는 운영 환경에서의 실시간 성능 모니터링 및 장애 진단에 활용된다.

---

## 8.5 Docker 컨테이너화 및 NGINX 배포

### 8.5.1 FastAPI 백엔드 컨테이너 (Dockerfile)

FastAPI 백엔드의 Docker 이미지 빌드는 다음의 최적화된 빌드 전략을 따른다.

기반 이미지는 Python 3.11-slim으로, Debian 기반의 경량 이미지를 사용하여 불필요한 패키지를 배제하면서도 Native Extension(C 확장 모듈) 빌드에 필요한 기본 도구를 포함한다.

시스템 의존성 설치 단계에서 build-essential과 gcc(C 확장 빌드), libpq-dev(psycopg2 PostgreSQL 드라이버), portaudio19-dev(PyAudio 실시간 오디오), ffmpeg(미디어 처리/트랜스코딩), curl(헬스 체크)이 설치된다.

Docker 레이어 캐싱 최적화가 적용된다. requirements.txt를 먼저 복사하여 pip install -r requirements.txt를 수행한 후, 이후 소스 코드를 복사한다. 이 순서를 통해 소스 코드만 변경된 경우 의존성 레이어가 캐시에서 재사용되어 이미지 빌드 시간이 대폭 단축된다.

환경변수 설정으로 PYTHONUNBUFFERED=1(Python 출력 버퍼링 비활성화, Docker 로그 즉시 출력)과 APP_ENV=production(프로덕션 모드 활성화)이 적용된다.

헬스 체크는 HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8000/health로 설정되어, 30초 간격으로 /health 엔드포인트를 호출하며 3회 연속 실패 시 컨테이너를 비정상(Unhealthy)으로 판정한다. Docker Compose의 depends_on 조건이 이 헬스 체크 상태를 참조하여 의존 서비스의 준비 완료를 보장한다.

실행 명령은 CMD ["uvicorn", "integrated_interview_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--forwarded-allow-ips", "*"]이다. --workers 2로 2개의 uvicorn 워커 프로세스가 생성되어 다중 CPU 코어를 활용하며, --forwarded-allow-ips '*'로 NGINX 프록시 헤더(X-Forwarded-For, X-Forwarded-Proto)를 신뢰하여 실제 클라이언트 IP를 정확히 로깅한다.

### 8.5.2 Docker Compose 멀티 서비스 오케스트레이션

Docker Compose를 통해 6개(이상) 서비스가 정의되며, 기동 순서와 의존성이 다음과 같이 제어된다.

기동 순서 제1단계는 인프라 서비스이다. Redis와 PostgreSQL이 먼저 기동되며, 각각 헬스 체크가 통과한 후에야 다음 단계의 서비스가 기동된다. Redis는 redis-cli ping 명령으로, PostgreSQL은 pg_isready 명령으로 준비 완료가 확인된다.

기동 순서 제2단계는 애플리케이션 서비스이다. FastAPI 백엔드와 Celery 워커가 기동된다. Celery 워커는 FastAPI와 동일한 Docker 이미지를 사용하되, 진입점(Entrypoint)만 celery -A celery_app worker --loglevel=info로 변경된다. Celery Beat 스케줄러는 --beat 옵션을 추가하거나 별도 컨테이너로 실행된다.

기동 순서 제3단계는 프론트엔드 및 게이트웨이이다. Next.js 프론트엔드(포트 3000)와 NGINX(포트 80/443)가 마지막으로 기동된다. NGINX는 upstream 서비스(FastAPI, Next.js)가 모두 준비된 후에야 트래픽을 프록시할 수 있으므로 마지막에 기동된다.

내부 서비스 통신은 Docker 브릿지 네트워크를 통해 이루어진다. 각 서비스는 서비스 이름(fastapi, nextjs, redis, postgres)을 DNS 호스트명으로 사용하며, Docker의 내장 DNS 서버가 서비스 이름을 컨테이너 IP로 자동 해석한다. 외부에 노출되는 포트는 NGINX의 80번(HTTP → HTTPS 리다이렉트)과 443번(HTTPS)으로 한정되며, 내부 서비스 포트(8000, 3000, 6379, 5432)는 Docker 네트워크 외부에서 직접 접근할 수 없도록 격리된다.

### 8.5.3 NGINX 배포 설정

NGINX 컨테이너에는 nginx.conf 설정 파일과 SSL 인증서가 볼륨 마운트(Volume Mount)된다. 주요 성능 최적화 설정은 다음과 같다.

워커 프로세스는 worker_processes auto로 CPU 코어 수에 자동 조절되며, 워커당 최대 동시 연결은 worker_connections 1024로 설정된다. 성능 최적화 지시어로 sendfile on(커널 수준 파일 전송), tcp_nopush on(패킷 최적화), tcp_nodelay on(소패킷 즉시 전송), keepalive_timeout 65(연결 유지 시간)가 적용된다.

업로드 크기 제한은 client_max_body_size 50m으로 설정되어, 이력서 PDF 등 최대 50MB 파일의 업로드를 허용한다. Gzip 압축은 레벨 6으로 설정되어 text/plain, text/css, application/json, application/javascript, image/svg+xml 등 10종 MIME 타입에 적용되며, 1,000바이트 이상의 응답에만 활성화된다.

FastAPI 업스트림(backend)은 least_conn 알고리즘(최소 연결 수 우선)으로 부하 분산되며, 업스트림 서버 목록에 인스턴스를 추가하는 것만으로 수평적 확장이 가능하다. WebSocket 프록시는 proxy_set_header Upgrade $http_upgrade와 proxy_set_header Connection "upgrade"로 프로토콜 업그레이드가 처리되며, proxy_read_timeout 7200으로 면접 세션 최대 지속 시간(120분)을 지원한다.

### 8.5.4 로컬 개발 환경 (start_all.ps1)

Windows 환경에서 Docker 없이 로컬 개발을 수행하기 위한 start_all.ps1 PowerShell 스크립트가 제공된다. 이 스크립트는 다음의 서비스를 순서대로 기동한다.

Redis 서버를 기동하고 redis-cli ping으로 준비 완료를 확인한다. PostgreSQL 서비스를 확인하고 pg_isready로 준비 완료를 확인한다. Ollama 런타임을 기동하고 EXAONE 3.5, Qwen3-Coder, nomic-embed-text 모델의 로딩을 확인한다. FastAPI 서버를 uvicorn으로 기동한다. Celery 워커를 기동한다. Next.js 개발 서버를 npm run dev로 기동한다.

각 단계에서 이전 서비스의 건강 상태가 확인된 후에야 다음 서비스가 기동되며, 기동 실패 시 오류 메시지와 함께 중단된다. 이를 통해 Docker Compose 환경과 유사한 순서 제어가 로컬 개발에서도 보장된다.

---

본 장에서 기술된 비동기 처리 및 인프라 설계는 본 시스템의 운영적 안정성(Operational Stability)과 성능 보장(Performance Guarantee)의 기반을 형성한다. 특히 Celery 6큐 분리 설계, EventBus 3단계 이벤트 전파, LatencyMonitor SLA 자동 감시의 세 구성 요소는 상호 보완적으로 작동하여, 다수의 AI 서비스가 실시간으로 통합 운용되는 환경에서도 일관된 응답 성능과 시스템 안정성을 유지한다. 9장에서는 이러한 시스템의 테스트 전략과 품질 관리 방안을 기술한다.
