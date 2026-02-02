from __future__ import annotations

from pydantic import BaseModel


class InterviewCreateIn(BaseModel):
    """면접 생성 입력."""
    profile_id: int


class InterviewOut(BaseModel):
    """면접 출력."""
    id: int
    profile_id: int
    status: str

    class Config:
        from_attributes = True
