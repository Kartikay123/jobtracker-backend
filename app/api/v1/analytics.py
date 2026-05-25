"""Analytics endpoints — heavy aggregations cached in Redis."""

from typing import Annotated, Literal

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.api.utils import CamelAPIRouter
from app.core.cache import get_cached, set_cached
from app.db.deps import get_db
from app.schemas.analytics import AnalyticsSummary
from app.services.analytics import compute_summary

router = CamelAPIRouter(prefix="/analytics", tags=["analytics"])

CACHE_TTL_SECONDS = 300  # 5 minutes


@router.get("/summary", response_model=AnalyticsSummary)
async def summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    range: Annotated[Literal["7d", "30d", "90d"], Query()] = "30d",
) -> dict:
    cache_key = f"analytics:user:{current_user.id}:{range}"

    if (cached := await get_cached(cache_key)) is not None:
        return cached

    data = await compute_summary(db, current_user.id, range)
    await set_cached(cache_key, data, ttl_seconds=CACHE_TTL_SECONDS)
    return data
