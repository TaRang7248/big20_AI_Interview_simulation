from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from IMH.common.time import utc_now
from IMH.db.base import Base


class CandidateProfile(Base):
    """지원자 프로필(이력서/직무/회사/기술스택)."""

    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_job: Mapped[str] = mapped_column(String(200), nullable=False)
    target_company: Mapped[str] = mapped_column(String(200), nullable=False)
    skills: Mapped[str] = mapped_column(String(1000), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
