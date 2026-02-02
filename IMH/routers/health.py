from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router: APIRouter = APIRouter()


class HealthOut(BaseModel):
    """헬스체크 응답 스키마."""
    ok: bool


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    """헬스체크 엔드포인트.

    Returns:
        HealthOut: {"ok": True}
    """
    return HealthOut(ok=True)