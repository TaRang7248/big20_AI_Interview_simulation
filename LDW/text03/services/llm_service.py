import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o" # or gpt-3.5-turbo

    async def get_embedding(self, text):
        """Generates embedding for vector search or storage."""
        response = self.client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    async def generate_initial_question(self, job_title, context_questions=None):
        """Generates the first interview question based on job title and RAG context."""
        context_str = ""
        if context_questions:
            context_str = "\n관련된 기출 질문들:\n" + "\n".join([f"- {q}" for q in context_questions])

        prompt = f"""
당신은 전문 면접관입니다. 지원자가 지원한 직무는 '{job_title}'입니다.
{context_str}

위의 기출 질문들과 직무 내용을 참고하여, 지원자에게 던질 첫 번째 면접 질문을 하나만 생성해 주세요.
질문은 정중하고 전문적인 한국어 공대(합쇼체)를 사용하세요.
추가적인 설명 없이 오직 질문 내용만 반환하세요.
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "당신은 채용 전문가이며 전문 면접관입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

    async def evaluate_and_next_action(self, job_title, question, answer):
        """Evaluates the candidate's answer and decides on a follow-up or next question."""
        prompt = f"""
면접 직무: {job_title}
질문: {question}
답변: {answer}

위 답변을 바탕으로 다음을 수행하세요:
1. 답변의 충실도, 전문성, 구체성을 평가하여 0~100점 사이의 점수를 부여하세요.
2. 답변에 대한 구체적인 한국어 피드백을 작성하세요.
3. 답변 내용 중 추가 확인이 필요한 부분이 있다면 관련하여 꼬리 질문(follow-up)을 생성하세요.
4. 만약 답변이 충분하다면 다음 단계로 넘어갈 새로운 질문(next_question)을 생성하세요.

반드시 아래의 JSON 형식을 유지하여 응답하세요:
{{
    "score": 85,
    "feedback": "답변이 매우 구체적이고 기술적인 이해도가 높습니다.",
    "is_follow_up": true,
    "next_step_question": "생성된 질문 내용"
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "당신은 면접 답변을 평가하고 질문을 이어가는 전문 면접관입니다. 반드시 JSON으로만 응답하세요."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
