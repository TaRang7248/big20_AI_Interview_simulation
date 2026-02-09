# [평가 루브릭 상세 테이블] 기반 '최종 리포트 생성(Evaluation Report)' 구현


# 비언어적 태도 처리: 현재는 '음성/텍스트'만 있고 '영상(Vision)'이 없으므로, 
# [비언어적 태도] 항목은 **"텍스트 기반의 정중함/자신감"**으로 우회하여 평가하거나, 
# 추후 DeepFace 연동 전까지는 '분석 불가(N/A)'로 처리하는 것이 현실적.

import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

# [수정] 루브릭 문서의 4대 영역 + 가중치 반영을 위한 데이터 모델
class RubricScore(BaseModel):
    score: int = Field(description="1점(미흡), 3점(보통), 5점(탁월) 중 하나")
    rationale: str = Field(description="해당 점수를 부여한 구체적인 근거")
    feedback: str = Field(description="개선 제안")

class InterviewReport(BaseModel):
    # 1. 직무 역량 (Hard Skill) - 가중치 40%
    hard_skill: RubricScore = Field(description="개념 정확성 및 기술 이해도 평가")
    
    # 2. 문제 해결력 (Logic) - 가중치 30%
    problem_solving: RubricScore = Field(description="논리적 구조화(Decomposition) 및 접근 방식 평가")
    
    # 3. 의사소통 (Communication) - 가중치 20%
    communication: RubricScore = Field(description="STAR 기법 적용 여부 및 핵심 전달 능력")
    
    # 4. 태도 (Attitude/Vision) - 가중치 10% (현재는 텍스트/음성 톤으로만 추정)
    attitude: RubricScore = Field(description="자신감, 정중함, 답변 태도 등")

    # 종합 결과
    total_weighted_score: float = Field(description="가중치가 적용된 최종 점수 (100점 만점 환산)")
    final_result: str = Field(description="PASS / FAIL / HOLD")
    overall_summary: str = Field(description="면접관의 종합 총평")

async def generate_interview_report(transcripts: list) -> dict:
    """
    [평가 루브릭 문서 기반] 대화 기록을 분석하여 정밀 평가 리포트를 생성합니다.
    """
    # 1. 대화 내용 텍스트 변환
    full_conversation = ""
    for t in transcripts:
        speaker = "지원자" if t.sender == "human" else "면접관"
        full_conversation += f"{speaker}: {t.content}\n"

    # 2. LLM 초기화
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0) # 평가의 일관성을 위해 온도 0 설정
    
    # 3. [핵심] 루브릭 기준을 시스템 프롬프트에 주입
    # 문서 내용을 그대로 반영했습니다.
    rubric_criteria = """
    [평가 루브릭 기준표]
    1. 직무 역량 (Hard Skill)
       - 5점: 원리를 정확히 이해하고, 장단점(Trade-off)과 실무 적용 사례까지 연결함.
       - 3점: 교과서적인 정의는 알고 있으나, 깊이 있는 설명이나 응용이 부족함.
       - 1점: 핵심 개념을 오해하거나 틀린 정보를 자신 있게 답변함.
    
    2. 문제 해결력 (Problem Solving)
       - 5점: 문제를 스스로 구조화하고, 엣지 케이스(Edge Case)를 고려하여 논리적으로 전개함.
       - 3점: 주장은 명확하나 근거가 일반론에 그침.
       - 1점: 힌트를 줘야만 해결하거나 횡설수설함.
    
    3. 의사소통 (Communication)
       - 5점: 두괄식으로 말하며, STAR(상황-과제-행동-결과) 흐름이 명확함.
       - 3점: 질문에 대답은 했으나 핵심을 빗겨가거나 다소 장황함.
       - 1점: 동문서답하거나 요지를 파악하지 못함.
    
    4. 태도 (Attitude) - *현재 비디오 분석 불가로 텍스트/음성 뉘앙스로 판단*
       - 5점: 자신감 있고 정중하며, 질문의 의도를 적극적으로 파악하려는 태도.
       - 3점: 평이한 태도.
       - 1점: 소극적이거나 방어적인 태도.
    """

    system_prompt = f"""
    당신은 30년 차 베테랑 기술 면접관입니다. 
    제공된 면접 대화 기록을 분석하여 아래 [평가 루브릭 기준표]에 따라 엄격하게 채점하십시오.
    
    {rubric_criteria}

    [최종 점수 계산 방식]
    - (직무역량 * 0.4) + (문제해결력 * 0.3) + (의사소통 * 0.2) + (태도 * 0.1) 
    - 위 결과(5점 만점)를 100점 만점으로 환산하여 'total_weighted_score'에 기입하십시오.
    """

    # 4. 구조화된 출력 요청
    structured_llm = llm.with_structured_output(InterviewReport)
    
    try:
        report = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"--- 면접 대화 기록 ---\n{full_conversation}")
        ])
        
        return report.model_dump()
        
    except Exception as e:
        print(f"❌ 리포트 생성 실패: {e}")
        return None