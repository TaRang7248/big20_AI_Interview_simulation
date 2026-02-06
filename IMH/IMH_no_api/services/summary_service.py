from __future__ import annotations
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from IMH.IMH_no_api.IMH_no_api.services.llm import ollama_service

class SummaryService:
    """대화의 핵심 내용을 요약하여 summary_slot을 관리하는 서비스."""

    def __init__(self):
        self.llm = ollama_service.get_llm()

    async def summarize_history(self, history: str, model_name: Optional[str] = None) -> str:
        """현재까지의 대화 이력을 분석하여 지원자의 핵심 역량 및 주요 답변을 요약합니다."""
        if not history:
            return "아직 요약된 내용이 없습니다."

        llm = ollama_service.get_llm(model_name)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "당신은 전문 채용 평가관입니다. 아래 면접 대화 이력에서 지원자의 핵심 역량, "
                "주요 성과, 그리고 이전 답변에서 확인된 강점과 약점을 아주 간결하게(최대 300자) 요약하세요.\n"
                "이 요약은 다음 질문을 결정하는 중요한 참고 자료가 됩니다."
            )),
            ("human", "다음 대화 이력을 요약해 주세요:\n\n{history}")
        ])

        try:
            chain = prompt | llm
            response = await chain.ainvoke({"history": history})
            return response.content
        except Exception as e:
            print(f"[WARNING] Summarization failed: {e}")
            return "요약 생성 중 오류가 발생했습니다."

# 싱글톤 인스턴스
summary_service = SummaryService()
