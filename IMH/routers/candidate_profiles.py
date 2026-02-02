from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from IMH.core.deps import get_current_user
from IMH.db.session import get_db
from IMH.models.candidate_profile import CandidateProfile
from IMH.models.user import User, UserRole
from IMH.schemas.candidate_profile import CandidateProfileCreateIn, CandidateProfileOut

router: APIRouter = APIRouter()


@router.post("", response_model=CandidateProfileOut)
async def create_profile(
    payload: CandidateProfileCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfileOut:
    """지원자 프로필 생성(지원자 본인만)."""
    if user.role != UserRole.candidate:
        raise HTTPException(status_code=403, detail="Only candidate can create profile")

    # 한 유저 1프로필 MVP 정책(원하면 나중에 다중 프로필로 확장)
    res = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    exists = res.scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Profile already exists")

    profile = CandidateProfile(
        user_id=user.id,
        resume_text=payload.resume_text,
        target_job=payload.target_job,
        target_company=payload.target_company,
        skills=payload.skills,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/me", response_model=CandidateProfileOut)
async def get_my_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfileOut:
    """내 프로필 조회."""
    res = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
