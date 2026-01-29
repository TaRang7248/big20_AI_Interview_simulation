import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_questions_from_json(file_path: str):
    """Loads interview questions from a JSON file."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_interview_question(file_path=None):
    """Generates a new interview question using LLM based on examples in JSON."""
    examples = ""
    if file_path and os.path.exists(file_path):
        questions = load_questions_from_json(file_path)
        if questions:
            import random
            # Use 5 random questions as context to understand the style and topics
            sample_size = min(len(questions), 5)
            samples = random.sample(questions, sample_size)
            # Only provide questions as samples to prevent the LLM from generating answers
            examples = "\n".join([f"- {q.get('질문')}" for q in samples])

    system_prompt = """당신은 소프트웨어 엔지니어 채용을 담당하는 전문 면접관입니다.
제공된 기존 질문 리스트를 참고하여, 해당 주제들과 유사한 수준의 전문성을 갖춘 '새로운' 질문을 한 개 생성해야 합니다.
이미 존재하는 질문을 그대로 사용하지 말고, 새로운 관점이나 세부적인 기술 내용을 묻는 독창적인 질문을 만드세요.

**중요: 답변 예시나 부연 설명 없이 오직 '질문' 내용만 한 문장 혹은 한 단락으로 출력하세요.**"""

    user_content = "실무적인 소프트웨어 엔지니어 면접 질문을 한국어로 한 개 생성해 주세요."
    
    if examples:
        user_content = f"""다음은 우리 회사의 기존 면접 질문 예시들입니다:
{examples}

위 질문들과 겹치지 않는 '새롭고' 도전적인 면접 질문을 기술적으로 깊이 있게 한 개만 생성해 주세요.
질문은 한국어로 작성하며, 질문 외에 어떠한 텍스트(답변 예시 등)도 포함하지 마세요."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    )
    return response.choices[0].message.content.strip()

def evaluate_answer(question, answer):
    """Evaluates the user's answer using LLM and returns a JSON response."""
    prompt = f"""
    Interview Question: {question}
    User Answer: {answer}
    
    Evaluate the answer based on:
    1. Relevance
    2. Technical accuracy (if applicable)
    3. Communication style
    
    Return the result strictly in JSON format with the following keys:
    - score: (Int, 0-100)
    - feedback: (String, in Korean)
    - improvements: (String, in Korean)
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an interviewer evaluating an applicant's answer. Respond only in valid JSON."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
