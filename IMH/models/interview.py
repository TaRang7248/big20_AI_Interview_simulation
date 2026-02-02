from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from IMH.db.base import Base


class InterviewStatus(str, enum.Enum):
    """면접 상태."""
    created = "created"
    live = "live"
    finished = "finished"
    aborted = "aborted"


class Interview(Base):
    """면접 세션 테이블."""

    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), nullable=False, index=True)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus),
        default=InterviewStatus.created,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
