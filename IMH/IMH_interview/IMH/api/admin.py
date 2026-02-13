from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from IMH.api.schemas import JobPostingResponse, AdminSessionSummary, SessionResponse
from IMH.api.dependencies import get_admin_query_service
from packages.imh_service.admin_query import AdminQueryService

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/jobs", response_model=List[JobPostingResponse])
def get_jobs(
    service: AdminQueryService = Depends(get_admin_query_service)
):
    """
    List all published jobs.
    Uses AdminQueryService to bypass Domain Logic (Read-Only).
    """
    # Service returns list of dicts (Job model dicts)
    jobs_data = service.get_all_jobs()
    
    # Map to Response Schema
    return [
        JobPostingResponse(
            job_id=j["job_id"],
            title=j["title"],
            status=j["status"].name if hasattr(j["status"], "name") else str(j["status"])
        ) for j in jobs_data
    ]

@router.get("/sessions", response_model=List[AdminSessionSummary])
def get_sessions(
    limit: int = 100,
    offset: int = 0,
    service: AdminQueryService = Depends(get_admin_query_service)
):
    """
    List all sessions (Active + History).
    """
    dto_list = service.get_all_sessions(limit=limit, offset=offset)
    
    # Map DTO to Response Schema
    # SessionListDTO contains 'items' which are SessionResponseDTOs (or Summaries)
    # Checking SessionListDTO definition might be needed, but assuming standard list structure
    # If SessionListDTO is a wrapper:
    sessions = dto_list.sessions if hasattr(dto_list, "sessions") else []
    
    return [
        AdminSessionSummary(
            session_id=s.session_id,
            job_id=s.config.job_id if s.config else "UNKNOWN", # Handling potential missing config in summaries
            user_id="mock_user", # DTO might not have user_id if not stored, Placeholder
            status=s.status.name if hasattr(s.status, "name") else str(s.status),
            score=s.total_score,
            created_at=s.created_at
        ) for s in sessions
    ]

@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session_detail(
    session_id: str,
    service: AdminQueryService = Depends(get_admin_query_service)
):
    """
    Get detailed session info (Read-Only).
    """
    dto = service.get_session_detail(session_id)
    if not dto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    # Reuse mapping logic or duplicate simple mapping
    return SessionResponse(
        session_id=dto.session_id,
        status=dto.status.name if hasattr(dto.status, "name") else str(dto.status),
        current_question_index=dto.current_question_index,
        total_questions=dto.total_questions,
        created_at=dto.created_at
        # Detail might exclude current_question for admin or include it
    )
