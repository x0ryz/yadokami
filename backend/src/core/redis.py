from redis import asyncio as aioredis
from src.core.config import settings

redis_client: aioredis.Redis | None = None


async def init_redis():
    """Initialization of the global connection pool"""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=100,
        )


async def close_redis():
    """Closing connections"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


def get_redis() -> aioredis.Redis:
    """Getter for use in services"""
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return redis_client
