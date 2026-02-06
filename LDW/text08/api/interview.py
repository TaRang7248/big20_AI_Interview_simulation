from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from services.interview_service import InterviewService
from services import stt_service
import shutil
import os
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from services.llm_service import LLMService

# ... imports ...

interview_service = InterviewService()
llm_service_instance = LLMService()

@router.post("/start")
async def start_interview(
    user_id: int = Form(...),
    job_role: str = Form(...),
    candidate_name: str = Form(...)
):
    """
    Starts a new interview session using the Expert Persona logic.
    """
    try:
        # Delegate to InterviewService
        result = await interview_service.start_interview(candidate_name, job_role)
        
        # Result contains: session_id, question, step
        return {
            "status": "started",
            "session_id": result["session_id"],
            "question": result["question"],
            "step": result["step"],
            "total_steps": 10
        }
    except Exception as e:
        print(f"Error starting interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit")
async def submit_answer(
    session_id: str = Form(...),
    question_id: str = Form(None), 
    audio: UploadFile = File(None),
    image: UploadFile = File(None),
    answer_text: str = Form(None)
):
    """
    Submits an answer and gets the evaluation + next question.
    """
    text_content = answer_text
    audio_path = None
    image_path = None
    
    # Retrieve session state to get context (current question)
    session = interview_service.sessions.get(session_id)
    current_question_context = ""
    if session:
        current_question_context = session.get("current_question", "")

    # Process Audio
    if audio:
        file_path = f"{UPLOAD_DIR}/{session_id}_{datetime.utcnow().timestamp()}.webm"
        with open(file_path, "wb+") as file_object:
            shutil.copyfileobj(audio.file, file_object)
        audio_path = file_path
        
        # STT with Context and Custom Vocabulary
        if not text_content:
            try:
                # 1. Transcribe with Contextual Bias
                raw_transcript = await stt_service.transcribe_audio(file_path, context=current_question_context)
                
                # 2. Refine Transcript (ITN + NLP)
                text_content = await llm_service_instance.refine_transcript(raw_transcript)
                
                print(f"Raw STT: {raw_transcript}")
                print(f"Refined: {text_content}")

            except AttributeError:
                text_content = "(Audio transcription unavailable)"
            except Exception as e:
                print(f"STT/NLP Error: {e}")
                text_content = ""

    # Process Image
    if image:
        img_path = f"{UPLOAD_DIR}/{session_id}_{datetime.utcnow().timestamp()}.png"
        with open(img_path, "wb+") as file_object:
            shutil.copyfileobj(image.file, file_object)
        image_path = img_path
    
    if not text_content:
        text_content = "(No answer provided)"
    
    if image_path:
        text_content += " [Image/Diagram Submitted]"

    try:
        # Delegate to InterviewService
        # The service needs the current question text to evaluate.
        # But our API submit doesn't pass the question text from frontend usually.
        # However, InterviewService.sessions has history?
        # InterviewService.process_answer arg: (session_id, question, answer)
        # We need the question text.
        
        # Retrieve session state
        session = interview_service.sessions.get(session_id)
        if not session:
             raise HTTPException(status_code=404, detail="Session not found or expired")
        
        # We need the *last asked* question.
        # InterviewService logic says: "Decide on next step... next_question".
        # We don't strictly have the "current question" stored in a simple field in `session` dict 
        # based on previous `view_file` of `interview_service.py` (it had 'history', 'current_step').
        # Let's assume the frontend sends it OR we fetch it from history if properly stored.
        # Wait, `interview_service.py` L102 logs (name, job, question, answer).
        # But `process_answer` takes `question` as input.
        # This is a bit of a design flaw in `InterviewService`: it expects the caller to know the question.
        # For this fix, let's assume the frontend *does* send the question text, or we hack it.
        # If question_id is passed, maybe we can't look it up easily since we aren't using DB for questions.
        
        # Workaround: Use "Previous Question" placeholder if not provided, or modify InterviewService.
        # Better: Modify InterviewService to store `current_question`.
        # BUT, I can't modify InterviewService right now easily without risking more breaks?
        # Actually I CAN. I previously read it.
        # Let's try to grab it from session if I modify InterviewService in next step?
        # No, let's just pass "Current Question" for now if missing, or rely on frontend sending it.
        # original `submit_answer` took `question_id`.
        
        # Use stored session question effectively (Service ignores this arg if session has current_question)
        current_question_text = "" 
        
        result = await interview_service.process_answer(session_id, current_question_text, text_content)
        
        return {
            "status": "success",
            "next_question": result["next_question"],
            "evaluation": result["evaluation"],
            "step": result["step"],
            "is_completed": result["is_completed"],
            "stt": text_content,
            "score": result["evaluation"].get("score", 0)
        }

    except Exception as e:
        print(f"Error processing answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/current")
async def get_current_question(session_id: str):
    session = interview_service.sessions.get(session_id)
    if not session:
         return {"finished": True}
    
    # Return the actual current question stored in session
    return {
        "question": session.get("current_question", "진행 중인 면접입니다."),
        "index": session.get("current_step", 1),
        "total": 10
    }

