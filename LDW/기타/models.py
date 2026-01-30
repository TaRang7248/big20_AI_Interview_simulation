from sqlalchemy import Column, Integer, Text, JSON, DateTime
from datetime import datetime
from .database import Base

class InterviewResult(Base):
    __tablename__ = "interview_results"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    evaluation = Column(JSON, nullable=False)  # LLM evaluation (score, feedback, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
