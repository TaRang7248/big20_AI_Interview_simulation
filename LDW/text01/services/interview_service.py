from .llm_service import LLMService
from db.sqlite import log_interview_step
from db.postgres import SessionLocal, InterviewResult
import uuid

class InterviewService:
    def __init__(self):
        self.llm = LLMService()

    async def start_interview(self, name: str, job_title: str):
        session_id = str(uuid.uuid4())
        first_question = await self.llm.generate_initial_question(job_title)
        return {
            "session_id": session_id,
            "question": first_question
        }

    async def process_answer(self, name: str, job_title: str, question: str, answer: str):
        # 1. Evaluate answer and get next question/follow-up
        evaluation = await self.llm.evaluate_and_next_action(job_title, question, answer)
        
        # 2. Log to SQLite
        log_interview_step(name, job_title, question, answer, evaluation)
        
        # 3. Save to PostgreSQL (with embedding for future reference/recovery)
        embedding = await self.llm.get_embedding(answer)
        db = SessionLocal()
        try:
            result = InterviewResult(
                candidate_name=name,
                job_title=job_title,
                question=question,
                answer=answer,
                evaluation=evaluation,
                embedding=embedding
            )
            db.add(result)
            db.commit()
        except Exception as e:
            print(f"Error saving to Postgres: {e}")
            db.rollback()
        finally:
            db.close()
            
        return evaluation
