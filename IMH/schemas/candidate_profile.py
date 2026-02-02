from __future__ import annotations

from pydantic import BaseModel


class CandidateProfileCreateIn(BaseModel):
    """프로필 생성 입력."""
    resume_text: str
    target_job: str
    target_company: str
    skills: str = ""


class CandidateProfileOut(BaseModel):
    """프로필 출력."""
    id: int
    user_id: int
    resume_text: str
    target_job: str
    target_company: str
    skills: str

    class Config:
        from_attributes = True
