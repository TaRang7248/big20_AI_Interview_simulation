
import os
import sys
import unittest
from dotenv import load_dotenv

# Path setup to import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load env from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from app.services.llm_service import get_job_questions, summarize_resume, evaluate_answer
# Mock DB connection for get_job_questions to avoid DB errors if possible, 
# or just rely on the fact that if DB fails it catches exception.
# But get_job_questions tries to connect to DB. 
# For simple testing, we might want to mock generic model generation if we don't have DB.
# However, let's try to see if we can test summarize_resume first as it doesn't need DB.

class TestGeminiIntegration(unittest.TestCase):
    def test_summarize_resume(self):
        print("\nTesting summarize_resume with Gemini...")
        text = "저는 Python과 AWS를 이용한 백엔드 개발 경험이 있는 개발자 김철수입니다. 주요 프로젝트로는 쇼핑몰 구축이 있습니다."
        summary = summarize_resume(text)
        print(f"Summary result: {summary}")
        self.assertNotEqual(summary, "내용 없음")
        self.assertTrue(len(summary) > 0)

    def test_evaluate_answer(self):
        print("\nTesting evaluate_answer with Gemini...")
        job_title = "Backend Developer"
        applicant_name = "Test User"
        current_q_count = 1
        prev_question = "자기소개를 해주세요."
        applicant_answer = "저는 백엔드 개발자입니다. 잘 부탁드립니다."
        next_phase = "Skill Check"
        
        evaluation, next_q = evaluate_answer(
            job_title, applicant_name, current_q_count, prev_question, applicant_answer, next_phase
        )
        print(f"Evaluation: {evaluation}")
        print(f"Next Question: {next_q}")
        self.assertIsNotNone(evaluation)
        self.assertIsNotNone(next_q)
        self.assertNotEqual(evaluation, "평가 중 오류 발생")

if __name__ == '__main__':
    unittest.main()
