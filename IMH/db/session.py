from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from IMH.core.config import settings

engine = create_async_engine(settings.POSTGRES_CONNECTION_STRING, future=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청 스코프 DB 세션 제공.

    Yields:
        AsyncSession: async SQLAlchemy 세션.
    """
    async with AsyncSessionLocal() as session:
        yield session