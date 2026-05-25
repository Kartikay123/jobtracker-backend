"""Async Redis client.

One connection pool is created at import time and shared across the process —
redis-py's pool is lazy and thread/coroutine safe.

Usage:
    # In route handlers (testable, mockable):
    from app.core.redis import get_redis
    @router.get("/x")
    async def x(redis: Redis = Depends(get_redis)): ...

    # In services / helpers (simpler):
    from app.core.redis import redis_client
    await redis_client.get("key")
"""

from redis.asyncio import Redis, from_url

from app.core.config import settings

redis_client: Redis = from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,         # str responses, not bytes
    health_check_interval=30,      # auto-ping idle connections
)


async def get_redis() -> Redis:
    """FastAPI dependency. Returns the shared client (no setup/teardown)."""
    return redis_client
