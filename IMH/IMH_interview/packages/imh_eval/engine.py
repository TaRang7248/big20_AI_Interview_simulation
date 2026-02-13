from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .schema import EvaluationResult, RubricScoreItem, EvidenceData
from .rules import (
    calculate_knowledge_score,
    calculate_problem_solving_score,
    calculate_communication_score,
    calculate_attitude_score
)
from .weights import get_weights

class EvaluationContext(BaseModel):
    """
    Input context for evaluation. 
    Combines raw analysis results and mock data for missing providers.
    """
    job_category: str = Field(..., description="DEV or NON_TECH")
    job_id: Optional[str] = Field(None, description="Job ID")
    
    # Analysis Inputs
    answer_text: str
    code_snippet: Optional[str] = None
    hint_count: int = 0
    
    # Provider Results (Raw Dicts from previous tasks)
    visual_analysis: Optional[Dict[str, Any]] = None
    emotion_analysis: Optional[Dict[str, Any]] = None
    
    # Mock Data for Missing Providers (RAG/LLM)
    # in real implemenation, these would be results from those providers
    rag_keywords_found: List[str] = Field(default_factory=list)
    ast_complexity: Optional[float] = None
    star_structure_detected: bool = False
    rephrasing_detected: bool = False

class RubricEvaluator:
    def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        # 1. Get Weights
        weights = get_weights(context.job_category)
        
        # 2. Calculate Category Scores
        
        # 2.1 Knowledge
        knowledge_score = calculate_knowledge_score(context.rag_keywords_found, context.ast_complexity)
        knowledge_item = RubricScoreItem(
            category="직무 역량",
            tag_code="capability.knowledge",
            score=knowledge_score,
            rationale=f"Keywords matched: {len(context.rag_keywords_found)}",
            evidence_data=EvidenceData(
                keyword_match=context.rag_keywords_found,
                ast_complexity=context.ast_complexity
            )
        )
        
        # 2.2 Problem Solving
        ps_score = calculate_problem_solving_score(context.hint_count)
        ps_item = RubricScoreItem(
            category="문제 해결",
            tag_code="capability.problem_solving",
            score=ps_score,
            rationale=f"Hints used: {context.hint_count}",
            evidence_data=EvidenceData(
                hint_count=context.hint_count,
                rephrasing_detected=context.rephrasing_detected
            )
        )
        
        # 2.3 Communication
        comm_score = calculate_communication_score(context.star_structure_detected)
        comm_item = RubricScoreItem(
            category="의사소통",
            tag_code="capability.communication",
            score=comm_score,
            rationale=f"STAR structure: {context.star_structure_detected}",
            evidence_data=EvidenceData(
                star_structure=context.star_structure_detected
            )
        )
        
        # 2.4 Attitude
        # Extract metrics from analysis dicts (Defensive extraction)
        gaze_pct = 0.0
        neg_emotion_pct = 0.0
        
        if context.visual_analysis:
            # Assuming imh_providers.visual result structure (TASK-010)
            # visual_analysis = {"gaze": {"center_ratio": 0.8}, ...}
            gaze_pct = context.visual_analysis.get("gaze", {}).get("center_ratio", 0.0) * 100.0
            
        if context.emotion_analysis:
            # Assuming imh_providers.emotion result structure (TASK-008)
            # emotion_analysis = {"time_series": [{"emotion": "fear"}, ...]}
            # For simplicity in mock, let's assume raw counts or list
            # But here we parse list of emotions
            emotions = [entry.get("emotion") for entry in context.emotion_analysis.get("time_series", [])]
            if emotions:
                neg_count = emotions.count("fear") + emotions.count("sad")
                neg_emotion_pct = (neg_count / len(emotions)) * 100.0
        
        attitude_score = calculate_attitude_score(gaze_pct, neg_emotion_pct)
        attitude_item = RubricScoreItem(
            category="태도/비언어",
            tag_code="capability.attitude",
            score=attitude_score,
            rationale=f"Gaze: {gaze_pct:.1f}%, NegEmotion: {neg_emotion_pct:.1f}%",
            evidence_data=EvidenceData(
                gaze_center_percent=gaze_pct,
                negative_emotion_percent=neg_emotion_pct
            )
        )
        
        # 3. Aggregate Total Score
        items = [knowledge_item, ps_item, comm_item, attitude_item]
        total_weighted_score = 0.0
        
        for item in items:
            # Use tag_code as key for weights
            weight = weights.get(item.tag_code, 0.0)
            total_weighted_score += item.score * weight
            
        return EvaluationResult(
            total_score=total_weighted_score,
            details=items,
            job_category=context.job_category,
            job_id=context.job_id
        )
