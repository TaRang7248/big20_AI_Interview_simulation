from fastapi import APIRouter, Depends, HTTPException
from api.interview import interview_service

router = APIRouter()

@router.get("/{session_id}")
async def get_feedback(session_id: str):
    # 1. Try to get from in-memory session (Primary for this version)
    session = interview_service.sessions.get(session_id)
    
    if not session:
        return {"error": "Session not found or expired"}
        
    # Calculate scores from session data
    answer_scores = session.get("answer_scores", [])
    video_scores_list = session.get("video_scores_list", [])
    
    # Calculate Averages
    avg_score = sum(answer_scores) / len(answer_scores) if answer_scores else 0
    
    avg_confidence = 0
    avg_attitude = 0
    avg_video_score = 0
    
    if video_scores_list:
        avg_confidence = sum([v.get("confidence", 0) for v in video_scores_list]) / len(video_scores_list)
        avg_attitude = sum([v.get("attitude", 0) for v in video_scores_list]) / len(video_scores_list)
        avg_video_score = sum([v.get("avg_video_score", 0) for v in video_scores_list]) / len(video_scores_list)
        
    # Pass criteria: Answer Avg >= 70 AND Video Avg >= 70
    passed = (avg_score >= 70) and (avg_video_score >= 70)
    
    # Construct Details List
    # We need to correlate questions, answers, and scores.
    # session["history"] might be empty if we didn't populate it explicitly in service (check service logic).
    # Checking interview_service.py: log_interview_step logs to SQLite, but session dict has:
    # "answer_scores" list.
    # We don't have a clean list of (Q, A, Score) in the session dict easily available 
    # unless we parse 'history' if it was being used, OR query the SQLite DB log.
    
    # Let's try to best-effort reconstruct or just list what we have.
    # Actually, `interview_service.sessions` doesn't seem to store the full Q&A history in the dictionary deeply enough 
    # to easily reconstruct the full list for the UI without querying the DB.
    # However, for the IMMEDIATE fix of "Score not showing", we have the aggregates.
    
    return {
        "session_id": session_id,
        "average_score": round(avg_score, 1),
        "average_video_score": round(avg_video_score, 1),
        "passed": passed,
        "details": [], # Todo: Retrieve full details from SQLite logs if needed, but summary is most important now.
        "message": "상세 내역은 서버 로그를 확인해주세요."
    }

