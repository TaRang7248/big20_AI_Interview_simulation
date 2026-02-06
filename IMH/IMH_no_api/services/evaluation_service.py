from __future__ import annotations
import re
import json
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from IMH.IMH_no_api.IMH_no_api.core.config import settings
from IMH.IMH_no_api.IMH_no_api.services.llm import ollama_service
from IMH.IMH_no_api.IMH_no_api.schemas.interview_schemas import EvaluationRubric


class EvaluationService:
    """면접 평가 및 점수 산정 서비스."""

    def __init__(self):
        self.llm = ollama_service.get_llm()
        self.parser = JsonOutputParser(pydantic_object=EvaluationRubric)

    def _extract_json(self, text: str) -> str:
        """Ollama의 응답에서 JSON 블록만 추출합니다 (정규표현식 활용)."""
        json_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        return json_match.group(0) if json_match else text

    async def evaluate_interview(self, history: str, model_name: str | None = None) -> EvaluationRubric:
        """대화 이력을 분석하여 루브릭에 따른 평가를 수행합니다."""
        llm = ollama_service.get_llm(model_name)
        
        system_prompt = (
            "당신은 전문 채용 평가관입니다. 제공된 면접 대화 이력을 분석하여 평가 루브릭에 따라 점수를 부여하세요.\n\n"
            "# 평가 가이드라인\n"
            "1. **Evidence**: 점수의 근거가 된 지원자의 실제 답변 핵심 구절을 정확히 추출하세요.\n"
            "2. **Turn Reference**: 해당 답변이 나온 문답 순번(Turn)을 기록하세요.\n"
            "3. **Scoring Anchor**:\n"
            "   - 5점: 개념이 정확하며 실무 적용 사례와 Trade-off까지 완벽히 설명함.\n"
            "   - 3점: 개념은 인지하고 있으나 구체적인 수치나 사례가 부족함.\n"
            "   - 1점: 오개념을 말하거나 질문의 의도를 파악하지 못하고 답변을 회피함.\n\n"
            "# 출력 형식 (JSON Schema) - CRITICAL: 엄격 준수\n"
            "반드시 아래의 정해진 JSON 필드 구조를 엄격히 지켜 응답하세요. 다른 텍스트는 절대 금지합니다.\n"
            "```json\n"
            "{{{{\n"
            '  "technical_skill": {{{{ "score": int, "justification": "string", "evidence": ["string"], "turn_reference": [int] }}}},\n'
            '  "communication": {{{{ "score": int, "justification": "string", "evidence": ["string"], "turn_reference": [int] }}}},\n'
            '  "problem_solving": {{{{ "score": int, "justification": "string", "evidence": ["string"], "turn_reference": [int] }}}},\n'
            '  "cultural_fit": {{{{ "score": int, "justification": "string", "evidence": ["string"], "turn_reference": [int] }}}},\n'
            '  "overall_feedback": "string"\n'
            "}}}}\n"
            "```"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "다음 대화 이력을 평가해 주세요:\n\n{history}")
        ])

        for attempt in range(settings.MAX_RETRY_JSON):
            try:
                chain = prompt | llm
                raw_response = await chain.ainvoke({"history": history})
                
                clean_json = self._extract_json(raw_response.content)
                parsed_data = self.parser.parse(clean_json)
                
                # 가끔 모델이 결과를 특정 키로 감싸는 경우 대응
                if isinstance(parsed_data, dict) and "technical_skill" not in parsed_data:
                    for value in parsed_data.values():
                        if isinstance(value, dict) and "technical_skill" in value:
                            parsed_data = value
                            break

                if isinstance(parsed_data, dict):
                    return EvaluationRubric(**parsed_data)
                raise ValueError("평가 데이터 형식이 올바르지 않습니다.")
                
            except Exception as e:
                print(f"[RETRY {attempt+1}] 평가 파싱 에러: {e}")
                if attempt == settings.MAX_RETRY_JSON - 1:
                    raise ValueError(f"최종 평가 데이터 파싱 실패: {str(e)}")
                continue

# 싱글톤 인스턴스
evaluation_service = EvaluationService()
