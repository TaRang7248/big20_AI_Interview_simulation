from fastapi import APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from .schemas import CandidateInfo, InterviewStep, InterviewStartResponse
from services.interview_service import InterviewService
import asyncio
import json

router = APIRouter()
interview_service = InterviewService()

@router.post("/start", response_model=InterviewStartResponse)
async def start_interview(candidate: CandidateInfo):
    """Starts the interview process for a candidate."""
    try:
        result = await interview_service.start_interview(candidate.name, candidate.job_title)
        return result
    except Exception as e:
        print(f"Start Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribes client-side audio blob."""
    try:
        audio_content = await file.read()
        text = await interview_service.stt.transcribe_blob(audio_content)
        return {"text": text}
    except Exception as e:
        print(f"Transcription Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/answer")
async def submit_answer(step: InterviewStep):
    """Processes candidate answer, evaluates it, and generates the next question."""
    try:
        result = await interview_service.process_answer(
            step.session_id,
            step.question,
            step.answer
        )
        return result
    except Exception as e:
        print(f"Answer Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/stt")
async def websocket_stt(websocket: WebSocket):
    """WebSocket for real-time STT updates."""
    await websocket.accept()
    try:
        while True:
            # Send current transcript every second while recording
            if interview_service.stt.is_recording:
                # This is a bit of a hack for "real-time" with Whisper
                # We can't easily do partial transcripts without stopping
                # So we'll just send an "In Progress" status for now
                # Or we could implement a more sophisticated chunking logic here
                await websocket.send_json({"status": "recording", "text": "말씀하시는 중..."})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")
