from pydantic import BaseModel
from typing import Optional, List, Dict

class CandidateInfo(BaseModel):
    name: str
    job_title: str

class InterviewStep(BaseModel):
    candidate_name: str
    job_title: str
    question: str
    answer: str

class EvaluationResult(BaseModel):
    score: int
    feedback: str
    is_follow_up: bool
    next_step_question: str

class InterviewSession(BaseModel):
    session_id: str
    candidate_name: str
    job_title: str
    history: List[Dict[str, str]] = []
