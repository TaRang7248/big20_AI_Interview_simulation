import os
import json
import logging
import time
from fastapi import APIRouter, File, UploadFile, Form, BackgroundTasks
from ..services.video_analysis_service import video_analysis_service
from ..config import UPLOAD_FOLDER

router = APIRouter(prefix="/api/video", tags=["video"])
logger = logging.getLogger(__name__)

# 비디오 로그 디렉토리가 존재하는지 확인
VIDEO_LOGS_DIR = os.path.join(UPLOAD_FOLDER, "video_logs")
os.makedirs(VIDEO_LOGS_DIR, exist_ok=True)

def append_video_log(interview_number: str, analysis_result: dict):
    """
    특정 면접의 JSON 파일에 분석 결과를 추가합니다.
    """
    try:
        file_path = os.path.join(VIDEO_LOGS_DIR, f"{interview_number}.json")
        
        # 타임스탬프 추가
        analysis_result["timestamp"] = time.time()
        
        # 기존 파일 읽기 또는 새로 만들기
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
    비디오 프레임을 수신하여 분석하고 결과를 로깅합니다.
    """
    try:
        contents = await frame.read()
        
        # 분석 수행
        result = video_analysis_service.process_frame(contents)
        
        # 백그라운드에서 파일에 로깅
        background_tasks.add_task(append_video_log, interview_number, result)
        
        return {"success": True, "analysis": result}
        
    except Exception as e:
        logger.error(f"Video analysis endpoint error: {e}")
        return {"success": False, "error": str(e)}
