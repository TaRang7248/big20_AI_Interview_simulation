from openai import AsyncOpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def get_embedding(self, text: str):
        """Generates embedding for the given text."""
        try:
            response = await self.client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return []

    async def generate_question(self, job_title: str, stage: str, context: list = None):
        """
        Generates the next interview question based on the stage and context.
        Persona: Expert Interviewer in the specific field.
        """
        context_str = ""
        if context:
            context_str = "\n".join([f"- {q}" for q in context])

        system_prompt = f"""
        당신은 '{job_title}' 분야의 20년차 베테랑 전문가이자 면접관입니다.
        지원자의 역량을 깊이 있게 파악하기 위해 날카롭고 핵심적인 질문을 던집니다.
        
        당신의 역할:
        1. '{job_title}' 직무에 가장 중요하고 실무적인 질문을 던지십시오.
        2. 말투는 정중하면서도 전문적인 무게감이 있어야 합니다.
        3. 반드시 '한국어'로 질문하십시오.
        """

        user_prompt = f"""
        현재 면접 단계: {stage}
        
        참고 가능한 질문 리스트 (이 질문들과 유사하지만 다르게 변형하여 질문하세요):
        {context_str}
        
        요구사항:
        - 현재 단계({stage})에 맞는 질문을 1개만 생성하세요.
        - 'intro' 단계라면 자기소개를 요청하세요.
        - 질문 내용만 평문 텍스트로 출력하세요 (따옴표나 설명 없이).
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating question: {e}")
            return f"{job_title} 직무에 대한 자기소개를 부탁드립니다."

    async def evaluate_and_next_action(self, job_title: str, question: str, answer: str, is_last_question: bool):
        """
        Evaluates the answer and decides the next step.
        """
        system_prompt = f"""
        당신은 '{job_title}' 분야의 최고 전문가 면접관입니다.
        지원자의 답변을 평가하고 피드백을 제공해야 합니다.
        
        평가 기준:
        1. 직무 이해도 및 전문성
        2. 논리적 사고 및 문제 해결 능력
        3. 답변의 구체성 및 진실성
        
        출력 형식 (JSON Only):
        {{
            "score": 0~100 사이의 점수 (정수),
            "feedback": "지원자의 답변에 대한 구체적이고 전문적인 피드백 (반드시 한국어로 작성, 전문가의 조언 포함)",
            "is_follow_up": true/false (답변이 부족하거나 흥미로워서 꼬리 질문이 필요한지 여부),
            "next_step_question": "꼬리 질문 내용 (is_follow_up이 true일 때만 작성, 아니면 null)"
        }}
        
        주의사항:
        - 피드백은 지원자에게 직접 말하듯이 "~~한 점은 좋았습니다. 다만 ~~ 부분은 보완이 필요합니다." 형태로 작성하세요.
        - is_follow_up은 답변이 모호하거나 더 깊이 파고들 가치가 있을 때만 true로 설정하세요.
        """

        user_prompt = f"""
        질문: {question}
        지원자 답변: {answer}
        마지막 질문 여부: {is_last_question}
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"Error evaluating answer: {e}")
            return {
                "score": 50,
                "feedback": "시스템 오류로 인해 평가를 완료할 수 없습니다. 다시 시도해 주세요.",
                "is_follow_up": False,
                "next_step_question": None
            }
