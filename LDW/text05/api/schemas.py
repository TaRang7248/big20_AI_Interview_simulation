from pydantic import BaseModel
from typing import Optional, Any

class CandidateInfo(BaseModel):
    name: str
    job_title: str

class InterviewStartResponse(BaseModel):
    session_id: str
    question: str
    step: int

class InterviewStep(BaseModel):
    session_id: str
    question: str
    answer: str

class InterviewEvaluation(BaseModel):
    score: int
    feedback: str
    is_follow_up: bool
    next_step_question: str
