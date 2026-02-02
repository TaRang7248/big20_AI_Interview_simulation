from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginIn(BaseModel):
    """로그인 입력."""
    email: EmailStr
    password: str


class LoginOut(BaseModel):
    """로그인 출력."""
    token: str
    token_type: str = "bearer"
