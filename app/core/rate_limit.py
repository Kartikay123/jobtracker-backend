"""Per-user fixed-window rate limiter, used as a FastAPI dependency factory.

Usage:

    from app.core.rate_limit import rate_limit

    @router.post(
        "/ai/resume-match",
        dependencies=[Depends(rate_limit("resume_match", max_requests=10, window_seconds=3600))],
    )
    async def resume_match(...): ...

That gives each authenticated user 10 requests per hour to that endpoint.

How it works (Redis side):
    INCR rl:<scope>:<user_id>     -> atomic counter, starts at 1
    EXPIRE ... <window_seconds>   -> set TTL only on first hit of the window
    if counter > max -> 429

The window is "fixed" (resets when the key expires). Simpler and faster than
sliding-window; good enough for cost-protection on AI endpoints.
"""

from typing import Awaitable, Callable

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis

from app.api.deps import CurrentUser
from app.core.redis import get_redis


def rate_limit(
    scope: str,
    max_requests: int,
    window_seconds: int,
) -> Callable[..., Awaitable[None]]:
    """Build a FastAPI dependency that enforces a per-user fixed-window limit."""

    async def _check(
        current_user: CurrentUser,
        redis: Redis = Depends(get_redis),
    ) -> None:
        key = f"rl:{scope}:{current_user.id}"
        count = await redis.incr(key)
        if count == 1:
            # First hit of a new window — set TTL so the key auto-resets.
            await redis.expire(key, window_seconds)
        if count > max_requests:
            ttl = await redis.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded ({max_requests} per {window_seconds}s)."
                    f" Try again in {max(ttl, 1)}s."
                ),
                headers={"Retry-After": str(max(ttl, 1))},
            )

    return _check
