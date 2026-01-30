from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    original_answer = Column(Text, nullable=True) # From the JSON, for reference/RAG
    category = Column(String, nullable=True)

class InterviewSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, default="Candidate")
    start_time = Column(DateTime, default=datetime.utcnow)
    
    interactions = relationship("InterviewInteraction", back_populates="session")

class InterviewInteraction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    
    bot_question = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=True)
    
    # JSON string or distinct columns for evaluation
    llm_evaluation = Column(Text, nullable=True) 
    
    interaction_type = Column(String, default="initial") # initial, followup
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("InterviewSession", back_populates="interactions")
