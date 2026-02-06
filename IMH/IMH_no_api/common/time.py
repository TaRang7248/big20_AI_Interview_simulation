from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """IMH 내에서 균일하게 시간대를 포함함 UTC 현재 시각을 반환함.

    Returns:
        datetime: timezone-aware UTC datetime 객체.
    """
    return datetime.now(timezone.utc)
