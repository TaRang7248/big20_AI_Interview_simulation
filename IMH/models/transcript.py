from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from IMH.common.time import utc_now
from IMH.db.base import Base


class Speaker(str, enum.Enum):
    """발화자 구분."""
    candidate = "candidate"
    ai = "ai"
    system = "system"


class Transcript(Base):
    """발화 텍스트 로그(STT/LLM 결과 저장)."""

    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), nullable=False, index=True)

    speaker: Mapped[Speaker] = mapped_column(Enum(Speaker), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # 세션 기준 상대시간(ms): 재현/정렬에 사용
    t_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
