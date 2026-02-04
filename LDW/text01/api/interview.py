from fastapi import APIRouter, HTTPException
from .schemas import CandidateInfo, InterviewStep, EvaluationResult
from services.interview_service import InterviewService

router = APIRouter()
interview_service = InterviewService()

@router.post("/start")
async def start_interview(candidate: CandidateInfo):
    try:
        result = await interview_service.start_interview(candidate.name, candidate.job_title)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/answer")
async def submit_answer(step: InterviewStep):
    try:
        evaluation = await interview_service.process_answer(
            step.candidate_name, 
            step.job_title, 
            step.question, 
            step.answer
        )
        return evaluation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
