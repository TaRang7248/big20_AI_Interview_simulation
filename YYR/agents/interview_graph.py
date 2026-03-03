# (핵심) LangGraph 워크플로우 정의
import os
from dotenv import load_dotenv
load_dotenv()

from typing import Annotated, TypedDict, List, Literal
from pydantic import BaseModel, Field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# ✅ RAG 체인 (네 프로젝트에 맞게 경로 유지)
from YJH.chains.rag_chain import retrieve_interview_context


# --- 1. 상태(State) 정의 ---
RoleType = Literal["ux", "tech"]

from typing import Literal

class InterviewState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    phase: str
    question_count: int
    last_assessment: dict
    role: Literal["ux", "tech"]   # ✅ 추가


# --- 2. 구조화된 출력(Structured Output) 정의 ---
class AnswerAssessment(BaseModel):
    relevance: int = Field(description="답변이 질문 의도에 얼마나 부합하는지 (1-5점)")
    technical_accuracy: int = Field(description="기술적 정확성 (1-5점)")
    completeness: bool = Field(description="답변이 충분히 완료되었는지 여부")
    follow_up_needed: bool = Field(description="심층 질문(꼬리물기)이 필요한지 여부")
    reasoning: str = Field(description="평가 이유 및 관찰 내용")


# --- 3. 모델 초기화 ---
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7
)


# --- 4. 노드(Node) 함수 정의 ---

def _get_last_user_text(state: InterviewState) -> str:
    if not state.get("messages"):
        return ""
    last = state["messages"][-1]
    if isinstance(last, HumanMessage):
        return (last.content or "").strip()
    return ""

def _detect_role_from_thread_id(thread_id: str) -> RoleType:
    """
    ✅ 매우 단순한 기본 룰:
    - thread_id에 'ux'/'design' 있으면 ux
    - 그 외는 tech
    나중에 /chat 요청 바디에 role을 넣어 state로 전달하는 방식으로 확장 가능.
    """
    tid = (thread_id or "").lower()
    if "ux" in tid or "design" in tid:
        return "ux"
    return "tech"


def node_analyze_answer(state: InterviewState):
    """지원자의 답변을 분석하고 평가합니다. (짧은 답변 폭주 방지 포함)"""
    messages = state.get("messages", [])

    # 메시지 없거나 마지막이 시스템이면 평가 스킵
    if not messages or isinstance(messages[-1], SystemMessage):
        return {"last_assessment": {}}

    last = messages[-1]
    if isinstance(last, HumanMessage):
        user_text = (last.content or "").strip()

        # ✅ 너무 짧으면 평가 스킵하고 follow_up_needed로만 처리
        if len(user_text) < 15:
            return {
                "last_assessment": {
                    "follow_up_needed": True,
                    "reasoning": "사용자 답변이 너무 짧음",
                }
            }

    evaluator_prompt = SystemMessage(content="""
당신은 15년 차 시니어 면접관입니다.
지원자의 답변을 듣고 논리성/구체성/완성도를 평가하세요.
답변이 짧거나 모호하면 follow_up_needed=true로 설정하세요.

출력 규칙:
- 반드시 지정된 스키마(AnswerAssessment)에 맞춰 간결하게 작성하세요.
- 불필요한 장문 금지.
""".strip())

    structured_llm = llm.bind(max_tokens=800).with_structured_output(AnswerAssessment)

    try:
        response = structured_llm.invoke([evaluator_prompt] + messages[-5:])
        return {"last_assessment": response.model_dump()}
    except Exception:
        return {
            "last_assessment": {
                "follow_up_needed": True,
                "reasoning": "평가 중 오류, 재질문 필요",
            }
        }


def node_generate_question(state: InterviewState):
    """
    ✅ UX/UI + TECH 동시 지원 질문 생성 노드
    - role: ux / tech
    - intro: 환영 + 자기소개
    - 이후 단계: role에 따라 질문 스타일 분기
    - '모르겠습니다' 반복 시 폭주 방지(난이도 낮추기)
    """
    phase = state.get("phase", "intro")
    assessment = state.get("last_assessment", {})
    q_count = state.get("question_count", 0)
    role: RoleType = state.get("role", "tech")

    print("HIT node_generate_question | phase=", phase, "| role=", role)
    print("HIT node_generate_question | follow_up_needed =", (assessment or {}).get("follow_up_needed"), "| last_assessment keys =", list((assessment or {}).keys()))

    last_user_text = _get_last_user_text(state)
    dont_know = ("모르겠" in last_user_text) or ("잘 모르" in last_user_text)

        # ✅ 추가: 모르겠습니다 연속 횟수(스트릭)
    dont_know_streak = int(state.get("dont_know_streak", 0))
    if dont_know:
        dont_know_streak += 1
    else:
        dont_know_streak = 0

    # -------------------------
    # Phase 1: Intro (공통)
    # -------------------------
    if phase == "intro":
        system_prompt = f"""
        당신은 전문 면접관입니다.
        지원자가 처음 입장했습니다.
        - 긴장을 풀어주는 환영 인사
        - 30초~1분 자기소개 요청
        - 아직 깊은 기술 질문은 금지
        (현재 트랙: {role})
        """.strip()

        msg = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="면접관님 안녕하세요, 면접 보러 왔습니다.")
        ])

        next_phase = "role_interview"
        return {
            "messages": [msg],
            "phase": next_phase,
            "question_count": q_count,
            "role": role,
        }

    # -------------------------
    # Phase 2: Role Interview
    # -------------------------
    # 0) '모르겠습니다' 폭주 방지 (role별로 난이도 낮추기)
    # if dont_know:
    # ✅ follow_up_needed가 True면, dont_know로 빠지지 말고 꼬리질문 로직을 우선시
    if dont_know and not assessment.get("follow_up_needed"):
                # ✅ 추가: 2번 연속이면 더 이상 기술문제 폭주시키지 않고 선택지로 전환
        if dont_know_streak >= 2:
            msg = llm.invoke([
                SystemMessage(content="""
                당신은 면접관입니다.
                지원자가 '모르겠습니다'를 연속으로 말하면:
                - 질문을 계속 던지지 말고,
                - 부담을 낮추는 안내 + 선택지(1개만 고르게) 를 제시하세요.
                - 질문은 1개만.
                """.strip()),
                HumanMessage(content=f"""
                괜찮아요. 지금은 난이도를 조절할게요.

                아래 중에서 **하나만 골라서** 이야기해 주세요. (번호로 답해도 OK)
                1) (경험) 최근 프로젝트에서 내가 맡은 역할 + 가장 어려웠던 점 1가지
                2) (협업) 개발자/기획자와 의견 충돌이 있었을 때 어떻게 풀었는지
                3) (기술-기초) REST API를 한 문장으로 정의 + 예시 엔드포인트 1개
                """.strip())
                ])

            return {
                "messages": [msg],
                "question_count": q_count + 1,
                "role": role,
                "dont_know_streak": dont_know_streak,  # ✅ 꼭 같이 반환
            }

        if role == "ux":
            system_prompt = """
            당신은 UX/UI 디자이너 면접관입니다.
            지원자가 '모르겠습니다'라고 하면:
            - 난이도를 낮추고 경험 기반으로 답할 수 있게 유도하세요.
            - 질문은 1개만.
            """.strip()

            msg = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="""
                좋아요. 그럼 경험 기반으로만 답해봐요.

                질문(1개):
                최근 프로젝트 1개를 골라서
                1) 문제(사용자/비즈니스) 정의
                2) 사용자 확인 방법(리서치/데이터/관찰 등)
                3) 디자인 결정 1가지와 근거
                이 3가지를 짧게 말해주세요.
                """.strip())
                ])
                
            return {
                "messages": [msg],
                "question_count": q_count + 1,
                "role": role,
                "dont_know_streak": dont_know_streak
                }

        else:  # tech
            system_prompt = """
            당신은 테크 면접관입니다.
            지원자가 '모르겠습니다'라고 하면:
            - 더 쉬운 난이도의 질문으로 전환하거나,
            - 같은 주제를 '개념→예시' 형태로 풀어 답할 수 있게 유도하세요.
            - 질문은 1개만.
            """.strip()

            msg = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="""
                좋아요. 그럼 아주 기본으로 갈게요.

                질문(1개):
                REST API가 뭔지 '한 문장 정의' + '예시 엔드포인트 1개'로 설명해 주세요.
                (예: GET /users/1 같은 형태)
                """.strip())
            ])
            
            return {
                "messages": [msg],
                "question_count": q_count + 1,
                "role": role,
                "dont_know_streak": dont_know_streak
                }

    # 1) RAG 컨텍스트 조회(공통)
    query = f"면접 트랙: {role}, 지원자 답변: {last_user_text}"
    rag_context = retrieve_interview_context(query)

    # 2) role별 시스템 프롬프트
    if role == "ux":
        system_prompt = f"""
당신은 15년 차 UX/UI 디자이너 면접관입니다.
목표: 문제정의/리서치/설계/협업/성과 측정 역량 확인.

[참고(RAG)]
{rag_context}

규칙:
- 질문은 1개만
- UX/UI 범위에서만 질문(리서치, IA, 플로우, 와이어프레임, 프로토타입, 디자인시스템, 협업, KPI 등)
- 서버/DB/알고리즘 같은 CS 기술면접 질문 금지
""".strip()
    else:
        system_prompt = f"""
당신은 15년 차 시니어 테크 면접관입니다.
목표: 문제해결/설계/트러블슈팅/기본 CS 이해 확인.

[참고(RAG)]
{rag_context}

규칙:
- 질문은 1개만
- 너무 뜬구름 질문 금지: 실제 구현/경험/근거를 묻는 형태
""".strip()

    # 3) follow_up 여부에 따른 지시문
    if assessment.get("follow_up_needed"):
        instructions = f"""
지원자 답변을 더 구체화하는 꼬리질문 1개만 하세요.
직전 답변: {last_user_text}
""".strip()
    else:
        if role == "ux":
            instructions = """
새로운 UX 주제 질문 1개를 하세요.
(예: 리서치 방법 선택 이유 / 프로토타입 검증 / 디자인시스템 운영 / 개발자 협업 / 성과 측정)
""".strip()
        else:
            instructions = """
새로운 테크 주제 질문 1개를 하세요.
(예: API 설계/DB 인덱스/캐시/동시성/에러 핸들링/배포/로깅 중 1개)
""".strip()

    # 4) 종료 조건
    if q_count >= 6:
        closing = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="면접을 마무리하는 짧은 멘트를 1~2문장으로 해주세요.")
        ])
        return {
            "messages": [closing],
            "question_count": q_count + 1,
            "role": role,
            "dont_know_streak": 0
            }

    # 5) 질문 생성
    msg = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=instructions)
    ])

    return {
        "messages": [msg],
        "question_count": q_count + 1,
        "role": role,
        "dont_know_streak": dont_know_streak
        }


# --- 5. 그래프 구성 (Workflow) ---
workflow = StateGraph(InterviewState)

workflow.add_node("analyze_answer", node_analyze_answer)
workflow.add_node("generate_question", node_generate_question)

workflow.set_entry_point("analyze_answer")
workflow.add_edge("analyze_answer", "generate_question")
workflow.add_edge("generate_question", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# # (핵심) LangGraph 워크플로우 정의


# import os
# # [추가] 환경 변수 로드 라이브러리 임포트
# from dotenv import load_dotenv
# # [추가] .env 파일 즉시 로드 (이 코드가 llm 초기화보다 먼저 실행되어야 함)
# load_dotenv()

# from typing import Annotated, Literal, TypedDict, List
# from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
# # [수정 1] pydantic에서 직접 import 합니다.
# from pydantic import BaseModel, Field 
# from langchain_openai import ChatOpenAI
# from langgraph.graph import StateGraph, END
# from langgraph.graph.message import add_messages
# # [추가] 메모리 저장을 위한 체크포인터
# from langgraph.checkpoint.memory import MemorySaver 

# # RAG 체인 함수 임포트 (경로 주의)
# from YJH.chains.rag_chain import retrieve_interview_context


# # --- 1. 상태(State) 정의 ---
# class InterviewState(TypedDict):
#     messages: Annotated[List[BaseMessage], add_messages]
#     phase: str
#     question_count: int
#     last_assessment: dict 

# # --- 2. 구조화된 출력(Structured Output) 정의 ---
# class AnswerAssessment(BaseModel):
#     """지원자 답변 평가 모델"""
#     relevance: int = Field(description="답변이 질문 의도에 얼마나 부합하는지 (1-5점)")
#     technical_accuracy: int = Field(description="기술적 정확성 (1-5점)")
#     completeness: bool = Field(description="답변이 충분히 완료되었는지 여부")
#     follow_up_needed: bool = Field(description="심층 질문(꼬리물기)이 필요한지 여부")
#     reasoning: str = Field(description="평가 이유 및 관찰 내용")

# # --- 3. 모델 초기화 ---
# llm = ChatOpenAI(
#     model="gpt-4o",
#     temperature=0.7
# )

# # --- 4. 노드(Node) 함수 정의 ---

# from langchain_core.messages import SystemMessage, HumanMessage

# def node_analyze_answer(state: InterviewState):
#     """지원자의 답변을 분석하고 평가합니다."""
#     messages = state["messages"]

#     # 메시지 없거나 마지막이 시스템이면 평가 스킵
#     if not messages or isinstance(messages[-1], SystemMessage):
#         return {"last_assessment": {}}

#     # ✅ 1) "너무 짧은 답변"이면 LLM 평가 스킵 (폭주 방지 + UX)
#     last = messages[-1]
#     if isinstance(last, HumanMessage):
#         user_text = (last.content or "").strip()
#         # 기준은 너가 조절 가능: 너무 짧으면 follow_up_needed로 바로 반환
#         if len(user_text) < 15:  # "안녕하세요" 같은 케이스
#             return {
#                 "last_assessment": {
#                     "follow_up_needed": True,
#                     "feedback": "답변이 너무 짧아요. 3문장으로 (현재/경험/지원동기) 형태로 30초~1분 자기소개를 해주세요.",
#                 }
#             }

#     evaluator_prompt = SystemMessage(content="""
#     당신은 15년 차 시니어 테크니컬 면접관입니다.
#     지원자의 답변을 듣고 기술적 정확성과 논리성을 냉철하게 평가하십시오.
#     답변이 너무 짧거나 모호하면 follow_up_needed를 true로 설정하세요.
    
#     출력 규칙:
#     - 반드시 지정된 스키마(AnswerAssessment)에 맞춰 '간결하게' 작성하세요.
#     - feedback/strengths/weaknesses가 있다면 각각 3개 이내로 제한하세요.
#     - 불필요한 서술을 길게 하지 마세요.
#     """.strip())

#     # ✅ 2) structured output + max_tokens 강제
#     # llm이 ChatOpenAI 계열이면 bind(max_tokens=...)가 먹는다.
#     structured_llm = llm.bind(max_tokens=800).with_structured_output(AnswerAssessment)

#     try:
#         # 최근 5개 턴만 분석
#         response = structured_llm.invoke([evaluator_prompt] + messages[-5:])
#         return {"last_assessment": response.model_dump()}

#     except Exception as e:
#         # ✅ 3) 길이 제한/파싱 실패 폴백: 더 짧게 재시도 → 그래도 실패하면 최소 응답
#         err_text = str(e)

#         # 길이 제한/파싱류를 넓게 커버 (LengthFinishReasonError 포함)
#         if "LengthFinishReasonError" in err_text or "length limit" in err_text or "Could not parse response content" in err_text:
#             try:
#                 retry_prompt = SystemMessage(content="""
#                 당신은 면접 평가자입니다.
#                 반드시 AnswerAssessment 스키마만 출력하세요.
#                 아주 짧게 작성하세요. (각 항목 1~2문장/2개 이내)
#                 """.strip())

#                 retry_llm = llm.bind(max_tokens=300).with_structured_output(AnswerAssessment)
#                 response = retry_llm.invoke([retry_prompt] + messages[-3:])
#                 return {"last_assessment": response.model_dump()}
#             except Exception:
#                 # 최후 폴백: 500 내지 말고 follow_up_needed로 보내서 UI가 멈추지 않게
#                 return {
#                     "last_assessment": {
#                         "follow_up_needed": True,
#                         "feedback": "답변 분석 중 일시적인 문제가 발생했어요. 답변을 조금 더 길게 말한 뒤 다시 시도해주세요.",
#                     }
#                 }

#         # 그 외 예외도 500 대신 안전 응답
#         return {
#             "last_assessment": {
#                 "follow_up_needed": True,
#                 "feedback": "답변 분석 중 오류가 발생했어요. 다시 한 번 답변을 말해주시겠어요?",
#             }
#         }


# # YJH/agents/interview_graph.py 내부 함수 수정(26.02.02)
# def node_generate_question(state: InterviewState):
#     """
#     현재 면접 단계(phase)에 따라 적절한 질문을 생성합니다.
#     - intro: 환영 인사 및 자기소개 요청
#     - technical_interview: RAG 기반 기술 질문
#     """
#     # 1. 상태 가져오기 (기본값 'intro'로 설정하여 안전장치 마련)
#     phase = state.get("phase", "intro") 
#     assessment = state.get("last_assessment", {})
#     q_count = state.get("question_count", 0)
    
#     # --- [수정된 부분] Phase 1: 도입부 (Intro) 로직 추가 ---
#     if phase == "intro":
#         # RAG 검색 없이, 정중한 환영 인사 생성
#         system_prompt = """
#         당신은 전문적인 AI 면접관입니다. 
#         지원자가 면접장에 처음 들어온 상황입니다. 
#         긴장을 풀어주며 정중하게 환영 인사를 건네고, 간단한 자기소개를 요청하세요.
#         (아직 기술 질문은 하지 마세요.)
#         """
        
#         msg = llm.invoke([
#             SystemMessage(content=system_prompt),
#             HumanMessage(content="면접관님 안녕하세요, 면접 보러 왔습니다.") # 문맥 부여용 가짜 입력
#         ])
        
#         # 중요: 인사가 끝났으니 다음 턴을 위해 단계를 'technical_interview'로 변경함
#         return {
#             "messages": [msg], 
#             "phase": "technical_interview", 
#             "question_count": q_count 
#         }

#     # --- Phase 2: 기술 면접 (Technical) - 기존 로직 ---
    
#     # 1. RAG 검색 쿼리 생성
#     last_msg_content = state["messages"][-1].content if state["messages"] else ""
#     query = f"면접 단계: {phase}, 지원자 답변: {last_msg_content}"
    
#     # 2. RAG 검색
#     rag_context = retrieve_interview_context(query)
    
#     # 3. 프롬프트 구성
#     system_prompt = f"""
#     당신은 15년 차 시니어 기술 면접관입니다. 현재 단계: '{phase}'
    
#     [참고 자료(RAG)]
#     {rag_context}
    
#     위 자료를 참고하여 지원자에게 기술 질문을 하나 던지세요.
#     """
    
#     instructions = ""
#     if assessment.get("follow_up_needed"):
#         instructions = f"이전 답변({assessment.get('reasoning')})에 대해 더 깊이 파고드는 꼬리 질문을 하세요."
#     else:
#         instructions = "이전 답변은 됐습니다. 새로운 주제의 기술 질문을 하세요."

#     if q_count >= 5: 
#         instructions = "면접을 마무리하는 멘트를 하세요."

#     # 4. LLM 호출
#     msg = llm.invoke([
#         SystemMessage(content=system_prompt),
#         HumanMessage(content=instructions)
#     ])
    
#     return {"messages": [msg], "question_count": q_count + 1}

# # --- 5. 그래프 구성 (Workflow) ---

# workflow = StateGraph(InterviewState)

# workflow.add_node("analyze_answer", node_analyze_answer)
# workflow.add_node("generate_question", node_generate_question)

# # 시작점 설정
# workflow.set_entry_point("analyze_answer")

# # 엣지 연결
# workflow.add_edge("analyze_answer", "generate_question")
# workflow.add_edge("generate_question", END)

# # [추가] 체크포인터 설정 (대화 기억 유지용)
# memory = MemorySaver()
# app = workflow.compile(checkpointer=memory)