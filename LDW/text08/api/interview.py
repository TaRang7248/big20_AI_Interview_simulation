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
            data = await websocket.receive_bytes()
            if data:
                # Transcribe chunk
                text = await interview_service.stt.transcribe_blob(data)
                if text:
                    await websocket.send_json({"status": "transcribed", "text": text})
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")

# --- Vision AI (DeepFace) ---
from services.vision_service import VisionService
vision_service = VisionService()

@router.post("/analyze_face")
async def analyze_face(file: UploadFile = File(...), session_id: str = Form(None)):
    """Analyzes a video frame for emotion and processes confidence."""
    try:
        image_content = await file.read()
        
        # 1. Vision Analysis (Emotion) - for UI feedback
        # We need to run this concurrently effectively or just await it
        result = await vision_service.analyze_frame(image_content)
        
        # 2. Confidence Analysis (Background process)
        if session_id:
            # Run directly since it's fast media pipe calculation
            interview_service.process_frame(session_id, image_content)
            
        return result
    except Exception as e:
        print(f"Face Analysis Error: {e}")
        # Return neutral fallback rather than 500 to keep UI alive
        return {"dominant_emotion": "neutral", "error": str(e)}
