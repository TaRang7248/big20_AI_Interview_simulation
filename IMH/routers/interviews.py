from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from IMH.core.deps import get_current_user
from IMH.core.exceptions import NotFoundError, PermissionDeniedError
from IMH.db.session import get_db
from IMH.models.candidate_profile import CandidateProfile
from IMH.models.event_log import EventLog, EventType
from IMH.models.interview import Interview
from IMH.models.user import User, UserRole
from IMH.schemas.interview import InterviewCreateIn, InterviewOut

router: APIRouter = APIRouter()
logger = logging.getLogger("IMH.interviews")


@router.post("", response_model=InterviewOut)
async def create_interview(
    payload: InterviewCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    """면접 세션 생성(프로필 연결).

    정책:
      - candidate: 본인 profile로만 생성 가능
      - admin: 모든 profile 가능

    Args:
        payload: profile_id 포함.
        user: 인증된 사용자.
        db: DB 세션.

    Returns:
        InterviewOut: 생성된 면접.

    Raises:
        HTTPException: 프로필 없음(404), 권한 없음(403).
    """
    profile: CandidateProfile | None = await db.get(CandidateProfile, payload.profile_id)
    if profile is None:
        raise NotFoundError(message="Profile not found")

    if user.role == UserRole.candidate and profile.user_id != user.id:
        raise PermissionDeniedError(message="Cannot create interview for other user's profile")

    interview = Interview(profile_id=profile.id)
    db.add(interview)
    await db.flush()  # interview.id 확보

    db.add(
        EventLog(
            interview_id=interview.id,
            type=EventType.status_change,
            payload={"from": None, "to": "created"},
        )
    )

    await db.commit()
    await db.refresh(interview)
    logger.info(f"Interview created: {interview.id} for user: {user.id} (profile: {profile.id})")
    return interview
