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
RoleType = Literal["ux", "tech", "data"]

from typing import Literal

class InterviewState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    phase: str
    question_count: int
    last_assessment: dict
    role: Literal["ux", "tech", "data"]   # ✅ 추가


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

        elif role == "data":
            system_prompt = """
            당신은 데이터 분석가 면접관입니다.
            지원자가 '모르겠습니다'라고 하면:
            - 난이도를 낮추고 실제 분석 경험 기반으로 답할 수 있게 유도하세요.
            - 질문은 1개만.
            """.strip()

            msg = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="""
                좋아요. 그럼 경험 기반으로만 답해봐요.

                질문(1개):
                최근 분석 프로젝트 1개를 골라서
                1) 어떤 문제를 풀었는지 (비즈니스 목표)
                2) 어떤 데이터를 활용했는지
                3) 분석 결과로 어떤 인사이트를 냈는지
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
    elif role == "data":
        system_prompt = f"""
당신은 15년 차 시니어 데이터 분석가 면접관입니다.
목표: 데이터 분석 역량/통계 이해/도구 활용/비즈니스 인사이트 도출 역량 확인.

[참고(RAG)]
{rag_context}

규칙:
- 질문은 1개만
- 데이터 분석 범위에서만 질문 (EDA, 통계, SQL, 시각화, 머신러닝 기초, A/B테스트, KPI 정의 등)
- 지원자의 이력서 기반으로 실제 경험을 묻는 형태로 질문
- UX 디자인이나 순수 백엔드 개발 질문 금지
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
        elif role == "data":
            instructions = """
새로운 데이터 분석 주제 질문 1개를 하세요.
(예: SQL 쿼리 최적화 / A/B 테스트 설계 / 이상치 처리 방법 / 모델 성능 평가 / 대시보드 KPI 정의 / 분석 결과 커뮤니케이션 중 1개)
반드시 지원자의 이력서 내용(경력/프로젝트)과 연결해서 질문하세요.
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