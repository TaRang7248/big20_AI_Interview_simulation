from enum import Enum
from pydantic import BaseModel, ConfigDict


class InterviewerPersona(str, Enum):
    WARM = "WARM"
    PRESSURE = "PRESSURE"
    LOGICAL = "LOGICAL"


class InterviewCreateIn(BaseModel):
    """면접 생성 입력."""
    profile_id: int
    persona: InterviewerPersona = InterviewerPersona.WARM


class InterviewOut(BaseModel):
    """면접 출력."""
    id: int
    profile_id: int
    status: str
    persona: InterviewerPersona

    model_config = ConfigDict(from_attributes=True)


class InterviewQuestionIntent(BaseModel):
    type: str
    detail: str


class InterviewQuestionMeta(BaseModel):
    research_needed: bool
    focus_area: str


class InterviewQuestionOut(BaseModel):
    question: str
    intent: InterviewQuestionIntent
    meta: InterviewQuestionMeta
