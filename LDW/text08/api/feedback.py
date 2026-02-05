from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.database import get_db
from db.models import InterviewSession, InterviewAnswer

router = APIRouter()

@router.get("/{session_id}")
async def get_feedback(session_id: int, db: AsyncSession = Depends(get_db)):
    # Get Session
    session_res = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = session_res.scalars().first()
    
    if not session:
        return {"error": "Session not found"}
        
    # Get Answers
    answers_res = await db.execute(select(InterviewAnswer).where(InterviewAnswer.session_id == session_id).order_by(InterviewAnswer.id))
    answers = answers_res.scalars().all()
    
    total_score = 0
    count = 0
    details = []
    
    for ans in answers:
        score = ans.score or 0
        total_score += score
        count += 1
        details.append({
            "question": ans.question_content,
            "answer": ans.answer_text,
            "score": score,
            "feedback": ans.evaluation_json.get("feedback") if ans.evaluation_json else "No feedback"
        })
        
    avg_score = total_score / count if count > 0 else 0
    passed = avg_score >= 70 # Pass criteria
    
    return {
        "session_id": session_id,
        "average_score": avg_score,
        "passed": passed,
        "details": details
    }
