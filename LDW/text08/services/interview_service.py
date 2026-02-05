from .llm_service import LLMService
from .stt_service import STTService
from .confidence_service import ConfidenceService
from db.sqlite import log_interview_step, get_questions_by_job
from db.postgres import SessionLocal, InterviewResult, QuestionPool
import uuid
import json

class InterviewService:
    def __init__(self):
        self.llm = LLMService()
        self.stt = STTService()
        self.sessions = {} # session_id -> { "current_step": 1, "is_follow_up": False, "history": [], "confidence_service": ... }

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
        # 1번째 질문은 항상 자기소개를 하도록 하며, 기술적 질문들이 섞인 컨텍스트를 제외하여 주제를 고정합니다.
        first_question = await self.llm.generate_question(job_title, "intro", None)
        
        self.sessions[session_id] = {
            "name": name,
            "job_title": job_title,
            "current_step": 1,
            "is_follow_up": False,
            "history": [],
            "combined_context": combined_context,
            "confidence_service": ConfidenceService()
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
        
        # 1. Evaluate answer
        evaluation = await self.llm.evaluate_and_next_action(job_title, question, answer, is_last_question)
        
        # Track scores for average calculation
        if "scores" not in session:
            session["scores"] = []
        session["scores"].append(evaluation.get("score", 0))
        
        # 2. Log to SQLite (interview_save.db)
        log_interview_step(name, job_title, question, answer, evaluation)
        
        # 3. Save to PostgreSQL for vector search
        try:
            embedding = await self.llm.get_embedding(answer)
            db = SessionLocal()
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
            db.close()
        except Exception as e:
            print(f"Error saving to Postgres: {e}")

        # Decide on next step
        # Rule: One tail question max per main question
        if evaluation.get("is_follow_up") and not session.get("is_follow_up_active"):
            session["is_follow_up_active"] = True
            next_question = evaluation["next_step_question"]
            is_completed = False
        else:
            # Advance to next main question
            session["is_follow_up_active"] = False
            session["current_step"] += 1
            
            if session["current_step"] > 10:
                avg_score = sum(session["scores"]) / len(session["scores"]) if session["scores"] else 0
                pass_fail = "합격" if avg_score >= 70 else "불합격"
                next_question = f"면접이 종료되었습니다. 평균 점수는 {avg_score:.1f}점이며, 결과는 '{pass_fail}'입니다. 수고하셨습니다."
                is_completed = True
                evaluation["avg_score"] = avg_score
                evaluation["result_status"] = pass_fail
                
                # Confidence Score
                conf_score = self.get_final_confidence_score(session_id)
                evaluation["confidence_score"] = conf_score
            else:
                stage = self._get_stage(session["current_step"])
                next_question = await self.llm.generate_question(job_title, stage, session["combined_context"])
                is_completed = False

        return {
            "evaluation": evaluation,
            "next_question": next_question,
            "step": session["current_step"],
            "is_completed": is_completed,
            "is_follow_up": session.get("is_follow_up_active", False)
        }

    def process_frame(self, session_id: str, image_data: bytes):
        if session_id in self.sessions:
            service = self.sessions[session_id]["confidence_service"]
            service.process_frame(image_data)

    def get_final_confidence_score(self, session_id: str):
        if session_id in self.sessions:
            service = self.sessions[session_id]["confidence_service"]
            return service.get_confidence_score()
        return 0

    async def evaluate_architecture_drawing(self, session_id: str, image_data_url: str):
        """Evaluates the architecture drawing provided by the candidate."""
        if session_id not in self.sessions:
             # Just proceed without saving if session is invalid for testing, or raise
             pass
        
        evaluation = await self.llm.evaluate_architecture(image_data_url)
        
        # Log to session history if needed, or just return
        # Might want to add to session scores or separate architecture score
        
        return evaluation

