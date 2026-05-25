"""arq pool wired into the FastAPI app — for ENQUEUEING from the API.

(Workers connect to Redis themselves via WorkerSettings.redis_settings.)

Lifecycle:
- `init_arq_pool(app)` is called from main.py's lifespan handler on startup.
- The pool sits on `app.state.arq` so the `get_arq` dependency can read it.
- `close_arq_pool(app)` runs on shutdown.

To enqueue from a route:

    from app.core.queue import get_arq
    @router.post("/x")
    async def x(arq: ArqRedis = Depends(get_arq)):
        await arq.enqueue_job("send_followup_reminder", user_id, job_id)
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import FastAPI, Request

from app.core.config import settings


async def init_arq_pool(app: FastAPI) -> None:
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))


async def close_arq_pool(app: FastAPI) -> None:
    pool: ArqRedis | None = getattr(app.state, "arq", None)
    if pool is not None:
        await pool.aclose()


async def get_arq(request: Request) -> ArqRedis:
    return request.app.state.arq
