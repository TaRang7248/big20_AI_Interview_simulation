# 5. 핵심 기능 설계 및 구현

본 장에서는 AI 모의면접 시뮬레이션 시스템의 핵심 기능을 설계 의도와 구현 세부사항의 두 관점에서 심층적으로 기술한다. 3장에서 정의된 6계층 아키텍처와 4장의 기술 스택을 기반으로, 각 기능이 어떻게 설계되었고 어떤 알고리즘 및 데이터 흐름을 통해 구현되었는지를 소스 코드 수준에서 분석한다.

---

## 5.1 AI 면접 흐름

### 5.1.1 면접 세션 라이프사이클

면접 세션은 생성(Creation)에서 종료(Termination)에 이르는 명확한 라이프사이클을 갖는다. 세션 라이프사이클은 다음 6단계로 구성된다.

첫째, 세션 초기화(Session Initialization) 단계이다. 지원자가 면접 시작을 요청하면, 고유 세션 ID(UUID v4)가 생성되고 WorkflowState 초기 상태가 구성된다. 초기 상태에는 session_id, user_email, job_posting_id, max_questions(기본 10), question_count(0), current_phase(IDLE), chat_history(빈 리스트), emotion_adaptive_mode("normal") 등의 필드가 포함된다. 세션 메타데이터는 PostgreSQL에 영속 저장되고, 진행 상태는 Redis에 캐싱된다.

둘째, WebRTC 연결 수립(RTC Connection Establishment) 단계이다. 클라이언트와 서버 간 SDP offer/answer 교환 및 ICE 후보 협상이 WebSocket 시그널링을 통해 수행되고, DTLS 핸드셰이크가 완료되면 비디오/오디오 미디어 스트림이 서버로 전송되기 시작한다.

셋째, 면접 진행(Interview Execution) 단계이다. LangGraph 상태머신이 IDLE → GREETING으로 전이되며 면접이 개시된다. 이후 GENERATE_QUESTION → WAIT_ANSWER → PROCESS_ANSWER → EVALUATE → ROUTE_NEXT의 루프가 max_questions에 도달할 때까지 반복된다.

넷째, 면접 종료(Interview Completion) 단계이다. 최대 질문 수 도달 시 COMPLETE 노드에서 종료 인사가 생성되고, Celery를 통한 비동기 리포트 생성 워크플로우가 트리거된다.

다섯째, 리포트 생성(Report Generation) 단계이다. Celery 워커에서 STAR 분석, 키워드 추출, 점수 집계, PDF 생성 등이 백그라운드로 처리되며, 완료 시 EventBus를 통해 report.generated 이벤트가 발행된다.

여섯째, 세션 정리(Session Cleanup) 단계이다. WebRTC 연결 해제, 미디어 트랙 종료, 임시 파일 정리, Redis 세션 데이터 삭제가 수행된다. Celery Beat의 cleanup_sessions_task가 5분 간격으로 만료 세션을 자동 정리한다.

### 5.1.2 LangGraph 상태머신 설계 (10 Phase 전이)

면접의 전체 진행 흐름은 LangGraph 프레임워크를 활용한 유한 상태 기계(FSM)로 모델링된다. interview_workflow.py 모듈에 구현된 이 상태머신은 10개의 Phase와 조건부 분기 엣지로 구성된 유향 그래프(Directed Graph)이다.

10개 Phase의 정의 및 역할은 다음과 같다. IDLE은 초기 대기 상태로 면접 시작 전 시스템이 대기하는 상태이다. GREETING은 AI 면접관이 인사말과 자기소개 요청을 생성하는 상태이다. GENERATE_QUESTION은 RAG 컨텍스트와 대화 이력을 기반으로 LLM이 새로운 면접 질문을 생성하는 상태이다. WAIT_ANSWER는 지원자의 음성 답변을 대기하는 상태로, VAD가 발화 종료를 감지할 때까지 유지된다. PROCESS_ANSWER는 STT 변환 결과를 수신하고 전처리(띄어쓰기 보정, 기술 토큰 보호 등)를 수행하는 상태이다. EVALUATE는 답변 평가(Celery 태스크 오프로딩)와 비언어 분석(DeepFace, Hume Prosody)이 asyncio.gather()를 통해 병렬 실행되는 상태이다. ROUTE_NEXT는 꼬리질문 여부, 질문 횟수, 감정 적응 모드를 종합하여 다음 노드(GENERATE_QUESTION, FOLLOW_UP, COMPLETE)를 결정하는 조건부 라우팅 상태이다. FOLLOW_UP은 이전 답변의 특정 부분에 대해 꼬리질문을 생성하는 상태이다. COMPLETE은 면접 종료 인사를 생성하고 리포트 생성 워크플로우를 트리거하는 최종 상태이다. ERROR는 각 노드에서 발생하는 예외를 캐치하여 면접이 비정상 종료되지 않도록 복구하는 오류 처리 상태이다.

조건부 분기(Conditional Edge)의 핵심 로직은 route_after_route_next 함수에서 구현된다. 이 함수는 세 가지 출구(Exit)를 갖는다. question_count가 max_questions에 도달한 경우 COMPLETE으로 전이한다. needs_follow_up이 True이고, 현재 주제의 topic_question_count가 2 미만이며, emotion_adaptive_mode가 "encouraging"이 아닌 경우 FOLLOW_UP으로 전이한다. 그 외의 경우 GENERATE_QUESTION으로 전이하여 새로운 질문 주제를 시작한다.

WorkflowState는 TypedDict 자료구조로 정의되며, session_id, phase, question_count, max_questions, chat_history, current_question, last_answer, last_emotion, emotion_adaptive_mode, needs_follow_up, current_topic, topic_question_count, evaluations, trace 등 20개 이상의 필드로 구성된다. 각 노드가 반환하는 갱신된 상태는 MemorySaver 체크포인트에 자동 저장되어 세션의 중단 및 재개가 가능하다.

감사 추적(Audit Trail)은 _trace_entry() 함수를 통해 각 노드 실행 시 노드 이름, 타임스탬프, 실행 시간(밀리초), 주요 판단 근거(예: "follow_up=True, topic_count=1, emotion=normal")가 trace 리스트에 누적되어, 면접 종료 후 전체 의사결정 과정을 재현할 수 있다.

### 5.1.3 적응형 질문 생성 (RAG 컨텍스트 + 프롬프트 엔지니어링)

적응형 질문 생성은 본 시스템의 가장 핵심적인 기능으로, 지원자 개인에 특화된 맞춤형 질문을 실시간으로 생성한다. 이 기능은 세 요소의 결합으로 구현된다.

첫째, 시스템 프롬프트(INTERVIEWER_PROMPT)이다. prompt_templates.py에 정의된 시스템 프롬프트는 AI 면접관의 페르소나를 "IT 기업의 30년차 수석 개발자 면접관"으로 설정하고, 8가지 핵심 규칙을 명시한다. 주요 규칙으로는 모든 응답의 한국어 강제(기술 용어 영어 병기 허용), 한 번에 질문 1개만 생성(복수 질문 나열 절대 금지), 지원자의 직전 답변 내용에 기반한 후속 질문 필수, 맥락 없는 질문 전환 금지 등이 포함된다.

둘째, 동적 컨텍스트 프롬프트(build_question_prompt)이다. 매 질문 생성 시 현재 진행 상황(질문 번호/총 질문 수), 현재 주제(project, technical 등), 주제 내 질문 횟수(최대 2회), 꼬리질문/주제전환 지시, 지원자의 직전 답변 원문(최대 300자 요약)이 동적으로 프롬프트에 주입된다. 마지막 질문(question_count == max_questions - 1)에서는 "마무리 질문을 해주세요"라는 추가 지시가 자동 삽입된다.

셋째, RAG 컨텍스트이다. resume_rag.py의 ResumeRAG 모듈을 통해 지원자의 이력서에서 현재 대화 맥락과 관련성이 높은 텍스트 청크가 검색되어 프롬프트에 "[참고용 이력서 내용]" 섹션으로 주입된다. 이 컨텍스트는 LLM이 지원자의 경력, 기술 스택, 프로젝트 경험을 구체적으로 참조하여 질문을 생성할 수 있게 한다.

LLM 출력 후처리 파이프라인에서는 strip_think_tokens() 함수가 EXAONE Deep의 <thought>...</thought> 태그와 Qwen3의 <think>...</think> 태그를 자동 제거하며, extract_single_question() 함수가 LLM이 규칙을 위반하여 복수 질문을 생성한 경우 첫 번째 질문만 추출한다. Korean Guard는 생성된 텍스트의 한글 비율이 60% 미만인 경우 재생성을 요청하여, 간혹 발생하는 영어 전환 문제를 방지한다.

### 5.1.4 SSE 기반 실시간 답변 스트리밍

LLM이 생성하는 면접 질문 텍스트는 SSE(Server-Sent Events) 프로토콜을 통해 토큰 단위로 클라이언트에 실시간 스트리밍된다. FastAPI의 StreamingResponse를 사용하여 구현되며, Ollama의 스트리밍 API를 활용하여 LLM이 토큰을 생성하는 즉시 클라이언트에 전달한다. 이를 통해 LLM의 전체 추론이 완료될 때까지 기다리지 않고, 첫 번째 토큰이 생성되는 즉시(Time-to-First-Token) 사용자에게 텍스트가 표시되기 시작하여, 체감 응답 시간이 크게 단축된다.

SSE 이벤트 포맷은 표준 text/event-stream MIME 타입을 따르며, 각 토큰은 data: {token} 형식으로 전송된다. 스트리밍 완료 시 data: [DONE] 이벤트가 전송되어 클라이언트가 스트리밍 종료를 인식한다. 프론트엔드에서는 EventSource API를 통해 SSE 스트림을 수신하며, 자동 재연결(Auto-reconnect) 기능이 내장되어 네트워크 불안정 시에도 스트리밍이 재시도된다.

### 5.1.5 면접 개입 시스템 (VAD 기반 Turn-taking)

VAD(Voice Activity Detection) 기반 Turn-taking 시스템은 지원자의 발화 시작과 종료를 자동으로 감지하여, 별도의 버튼 조작 없이 자연스러운 대화 흐름을 구현한다. Deepgram Nova-3의 내장 VAD 기능이 UtteranceEnd 이벤트를 발행하며, 이 이벤트가 수신되면 직전까지 누적된 STT 전사(Transcription) 결과가 LangGraph 상태머신의 PROCESS_ANSWER 노드로 전달되어 다음 질문 생성 파이프라인이 개시된다.

Turn-taking의 핵심 설계 요소는 발화 종료 판정의 적절한 지연(Delay) 설정이다. 너무 짧으면 지원자의 말이 끝나기 전에 AI가 끼어드는 느낌을 주고, 너무 길면 부자연스러운 침묵이 발생한다. Deepgram의 endpointing 파라미터를 통해 발화 종료 판정 지연이 조절되며, 한국어 특유의 발화 패턴(문장 종결 어미 후 잠깐의 사고 시간)을 고려한 설정이 적용된다.

---

## 5.2 답변 평가 시스템

### 5.2.1 5축 언어 평가 (문제해결력/논리성/기술이해도/STAR/전달력)

답변 평가는 EVALUATION_PROMPT에 정의된 5개 축(Axis)에 따라 LLM이 구조화된 JSON 형식으로 평가를 수행한다. 5개 축은 다음과 같다.

문제 해결력(Problem Solving, 1~5점)은 지원자가 문제를 어떻게 접근하고 해결하는지를 평가한다. 논리성(Logic, 1~5점)은 답변의 논리적 흐름이 일관성 있는지를 평가한다. 직무 역량 및 기술 이해도(Technical, 1~5점)는 기술적 개념이나 원리에 대한 이해가 정확한가, 설명이나 예시가 충분하고 적절한가를 평가한다. STAR 기법(STAR, 1~5점)은 상황(Situation)-과제(Task)-행동(Action)-결과(Result) 구조로 답변했는가를 평가한다. 의사소통능력(Communication, 1~5점)은 지원자가 자신의 생각을 명확하게 전달하는지, 면접관의 질문에 적절히 반응하는지를 평가한다.

평가 작업은 celery_tasks.py의 evaluate_answer_task로 Celery 워커에 오프로딩되어 비동기적으로 처리된다. 태스크 설정은 soft_time_limit=60초, time_limit=90초, max_retries=3이다. Celery 워커에서 직접 RAG를 호출하여 이력서 컨텍스트를 자체 조회하는 폴백 메커니즘이 구현되어 있어, 호출 측에서 resume_context를 전달하지 않은 경우에도 이력서 맥락 기반의 정확한 평가가 보장된다.

LLM 응답의 JSON 파싱은 parse_evaluation_json() 함수(json_utils.py)를 통해 수행되며, LLM이 간혹 생성하는 비규격 JSON(예: 후행 쉼표, 주석, 불완전한 중괄호)에 대한 복원력(Resilience)을 갖도록 다단계 파싱 폴백이 적용된다.

### 5.2.2 비언어 평가 (발화속도/시선추적/감정안정성/Prosody)

비언어 평가는 4개의 독립적 분석 파이프라인에서 수집된 데이터를 통합하여 산출된다.

발화 속도(Speech Rate) 평가는 speech_analysis_service.py에서 SPM(Syllables Per Minute) 기반으로 측정되며, '매우 느림', '느림', '적정', '빠름', '매우 빠름'의 5등급으로 분류된다. 적정 범위에 가까울수록 높은 비언어 점수가 부여된다.

시선 추적(Eye Contact) 평가는 gaze_tracking_service.py의 GazeTrackingService에서 산출된 정면 응시 비율(Eye Contact Ratio)에 기반한다. S(60~85%, 매우 적절), A(50~60% 또는 85~95%, 양호), B(35~50% 또는 95% 초과, 보통), C(20~35%, 부족), D(20% 미만, 매우 부족)의 5등급으로 평가된다.

감정 안정성(Emotional Stability) 평가는 DeepFace 분석 결과에서 면접 전체 과정의 감정 분포를 분석하여, neutral과 happy의 비율이 높을수록 안정적으로, fear, sad, angry의 비율이 높을수록 불안정한 것으로 판단한다.

Prosody 복합 점수는 Hume AI가 분석한 10개 핵심 지표(자신감, 흥미, 집중, 편안함, 불안, 열정, 망설임, 명확성, 스트레스, 전반적 긍정성) 중 긍정 지표(자신감, 흥미, 집중, 열정, 명확성, 긍정성)의 평균에서 부정 지표(불안, 망설임, 스트레스)의 가중 평균을 차감하여 산출된다.

### 5.2.3 통합 점수 산출 (언어 60% + 비언어 40%)

최종 통합 점수는 언어 평가 점수와 비언어 평가 점수를 60:40의 비율로 가중 합산하여 산출된다. 언어 평가 점수는 5개 축의 평균(5.0 만점 척도)이며, 비언어 평가 점수는 발화 속도, 시선 추적, 감정 안정성, Prosody 복합 점수의 정규화된 평균(5.0 만점 척도 변환)이다. 이 가중 비율은 면접 평가에서 답변의 내용(Content)이 비언어적 표현(Delivery)보다 상대적으로 더 중요하다는 채용 심리학의 일반적 견해를 반영한 것이다.

### 5.2.4 합격/불합격 이진 판정 로직

합격 판정은 세 가지 조건이 모두 충족될 때 이루어진다. 첫째, 5개 축 총점이 20점 이상(25점 만점)이어야 한다. 둘째, 모든 항목이 3점 이상이어야 한다. 셋째, 최종 통합 점수(언어+비언어)가 4.0 이상이어야 한다. 이 세 조건 중 하나라도 미충족 시 불합격으로 판정된다. recommendation 필드에 "합격" 또는 "불합격"이, recommendation_reason 필드에 판정 사유가 한 줄로 기록된다. 폴백 평가(_default_evaluation)에서는 모든 점수가 중간값(3.0)으로 설정되고 "불합격"으로 판정되며, fallback: True 플래그가 포함되어 실제 LLM 평가와 구분된다.

---

## 5.3 이력서 RAG (Retrieval-Augmented Generation)

### 5.3.1 PDF 파싱 및 청킹

이력서 RAG 파이프라인의 첫 번째 단계는 지원자가 업로드한 PDF 파일에서 텍스트를 추출하고, LLM의 컨텍스트 윈도우에 적합한 크기로 분할(Chunking)하는 것이다. resume_rag.py의 ResumeRAG.load_and_index_pdf() 메서드가 이 과정을 담당한다.

PDF 텍스트 추출은 pypdf 라이브러리를 통해 수행된다. 추출된 텍스트는 RecursiveCharacterTextSplitter를 통해 청크 단위로 분할되며, 청크 크기는 1,500자, 청크 간 오버랩(Overlap)은 200자로 설정된다. 이 설정은 nomic-embed-text 모델의 8,192 토큰 컨텍스트 윈도우를 활용하여 충분히 큰 청크를 사용하면서도, 검색의 정밀도(Precision)를 유지하기 위한 균형 설정이다.

각 청크에는 nomic-embed-text의 비대칭 검색 최적화를 위해 "search_document:" 접두사가 자동으로 추가된다. 이 접두사는 nomic-embed-text 모델이 문서(Document)와 쿼리(Query)를 서로 다른 임베딩 공간에 매핑하도록 학습되었다는 특성을 활용하는 것으로, 검색 쿼리에는 "search_query:" 접두사를 사용하여 비대칭 검색의 품질을 높인다.

면접 Q&A JSON 데이터 인덱싱도 지원된다. load_and_index_json() 메서드는 사전 정의된 면접 질문-답변 쌍을 벡터화하여 별도의 qa_embeddings 테이블에 저장하며, 배치 크기(batch_size=100)를 조절하여 대량 데이터 인덱싱 시 메모리 사용량을 제어한다.

### 5.3.2 PGVector 벡터 저장 및 유사도 검색

벡터 저장은 PostgreSQL의 pgvector 확장을 활용하는 PGVectorStore(langchain-postgres V2)를 통해 구현된다. nomic-embed-text 모델이 생성한 768차원 벡터는 PostgreSQL 테이블의 embedding 컬럼에 직접 저장되며, 인덱싱을 통한 ANN(Approximate Nearest Neighbor) 검색이 지원된다.

검색 전략은 MMR(Maximal Marginal Relevance)이 적용된다. get_retriever() 메서드에서 search_type="mmr"로 설정되어, 단순 유사도 검색(Similarity Search) 대비 검색 결과의 다양성(Diversity)이 보장된다. fetch_k 파라미터로 초기 후보를 넓게 가져온 뒤, k개의 최종 결과를 다양성 점수까지 고려하여 선별한다.

Redis 캐싱이 유사도 검색에 적용된다. similarity_search() 메서드는 검색 쿼리의 SHA-256 해시를 키로 Redis에 결과를 캐싱(TTL: 30분)하며, 동일 쿼리의 반복 검색 시 Ollama 임베딩 호출을 생략하여 GPU 부하를 절감한다. 캐시 키 생성은 테이블명, 쿼리 해시, k값을 조합하여 서로 다른 검색 설정의 충돌을 방지한다. Redis 연결 실패 시에도 RAG 검색 자체는 정상 동작하도록 None 반환에 의한 Graceful Degradation이 보장된다.

### 5.3.3 면접 질문 맞춤화 흐름

면접 질문 생성 시 RAG 컨텍스트가 LLM 프롬프트에 주입되는 전체 흐름은 다음과 같다. GENERATE_QUESTION 노드에서 현재 질문의 주제(current_topic)와 이전 대화 맥락을 조합한 검색 쿼리가 생성된다. 이 쿼리가 ResumeRAG.similarity_search()에 전달되어 이력서에서 관련 텍스트 청크가 검색된다. 검색된 청크(최대 3개)가 LLM 프롬프트의 "[참고용 이력서 내용]" 섹션에 삽입된다. LLM은 INTERVIEWER_PROMPT(시스템 프롬프트) + build_question_prompt(동적 컨텍스트) + RAG 컨텍스트의 세 요소를 결합한 프롬프트를 입력으로 받아 질문을 생성한다.

이 과정에서 RAG 컨텍스트 조회는 LLM 추론보다 먼저 직렬로 실행되어, Ollama 임베딩 모델(nomic-embed-text)과 LLM(EXAONE)의 GPU 동시 사용으로 인한 VRAM 경합을 방지한다. 동일 세션 내 이전 질문에서 이미 조회된 RAG 결과는 Redis 캐시에서 즉시 반환되어 반복 GPU 호출이 회피된다.

---

## 5.4 실시간 비언어 분석

### 5.4.1 WebRTC 미디어 파이프라인 (비디오/오디오 분기)

WebRTC를 통해 수신된 미디어 스트림은 서버 측에서 비디오 트랙과 오디오 트랙으로 분기되어 각각 독립적인 AI 분석 파이프라인으로 전달된다.

비디오 트랙은 1초 간격으로 프레임이 추출되어 DeepFace 표정 감정 분석과 GazeTrackingService 시선 추적 분석에 동시에 활용된다. 오디오 트랙은 두 갈래로 분기되는데, 하나는 Deepgram Nova-3 API로 스트리밍되어 실시간 STT가 수행되고, 다른 하나는 발화 구간의 청크가 축적되어 Hume AI Prosody API에 전송된다.

미디어 녹화는 media_recording_service.py 모듈이 FFmpeg를 활용하여 비디오/오디오 스트림을 WebM 또는 MP4 형식으로 저장하며, 녹화 완료 후 Celery의 transcode_recording_task를 통해 트랜스코딩 및 압축이 수행된다. 녹화 파일은 AES-256-GCM으로 암호화되어 저장된다.

### 5.4.2 DeepFace 표정 감정 분석 (7가지, 1초 간격)

DeepFace 감정 분석은 VISION_EXECUTOR(ThreadPoolExecutor, max_workers=2)를 통해 메인 이벤트 루프를 블로킹하지 않는 비동기 방식으로 실행된다. DeepFace.analyze() 함수가 enforce_detection=False 옵션으로 호출되어, 얼굴이 감지되지 않는 프레임에서도 예외 없이 처리가 계속된다.

분석 결과는 7가지 감정(happy, sad, angry, surprise, fear, disgust, neutral)에 대한 확률 분포(합계 100%)와 지배적 감정(dominant_emotion)으로 반환된다. 확률 분포는 정규화되어 각 감정의 확률이 0~1 범위로 변환된다.

감정 적응 모드(Emotion Adaptive Mode)의 결정 로직은 다음과 같다. 지배적 감정이 sad, fear, disgust인 경우 "encouraging" 모드로 전환되어 꼬리질문이 완화되고 격려적 톤의 질문이 생성된다. 지배적 감정이 happy, surprise인 경우 "challenging" 모드로 전환되어 더 심화된 기술적 질문이 생성된다. 그 외의 경우(neutral, angry) "normal" 모드가 유지된다.

각 턴의 감정 분석 결과는 WorkflowState의 last_emotion 필드에 저장되며, 세션 전체의 감정 통계는 batch_emotion_analysis_task를 통해 일괄 집계되어 리포트에 포함된다.

### 5.4.3 발화 속도 분석 (SPM, 등급 판정)

발화 속도 분석은 speech_analysis_service.py 모듈에서 SPM(Syllables Per Minute) 기반으로 수행된다. STT 변환 결과의 텍스트를 한국어 음절 단위로 분리하고, 발화 구간의 경과 시간으로 나누어 SPM을 산출한다.

SPM 등급 판정 기준은 다음과 같이 5단계로 정의된다. 200 SPM 미만은 매우 느림(Very Slow)으로 "너무 천천히 말하고 있어 면접관의 집중력이 떨어질 수 있습니다"라는 피드백이 생성된다. 200~280 SPM은 느림(Slow), 280~380 SPM은 적정(Appropriate)으로 가장 이상적인 발화 속도로 판단된다. 380~450 SPM은 빠름(Fast), 450 SPM 초과는 매우 빠름(Very Fast)으로 "발화 속도가 너무 빨라 전달력이 저하될 수 있습니다"라는 피드백이 생성된다.

턴별 SPM 추이는 시계열 데이터로 기록되어, 리포트의 발화 속도 영역 차트(Area Chart)에서 면접 전체 과정의 발화 패턴 변화를 시각화할 수 있다.

### 5.4.4 시선 추적 분석 (OpenCV, 눈 접촉 비율)

시선 추적 분석은 gaze_tracking_service.py의 GazeTrackingService 클래스에서 수행된다. DeepFace 분석 결과에 포함된 얼굴 영역(face region: x, y, w, h)을 입력으로 받아, estimate_gaze_direction() 함수를 통해 시선 방향을 추정한다.

시선 방향 추정 알고리즘은 다음과 같이 동작한다. 얼굴 바운딩 박스의 중심 좌표를 프레임 대비 정규화 좌표(0~1)로 변환한다. 프레임 중심(0.5, 0.5)으로부터의 편차(dx, dy)를 계산한다. dx와 dy가 모두 center_threshold(기본 ±0.20) 이내이면 "center"(정면 응시)로 판정한다. 그 외에는 편차의 방향과 크기에 따라 "left", "right", "up", "down"으로 분류한다. 얼굴이 감지되지 않은 프레임은 "away"(시선 이탈)로 분류된다.

턴별 시선 통계(GazeTurnStats)에는 총 샘플 수, 방향별 개수(center, left, right, up, down, away), 정면 응시 비율(eye_contact_ratio)이 기록된다. 세션 전체 통계(SessionGazeStats)에서는 시선 안정성(Consistency Score)이 턴별 정면 응시 비율의 표준편차(stdev)를 기반으로 산출되며, max(0.0, 1.0 - stdev)의 수식으로 표준편차가 낮을수록(둘 간의 차이가 작을수록) 안정적이라 판단한다.

등급 평가에서는 100% 응시가 S등급이 아닌 B등급으로 평가된다는 점이 주목할 만하다. 이는 실제 면접에서 100% 정면 응시는 역설적으로 부자연스러운 인상을 줄 수 있다는 면접 심리학의 연구 결과를 반영한 것으로, 상한 임계값(85%)을 별도로 설정하여 자연스러운 시선 분산이 오히려 높은 평가를 받도록 설계되었다.

### 5.4.5 Hume AI Prosody 감정 분석 (10개 지표)

Hume AI Prosody 분석은 hume_prosody_service.py 모듈을 통해 수행된다. 지원자의 발화 오디오가 Hume AI Prosody API에 전송되면, 억양(Intonation), 강세(Stress), 리듬(Rhythm), 속도 변화(Tempo Variation) 등 초분절적(Suprasegmental) 특성이 분석되어 48개 감정 차원의 점수가 반환된다.

이 중 면접 맥락에서 유의미한 10개 핵심 지표가 추출되어 interview_indicators 딕셔너리로 정리된다. 자신감(Confidence), 흥미(Interest), 집중(Focus), 편안함(Comfort), 불안(Anxiety), 열정(Enthusiasm), 망설임(Hesitation), 명확성(Clarity), 스트레스(Stress), 전반적 긍정성(Positivity)이 이에 해당한다.

DeepFace 분석 결과와의 멀티모달 융합은 merge_with_deepface() 함수에서 수행된다. 융합 가중치는 Prosody 50%, DeepFace 50%로 설정되어, 음성과 영상의 이중 채널 감정 정보가 균형 있게 결합된다. 융합 결과에서 부정적 감정 지표(불안, 스트레스, 망설임)의 가중 합이 긍정적 감정 지표(자신감, 열정, 편안함)의 가중 합을 초과하면 "encouraging" 모드로, 그 반대이면서 자신감과 흥미가 높으면 "challenging" 모드로, 그 외에는 "normal" 모드로 최종 감정 적응 모드가 결정된다.

---

## 5.5 코딩 테스트

### 5.5.1 다국어 코드 실행 (Python/JS/Java/C/C++, Docker 샌드박스)

코딩 테스트의 코드 실행은 code_execution_service.py 모듈이 담당하며, 지원자가 작성한 코드를 격리된 Docker 컨테이너 샌드박스 환경에서 안전하게 실행한다. 각 실행 요청마다 독립적인 Docker 컨테이너가 생성되며, 컨테이너는 호스트 시스템의 네트워크, 파일 시스템, 프로세스 공간으로부터 완전히 격리된다.

5개 프로그래밍 언어별 실행 환경은 다음과 같다. Python은 python:3.11-slim 이미지에서 python3 명령으로 실행된다. JavaScript는 node:18-slim 이미지에서 node 명령으로 실행된다. Java는 openjdk:17-slim 이미지에서 javac 컴파일 후 java 명령으로 실행된다. C는 gcc:latest 이미지에서 gcc 컴파일 후 실행 바이너리를 실행한다. C++는 gcc:latest 이미지에서 g++ 컴파일 후 실행 바이너리를 실행한다.

각 컨테이너에는 엄격한 리소스 제한이 적용된다. CPU 시간 제한(타임아웃)을 초과하면 컨테이너가 강제 종료(docker kill)되며, 메모리 사용량 제한과 네트워크 접근 차단(--network none)이 적용되어 악의적 코드(무한 루프, 메모리 폭탄, 외부 통신 시도)로 인한 서버 영향이 원천 차단된다.

실행 결과는 표준 출력(stdout), 표준 오류(stderr), 반환 코드(return code), 실행 시간(execution time)으로 구성되며, 테스트 케이스별 통과/실패 판정과 함께 프론트엔드에 반환된다.

### 5.5.2 AI 코드 분석 (Qwen3-Coder-30B 기반)

지원자가 제출한 코드에 대해 Qwen3-Coder-30B-A3B 모델이 다차원적 AI 코드 분석을 수행한다. 분석 차원은 알고리즘 정확성(Correctness, 올바른 출력을 생성하는가), 시간 복잡도(Time Complexity, Big-O 분석), 공간 복잡도(Space Complexity, 메모리 사용 효율), 코드 품질(Code Quality, 가독성, 변수명, 함수 분리), 엣지 케이스(Edge Case, 빈 입력, 경계값, 대규모 입력 처리)로 구성된다.

분석 결과는 JSON 형식으로 반환되며, 각 차원에 대한 점수와 구체적 피드백, 개선 제안(Improvement Suggestions)이 포함된다. 이 피드백은 단순 정오 판정을 넘어 지원자의 코딩 역량 향상에 기여하는 교육적(Educational) 가치를 함께 지닌다.

### 5.5.3 동적 문제 생성 (난이도별)

코딩 문제는 면접 시작 시 Celery의 pre_generate_coding_problem_task를 통해 사전 생성(Pre-generation)되어 Redis에 캐싱된다. Qwen3-Coder-30B-A3B 모델이 지정된 난이도(easy, medium, hard)에 따라 문제를 동적으로 생성하며, 문제 구성 요소는 문제 설명(Problem Description), 입출력 예시(Input/Output Examples), 제약 조건(Constraints), 테스트 케이스(Test Cases)로 이루어진다.

사전 생성 전략은 지원자가 코딩 테스트 페이지에 진입하는 시점에 즉각적으로 문제가 제공될 수 있도록 하기 위한 것으로, LLM 추론 지연(수 초~수십 초)이 사용자 경험에 영향을 미치지 않도록 한다.

---

## 5.6 화이트보드 시스템 설계

### 5.6.1 Claude 3.5 Sonnet Vision 다이어그램 분석

화이트보드 시스템 설계 평가는 whiteboard_service.py 모듈에서 구현된다. 지원자가 웹 기반 화이트보드 인터페이스(Canvas API)에서 시스템 설계 다이어그램을 그리면, 캔버스 렌더링 데이터가 PNG 이미지로 변환되어 Anthropic Claude 3.5 Sonnet Vision API에 전달된다.

Claude 3.5 Sonnet은 이미지에서 시스템 구성 요소(서버, 데이터베이스, 캐시, 로드 밸런서, 메시지 큐 등), 구성 요소 간의 관계(데이터 흐름, API 호출, 이벤트 전파 등), 텍스트 레이블(서비스명, 프로토콜명, 포트 번호 등)을 인식하고, 이를 시스템 설계 원칙에 비추어 분석한다.

### 5.6.2 아키텍처 평가 기준 및 피드백

Claude Vision의 분석 프롬프트에는 5개의 평가 기준이 명시된다. 확장성(Scalability)은 시스템이 트래픽 증가에 따라 수평적으로 확장 가능한가를 평가한다. 가용성(Availability)은 단일 장애 지점(Single Point of Failure)이 존재하는가, 장애 복구 전략이 설계에 포함되어 있는가를 평가한다. 데이터 일관성(Data Consistency)은 분산 환경에서 데이터의 일관성 보장 전략(예: 이벤추얼 컨시스턴시, Strong Consistency)이 적절한가를 평가한다. 보안(Security)은 인증, 암호화, 네트워크 격리 등 보안 요소가 설계에 반영되어 있는가를 평가한다. 성능(Performance)은 캐싱, 비동기 처리, 부하 분산 등 성능 최적화 전략이 포함되어 있는가를 평가한다.

각 기준에 대해 점수(1~5점)와 구체적 피드백이 생성되며, "이 설계에서 가장 우려되는 부분"과 "개선 제안"이 함께 제공된다. 이는 실제 시스템 설계 면접에서 면접관이 제공하는 피드백의 형식과 깊이를 재현한 것이다.

---

## 5.7 종합 리포팅

### 5.7.1 Recharts 인터랙티브 대시보드 (7종 차트)

면접 결과 리포트 페이지에서는 7종의 인터랙티브 차트가 Recharts 및 Chart.js 라이브러리를 통해 제공된다.

레이더 차트(RadarChart)는 5축 언어 평가(문제해결력, 논리성, 기술이해도, STAR, 전달력)를 다각형 그래프로 시각화하여, 지원자의 강점과 약점 영역을 한눈에 파악할 수 있게 한다. 바 차트(BarChart)는 각 질문별 평가 점수의 분포를 막대 그래프로 표시하여, 면접 전체 과정에서의 성과 추이를 보여준다. STAR 구조 분석 차트는 Situation, Task, Action, Result 각 요소의 출현 빈도를 시각화하여, 지원자의 STAR 기법 활용도를 평가한다. 감정 분포 파이 차트(PieChart)는 DeepFace 기반 7가지 감정의 전체 분포를 원형 차트로 표시한다. 키워드 빈도 차트는 답변에서 추출된 기술 키워드의 출현 빈도를 수평 바 차트로 시각화한다. 발화 속도 시계열 영역 차트(AreaChart)는 턴별 SPM 변화를 시간축 그래프로 표시하여, 면접 진행에 따른 발화 패턴 변화를 보여준다. 시선 방향 분포 차트(RadialBarChart)는 center, left, right, up, down, away 6방향의 시선 분포를 방사형 차트로 시각화한다.

각 차트는 마우스 오버 시 세부 데이터를 표시하는 Tooltip과 범례(Legend) 인터랙션을 지원하여, 지원자가 자신의 면접 수행 패턴을 직관적으로 탐색하고 이해할 수 있다.

### 5.7.2 PDF 리포트 생성 (ReportLab)

면접 종료 후 종합 평가 리포트는 pdf_report_service.py 모듈이 ReportLab 라이브러리를 활용하여 PDF 형식으로 자동 생성한다. PDF 리포트에는 다음 항목이 포함된다.

지원자 정보 및 면접 일시, 면접 개요(총 질문 수, 총 답변 수, 평균 답변 길이, 면접 소요 시간), 5축 언어 평가 상세(각 축의 점수, 축별 피드백, 강점 및 개선점), 비언어 분석 결과(감정 분포, 시선 추적 등급, 발화 속도 등급, Prosody 복합 점수), STAR 기법 분석(각 요소의 출현 빈도 및 종합 점수), 기술 키워드 분석(언급된 기술 스택과 빈도), 합격/불합격 판정 및 사유, 개선 권고사항(맞춤형 학습 제안)이 포함된다.

ReportLab의 Platypus 레이아웃 엔진을 사용하여 표, 문단, 목록 등의 다양한 레이아웃 요소가 조합되며, 한국어 폰트(NanumGothic 등) 지원을 통해 한글 텍스트가 정확하게 렌더링된다. 생성된 PDF 파일은 security.py의 AES-256-GCM 암호화 모듈을 통해 암호화되어 서버에 저장되며, 지원자가 다운로드 요청 시 복호화된 파일이 HTTP 응답으로 전달된다.

### 5.7.3 STAR 기법 분석 결과

STAR 기법 분석은 celery_tasks.py의 _analyze_star_structure() 함수에서 수행된다. STAR의 4개 요소(Situation, Task, Action, Result) 각각에 대해 사전 정의된 한국어 키워드 사전이 구성되어 있다.

Situation 키워드: 상황, 배경, 당시, 그때, 환경, 상태, 문제, 이슈, 과제 (9개)
Task 키워드: 목표, 과제, 임무, 역할, 담당, 책임, 해야 할, 목적, 미션 (9개)
Action 키워드: 행동, 수행, 실행, 처리, 해결, 개발, 구현, 적용, 진행, 시도, 노력 (11개)
Result 키워드: 결과, 성과, 달성, 완료, 개선, 향상, 증가, 감소, 효과, 성공 (10개)

지원자의 모든 답변 텍스트에서 각 요소의 키워드 출현 횟수가 카운트되며, 각 요소의 점수는 min(출현 횟수 × 25, 25)로 산출되어 최대 25점(합계 100점)으로 정규화된다. 또한 리포트에서는 각 요소별 점수를 min(출현 수 × 20, 100)으로 100점 척도에 맞추어 시각화한다.

_extract_keywords() 함수는 답변에서 기술 키워드(Python, Java, JavaScript, React, Docker, Kubernetes, AWS, PostgreSQL, LLM, RAG, LangChain, FastAPI 등 40개 이상)의 출현 빈도를 카운트하여, 지원자가 면접에서 언급한 기술 스택의 분포를 정량적으로 분석한다. 상위 10개 기술 키워드가 키워드 빈도 차트에 표시되며, 기술 키워드의 총 언급 횟수(total_tech_mentions)도 함께 제공된다.

_generate_recommendations() 함수는 평가 점수와 STAR 분석 결과를 기반으로 맞춤화된 개선 권고사항을 생성한다. 문제 해결력 3점 미만 시 "구체적인 수치와 사례 포함 권고", STAR 점수 3점 미만 시 "STAR 기법 활용 구조적 답변 권고", Result 요소 출현 빈도 2회 미만 시 "프로젝트 결과와 성과 강조 권고", 기술 이해도 3점 미만 시 "기술적 용어의 정확한 사용 연습 권고" 등의 4가지 조건부 권고가 정의되어 있으며, 모든 항목을 충족한 경우에는 "전반적으로 좋은 면접이었습니다! 자신감을 가지세요."라는 긍정적 메시지가 제공된다.

---

본 장에서 기술된 핵심 기능의 설계 및 구현은 2장의 기능적 요구사항(REQ-F-001~018)을 직접적으로 실현하는 기술적 구체물(Technical Artifact)이다. 특히 LangGraph 상태머신(5.1.2), 멀티모달 비언어 분석 파이프라인(5.4), 이력서 RAG(5.3)의 세 핵심 기능은 본 시스템을 기존의 단순 AI 면접 서비스와 차별화하는 고유한 기술적 기여(Technical Contribution)에 해당한다. 6장에서는 이러한 백엔드 기능과 상호작용하는 프론트엔드의 설계 및 구현을 상세히 기술한다.
