# (핵심) LangGraph 워크플로우 정의


import os
# [추가] 환경 변수 로드 라이브러리 임포트
from dotenv import load_dotenv
# [추가] .env 파일 즉시 로드 (이 코드가 llm 초기화보다 먼저 실행되어야 함)
load_dotenv()

from typing import Annotated, Literal, TypedDict, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder # 26.02.05 추가(500 error)
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
    """
    지원자의 답변을 분석하고 평가합니다.
    (수정사항: 짧은 인사말이나 초기 단계는 평가를 건너뛰어 무한 루프 방지)
    """
    print("--- 노드 실행: 답변 평가 (Analyze Answer) ---")
    
    messages = state["messages"]
    
    # 1. 메시지가 없거나 시스템 메시지인 경우 건너뜀
    if not messages or isinstance(messages[-1], SystemMessage):
        return {"last_assessment": {}}

    user_answer = messages[-1].content
    
    # ------------------------------------------------------------------
    # [핵심 수정] "안녕하세요" 같은 짧은 인사는 평가하지 않고 바로 통과시킵니다.
    # 이 부분이 없으면 AI가 인사를 기술적으로 평가하려다 에러(토큰 초과)가 납니다.
    # ------------------------------------------------------------------
    if len(user_answer) < 20: 
        print(f"⏩ [Skip] 답변 길이({len(user_answer)}자)가 짧아 정밀 평가를 생략합니다.")
        # 가짜(Dummy) 평가 데이터를 반환하여 다음 단계로 넘김
        return {
            "last_assessment": {
                "technical_accuracy": 5,   # 기본 점수 부여
                "logic": 5,
                "communication": 5,
                "feedback": "인사 및 도입 단계입니다.",
                "follow_up_needed": False
            }
        }

    # 2. 평가 프롬프트 설정 (긴 답변일 경우에만 실행됨)
    evaluator_prompt = SystemMessage(content="""
    당신은 15년 차 시니어 테크니컬 면접관입니다. 
    지원자의 답변을 듣고 기술적 정확성과 논리성을 냉철하게 평가하십시오.
    답변이 너무 짧거나 모호하면 'follow_up_needed'를 true로 설정하세요.
    """)
    
    # 3. LLM 호출
    # (주의: AnswerAssessment 모델이 정의되어 있어야 합니다)
    try:
        structured_llm = llm.with_structured_output(AnswerAssessment)
        # 최근 5개 턴만 분석
        response = structured_llm.invoke([evaluator_prompt] + messages[-5:]) 
        
        return {"last_assessment": response.model_dump()}
        
    except Exception as e:
        print(f"❌ 평가 로직 에러: {e}")
        # 에러 발생 시에도 멈추지 않도록 기본값 반환
        return {
            "last_assessment": {
                "feedback": "평가 중 오류가 발생하여 넘어갑니다.",
                "follow_up_needed": False
            }
        }



# [수정] node_generate_question 함수 전체 교체 (26.02.05)

def node_generate_question(state: InterviewState):
    """
    현재 면접 단계에 따라 적절한 질문을 생성합니다.
    - intro: 환영 인사 (기존 로직 유지)
    - technical_interview: 이력서 기반 강제 질문 (Strict Mode 적용)
    """
    print("--- 노드 실행: 질문 생성 (Generate Question) ---")

    phase = state.get("phase", "intro")
    messages = state["messages"]
    q_count = state.get("question_count", 0)

    # --- [Phase 1] 도입부 (Intro) ---
    # 아직 면접이 시작되지 않았거나, 첫 인사를 해야 할 때
    if phase == "intro":
        print("👋 [Phase: Intro] 환영 인사 생성")
        system_prompt = """
        당신은 전문적인 AI 면접관입니다. 
        지원자가 면접장에 처음 들어온 상황입니다. 
        긴장을 풀어주며 정중하게 환영 인사를 건네고, 간단한 자기소개를 요청하세요.
        (아직 기술 질문은 하지 마세요.)
        """
        
        # 가짜 사용자 메시지를 넣어 AI의 첫 마디를 유도
        msg = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="면접관님 안녕하세요, 면접 보러 왔습니다.") 
        ])
        
        # 인사가 끝났으므로 다음 턴부터는 'technical_interview'로 전환
        return {
            "messages": [msg], 
            "phase": "technical_interview", 
            "question_count": q_count 
        }

    # --- [Phase 2] 기술 면접 (Technical) - Strict Mode 적용 ---
    
    # 1. 사용자의 마지막 발언 내용 확인 (main_yjh.py에서 주입한 프롬프트가 있는지)
    last_user_msg = messages[-1].content if messages else ""
    
    # 기본 시스템 프롬프트 (일반 모드)
    system_instruction = f"""
    당신은 15년 차 시니어 기술 면접관입니다. (질문 횟수: {q_count + 1}번째)
    지원자의 답변을 듣고 이어지는 기술 질문(꼬리 질문)을 하나 던지세요.
    """

    # 2. [Strict Mode 감지] 이력서 컨텍스트가 주입되었는지 확인
    # main_yjh.py에서 "Resume Context"라는 단어를 포함해서 보냈다면 이 모드가 발동됩니다.
    if "Resume Context" in last_user_msg or "System Instruction" in last_user_msg:
        print("🔒 [Strict Mode] 이력서 기반 질문 모드 발동 (딴소리 차단)")
        system_instruction = """
        [Role]
        당신은 지원자의 '이력서(Resume)'를 검증하는 깐깐한 면접관입니다.

        [Critical Rules]
        1. 반드시 사용자가 방금 제공한 [Resume Context] 내용 안에서만 질문하십시오.
        2. 이력서에 없는 '강화학습(RL)', 'NLP', 'AI', '딥러닝' 질문은 **절대 금지**입니다.
        3. 지원자는 '백엔드(Java/Python/AWS)' 개발자입니다. DB, API, 배포, 마이그레이션 관련 질문만 하십시오.
        4. "이전 답변에서 언급하신..." 같은 서두를 사용하여 연결성을 강조하십시오.
        5. 질문은 한 번에 하나만 하세요.
        """
    
    # 3. 질문 생성
    # 기존 코드의 'retrieve_interview_context'는 삭제했습니다. (이미 메시지 안에 정보가 있으므로 중복 제거)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    chain = prompt | llm
    
    try:
        response = chain.invoke({"messages": messages})
        
        return {
            "messages": [response],
            "question_count": q_count + 1
        }
    except Exception as e:
        print(f"❌ 질문 생성 중 에러: {e}")
        return {
            "messages": [AIMessage(content="죄송합니다. 잠시 통신 오류가 있었습니다. 다시 한 번 프로젝트 경험을 말씀해 주시겠습니까?")]
        }



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