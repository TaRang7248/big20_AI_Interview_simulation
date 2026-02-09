# 🗄️ 1단계: 데이터베이스 모델 정의

# Python 객체를 PostgreSQL 테이블로 매핑
# 핵심 테이블:
# - InterviewSession: 면접 세션 정보 (누가, 언제)
# - Transcript: 대화 기록 (질문과 답변 텍스트)
# - EvaluationReport: 최종 평가 결과 (점수, 피드백)

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import datetime

Base = declarative_base()

# InterviewSession: 면접 세션 정보 (누가, 언제)
class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, unique=True, index=True)  # LangGraph의 thread_id와 매핑
    candidate_name = Column(String, nullable=True)
    status = Column(String, default="in_progress")       # in_progress, completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계 설정
    transcripts = relationship("Transcript", back_populates="session")
    report = relationship("EvaluationReport", back_populates="session", uselist=False)

# Transcript: 대화 기록 (질문과 답변 텍스트)
class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    sender = Column(String)  # 'human' or 'ai'
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="transcripts")

# EvaluationReport: 최종 평가 결과 (점수, 피드백)
class EvaluationReport(Base):
    __tablename__ = "evaluation_reports"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    
    total_score = Column(Integer)             # 종합 점수 (100점 만점 등)
    technical_score = Column(Integer)         # 기술 점수
    communication_score = Column(Integer)     # 커뮤니케이션 점수
    
    summary = Column(Text)                    # 종합 요약 평
    details = Column(JSON)                    # 상세 분석 결과 (JSON 저장)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="report")