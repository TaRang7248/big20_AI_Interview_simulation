
import os
import sys
import json
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_service import get_job_questions, evaluate_answer

def test_llm():
    print("Testing LLM with Gemini...")
    
    # Test 1: Get Job Questions
    print("\n[Test 1] Get Job Questions")
    try:
        questions = get_job_questions("Python Developer")
        print(f"Questions: {questions}")
    except Exception as e:
        print(f"Get Questions Failed: {e}")

    # Test 2: Evaluate Answer
    print("\n[Test 2] Evaluate Answer")
    try:
        evaluation, next_q = evaluate_answer(
            job_title="Python Developer",
            applicant_name="Tester",
            current_q_count=1,
            prev_question="자기소개를 해주세요.",
            applicant_answer="저는 파이썬 개발자입니다.",
            next_phase="직무 기술(Technical Skill)"
        )
        print(f"Evaluation: {evaluation}")
        print(f"Next Question: {next_q}")
    except Exception as e:
        print(f"Evaluation Failed: {e}")

if __name__ == "__main__":
    test_llm()
