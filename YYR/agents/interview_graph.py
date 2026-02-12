# (핵심) LangGraph 워크플로우 정의


import os
# [추가] 환경 변수 로드 라이브러리 임포트
from dotenv import load_dotenv
# [추가] .env 파일 즉시 로드 (이 코드가 llm 초기화보다 먼저 실행되어야 함)
load_dotenv()

from typing import Annotated, Literal, TypedDict, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
# [수정 1] pydantic에서 직접 import 합니다.
from pydantic import BaseModel, Field 
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
# [추가] 메모리 저장을 위한 체크포인터
from langgraph.checkpoint.memory import MemorySaver 

# RAG 체인 함수 임포트 (경로 주의)
from YJH.chains.rag_chain import retrieve_interview_context


# --- 1. 상태(State) 정의 ---
class InterviewState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    phase: str
    question_count: int
    last_assessment: dict 

# --- 2. 구조화된 출력(Structured Output) 정의 ---
class AnswerAssessment(BaseModel):
    """지원자 답변 평가 모델"""
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

def node_analyze_answer(state: InterviewState):
    """지원자의 답변을 분석하고 평가합니다."""
    messages = state["messages"]
    
    # 시스템 메시지가 아닌, 최근 대화 내용(답변)이 있는지 확인
    if not messages or isinstance(messages[-1], SystemMessage):
        return {"last_assessment": {}}

    evaluator_prompt = SystemMessage(content="""
    당신은 15년 차 시니어 테크니컬 면접관입니다. 
    지원자의 답변을 듣고 기술적 정확성과 논리성을 냉철하게 평가하십시오.
    답변이 너무 짧거나 모호하면 'follow_up_needed'를 true로 설정하세요.
    """)
    
    structured_llm = llm.with_structured_output(AnswerAssessment)
    # 최근 5개 턴만 분석
    response = structured_llm.invoke([evaluator_prompt] + messages[-5:]) 
    
    # [수정 2] Pydantic V2에서는 .dict() 대신 .model_dump() 사용 권장
    return {"last_assessment": response.model_dump()}


# YJH/agents/interview_graph.py 내부 함수 수정(26.02.02)
def node_generate_question(state: InterviewState):
    """
    현재 면접 단계(phase)에 따라 적절한 질문을 생성합니다.
    - intro: 환영 인사 및 자기소개 요청
    - technical_interview: RAG 기반 기술 질문
    """
    # 1. 상태 가져오기 (기본값 'intro'로 설정하여 안전장치 마련)
    phase = state.get("phase", "intro") 
    assessment = state.get("last_assessment", {})
    q_count = state.get("question_count", 0)
    
    # --- [수정된 부분] Phase 1: 도입부 (Intro) 로직 추가 ---
    if phase == "intro":
        # RAG 검색 없이, 정중한 환영 인사 생성
        system_prompt = """
        당신은 전문적인 AI 면접관입니다. 
        지원자가 면접장에 처음 들어온 상황입니다. 
        긴장을 풀어주며 정중하게 환영 인사를 건네고, 간단한 자기소개를 요청하세요.
        (아직 기술 질문은 하지 마세요.)
        """
        
        msg = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="면접관님 안녕하세요, 면접 보러 왔습니다.") # 문맥 부여용 가짜 입력
        ])
        
        # 중요: 인사가 끝났으니 다음 턴을 위해 단계를 'technical_interview'로 변경함
        return {
            "messages": [msg], 
            "phase": "technical_interview", 
            "question_count": q_count 
        }

    # --- Phase 2: 기술 면접 (Technical) - 기존 로직 ---
    
    # 1. RAG 검색 쿼리 생성
    last_msg_content = state["messages"][-1].content if state["messages"] else ""
    query = f"면접 단계: {phase}, 지원자 답변: {last_msg_content}"
    
    # 2. RAG 검색
    rag_context = retrieve_interview_context(query)
    
    # 3. 프롬프트 구성
    system_prompt = f"""
    당신은 15년 차 시니어 기술 면접관입니다. 현재 단계: '{phase}'
    
    [참고 자료(RAG)]
    {rag_context}
    
    위 자료를 참고하여 지원자에게 기술 질문을 하나 던지세요.
    """
    
    instructions = ""
    if assessment.get("follow_up_needed"):
        instructions = f"이전 답변({assessment.get('reasoning')})에 대해 더 깊이 파고드는 꼬리 질문을 하세요."
    else:
        instructions = "이전 답변은 됐습니다. 새로운 주제의 기술 질문을 하세요."

    if q_count >= 5: 
        instructions = "면접을 마무리하는 멘트를 하세요."

    # 4. LLM 호출
    msg = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=instructions)
    ])
    
    return {"messages": [msg], "question_count": q_count + 1}

# --- 5. 그래프 구성 (Workflow) ---

workflow = StateGraph(InterviewState)

workflow.add_node("analyze_answer", node_analyze_answer)
workflow.add_node("generate_question", node_generate_question)

# 시작점 설정
workflow.set_entry_point("analyze_answer")

# 엣지 연결
workflow.add_edge("analyze_answer", "generate_question")
workflow.add_edge("generate_question", END)

# [추가] 체크포인터 설정 (대화 기억 유지용)
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)