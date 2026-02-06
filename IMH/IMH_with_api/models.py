from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector # pgvector 연동
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    info = relationship("UserInfo", back_populates="user", uselist=False)
    resumes = relationship("Resume", back_populates="user")
    interviews = relationship("Interview", back_populates="user")

class UserInfo(Base):
    __tablename__ = "user_info"
    info_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), unique=True)
    name = Column(String)
    birth_date = Column(DateTime)
    gender = Column(String)
    address = Column(String)

    user = relationship("User", back_populates="info")

class Resume(Base):
    __tablename__ = "resumes"
    resume_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    target_role = Column(String)
    skills_text = Column(Text)
    experience_text = Column(Text)
    certifications_text = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="resumes")

class Interview(Base):
    __tablename__ = "interviews"
    interview_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    resume_id = Column(BigInteger, ForeignKey("resumes.resume_id"))
    persona = Column(String) # WARM, PRESSURE, LOGICAL 등
    status = Column(String, default="running")
    started_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    ended_at = Column(DateTime(timezone=True))
    total_questions_planned = Column(Integer, default=5)
    current_step = Column(Integer, default=1)
    progress_updated_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="interviews")
    messages = relationship("Message", back_populates="interview")
    evaluation = relationship("InterviewEvaluation", back_populates="interview", uselist=False)

class Message(Base):
    __tablename__ = "messages"
    message_id = Column(BigInteger, primary_key=True)
    interview_id = Column(BigInteger, ForeignKey("interviews.interview_id"))
    question_id = Column(BigInteger, ForeignKey("questions.question_id"), nullable=True)
    role = Column(String) # question, answer, system
    content_text = Column(Text)
    sequence_no = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    interview = relationship("Interview", back_populates="messages")

class Question(Base):
    __tablename__ = "questions"
    question_id = Column(BigInteger, primary_key=True)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text)
    tags = Column(JSONB) # 예: ["capability.knowledge", "backend"]
    embedding = Column(Vector(1536)) # OpenAI 임베딩 차원 기준
    embedding_model = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

class InterviewEvaluation(Base):
    __tablename__ = "interview_evaluations"
    evaluation_id = Column(BigInteger, primary_key=True)
    interview_id = Column(BigInteger, ForeignKey("interviews.interview_id"), unique=True)
    summary_text = Column(Text)
    feedback_text = Column(Text)
    decision = Column(String) # PASS, FAIL
    decision_reason_text = Column(Text)
    decision_created_at = Column(DateTime(timezone=True))

    interview = relationship("Interview", back_populates="evaluation")
    scores = relationship("EvaluationScore", back_populates="evaluation")

class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"
    score_id = Column(BigInteger, primary_key=True)
    evaluation_id = Column(BigInteger, ForeignKey("interview_evaluations.evaluation_id"))
    tag_id = Column(String) # 루브릭 태그 식별자
    score_value = Column(Float)
    rationale_text = Column(Text)
    evidence_message_ids = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    evaluation = relationship("InterviewEvaluation", back_populates="scores")

class WhiteboardNote(Base):
    __tablename__ = "whiteboard_notes"
    note_id = Column(BigInteger, primary_key=True)
    interview_id = Column(BigInteger, ForeignKey("interviews.interview_id"))
    message_id = Column(BigInteger, ForeignKey("messages.message_id"), nullable=True)
    content_json = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
