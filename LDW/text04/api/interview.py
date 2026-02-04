from fastapi import APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from .schemas import CandidateInfo, InterviewStep
from services.interview_service import InterviewService
import asyncio
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

@router.post("/start-recording")
async def start_recording():
    """Triggers the server-side PyAudio recording."""
    try:
        interview_service.start_recording()
        return {"status": "recording started"}
    except Exception as e:
        print(f"Start Recording Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-recording")
async def stop_recording():
    """Stops the server-side PyAudio recording and transcribes."""
    try:
        text = await interview_service.transcribe_audio()
        return {"text": text}
    except Exception as e:
        print(f"Stop Recording Error: {e}")
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
