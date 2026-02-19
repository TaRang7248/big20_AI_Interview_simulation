import os
import json
import logging
import time
from fastapi import APIRouter, File, UploadFile, Form, BackgroundTasks
from ..services.video_analysis_service import video_analysis_service
from ..config import UPLOAD_FOLDER

router = APIRouter(prefix="/api/video", tags=["video"])
logger = logging.getLogger(__name__)

# Ensure video logs directory exists
VIDEO_LOGS_DIR = os.path.join(UPLOAD_FOLDER, "video_logs")
os.makedirs(VIDEO_LOGS_DIR, exist_ok=True)

def append_video_log(interview_number: str, analysis_result: dict):
    """
    Appends the analysis result to a JSON file for the specific interview.
    """
    try:
        file_path = os.path.join(VIDEO_LOGS_DIR, f"{interview_number}.json")
        
        # Add timestamp
        analysis_result["timestamp"] = time.time()
        
        # Read existing or create new
        if os.path.exists(file_path):
            with open(file_path, "r+", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
                
                data.append(analysis_result)
                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.truncate()
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([analysis_result], f, ensure_ascii=False, indent=2)
                
    except Exception as e:
        logger.error(f"Failed to append video log: {e}")

@router.post("/analyze")
async def analyze_frame(
    background_tasks: BackgroundTasks,
    interview_number: str = Form(...),
    frame: UploadFile = File(...)
):
    """
    Receives a video frame, analyzes it, and logs the result.
    """
    try:
        contents = await frame.read()
        
        # Perform analysis
        result = video_analysis_service.process_frame(contents)
        
        # Log to file in background
        background_tasks.add_task(append_video_log, interview_number, result)
        
        return {"success": True, "analysis": result}
        
    except Exception as e:
        logger.error(f"Video analysis endpoint error: {e}")
        return {"success": False, "error": str(e)}
