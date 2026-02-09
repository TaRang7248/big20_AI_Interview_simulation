# 🗄️ 1단계: 데이터베이스 모델 정의 (user 추가 버전 26.02.09)

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

# 1. [신규] 사용자 테이블 (로그인/회원관리용)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)  # 닉네임 (로그인 ID)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 설정: 한 유저는 여러 개의 면접 세션을 가질 수 있음
    sessions = relationship("InterviewSession", back_populates="user")


# 2. [수정] 면접 세션 정보 (user_id 추가)
class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    
    # [핵심 변경] 누가 본 면접인가? (User 테이블과 연결)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 
    
    thread_id = Column(String, unique=True, index=True)
    candidate_name = Column(String, nullable=True)
    status = Column(String, default="in_progress")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="sessions")  # 유저와 연결
    transcripts = relationship("Transcript", back_populates="session")
    report = relationship("EvaluationReport", back_populates="session", uselist=False)


# 3. Transcript: 대화 기록 (변경 없음)
class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    sender = Column(String)  # 'human' or 'ai'
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    emotion = Column(String, nullable=True)

    session = relationship("InterviewSession", back_populates="transcripts")


# 4. [수정] 평가 결과 (문제해결 점수 추가)
class EvaluationReport(Base):
    __tablename__ = "evaluation_reports"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    
    total_score = Column(Integer)           # 종합 점수
    
    # 상세 점수 컬럼 (육각형 차트용)
    technical_score = Column(Integer, default=0)        # 기술 점수
    communication_score = Column(Integer, default=0)    # 소통 점수
    problem_solving_score = Column(Integer, default=0)  # [추가됨] 문제해결 점수
    
    summary = Column(Text)                  # 종합 요약 평
    details = Column(JSON, nullable=True)   # 상세 분석 결과 (JSON 원본)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="report")