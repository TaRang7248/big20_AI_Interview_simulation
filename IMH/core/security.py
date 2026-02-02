from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from passlib.context import CryptContext

from IMH.common.time import utc_now
from IMH.core.config import settings

pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """평문 비밀번호를 해시로 변환.

    Args:
        password: 평문 비밀번호.

    Returns:
        str: bcrypt 해시 문자열.
    """
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """평문 비밀번호와 해시를 비교.

    Args:
        password: 평문 비밀번호.
        password_hash: 저장된 해시.

    Returns:
        bool: 일치 여부.
    """
    return pwd_context.verify(password, password_hash)


def new_token() -> str:
    """로그인용 랜덤 토큰 생성.

    Returns:
        str: 64바이트 hex 토큰.
    """
    return secrets.token_hex(32)


def token_expiry(now: datetime | None = None) -> datetime:
    """토큰 만료 시각 계산.

    Args:
        now: 기준 시각(없으면 utcnow).

    Returns:
        datetime: 만료 시각(UTC).
    """
    base = now or utc_now()
    return base + timedelta(minutes=settings.TOKEN_TTL_MINUTES)
