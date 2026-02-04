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

    async def generate_question(self, job_title, stage, context_questions=None):
        """Generates an interview question based on stage and job title."""
        context_str = ""
        if context_questions:
            context_str = "\n참고할 질문들:\n" + "\n".join([f"- {q}" for q in context_questions])

        stage_prompts = {
            "intro": "지원자의 자기소개를 요청하는 질문을 생성해 주세요.",
            "personality": "지원자의 인성과 가치관을 파악할 수 있는 질문을 생성해 주세요.",
            "technical": f"지원자가 지원한 '{job_title}' 직무 지식을 심도 있게 묻는 질문을 생성해 주세요."
        }
        
        prompt = f"""
당신은 전문 면접관입니다. 지원자가 지원한 직무는 '{job_title}'입니다.
현재 면접 단계: {stage_prompts.get(stage, stage)}
{context_str}

위 내용을 바탕으로 면접 질문을 하나만 생성해 주세요.
질문은 자연스럽고 전문적인 한국어 공대(합쇼체)를 사용하세요.
추가적인 설명 없이 오직 질문 내용만 반환하세요.
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "당신은 노련한 채용 전문가이자 전문 면접관입니다. 모든 응답은 한글로 작성하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

    async def evaluate_and_next_action(self, job_title, question, answer, is_last_question=False):
        """Evaluates the candidate's answer and decides on a follow-up or next action."""
        prompt = f"""
면접 직무: {job_title}
질문: {question}
답변: {answer}

위 답변을 면접관의 관점에서 심층 분석하여 다음을 수행하세요:
1. 답변의 충실도, 전문성, 구체성, 그리고 질문에 대한 적절성을 평가하여 0~100점 사이의 점수를 부여하세요 (score).
2. 답변에 대한 구체적이고 건설적인 피드백을 한국어로 작성하세요 (feedback).
3. 답변 내용 중 추가 확인이나 보완이 필요한 부분이 있다면 관련하여 '꼬리 질문(follow-up)'을 생성하세요. 
4. 만약 답변이 충분히 완결되었다고 판단되면, 'is_follow_up'을 false로 설정하세요.
5. 마지막 질문인 경우('{is_last_question}'), 전체적인 면접 태도와 답변을 종합하여 'pass_fail'(합격/불합격) 여부를 결정하세요.

반드시 아래의 JSON 형식을 엄격히 유지하여 응답하세요:
{{
    "score": 85,
    "feedback": "답변이 매우 구체적이고 기술적인 이해도가 높습니다.",
    "is_follow_up": true,
    "next_step_question": "꼬리 질문 내용 (is_follow_up이 true인 경우에만 생성)",
    "pass_fail": "합격" // 마지막 질문인 경우 전체 평균 점수가 70점 이상이면 '합격', 아니면 '불합격'
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "당신은 면접 답변을 전문적으로 평가하고 꼬리 질문을 생성하는 전문 면접관입니다. 모든 응답은 한글이며 반드시 JSON 형식이어야 합니다."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
