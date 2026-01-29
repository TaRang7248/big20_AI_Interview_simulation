# (핵심) LangGraph 워크플로우 정의

import os
from typing import Annotated, Literal, TypedDict, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# --- 1. 상태(State) 정의 ---
# 면접의 전체 맥락을 저장하는 메모리 구조입니다.
# state.py로 분리하는 것이 정석이지만, 이해를 위해 이곳에 포함합니다.

class InterviewState(TypedDict):
    # 대화 이력 (add_messages 리듀서를 통해 자동 append 됨)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 면접 진행 단계 (intro -> technical -> behavioral -> wrapup)
    phase: str
    
    # 현재 질문 횟수 (면접 길이 제어용)
    question_count: int
    
    # 현재 지원자의 답변에 대한 AI의 내부 평가 (꼬리질문 판단용)
    last_assessment: dict 

# --- 2. 구조화된 출력(Structured Output) 정의 ---
# LLM이 단순 텍스트가 아닌, 명확한 판단 데이터를 뱉도록 강제합니다. (REQ-F-006, 007 관련)

class AnswerAssessment(BaseModel):
    """지원자 답변 평가 모델"""
    relevance: int = Field(description="답변이 질문 의도에 얼마나 부합하는지 (1-5점)")
    technical_accuracy: int = Field(description="기술적 정확성 (1-5점)")
    completeness: bool = Field(description="답변이 충분히 완료되었는지 여부")
    follow_up_needed: bool = Field(description="심층 질문(꼬리물기)이 필요한지 여부")
    reasoning: str = Field(description="평가 이유 및 관찰 내용")

# --- 3. 모델 초기화 ---
llm = ChatOpenAI(
    model="gpt-4o",  # 또는 gpt-3.5-turbo (비용 절감 시) / gpt-4o(적용)
    temperature=0.7
)

# --- 4. 노드(Node) 함수 정의 ---

def node_analyze_answer(state: InterviewState):
    """
    지원자의 마지막 답변을 분석하는 노드입니다.
    REQ-F-001(적응형 질문)을 위해 답변의 품질을 먼저 평가합니다.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # 시스템 프롬프트: 답변 평가자 페르소나
    evaluator_prompt = SystemMessage(content="""
    당신은 15년 차 시니어 테크니컬 면접관입니다. 
    지원자의 답변을 듣고 기술적 정확성과 논리성을 냉철하게 평가하십시오.
    답변이 너무 짧거나 모호하면 'follow_up_needed'를 true로 설정하세요.
    """)
    
    # 구조화된 출력 모드로 LLM 호출
    structured_llm = llm.with_structured_output(AnswerAssessment)
    response = structured_llm.invoke([evaluator_prompt] + messages[-5:]) # 최근 5개 턴만 분석 (토큰 절약)
    
    # 상태 업데이트: 평가 결과 저장 (사용자에게 보이지 않음)
    return {"last_assessment": response.dict()}

def node_generate_question(state: InterviewState):
    """
    다음 질문을 생성하는 노드입니다.
    이전 평가 결과(last_assessment)에 따라 꼬리 질문을 할지, 새로운 주제로 갈지 결정합니다.
    """
    phase = state["phase"]
    assessment = state.get("last_assessment", {})
    q_count = state["question_count"]
    
    # 기본 시스템 프롬프트 (면접관 페르소나) 
    system_prompt = f"""
    당신은 면접관입니다. 현재 면접 단계는 '{phase}'입니다.
    정중하지만 핵심을 찌르는 질문을 하십시오.
    질문은 한 번에 하나만 하세요.
    """
    
    instructions = ""
    
    # 로직 분기: 꼬리 질문 vs 새 질문
    if assessment.get("follow_up_needed"):
        instructions = f"지원자의 이전 답변({assessment.get('reasoning')})이 부족했습니다. 구체적인 사례를 묻거나 기술적 원리를 묻는 꼬리 질문을 하세요."
    else:
        # TODO: 여기서 RAG 체인을 호출하여 다음 질문 토픽을 가져오는 것이 이상적입니다.
        # 이번 단계에서는 하드코딩된 예시를 사용합니다.
        instructions = "지원자의 답변이 훌륭했습니다. 다음 주제로 넘어가세요. 관련된 다른 기술 질문을 던지세요."

    # 종료 조건 체크
    if q_count >= 5: # 예: 5턴 이후 종료
        instructions = "면접을 마무리하는 단계입니다. 지원자에게 수고했다는 말과 함께 마지막으로 하고 싶은 말이 있는지 물어보세요."
        # 상태 업데이트를 위해 phase 변경은 로직상 필요할 수 있음

    msg = llm.invoke([SystemMessage(content=system_prompt + "\n" + instructions)] + state["messages"])
    
    return {"messages": [msg], "question_count": q_count + 1}

# --- 5. 엣지(Edge) 조건부 로직 ---

def route_next_step(state: InterviewState) -> Literal["generate_question", "finalize_interview"]:
    """평가 후 다음 단계를 결정하는 라우터"""
    if state["question_count"] > 6:
        return "finalize_interview"
    return "generate_question"

# --- 6. 그래프 구성 (Workflow) ---

workflow = StateGraph(InterviewState)

# 노드 추가
workflow.add_node("analyze_answer", node_analyze_answer)
workflow.add_node("generate_question", node_generate_question)
# (선택사항) 면접 종료 노드 추가 가능

# 흐름 정의
# 1. 사용자가 답변을 입력하면(Start) -> 분석 노드로 이동
workflow.set_entry_point("analyze_answer")

# 2. 분석 후 -> 무조건 질문 생성으로 이동 (단순화된 버전)
# 실제로는 여기서 '면접 종료' 등의 분기가 일어납니다.
workflow.add_edge("analyze_answer", "generate_question")

# 3. 질문 생성 후 -> END (사용자 입력을 기다림)
workflow.add_edge("generate_question", END)

# 컴파일
app = workflow.compile()