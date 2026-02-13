import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_service import get_job_questions, evaluate_answer
from app.database import get_db_connection

def test_get_job_questions():
    print("Testing get_job_questions...")
    job_title = "Python Developer"
    
    # 1. Call function
    questions = get_job_questions(job_title)
    print(f"Questions returned for '{job_title}':")
    for q in questions:
        print(f"- {q}")
        
    # 2. Verify DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM job_question_pool WHERE job_title = %s", (job_title,))
    count = c.fetchone()[0]
    conn.close()
    
    if count > 0:
        print(f"SUCCESS: {count} questions found in pool for '{job_title}'.")
    else:
        print(f"FAILURE: No questions found in pool for '{job_title}'.")

def test_evaluate_answer():
    print("\nTesting evaluate_answer...")
    job_title = "Python Developer"
    applicant_name = "Test User"
    current_q_count = 1
    prev_question = "자기소개를 해주세요."
    applicant_answer = "저는 파이썬 개발자로서 웹 백엔드 개발 경험이 있습니다."
    next_phase = "직무 기술(Technical Skill)"
    resume_summary = "이 지원자는 Django와 FastAPI를 사용한 3년차 백엔드 개발자입니다."
    ref_questions = ["Python의 GIL에 대해 설명해주세요.", "REST API란 무엇인가요?"]
    
    evaluation, next_question = evaluate_answer(
        job_title, applicant_name, current_q_count, prev_question, applicant_answer, next_phase,
        resume_summary=resume_summary, ref_questions=ref_questions
    )
    
    print(f"Evaluation: {evaluation}")
    print(f"Next Question: {next_question}")
    
    if "Django" in next_question or "FastAPI" in next_question or "GIL" in next_question or "REST" in next_question:
         print("SUCCESS: Next question seems relevant to resume or reference questions.")
    else:
         print("WARNING: Next question might not be specific enough. Check the output carefully.")

if __name__ == "__main__":
    try:
        test_get_job_questions()
        test_evaluate_answer()
    except Exception as e:
        print(f"An error occurred: {e}")
