from __future__ import annotations

import redis.asyncio as redis
from IMH.IMH_no_api.IMH_no_api.core.config import settings

# Redis 클라이언트 생성
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)

async def get_redis():
    """Redis 클라이언트 의존성 주입용 함수"""
    return redis_client
