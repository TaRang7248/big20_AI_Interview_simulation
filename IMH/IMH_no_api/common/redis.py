from __future__ import annotations
import redis.asyncio as redis
from IMH.IMH_no_api.IMH_no_api.core.config import settings

class RedisClient:
    """Async Redis 클라이언트 서비스."""

    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )

    async def get(self, key: str):
        return await self.client.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        return await self.client.set(key, value, ex=ex, nx=nx)

    async def delete(self, *keys: str):
        if keys:
            return await self.client.delete(*keys)

    async def keys(self, pattern: str):
        return await self.client.keys(pattern)

# 싱글톤 인스턴스
redis_client = RedisClient()
