from .llm_service import LLMService
from .stt_service import STTService
from db.sqlite import log_interview_step, get_questions_by_job
from db.postgres import SessionLocal, InterviewResult, QuestionPool
import uuid
import json

class InterviewService:
    def __init__(self):
        self.llm = LLMService()
        self.stt = STTService()

    async def get_rag_context(self, job_title: str, limit: int = 3):
        """Fetches similar questions from PostgreSQL (pgvector) for RAG context."""
        db = SessionLocal()
        try:
            query_emb = await self.llm.get_embedding(job_title)
            # Find relevant questions by vector similarity
            results = db.query(QuestionPool).order_by(
                QuestionPool.embedding.cosine_distance(query_emb)
            ).limit(limit).all()
            return [r.question for r in results]
        except Exception as e:
            print(f"RAG Error: {e}")
            return []
        finally:
            db.close()

    async def start_interview(self, name: str, job_title: str):
        """Initializes the interview session and generates the first question."""
        session_id = str(uuid.uuid4())
        
        # 1. Try to get questions from SQLite (source interview.db)
        source_questions = get_questions_by_job(job_title)
        
        # 2. Try to get similar questions from Postgres (pgvector)
        rag_questions = await self.get_rag_context(job_title)
        
        # Combine contexts
        combined_context = list(set(source_questions + rag_questions))
        
        # 3. Generate initial question using LLM
        first_question = await self.llm.generate_initial_question(job_title, combined_context)
        
        return {
            "session_id": session_id,
            "question": first_question
        }

    async def transcribe_audio(self, audio_data: bytes):
        """Processes audio through STT (Whisper)."""
        return await self.stt.transcribe_from_blob(audio_data)

    async def process_answer(self, name: str, job_title: str, question: str, answer: str):
        """Evaluates an answer, logs result, and generates next question."""
        # 1. Evaluate answer and get next action
        evaluation = await self.llm.evaluate_and_next_action(job_title, question, answer)
        
        # 2. Log to SQLite (interview_save.db) - Requested by user
        log_interview_step(name, job_title, question, answer, evaluation)
        
        # 3. Save to PostgreSQL for later vector search
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
