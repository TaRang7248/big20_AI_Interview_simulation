from openai import AsyncOpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_questions(job_role: str, user_name: str, context_questions: list = []):
    """
    Generate 10 interview questions.
    """
    context_str = "\n".join([f"- {q}" for q in context_questions])
    
    prompt = f"""
    Create a structured interview for {user_name} applying for {job_role}.
    Context (similar questions):
    {context_str}
    
    Requirements:
    1. First question: Self-introduction.
    2. Second to Fourth: Personality/Character.
    3. Fifth to Ninth: Job Knowledge (Technical).
    4. Tenth: Closing question.
    
    Return a JSON object with a key "questions" containing a list of 10 strings.
    Example: {{"questions": ["Q1...", "Q2...", ...]}}
    Language: Korean.
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a professional interviewer. Output JSON only."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return data.get("questions", [])
    except Exception as e:
        print(f"Error generating questions: {e}")
        # Fallback
        return [f"Question {i+1} for {job_role}" for i in range(10)]

async def evaluate_answer(question: str, answer: str, job_role: str, image_path: str = None):
    """
    Evaluate answer and decide on follow-up.
    If image_path is provided, use Vision model capabilities.
    """
    
    messages = [
        {"role": "system", "content": "You are an interviewer evaluator. Output JSON only."}
    ]
    
    user_content = [
        {"type": "text", "text": f"Question: {question}\nAnswer: {answer}\nRole: {job_role}\nEvaluate this. If an image is provided, evaluate the architecture diagram as well."}
    ]
    
    if image_path:
        import base64
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encoded_image}"
                }
            })
        except Exception as e:
            print(f"Image load error: {e}")
            
    messages.append({"role": "user", "content": user_content})

    try:
        response = await client.chat.completions.create(
            model="gpt-4o", # GPT-4o supports vision
            messages=messages,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error eval: {e}")
        return {"score": 50, "feedback": f"Error: {e}", "follow_up_needed": False}
