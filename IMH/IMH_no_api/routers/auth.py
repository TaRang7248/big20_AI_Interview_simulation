from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from IMH.IMH_no_api.IMH_no_api.core.exceptions import AuthenticationError
from IMH.IMH_no_api.IMH_no_api.core.security import new_token, token_expiry, verify_password
from IMH.IMH_no_api.IMH_no_api.db.session import get_db
from IMH.IMH_no_api.IMH_no_api.models.auth_token import AuthToken
from IMH.IMH_no_api.IMH_no_api.models.user import User
from IMH.IMH_no_api.IMH_no_api.schemas.auth import LoginIn, LoginOut

router: APIRouter = APIRouter()
logger = logging.getLogger("IMH.IMH_no_api.IMH_no_api.auth")


@router.post("/login", response_model=LoginOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)) -> LoginOut:
    """로그인 후 DB 저장형 토큰 발급.

    Args:
        payload: 로그인 입력(email/password).
        db: DB 세션.

    Returns:
        LoginOut: bearer 토큰.

    Raises:
        HTTPException: 자격 증명 불일치(401).
    """
    res = await db.execute(select(User).where(User.email == payload.email))
    user: User | None = res.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        logger.warning(f"Login failed for email: {payload.email}")
        raise AuthenticationError()

    logger.info(f"User logged in: {user.id} ({user.email})")

    token: str = new_token()
    db.add(AuthToken(user_id=user.id, token=token, expires_at=token_expiry()))
    await db.commit()
    return LoginOut(token=token)
