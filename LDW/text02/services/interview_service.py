from .llm_service import LLMService
from .stt_service import STTService
from db.sqlite import log_interview_step
from db.postgres import SessionLocal, InterviewResult, QuestionPool
from pgvector.sqlalchemy import Vector
import uuid
import json

class InterviewService:
    def __init__(self):
        self.llm = LLMService()
        self.stt = STTService()

    async def get_similar_questions(self, job_title, limit=3):
        db = SessionLocal()
        try:
            query_emb = await self.llm.get_embedding(job_title)
            # Simple vector search using pgvector
            results = db.query(QuestionPool).order_by(
                QuestionPool.embedding.cosine_distance(query_emb)
            ).limit(limit).all()
            return results
        finally:
            db.close()

    async def start_interview(self, name: str, job_title: str):
        session_id = str(uuid.uuid4())
        # Pass the vector search function to LLM for RAG
        first_question = await self.llm.generate_initial_question(job_title, self.get_similar_questions)
        return {
            "session_id": session_id,
            "question": first_question
        }

    async def transcribe_audio(self, audio_data: bytes):
        return await self.stt.transcribe_from_blob(audio_data)

    async def process_answer(self, name: str, job_title: str, question: str, answer: str):
        # 1. Evaluate answer and get next question/follow-up
        evaluation = await self.llm.evaluate_and_next_action(job_title, question, answer)
        
        # 2. Log to SQLite (interview_save.db)
        log_interview_step(name, job_title, question, answer, evaluation)
        
        # 3. Save to PostgreSQL (interview_db)
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
