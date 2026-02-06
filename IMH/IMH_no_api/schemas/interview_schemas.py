from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class InterviewerPersona(str, Enum):
    WARM = "WARM"
    PRESSURE = "PRESSURE"
    LOGICAL = "LOGICAL"


class InterviewQuestionIntent(BaseModel):
    type: str = Field(..., description="질문 유형 (예: FOLLOW_UP, PROJECT_DEEP_DIVE, RETRY_ERROR)")
    detail: str = Field(..., description="질문의 상세 의도")


class InterviewQuestionMeta(BaseModel):
    research_needed: bool
    focus_area: str


class InterviewQuestionOut(BaseModel):
    """면접 질문 응담 스키마."""
    question: str
    intent: InterviewQuestionIntent
    meta: InterviewQuestionMeta


class CriterionEvaluation(BaseModel):
    """항목별 평가 결과."""
    score: int = Field(..., ge=1, le=5, description="1~5점 사이의 점수")
    justification: str = Field(..., description="점수 부여 이유")
    evidence: List[str] = Field(default_factory=list, description="점수의 근거가 된 답변 핵심 구절")
    turn_reference: List[int] = Field(default_factory=list, description="근거가 나타난 대화 순번(Turn)")


class EvaluationRubric(BaseModel):
    """전체 면접 평가 루브릭."""
    technical_skill: CriterionEvaluation
    communication: CriterionEvaluation
    problem_solving: CriterionEvaluation
    cultural_fit: CriterionEvaluation
    overall_feedback: str = Field(..., description="전체적인 면접 총평")
    
    # Stage 3 대비: 비언어적 데이터 분석 확장 필드
    non_verbal_cues: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="비언어적 지표 (시선 처리, 표정 분석 등) 확장 필드"
    )

    model_config = ConfigDict(from_attributes=True)
