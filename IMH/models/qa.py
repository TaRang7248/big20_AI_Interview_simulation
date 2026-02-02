from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from IMH.db.base import Base


class QA(Base):
    """질문-답변 레퍼런스 데이터.

    임베딩 모델/차원이 아직 결정되지 않았으므로 1차 마이그레이션에서는 텍스트만 저장한다.
    추후 `embedding(vector(n))`, `embedding_model` 컬럼 및 벡터 인덱스를 추가 마이그레이션으로 확장한다.
    """

    __tablename__ = "qa"

    # data.json에 이미 id가 있으므로 autoincrement는 끈다.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
