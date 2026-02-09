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
        self.sessions = {} # session_id -> { "current_step": 1, "is_follow_up": False, "history": [] }

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

    def _get_stage(self, step: int):
        if step == 1:
            return "intro"
        elif 2 <= step <= 4:
            return "personality"
        else:
            return "technical"

    async def start_interview(self, name: str, job_title: str):
        """Initializes the interview session and generates the first question."""
        session_id = str(uuid.uuid4())
        
        # 1. Try to get questions from SQLite (source interview.db)
        source_questions = get_questions_by_job(job_title)
        
        # 2. Try to get similar questions from Postgres (pgvector)
        rag_questions = await self.get_rag_context(job_title)
        
        # Combine contexts
        combined_context = list(set(source_questions + rag_questions))
        
        # 3. Generate initial question (Self-intro)
        first_question = await self.llm.generate_question(job_title, "intro", combined_context)
        
        self.sessions[session_id] = {
            "name": name,
            "job_title": job_title,
            "current_step": 1,
            "is_follow_up": False,
            "history": [],
            "combined_context": combined_context
        }
        
        return {
            "session_id": session_id,
            "question": first_question,
            "step": 1
        }

    async def transcribe_audio(self):
        """Stops recording and transcribes the audio."""
        filepath = self.stt.stop_recording()
        if filepath:
            return await self.stt.transcribe(filepath)
        return ""

    def start_recording(self):
        """Starts the PyAudio recording."""
        self.stt.start_recording()

    async def process_answer(self, session_id: str, question: str, answer: str):
        """Evaluates an answer, logs result, and decides on the next question or completion."""
        if session_id not in self.sessions:
            raise Exception("Invalid session ID")
        
        session = self.sessions[session_id]
        name = session["name"]
        job_title = session["job_title"]
        current_step = session["current_step"]
        
        is_last_question = (current_step == 10)
        
        # 1. Evaluate answer and get next action
        evaluation = await self.llm.evaluate_and_next_action(job_title, question, answer, is_last_question)
        
        # 2. Log to SQLite (interview_save.db)
        log_interview_step(name, job_title, question, answer, evaluation)
        
        # 3. Save to PostgreSQL for vector search
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

        # Decide on next step
        if evaluation.get("is_follow_up") and not session["is_follow_up"]:
            # Provide ONLY one follow-up to prevent infinite loop
            session["is_follow_up"] = True
            next_question = evaluation["next_step_question"]
            is_completed = False
        else:
            # Advance to next main question
            session["is_follow_up"] = False
            session["current_step"] += 1
            if session["current_step"] > 10:
                next_question = "면접이 종료되었습니다. 수고하셨습니다."
                is_completed = True
            else:
                stage = self._get_stage(session["current_step"])
                next_question = await self.llm.generate_question(job_title, stage, session["combined_context"])
                is_completed = False

        return {
            "evaluation": evaluation,
            "next_question": next_question,
            "step": session["current_step"],
            "is_completed": is_completed
        }
