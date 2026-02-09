# YJH/services/transcript_service.py

from sqlalchemy.orm import Session
from YJH.models import Transcript, InterviewSession

def save_transcript(db: Session, thread_id: str, sender: str, content: str, emotion: str = None):
    """
    대화 내용을 DB에 저장합니다.
    - emotion: 감정 상태 (happy, fear, neutral 등) 추가
    """
    # 1. thread_id로 세션 찾기
    session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
    
    # 세션이 없으면 새로 생성 (안전 장치)
    if not session:
        session = InterviewSession(thread_id=thread_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # 2. 대화 기록 저장
    transcript = Transcript(
        session_id=session.id,
        sender=sender,
        content=content,
        emotion=emotion  # [★핵심] 감정 데이터도 같이 저장!
    )
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    
    return transcript