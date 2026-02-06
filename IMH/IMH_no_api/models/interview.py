from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from IMH.IMH_no_api.IMH_no_api.common.time import utc_now
from IMH.IMH_no_api.IMH_no_api.db.base import Base


from IMH.IMH_no_api.IMH_no_api.schemas.interview import InterviewerPersona


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
    persona: Mapped[InterviewerPersona] = mapped_column(
        Enum(InterviewerPersona),
        default=InterviewerPersona.WARM,
        nullable=False,
    )
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus),
        default=InterviewStatus.created,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
