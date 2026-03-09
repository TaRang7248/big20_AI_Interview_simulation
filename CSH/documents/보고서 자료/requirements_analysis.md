# 2. 시스템 요구사항 분석

본 장에서는 AI 모의면접 시뮬레이션 시스템의 설계 및 구현에 앞서 수행된 요구사항 분석(Requirements Analysis)의 전 과정과 그 결과물을 체계적으로 기술한다. 요구사항 분석은 소프트웨어 공학의 가장 핵심적인 선행 단계로서, 시스템이 *무엇을(What)* 수행해야 하는가를 명확히 정의함으로써 이후의 아키텍처 설계, 기술 스택 선정, 구현 및 검증 단계의 일관성을 보장하는 지적 기반을 형성한다. 본 프로젝트의 요구사항 도출은 면접 준비자(Candidate), 채용담당자(Recruiter), 시스템 운영자(Operator)의 세 이해관계자 관점을 동시에 고려하여 진행되었으며, 기능적 요구사항(Functional Requirements)과 비기능적 요구사항(Non-Functional Requirements)으로 이원화하여 상세 명세화하였다.

---

## 2.1 기능적 요구사항 (Functional Requirements)

기능적 요구사항은 시스템이 반드시 제공해야 하는 구체적 기능과 행동(Behavior)을 기술한다. 본 시스템의 기능적 요구사항은 크게 다섯 개의 기능 도메인으로 분류되며, 각 도메인 내에서 핵심 요구항목(REQ-F)을 식별자를 통해 추적 가능하게 관리한다.

### 2.1.1 AI 면접 수행 기능 (REQ-F-001 ~ REQ-F-005)

AI 면접 수행 기능은 본 시스템의 핵심 가치를 구현하는 최상위 기능 도메인으로, 지원자와 AI 면접관 사이의 자연스러운 대화형 면접 세션을 생성·유지하고, 면접의 전체 생명주기를 관리하는 일련의 요구사항을 포함한다.

#### REQ-F-001: 적응형 면접 질문 생성

시스템은 대규모 언어 모델(LLM)을 활용하여 지원자의 답변 맥락과 이력서 정보에 기반한 적응형(Adaptive) 질문을 동적으로 생성하여야 한다. 단순히 사전에 준비된 질문 풀(Question Pool)에서 무작위로 질문을 선택하는 정적(Static) 방식과 달리, 본 시스템은 지원자가 이전에 제공한 답변의 내용, 품질, 주제를 실시간으로 분석하여 다음 질문의 유형, 난이도, 주제 영역을 동적으로 결정하는 메커니즘을 구현한다.

구체적으로, 본 시스템은 EXAONE 3.5 7.8B 파라미터 모델을 Ollama 런타임을 통해 로컬 환경에서 서빙하여 면접 질문 생성에 활용한다. 질문 생성 시에는 지원자의 이력서 정보에서 추출된 RAG(Retrieval-Augmented Generation) 컨텍스트, 이전 대화 이력(Chat History), 지원자의 실시간 감정 상태(Emotion Adaptive Mode), 현재 주제 영역(Current Topic) 및 주제 내 질문 횟수(Topic Question Count) 등 다차원적 컨텍스트 정보가 LLM 프롬프트에 체계적으로 주입된다. 이를 통해 생성된 질문은 해당 지원자의 경험과 역량에 특화된 고도로 맞춤화된(Personalized) 질문으로, 일반적인 AI 면접 시스템에서 관찰되는 획일적 질문 패턴의 한계를 극복한다.

또한 LLM의 출력 후처리(Post-processing) 단계에서 복수 질문 생성 방지(`extract_single_question`), 사고 토큰 제거(`strip_think_tokens`: EXAONE Deep의 `<thought>` 태그 및 Qwen3의 `<think>` 태그), 한국어 출력 품질 가드(Korean Guard: 한글 비율 ≥ 60% 강제) 등의 방어적 처리가 적용되며, LLM_TIMEOUT_SEC(기본 60초) 내에 응답이 없는 경우 사전 정의된 폴백(Fallback) 질문으로 자동 전환하여 시스템의 가용성을 유지한다.

#### REQ-F-002: 꼬리질문(Follow-up Question) 메커니즘

시스템은 지원자의 답변 품질과 깊이를 분석하여, 불충분하거나 추가 탐색이 필요한 경우 자동으로 꼬리질문을 생성하고 해당 주제를 심화하는 기능을 제공하여야 한다. 이 기능은 실제 인간 면접관이 지원자의 답변에 즉각 반응하여 구체적인 경험이나 논리적 근거를 추가로 요청하는 행위를 모사함으로써, 면접의 현실감(Realism)을 크게 높이는 핵심 요소이다.

꼬리질문 생성 여부의 판단은 `should_follow_up()` 함수를 통해 이루어지며, 해당 함수는 지원자의 답변 텍스트의 길이, 키워드 밀도, 구체성(Specificity) 등을 분석하여 추가 탐색의 필요성을 평가한다. 동시에 주제 반복 방지를 위한 `topic_question_count` 카운터가 도입되어, 동일 주제에 대한 꼬리질문은 최대 2회로 제한되며, 이 횟수 초과 시 자동으로 새로운 질문 주제로 전환된다. 또한 지원자의 감정 상태가 격려 모드(Encouraging Mode)로 판별될 경우, 추가적인 압박을 줄 수 있는 꼬리질문은 자동으로 완화되어 지원자가 과도한 스트레스 없이 면접에 임할 수 있도록 배려하는 인간 중심(Human-Centered) 설계가 반영되어 있다.

#### REQ-F-003: LangGraph 기반 면접 상태머신 (10 Phase)

시스템은 면접의 전체 진행 흐름을 유한 상태 기계(Finite State Machine, FSM)로 모델링하고 관리하여야 한다. 면접 프로세스는 시작(Start)에서 종료(End)에 이르기까지 명확히 정의된 상태(Phase) 간 전이(Transition)를 통해 진행되며, 각 상태에서의 입력과 조건에 따라 결정론적으로(Deterministically) 다음 상태가 결정되어야 한다.

본 시스템은 LangGraph 프레임워크를 활용하여 면접 워크플로우를 구현하며, 총 10개의 면접 단계(Phase)를 정의한다. 각 Phase는 `InterviewPhase` 열거형(Enum)으로 명세화되며, 구체적으로는 `IDLE`(초기 대기), `GREETING`(인사 및 자기소개 요청), `GENERATE_QUESTION`(LLM 질문 생성), `WAIT_ANSWER`(사용자 답변 대기), `PROCESS_ANSWER`(답변 수신 및 전처리), `EVALUATE`(답변 평가 및 비언어 분석 병렬 실행), `ROUTE_NEXT`(조건부 분기 라우팅), `FOLLOW_UP`(꼬리질문 생성), `COMPLETE`(면접 종료 및 보고서 생성 트리거), `ERROR`(오류 복구)로 구성된다.

각 Phase 간의 전이 로직은 LangGraph의 `add_conditional_edges` 기능을 통해 구현되며, 조건부 분기의 판단 기준으로는 질문 횟수(`question_count`)와 최대 질문 수(`max_questions`)의 비교, 꼬리질문 필요 여부(`needs_follow_up`), 지원자의 감정 적응 모드(`emotion_adaptive_mode`) 등이 활용된다. MemorySaver 체크포인트 메커니즘을 통해 세션의 중단 및 재개(Resume) 기능이 지원되며, 전체 실행 과정은 `WorkflowState` TypedDict 자료구조를 통해 단일 상태 컨텍스트로 관리된다. 각 노드의 실행 시간, 타임스탬프, 주요 판단 근거는 `trace` 필드에 감사 기록(Audit Log)으로 누적되어, 사후 분석 및 디버깅에 활용 가능하다.

#### REQ-F-004: 이력서 RAG 기반 맞춤형 컨텍스트 제공

시스템은 지원자가 업로드한 이력서(PDF) 문서를 벡터화하여 데이터베이스에 저장하고, 면접 질문 생성 시 지원자의 경력, 보유 기술, 프로젝트 경험 등 개인화된 정보를 LLM에 컨텍스트로 실시간 제공하는 RAG 파이프라인을 구현하여야 한다. 이를 통해 AI 면접관이 지원자 개인에 특화된 질문을 생성하는 것이 가능해지며, 일반적인 AI 면접 시스템에서 지적되는 몰개성(Impersonalized)적 질문의 문제를 근본적으로 해결한다.

본 기능의 구현은 `resume_rag.py` 서비스 모듈에 담당되며, PDF 파싱, 텍스트 청킹(Chunking), nomic-embed-text 모델을 통한 768차원 임베딩 생성, pgvector 확장을 통한 벡터 저장 및 코사인 유사도 기반 검색의 전체 파이프라인으로 구성된다. 검색 쿼리는 `search_query:` 접두사를 추가하여 nomic-embed-text 모델의 비대칭 검색(Asymmetric Search) 최적화 특성을 활용하며, 검색 결과는 Redis 캐시(TTL: 30분)에 저장되어 반복 검색에 의한 GPU 부하를 최소화한다. 동일 세션 내에서 이미 조회된 RAG 컨텍스트의 재활용을 통해, GPU 메모리 경합(VRAM Contention)이 발생하기 쉬운 저사양 환경에서도 전체 파이프라인의 지연 시간을 최소화하는 최적화 전략이 적용된다.

#### REQ-F-005: SSE 기반 실시간 답변 스트리밍 및 VAD Turn-taking

시스템은 LLM이 생성하는 면접 질문 텍스트를 토큰 단위로 클라이언트에 실시간 전송하는 SSE(Server-Sent Events) 스트리밍 방식을 채택하여야 한다. 이는 LLM 추론 완료까지의 긴 대기 시간(Time-to-first-token 문제)을 사용자가 직접적으로 인지하지 못하도록 함으로써, 마치 면접관이 실시간으로 질문을 입력하는 듯한 자연스러운 사용자 경험(UX)을 제공한다.

아울러 VAD(Voice Activity Detection) 메커니즘을 기반으로 한 Turn-taking 시스템이 구현되어야 한다. 시스템은 지원자의 발화 시작과 종료를 자동으로 감지하고, 발화 종료 감지 시 STT 변환 결과를 LLM에 전달하여 다음 질문 생성 파이프라인을 개시한다. 이 과정은 지원자가 별도의 버튼 조작 없이 자연스러운 발화 흐름만으로 면접을 진행할 수 있게 하며, 인간 면접관과의 대화에서 경험하는 자연스러운 대화 리듬을 최대한 재현한다.

---

### 2.1.2 비언어 행동 분석 기능 (REQ-F-006 ~ REQ-F-009)

비언어 행동 분석은 전통적 면접에서 인간 면접관의 직관에만 의존하던 지원자의 감정 상태, 시선 처리, 발화 특성 등을 AI 기술을 통해 객관적으로 정량화하는 핵심 기능 도메인이다. 본 시스템은 멀티모달(Multimodal) 비언어 분석 파이프라인을 통해 면접 전체 과정에서 지원자의 비언어적 신호를 지속적으로 수집하고 분석한다.

#### REQ-F-006: 표정 감정 분석 (DeepFace)

시스템은 WebRTC를 통해 수신되는 지원자의 실시간 비디오 스트림에서 1초 간격으로 프레임을 추출하여, DeepFace 라이브러리를 통한 표정 감정 분석을 수행하여야 한다. DeepFace는 happiness(행복), sadness(슬픔), anger(분노), fear(공포), surprise(놀람), disgust(혐오), neutral(중립)의 7가지 기본 감정(Basic Emotions)을 분류하며, 각 감정에 대한 신뢰도 점수(Confidence Score)와 지배적 감정(Dominant Emotion)을 실시간으로 출력한다.

분석 결과는 면접 워크플로우의 감정 적응 모드(Emotion Adaptive Mode) 결정에 직접 반영된다. 지배적 감정이 부정적(sad, fear, disgust)으로 판별될 경우 시스템은 격려 모드(Encouraging Mode)로 전환하여 꼬리질문을 완화하고, 긍정적(happy, surprise) 감정이 감지될 경우 도전 모드(Challenging Mode)로 전환하여 심화 질문을 강화한다. 분석 작업은 `VISION_EXECUTOR`(max_workers=2) ThreadPoolExecutor를 통해 비동기적으로 처리되어, 메인 이벤트 루프의 블로킹 없이 실시간 분석이 수행된다.

#### REQ-F-007: 시선 추적 분석 (OpenCV + GazeTrackingService)

시스템은 DeepFace 분석 결과에서 추출된 얼굴 영역(Face Region) 정보를 활용하여 지원자의 시선 방향을 추정하고, 면접 전체 과정에서의 눈 접촉(Eye Contact) 비율을 산출하여야 한다. `GazeTrackingService` 모듈은 얼굴 바운딩 박스의 중심 좌표를 프레임 대비 상대적 위치로 정규화하고, 프레임 중앙으로부터 ±20% 이내의 편차를 '정면 응시(Center)'로 판정하는 휴리스틱 알고리즘을 채택한다. 이보다 벗어난 경우 편차의 방향 및 크기에 따라 left, right, up, down, away의 5가지 방향으로 분류된다.

시선 등급은 정면 응시 비율에 따라 S/A/B/C/D의 5단계로 평가되며, 면접 적정 정면 응시 비율은 60~85%로 설정된다. 100% 정면 응시는 역설적으로 부자연스러움(Unnaturalness)으로 판정될 수 있으므로, 상한 임계값(85%)이 별도로 설정된다. 턴(Turn)별 시선 통계는 `GazeTurnStats` 데이터 클래스에, 세션 전체 통계는 `SessionGazeStats` 데이터 클래스에 누적 집계되며, 시선 안정성(Consistency Score)은 턴별 정면 응시 비율의 표준편차로 산출된다.

#### REQ-F-008: 발화 속도 분석 (SPM 기반)

시스템은 STT 변환 결과를 기반으로 지원자의 발화 속도(Speech Rate)를 분당 음절 수(Syllables Per Minute, SPM)로 측정하고, 이를 5개 등급으로 분류하는 기능을 제공하여야 한다. 발화 속도의 정량적 측정은 `speech_analysis_service.py` 모듈에서 담당하며, STT 변환 결과의 텍스트를 한국어 형태소 분석을 거쳐 음절 단위로 분리한 후, 발화 구간의 경과 시간으로 나누어 SPM을 산출한다. 측정된 SPM은 '매우 느림(Very Slow)', '느림(Slow)', '적정(Appropriate)', '빠름(Fast)', '매우 빠름(Very Fast)'의 5단계로 분류되며, 각 등급에 대한 정성적 평가 피드백도 함께 생성된다.

#### REQ-F-009: Hume AI Prosody 음성 감정 분석

시스템은 지원자의 발화 오디오에 대해 Hume AI Prosody API를 통한 심층 음성 감정 분석을 수행하여야 한다. Hume AI Prosody API는 인간의 발화에서 억양(Intonation), 강세(Stress), 리듬(Rhythm), 속도 변화(Tempo Variation) 등 초분절적(Suprasegmental) 특성을 분석하여, 48종의 기본 감정 중 면접 맥락에서 의미 있는 10개 핵심 지표(자신감/Confidence, 흥미/Interest, 집중/Focus, 편안함/Comfort, 불안/Anxiety, 열정/Enthusiasm, 망설임/Hesitation, 명확성/Clarity, 스트레스/Stress, 전반적 긍정성/Positivity)를 추출한다.

Prosody 분석 결과는 DeepFace 표정 감정 분석 결과와 가중 융합(Weighted Fusion)되어 최종 감정 적응 모드를 결정하는 멀티모달 융합(Multimodal Fusion) 프로세스에 활용된다. 융합 가중치는 Prosody 50%, DeepFace 50%로 설정되어(코드 내 구현은 prosody_weight=0.5), 음성과 영상의 이중 채널 감정 정보를 균형 있게 통합하는 방식을 채택한다. Prosody 분석 결과가 DeepFace 없이 단독으로 활용 가능한 경우(예: 비디오가 비활성화된 텍스트 전용 모드), Prosody 분석 결과만을 기반으로 감정 적응 모드가 결정된다.

---

### 2.1.3 기술 역량 평가 기능 (REQ-F-010 ~ REQ-F-012)

기술 역량 평가 기능은 소프트웨어 엔지니어 채용에서 필수적인 코딩 역량과 시스템 설계 능력을 객관적으로 측정하기 위한 기능 도메인으로, 코딩 테스트 환경과 화이트보드 시스템 설계 평가 환경을 통합하여 제공한다.

#### REQ-F-010: 다국어 코딩 테스트 및 Docker 샌드박스 실행

시스템은 Python, JavaScript, Java, C, C++의 5개 프로그래밍 언어를 지원하는 온라인 코딩 테스트 환경을 제공하며, 지원자가 작성한 코드를 격리된(Isolated) Docker 컨테이너 샌드박스 환경에서 안전하게 실행하여야 한다. `code_execution_service.py` 모듈이 이 기능을 담당하며, 각 코드 실행 요청마다 독립적인 Docker 컨테이너가 생성되어 지원자의 코드가 호스트 시스템이나 다른 지원자의 실행 환경에 접근하거나 영향을 주지 못하도록 원천 차단된다. 컨테이너는 엄격한 타임아웃(제한 시간) 내에 실행 결과(표준 출력, 표준 오류, 반환 코드)를 반환하며, 타임아웃 초과 시 강제 종료된다.

코딩 문제는 Qwen3-Coder-30B-A3B 모델에 의해 지정된 난이도에 따라 동적으로 생성되며, 단순 출력 문제부터 자료구조·알고리즘을 응용하는 복합 문제까지 다양한 난이도 스펙트럼을 제공한다. 문제 생성 결과는 Celery의 `pre_generate_coding_problem_task`를 통해 사전 생성(Pre-generation)되어 Redis에 캐싱됨으로써, 지원자가 코딩 테스트를 시작하는 시점에 즉각적인 문제 제공이 가능하도록 최적화된다.

#### REQ-F-011: AI 코드 분석 및 피드백 (Qwen3-Coder)

시스템은 지원자가 제출한 코드에 대해 Qwen3-Coder-30B-A3B 모델을 활용한 심층적 AI 코드 분석을 수행하고, 코드의 정확성(Correctness), 시간 복잡도(Time Complexity), 공간 복잡도(Space Complexity), 코드 품질(Code Quality), 엣지 케이스(Edge Case) 처리 등 다차원적 관점에서 평가 피드백을 생성하여야 한다. 생성된 피드백은 코딩 테스트 결과 페이지에서 지원자에게 제공되며, 단순한 정오(正誤) 판정을 넘어 코드 개선 방향을 제시하는 교육적(Educational) 가치를 함께 지닌다.

#### REQ-F-012: 화이트보드 시스템 설계 평가 (Claude Vision)

시스템은 지원자가 화이트보드 인터페이스를 통해 그린 시스템 설계 다이어그램을 실시간으로 캡처하여, Anthropic Claude 3.5 Sonnet 비전 모델에 전달하고, 해당 다이어그램에 대한 아키텍처 평가 피드백을 생성하는 기능을 제공하여야 한다. 평가 기준은 시스템의 확장성(Scalability), 가용성(Availability), 데이터 일관성(Data Consistency), 보안(Security), 성능(Performance) 등 실제 시스템 설계 면접에서 평가되는 핵심 차원을 준용한다. `whiteboard_service.py` 모듈이 캔버스 렌더링 데이터의 이미지 변환 및 Claude API 호출을 담당한다.

---

### 2.1.4 종합 평가 리포팅 기능 (REQ-F-013 ~ REQ-F-015)

종합 평가 리포팅 기능은 면접 전체 과정에서 수집된 언어적·비언어적 평가 데이터를 통합 집계하고, 지원자의 종합 역량을 다차원적으로 시각화하여 제공하는 기능 도메인이다.

#### REQ-F-013: 5축 언어 평가 및 통합 점수 산출

시스템은 지원자의 각 답변에 대해 LLM을 통한 5개 축(Axis)의 정량적 언어 평가를 수행하여야 한다. 5개 축은 문제해결력(Problem-Solving Ability), 논리성(Logical Coherence), 기술이해도(Technical Comprehension), STAR 기법 구조 준수(STAR Methodology Compliance), 전달력(Communication Clarity)으로 구성된다. 각 축은 1.0~5.0의 연속형 점수 척도로 평가되며, 이 5개 축 점수의 가중 평균이 언어 평가 점수를 구성한다.

최종 통합 점수는 언어 평가 점수와 비언어 평가 점수를 언어 60% : 비언어 40%의 비율로 가중 합산하여 산출하며, 비언어 평가는 발화 속도(SPM), 시선 추적(Eye Contact Ratio), 감정 안정성(Emotional Stability: DeepFace 기반), Prosody 복합 점수(Hume AI 기반)의 4개 축으로 구성된다. 합격/불합격 이진 판정은 최종 점수가 4.0 이상이고(AND), 총점이 20점 이상이며(AND), 5.0 만점 척도에서 저점수(1.0 미만) 항목이 없는 경우 합격으로 판정하는 엄격한 복합 조건 로직을 적용한다.

#### REQ-F-014: 인터랙티브 시각화 대시보드 (Recharts)

시스템은 면접 평가 결과를 7종의 인터랙티브 차트로 시각화하여 제공하여야 한다. 레이더 차트(5축 언어 평가 종합), 바 차트(답변별 점수 분포), STAR 구조 분석 차트, 감정 분포 파이 차트(DeepFace 기반 7감정 분포), 키워드 빈도 차트, 발화 속도 시계열 영역 차트, 시선 방향 분포 차트(방사형)가 Recharts 라이브러리를 통해 구현된다. 각 차트는 마우스 오버 툴팁 및 클릭 인터랙션을 지원하는 인터랙티브(Interactive) 방식으로 제공되어, 지원자가 자신의 면접 수행 패턴을 직관적으로 파악할 수 있다.

#### REQ-F-015: PDF 리포트 자동 생성

시스템은 면접 종료 후 평가 데이터를 취합하여 PDF 형식의 종합 평가 리포트를 자동 생성하고, 지원자가 이를 다운로드할 수 있는 기능을 제공하여야 한다. `pdf_report_service.py` 모듈이 ReportLab 라이브러리를 활용하여 PDF 생성을 담당하며, 리포트에는 지원자 정보, 면접 일시, 질문별 답변 요약, 5축 언어 평가 상세, 비언어 분석 결과, 합격/불합격 판정 및 개선 권고사항이 포함된다. 생성된 PDF 파일은 AES-256-GCM 알고리즘으로 암호화되어 서버에 저장됨으로써 개인정보 보호 요건을 충족한다.

---

### 2.1.5 사용자 관리 기능 (REQ-F-016 ~ REQ-F-018)

#### REQ-F-016: 인증 및 인가 (Authentication & Authorization)

시스템은 이메일/비밀번호 기반의 자체 인증과 소셜 로그인(OAuth2)을 통한 사용자 인증 체계를 구현하여야 한다. 비밀번호는 bcrypt 알고리즘(work factor: rounds=12)을 통해 해싱되어 저장되며, 기존 SHA-256 해시로 저장된 사용자의 경우 로그인 성공 시 자동으로 bcrypt로 재해싱(Re-hashing)하는 마이그레이션 메커니즘이 적용된다. JWT(JSON Web Token) HS256 알고리즘을 통해 액세스 토큰이 발급되며(기본 유효 시간: 120분), FastAPI의 `Depends()` 의존성 주입 메커니즘을 통한 보호 엔드포인트 접근 제어가 구현된다. 소셜 로그인은 카카오(Kakao), 구글(Google), 네이버(Naver)의 3개 OAuth2 제공자를 지원한다.

#### REQ-F-017: 채용공고 관리 및 이력서 업로드

시스템은 채용담당자가 채용공고를 생성·조회·수정·삭제(CRUD Operation)할 수 있는 기능과, 지원자가 PDF 형식의 이력서를 업로드하여 RAG 파이프라인에 활용될 수 있도록 하는 기능을 제공하여야 한다. 업로드된 이력서 파일은 Celery의 `process_resume_task`를 통해 비동기적으로 처리되며, 파싱 → 청킹 → 임베딩 → pgvector 저장의 4단계 파이프라인이 백그라운드에서 실행된다. 처리 완료 후에는 EventBus를 통해 처리 완료 이벤트가 발행되어 프론트엔드에 실시간 알림이 전달된다.

#### REQ-F-018: GDPR 준수 개인정보 전체 삭제

시스템은 사용자의 요청에 따라 해당 사용자와 관련된 모든 개인 데이터(사용자 계정 정보, 면접 세션 데이터, 평가 결과, 이력서 벡터, 녹화 파일, Redis 캐시, 암호화된 파일 포함)를 완전히 삭제하는 기능을 제공하여야 한다. 이는 GDPR 제17조에서 규정하는 '잊힐 권리(Right to be Forgotten)'를 구현하는 것으로, 단순한 데이터베이스 레코드 삭제뿐만 아니라 모든 연관 저장소에서의 완전한 데이터 소거(Purge)를 보장한다.

---

## 2.2 비기능적 요구사항 (Non-Functional Requirements)

비기능적 요구사항은 시스템이 *어떻게(How)* 동작해야 하는가, 즉 시스템의 품질 속성(Quality Attributes)을 규정한다. 이는 기능적 요구사항만큼이나 중요하며, 특히 실시간 AI 처리를 근간으로 하는 본 시스템에서 비기능적 요구사항의 충족 여부는 시스템의 실사용 가능성(Viability)을 결정하는 핵심 요인이다.

### 2.2.1 응답 시간 및 SLA (REQ-N-001)

**SLA(Service Level Agreement) 정의**: 시스템은 지원자의 발화 종료(STT UtteranceEnd 이벤트 수신 시점)부터 AI 면접관의 TTS 음성 응답이 출력되기 시작하는 시점까지의 전체 파이프라인 지연(End-to-End Latency)을 **1.5초 이내**로 유지하여야 한다. 이 파이프라인은 STT 후처리 → VAD 감지 → RAG 컨텍스트 조회 → LLM 추론 → TTS 합성의 다단계 직렬 처리를 포함하며, 각 단계의 처리 지연이 누적되어 최종 사용자 경험에 영향을 미친다.

SLA 모니터링은 `latency_monitor.py`의 `LatencyMonitor` 싱글톤 인스턴스를 통해 실시간으로 수행된다. FastAPI 미들웨어 레이어에서 모든 `/api/**` 요청의 응답 시간이 자동 측정되고, 핵심 파이프라인(RAG 조회, LLM 추론, TTS 합성) 내의 단계별 소요 시간은 `start_phase()`/`end_phase()` API를 통해 수동 계측된다. SLA 임계값(1.5초) 초과 시 즉각적인 경고 로그가 출력되며, SLA 위반 내역은 최근 200건까지 별도 이력으로 보관된다. 모니터링 데이터는 `/api/monitoring/latency` 엔드포인트를 통해 조회 가능하여, 운영 중 성능 병목 지점의 식별 및 개선에 활용된다.

LLM 추론 지연 최소화를 위해 LLM_TIMEOUT_SEC(기본 60초) 타임아웃 메커니즘과 함께, Ollama를 통한 로컬 GPU(GTX 1660, VRAM 6GB) 서빙 환경에서 GPU 메모리 경합을 방지하기 위한 `LLM_EXECUTOR`(max_workers=2), `RAG_EXECUTOR`(max_workers=2) 등의 Threading 전략이 적용된다.

### 2.2.2 보안 요구사항 (REQ-N-002 ~ REQ-N-004)

#### REQ-N-002: 전송 계층 보안 (TLS)

외부 네트워크를 통해 전송되는 모든 데이터는 TLS(Transport Layer Security) 1.2 이상의 프로토콜로 암호화되어야 한다. 특히 WebRTC 미디어 스트림은 DTLS(Datagram TLS) 계층에서 자동으로 암호화되며, REST API 통신은 NGINX에서 TLS 종료(TLS Termination)를 담당한다. 개발 환경에서는 `security.py`의 `generate_self_signed_cert()` 유틸리티를 통해 RSA-2048 자체 서명 인증서를 자동 생성하여 사용하며, 운영 환경에서는 공인 인증서(CA-signed Certificate)로 교체되어야 한다.

#### REQ-N-003: 저장 데이터 암호화 (AES-256-GCM)

시스템에 영구 저장되는 모든 민감 데이터(이력서 파일, 면접 녹화 파일, PDF 리포트 등)는 AES-256-GCM(Galois/Counter Mode) 알고리즘으로 암호화하여야 한다. AES-GCM은 기밀성(Confidentiality)과 무결성(Integrity)을 동시에 보장하는 AEAD(Authenticated Encryption with Associated Data) 방식으로, 단순 AES-CBC 대비 암호문 변조 공격(Tampering Attack)에 대한 내성을 갖는다. 암호화 키(256비트)는 환경변수 `AES_ENCRYPTION_KEY`에서 Base64 인코딩된 형태로 로드되며, 각 파일 암호화 시 12바이트의 고유 IV(Initialization Vector)가 생성되어 동일 데이터의 반복 암호화에서도 상이한 암호문이 생성된다. 암호화된 파일은 `AESF` 매직 바이트 헤더, 버전 정보, IV, 16바이트 인증 태그(GCM Tag), 암호문의 구조로 직렬화된다.

#### REQ-N-004: API 보안 (CORS, Rate Limiting, 인가)

시스템은 Cross-Origin Resource Sharing(CORS) 정책 설정을 통해 허가되지 않은 도메인에서의 API 접근을 차단하여야 하며, FastAPI `Depends(get_current_user)` 의존성을 통해 보호 API 엔드포인트(16개 이상)에 대한 JWT 기반 인가(Authorization) 검증을 수행하여야 한다. 중요 데이터 접근 API에 대해서는 Rate Limiting을 적용하여 무차별 대입 공격(Brute-Force Attack)을 방지한다.

### 2.2.3 확장성 및 가용성 (REQ-N-005 ~ REQ-N-006)

#### REQ-N-005: 수평적 확장성 (Horizontal Scalability)

Celery 기반 비동기 태스크 처리 아키텍처는 수평적 확장(Horizontal Scaling)을 지원하도록 설계되어야 한다. 현재 구현은 Docker Compose를 통한 단일 호스트 배포를 기본으로 하나, Celery의 분산 큐 구조는 워커(Worker) 프로세스의 수평적 추가만으로 처리 용량을 증가시킬 수 있도록 설계된다. 6개의 전용 큐(llm_evaluation, emotion_analysis, report_generation, tts_generation, rag_processing, question_generation)를 통해 서로 다른 AI 서비스의 부하가 격리되어, 특정 서비스의 부하 증가가 다른 서비스의 처리 성능에 영향을 미치지 않도록 하는 큐 격리(Queue Isolation) 전략이 적용된다.

#### REQ-N-006: Graceful Degradation (점진적 성능 저하)

외부 AI 서비스나 내부 서비스 구성 요소에 장애가 발생하더라도, 시스템은 완전히 중단되지 않고 핵심 기능을 유지하며 서비스를 지속 제공하는 점진적 성능 저하(Graceful Degradation) 설계를 따라야 한다. 구체적 폴백(Fallback) 전략은 다음과 같이 정의된다.

- **STT 서비스 폴백**: Deepgram Nova-3 API 장애 시 → OpenAI Whisper 로컬 모델 자동 전환
- **AES 암호화 폴백**: 암호화 라이브러리 오류 시 → 원본 파일 그대로 저장 (암호화 없이 운영 유지)
- **Redis 연결 실패**: Redis 불가 시 → EventBus 로컬 모드 전환 (인프로세스 핸들러만 동작)
- **Celery 미가용**: Celery 워커 장애 시 → 평가 작업을 `deferred` 상태로 세션에 저장 후 면접 종료 시 일괄 처리
- **LLM 타임아웃**: LLM 추론 60초 초과 시 → 사전 정의된 폴백 질문으로 즉시 전환

### 2.2.4 실시간성 (REQ-N-007)

시스템은 면접 대화의 자연스러운 흐름을 보장하기 위해, 아래의 실시간 통신 프로토콜 스택을 지원하여야 한다.

- **WebRTC (aiortc)**: 지원자의 비디오/오디오 스트림을 서버로 전달하는 실시간 미디어 통신 채널. SFU(Selective Forwarding Unit) 아키텍처를 통해 서버 측에서 미디어를 수신하여 STT 및 감정 분석에 활용하며, DTLS로 전송 구간을 암호화한다.
- **WebSocket**: 면접 진행 중 발생하는 실시간 이벤트(STT 중간 결과, 질문 텍스트, 감정 분석 결과, 시스템 알림 등)를 서버에서 클라이언트로 실시간 전달하는 양방향 통신 채널.
- **SSE (Server-Sent Events)**: LLM이 생성하는 면접 질문 텍스트를 토큰 단위로 클라이언트에 스트리밍하는 서버-클라이언트 단방향 푸시 채널. HTTP/1.1 기반으로 동작하며 자동 재연결(Auto-reconnect) 기능을 내장한다.

세 프로토콜의 협력적 운용을 통해, 비디오/오디오 스트리밍, 텍스트 이벤트 알림, LLM 응답 스트리밍이 동시에 비간섭적으로(Non-interfering) 처리되는 멀티채널 실시간 통신 환경이 구현된다.

---

## 2.3 유스케이스 다이어그램 및 시나리오

### 2.3.1 주요 액터(Actor) 정의

본 시스템에 참여하는 주요 액터는 다음과 같이 정의된다.

| 액터 | 유형 | 설명 |
|------|------|------|
| **지원자(Candidate)** | 인간 액터 | 면접 연습을 목적으로 시스템에 접근하는 취업 준비생 또는 이직 희망자 |
| **채용담당자(Recruiter)** | 인간 액터 | 채용공고를 관리하고 지원자의 면접 결과를 열람하는 기업 담당자 |
| **AI 면접관(AI Interviewer)** | 시스템 액터 | LLM 및 TTS를 기반으로 면접 진행, 질문 생성, 평가를 수행하는 AI 에이전트 |
| **외부 AI API(External AI)** | 외부 시스템 | Deepgram STT, Hume AI Prosody/TTS, Anthropic Claude Vision의 외부 API 서비스 |
| **로컬 AI 모듈(Local AI)** | 외부 시스템 | Ollama 기반의 EXAONE, Qwen3-Coder, nomic-embed-text 로컬 모델 |

### 2.3.2 핵심 유스케이스 시나리오

#### UC-001: AI 화상 면접 수행

**목표**: 지원자가 AI 면접관과 실시간 화상 면접을 수행하고 종합 평가를 받는다.

**사전 조건**: 지원자가 시스템에 로그인하였고, 이력서를 업로드하여 RAG 처리가 완료된 상태이다.

**주 시나리오 (Main Flow)**:
1. 지원자가 면접 시작 버튼을 클릭하면, 시스템은 WebRTC 연결을 수립하고 LangGraph 상태머신의 `IDLE` 상태에서 `GREETING` 상태로 전이된다.
2. AI 면접관이 인사말을 생성하여 TTS를 통해 음성으로 출력하고, 동시에 SSE를 통해 텍스트를 스트리밍한다.
3. 지원자가 자기소개를 음성으로 발화하면, VAD가 발화 종료를 감지하고 Deepgram STT가 텍스트로 변환한다.
4. STT 결과가 LangGraph의 `PROCESS_ANSWER` → `EVALUATE` → `ROUTE_NEXT` 노드를 거치며 처리되는 동안, DeepFace와 Hume Prosody가 병렬로 비언어 분석을 수행한다.
5. `ROUTE_NEXT` 노드에서 꼬리질문 여부와 다음 질문 주제를 결정하여 `GENERATE_QUESTION` 또는 `FOLLOW_UP` 노드로 전이된다.
6. LLM이 RAG 컨텍스트를 포함한 맞춤형 질문을 생성하고, TTS 및 SSE를 통해 지원자에게 전달한다.
7. 3~6 단계가 최대 질문 수(기본 10회)에 도달할 때까지 반복된다.
8. 최대 질문 수 도달 시 `COMPLETE` 노드로 전이되어 면접이 종료되고, Celery를 통한 비동기 리포트 생성 워크플로우가 트리거된다.
9. 리포트 생성 완료 후 EventBus를 통해 완료 이벤트가 발행되고, WebSocket을 통해 지원자에게 리포트 열람 알림이 전달된다.

**대안 시나리오**:
- **LLM 타임아웃(60초 초과)**: 폴백 질문이 즉시 출력되어 면접 흐름을 유지한다.
- **STT 장애(Deepgram API 불가)**: Whisper 로컬 모델로 자동 전환된다.
- **지원자 감정 과부하 감지**: 격려 모드 전환으로 꼬리질문이 완화되고 다음 주제로 전환된다.

#### UC-002: 코딩 테스트 수행

**목표**: 지원자가 온라인 코딩 테스트 환경에서 문제를 풀고 AI 피드백을 받는다.

**주 시나리오**:
1. 면접 진행 중 코딩 테스트 세그먼트로 진입하면, 사전 생성된 코딩 문제가 제공된다.
2. 지원자가 코드 에디터에서 코드를 작성하고 제출한다.
3. `code_execution_service.py`가 Docker 샌드박스 컨테이너를 생성하여 코드를 안전하게 실행하고 결과를 반환한다.
4. Qwen3-Coder-30B-A3B가 코드를 분석하여 알고리즘 정확성, 복잡도, 코드 품질에 대한 상세 피드백을 생성한다.
5. 모든 분석 결과가 최종 평가 리포트에 통합된다.

### 2.3.3 요구사항 추적 행렬 (Requirements Traceability Matrix)

| 요구사항 ID | 요구사항 명칭 | 구현 모듈 | 관련 기술 |
|------------|-------------|----------|---------|
| REQ-F-001 | 적응형 질문 생성 | `integrated_interview_server.py`, `prompt_templates.py` | EXAONE 3.5, Ollama, LangChain |
| REQ-F-002 | 꼬리질문 메커니즘 | `interview_workflow.py` (`route_next`, `follow_up` 노드) | LangGraph, EXAONE 3.5 |
| REQ-F-003 | 10 Phase 상태머신 | `interview_workflow.py` | LangGraph, MemorySaver |
| REQ-F-004 | 이력서 RAG | `resume_rag.py` | nomic-embed-text, pgvector, Redis |
| REQ-F-005 | SSE 스트리밍 & VAD | `integrated_interview_server.py` | FastAPI SSE, Deepgram VAD |
| REQ-F-006 | 표정 감정 분석 | `integrated_interview_server.py` (DeepFace 호출부) | DeepFace, OpenCV, ThreadPoolExecutor |
| REQ-F-007 | 시선 추적 분석 | `gaze_tracking_service.py` | OpenCV, DeepFace Region |
| REQ-F-008 | 발화 속도 분석 | `speech_analysis_service.py` | Python SPM 계산 |
| REQ-F-009 | Prosody 감정 분석 | `hume_prosody_service.py` | Hume AI Prosody API |
| REQ-F-010 | 코딩 테스트 & 샌드박스 | `code_execution_service.py` | Docker, Qwen3-Coder |
| REQ-F-011 | AI 코드 분석 | `code_execution_service.py` | Qwen3-Coder-30B-A3B |
| REQ-F-012 | 화이트보드 설계 평가 | `whiteboard_service.py` | Claude 3.5 Sonnet Vision |
| REQ-F-013 | 5축 언어 평가 & 통합 점수 | `celery_tasks.py` (`evaluate_answer_task`) | EXAONE 3.5, Celery |
| REQ-F-014 | 시각화 대시보드 | `frontend/` (Recharts 컴포넌트) | Next.js, Recharts, Chart.js |
| REQ-F-015 | PDF 리포트 생성 | `pdf_report_service.py` | ReportLab, AES-256-GCM |
| REQ-F-016 | 인증 & 인가 | `security.py` | bcrypt, JWT HS256, OAuth2 |
| REQ-F-017 | 채용공고 & 이력서 | `integrated_interview_server.py` (CRUD API) | PostgreSQL, SQLAlchemy, Celery |
| REQ-F-018 | GDPR 데이터 삭제 | `integrated_interview_server.py` (delete endpoint) | PostgreSQL, Redis, 파일 시스템 |
| REQ-N-001 | SLA 1.5초 이내 | `latency_monitor.py` | FastAPI Middleware, 단계별 계측 |
| REQ-N-002 | TLS 보안 | `security.py`, NGINX | TLS 1.2+, DTLS (WebRTC) |
| REQ-N-003 | AES-256-GCM 암호화 | `security.py` | AES-256-GCM, cryptography |
| REQ-N-004 | API 보안 | `integrated_interview_server.py`, NGINX | CORS, JWT Depends, Rate Limiting |
| REQ-N-005 | 수평적 확장성 | `celery_app.py` | Celery, Redis, Docker Compose |
| REQ-N-006 | Graceful Degradation | 전 모듈 (폴백 로직) | 예외 처리, 폴백 전략 |
| REQ-N-007 | 실시간 통신 | `integrated_interview_server.py` | WebRTC, WebSocket, SSE |

---

본 장에서 도출된 기능적·비기능적 요구사항 및 유스케이스는 이후 3장의 시스템 아키텍처 설계의 핵심 입력 사항으로 활용된다. 특히 REQ-N-001(SLA 1.5초)과 REQ-N-006(Graceful Degradation)은 아키텍처 설계 전반에서 가장 강하게 영향을 미치는 비기능적 제약(Non-Functional Constraint)으로, 비동기 처리 아키텍처, 이벤트 기반 설계, 계층적 폴백 전략의 도입을 필연적으로 요구하게 된다. 또한 REQ-F-001~009에서 명세화된 다양한 AI 서비스의 동시 운용 요건은, 5장에서 상세히 기술될 멀티모달 AI 파이프라인 설계의 직접적인 동기를 형성한다.
