from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from IMH.IMH_no_api.IMH_no_api.common.time import utc_now
from IMH.IMH_no_api.IMH_no_api.db.base import Base


class EventType(str, enum.Enum):
    """재현/디버깅용 이벤트 타입."""
    status_change = "status_change"
    timer = "timer"
    intervention = "intervention"
    system = "system"


class EventLog(Base):
    """면접 재현용 이벤트 로그.

    payload 예시:
        status_change: {"from": "created", "to": "live"}
        timer: {"kind": "start", "name": "answer_limit", "sec": 120}
        intervention: {"who": "admin", "action": "pause"}
    """

    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), nullable=False, index=True)

    type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # 세션 기준 상대시간(ms)
    t_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
