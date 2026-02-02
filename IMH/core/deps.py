from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from IMH.db.session import get_db
from IMH.models.auth_token import AuthToken
from IMH.models.user import User, UserRole

bearer: HTTPBearer = HTTPBearer(auto_error=False)


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Bearer 토큰으로 현재 사용자 조회.

    Args:
        cred: Authorization 헤더에서 파싱된 토큰.
        db: DB 세션.

    Returns:
        User: 인증된 사용자.

    Raises:
        HTTPException: 토큰 누락/불일치/만료/사용자 없음.
    """
    if cred is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token: str = cred.credentials
    res = await db.execute(select(AuthToken).where(AuthToken.token == token))
    t: AuthToken | None = res.scalar_one_or_none()

    if t is None or t.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid/expired token")

    user: User | None = await db.get(User, t.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """역할 기반 접근 제어용 Dependency 생성기.

    Args:
        roles: 허용할 역할 목록.

    Returns:
        Callable[[User], User]: FastAPI dependency.
    """

    async def _guard(user: User = Depends(get_current_user)) -> User:
        """요청 사용자의 역할을 검사.

        Args:
            user: 인증된 사용자.

        Returns:
            User: 통과 시 사용자.

        Raises:
            HTTPException: 권한 없음(403).
        """
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _guard
