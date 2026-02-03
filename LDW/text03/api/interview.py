from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from .schemas import CandidateInfo, InterviewStep
from services.interview_service import InterviewService
import json

router = APIRouter()
interview_service = InterviewService()

@router.post("/start")
async def start_interview(candidate: CandidateInfo):
    """Starts the interview process for a candidate."""
    try:
        result = await interview_service.start_interview(candidate.name, candidate.job_title)
        return result
    except Exception as e:
        print(f"Start Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribes uploaded audio blob and returns the text."""
    try:
        audio_data = await audio.read()
        text = await interview_service.transcribe_audio(audio_data)
        return {"text": text}
    except Exception as e:
        print(f"Transcribe Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/answer")
async def submit_answer(step: InterviewStep):
    """Processes candidate answer, evaluates it, and generates the next question."""
    try:
        evaluation = await interview_service.process_answer(
            step.candidate_name, 
            step.job_title, 
            step.question, 
            step.answer
        )
        return evaluation
    except Exception as e:
        print(f"Answer Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
