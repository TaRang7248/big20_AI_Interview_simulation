from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from IMH.db.session import get_db

router: APIRouter = APIRouter()

class HealthOut(BaseModel):
    """헬스체크 응답 스키마."""
    ok: bool

class HealthDBOut(BaseModel):
    """DB 헬스체크 응답 스키마."""
    ok: bool

@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    """헬스체크 엔드포인트.

    Returns:
        HealthOut: {"ok": True}
    """
    return HealthOut(ok=True)

@router.get("/health/db", response_model=HealthDBOut)
async def health_db(db: AsyncSession = Depends(get_db)) -> HealthDBOut:
    """DB 연결 헬스체크 엔드포인트.

    DB에 SELECT 1을 수행하여 연결이 유효한지 확인한다.

    Args:
        db (AsyncSession): DB 세션 의존성.

    Returns:
        HealthDBOut: 성공 시 {"ok": True}

    Raises:
        HTTPException: DB 연결 실패 시 500 에러.
    """
    try:
        await db.execute(text("SELECT 1"))
        return HealthDBOut(ok=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db error: {exc}") from exc
    