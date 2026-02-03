import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o" # Or gpt-3.5-turbo

    async def generate_initial_question(self, job_title):
        prompt = f"""
        당신은 전문 면접관입니다. 지원자가 지원한 직무는 '{job_title}'입니다.
        이 직무에 적합한 첫 번째 면접 질문을 하나 생성해 주세요.
        질문은 한국어로 작성해 주세요.
        질문만 반환해 주세요.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": "You are a professional interviewer."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

    async def evaluate_and_next_action(self, job_title, question, answer):
        prompt = f"""
        면접 직무: {job_title}
        질문: {question}
        답변: {answer}

        위 답변을 바탕으로 다음을 수행하세요:
        1. 답변이 충분히 구체적인지, 추가 꼬리 질문이 필요한지 판단하세요.
        2. 답변에 대한 평가(점수 0-100, 피드백)를 작성하세요.
        3. 만약 꼬리 질문이 필요하다면 'follow_up' 질문을 생성하고, 그렇지 않다면 다음 주제의 'next_question'을 생성하세요.

        출력 형식은 반드시 아래와 같은 JSON 형태여야 합니다:
        {{
            "score": 80,
            "feedback": "답변이 구체적이고 좋습니다.",
            "is_follow_up": true/false,
            "next_step_question": "생성된 질문 내용"
        }}
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": "You are a professional interviewer evaluating candidates. Respond only in JSON."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    async def get_embedding(self, text):
        response = self.client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
