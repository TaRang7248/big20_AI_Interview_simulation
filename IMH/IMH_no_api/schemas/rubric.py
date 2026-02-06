from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


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
