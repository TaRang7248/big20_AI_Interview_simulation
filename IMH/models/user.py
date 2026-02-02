from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from IMH.common.time import utc_now
from IMH.db.base import Base


class UserRole(str, enum.Enum):
    """사용자 역할."""
    candidate = "candidate"
    admin = "admin"


class User(Base):
    """사용자 테이블."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.candidate)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
