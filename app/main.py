"""
FastAPI application entrypoint.

Run locally:           uvicorn app.main:app --reload
Run via docker:        docker compose up
Interactive docs:      http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import api_router
from app.core.config import settings
from app.core.queue import close_arq_pool, init_arq_pool
from app.core.redis import get_redis, redis_client
from app.db.deps import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Process-level setup/teardown.

    On startup: open the arq pool so route handlers can enqueue background jobs.
    On shutdown: close arq + redis pools gracefully.
    """
    await init_arq_pool(app)
    yield
    await close_arq_pool(app)
    await redis_client.aclose()


app = FastAPI(
    title="JobTracker API",
    version="0.1.0",
    description="Backend for the JobTracker frontend.",
    docs_url="/docs",
    # We override /redoc below with a pinned-version variant
    # because the default redoc@next CDN bundle ships broken builds.
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js",
    )


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Feature routers (mounted under /api) ---
app.include_router(api_router, prefix="/api")


# --- Meta endpoints ---
@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "JobTracker API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"])
async def health(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    """Liveness + DB + Redis connectivity probe."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "fail"

    try:
        await redis.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "fail"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "status": overall,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "redis": redis_status,
    }
