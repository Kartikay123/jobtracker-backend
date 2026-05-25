"""Tiny JSON cache helpers built on top of `redis_client`.

Why a thin wrapper instead of using the client directly:
- Centralized JSON encode/decode (with `default=str` so datetimes serialize).
- One place to add metrics / logging later.
- Easier to swap to a different backend (e.g. memcached) without touching callers.

Key naming convention (used everywhere in the codebase):
    <feature>:<entity>:<id>[:<scope>]
    e.g. "analytics:user:42:30d", "jobs:user:42:list"
"""

import json
from typing import Any

from app.core.redis import redis_client


async def get_cached(key: str) -> Any | None:
    """Return the cached value, or None if missing/expired."""
    raw = await redis_client.get(key)
    return json.loads(raw) if raw else None


async def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    """Store a JSON-serializable value with a TTL (always; no infinite keys)."""
    await redis_client.set(key, json.dumps(value, default=str), ex=ttl_seconds)


async def delete_cached(key: str) -> None:
    await redis_client.delete(key)


async def delete_pattern(pattern: str) -> None:
    """Delete every key matching a glob pattern.

    Used for cache invalidation, e.g. after a job changes:
        await delete_pattern(f"analytics:user:{user_id}:*")

    SCAN is non-blocking; KEYS would freeze Redis on large datasets.
    """
    async for key in redis_client.scan_iter(match=pattern, count=200):
        await redis_client.delete(key)
