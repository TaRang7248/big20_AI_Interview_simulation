from db.repositories.user_repository import UserRepository
from db.repositories.interview_repository import InterviewRepository
from db.repositories.evaluation_repository import EvaluationRepository
from db.connection import init_db
import os

def test_repositories():
    print("--- Starting Repository Tests ---")

    # 1. Initialize DB (ensure tables exist)
    init_db()
    
    user_repo = UserRepository()
    interview_repo = InterviewRepository()
    eval_repo = EvaluationRepository()

    # 2. Test User Repository
    print("\n[Test] User Repository")
    email = "test_user@example.com"
    try:
        user_id = user_repo.create_user(email, "hashed_password_123")
        print(f"  - Created User ID: {user_id}")
    except ValueError:
        # If user exists from previous run, fetch ID
        user = user_repo.get_user_by_email(email)
        user_id = user['user_id']
        print(f"  - User already exists, ID: {user_id}")

    pii_id = user_repo.save_user_pii(user_id, "홍길동", "1990-01-01", "Male", "Seoul")
    print(f"  - Saved PII ID: {pii_id}")

    resume_id = user_repo.save_resume(user_id, "Backend Dev", "Python, SQL", "3 Years", "AWS Cloud")
    print(f"  - Saved Resume ID: {resume_id}")

    # 3. Test Interview Repository
    print("\n[Test] Interview Repository")
    interview_id = interview_repo.create_interview(user_id, resume_id, "Tech Interviewer")
    print(f"  - Created Interview ID: {interview_id}")

    interview_repo.add_message(interview_id, "sys", "면접을 시작합니다.", 1)
    interview_repo.add_message(interview_id, "q", "자기소개 해주세요.", 2)
    interview_repo.add_message(interview_id, "a", "저는 파이썬 개발자입니다.", 3)
    print("  - Added messages")

    messages = interview_repo.get_messages(interview_id)
    print(f"  - Retrieved {len(messages)} messages")
    assert len(messages) == 3

    # 4. Test Evaluation Repository
    print("\n[Test] Evaluation Repository")
    eval_id = eval_repo.create_evaluation(interview_id, "Good interview", "Technical skills are strong.")
    print(f"  - Created Evaluation ID: {eval_id}")

    score_id = eval_repo.add_score(eval_id, "Technical", 85, "Good Python knowledge")
    print(f"  - Added Score ID: {score_id}")

    decision_id = eval_repo.set_pass_fail_decision(eval_id, "pass", "Qualified")
    print(f"  - Decision ID: {decision_id}")

    print("\n--- Repository Tests Completed Successfully ---")

if __name__ == "__main__":
    test_repositories()
