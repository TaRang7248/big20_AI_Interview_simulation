from pydantic import BaseModel, Field
from typing import Optional
from .policy import InterviewMode, get_policy

class SessionConfig(BaseModel):
    """
    Configuration for an Interview Session.
    Derived from Job Posting options.
    """
    total_question_limit: int = Field(..., description="Total number of questions")
    min_question_count: int = Field(default=10, description="Minimum questions guaranteed")
    question_timeout_sec: int = Field(default=120, description="Time limit per question in seconds")
    silence_timeout_sec: int = Field(default=15, description="Silence timeout in seconds")
    early_exit_enabled: bool = Field(default=False, description="Whether early exit based on score is enabled")
    mode: InterviewMode = Field(default=InterviewMode.ACTUAL, description="Session Mode: ACTUAL or PRACTICE")
    job_id: Optional[str] = Field(default=None, description="Linked Job Posting ID (if applicable)")
    
    # Contract: min_question_count must default to 10 as per policy
    
class SessionContext(BaseModel):
    """
    Runtime context for a session.
    Represents the Hot State (Redis-like).
    """
    session_id: str
    job_id: str
    status: str
    started_at: Optional[float] = None # Timestamp
    current_step: int = 0
    completed_questions_count: int = 0
    early_exit_signaled: bool = False # Signal from Evaluation Layer
    history: list = Field(default_factory=list)
