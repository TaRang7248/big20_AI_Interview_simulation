from pydantic import BaseModel
from typing import Optional, Any

class CandidateInfo(BaseModel):
    name: str
    job_title: str

class InterviewStartResponse(BaseModel):
    session_id: str
    question: str

class InterviewStep(BaseModel):
    candidate_name: str
    job_title: str
    question: str
    answer: str

class InterviewEvaluation(BaseModel):
    score: int
    feedback: str
    is_follow_up: bool
    next_step_question: str
