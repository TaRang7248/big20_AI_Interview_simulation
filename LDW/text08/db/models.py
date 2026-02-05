from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Float, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    job_role = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("InterviewSession", back_populates="user")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    category = Column(String)  # e.g., "Intro", "Personality", "JobKnowledge"
    # Assuming 1536 dimensions for OpenAI embeddings, adjust if using different model
    embedding = Column(Vector(1536)) 
    
    answers = relationship("InterviewAnswer", back_populates="question")

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    total_score = Column(Float, nullable=True)
    feedback_summary = Column(Text, nullable=True) # Overall feedback

    user = relationship("User", back_populates="sessions")
    answers = relationship("InterviewAnswer", back_populates="session")

class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True) # Check if follow-up questions are in DB or dynamic
    question_content = Column(Text) # Store the actual question asked (especially for generated follow-ups)
    
    answer_text = Column(Text)
    answer_audio_url = Column(String, nullable=True)
    
    evaluation_json = Column(JSON) # Store score, feedback, follow-up suggestion
    score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("InterviewSession", back_populates="answers")
    question = relationship("Question", back_populates="answers")
