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

def get_interview_question(use_json=False, file_path=None):
    """Generates an interview question using LLM with context from JSON or loads from JSON."""
    examples = ""
    if file_path and os.path.exists(file_path):
        questions = load_questions_from_json(file_path)
        if questions:
            import random
            # If use_json is True, we return a random question from the file.
            # If False (default LLM mode), we use some questions as context to generate a NEW one.
            if use_json:
                selected = random.choice(questions)
                return selected.get("질문", "질문을 찾을 수 없습니다.")
            
            # Use 3 random questions as examples for the LLM
            sample_size = min(len(questions), 3)
            samples = random.sample(questions, sample_size)
            examples = "\n".join([f"- {q.get('질문')}" for q in samples])

    system_prompt = "You are a professional HR interviewer for a software engineer role."
    user_content = "Generate one new and challenging interview question in Korean."
    
    if examples:
        user_content = f"""Here are some existing interview questions for reference:
{examples}

Based on these, generate a NEW, unique, and challenging interview question for a software engineer role in Korean. 
The question should be professional and technical."""

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
