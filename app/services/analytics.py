"""Analytics aggregation queries.

Returns the exact shape the frontend AnalyticsPage reads. Computed from the
`jobs` table. Cached at the route layer.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


def _range_to_days(range_key: str) -> int:
    return {"7d": 7, "30d": 30, "90d": 90}.get(range_key, 30)


def _pct(num: int, denom: int) -> int:
    if denom <= 0:
        return 0
    return round((num / denom) * 100)


def _delta(curr: int, prev: int) -> int | None:
    """Period-over-period delta. None when prev is 0 to avoid meaningless infinity."""
    if prev == 0:
        return None
    return curr - prev


async def compute_summary(db: AsyncSession, user_id: int, range_key: str) -> dict:
    days = _range_to_days(range_key)
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    prev_start = now - timedelta(days=days * 2)

    # --- Counts: current period and previous period (by created_at). ---
    async def counts_in(start: datetime, end: datetime) -> dict[str, int]:
        rows = await db.execute(
            select(Job.status, func.count(Job.id))
            .where(
                Job.user_id == user_id,
                Job.created_at >= start,
                Job.created_at < end,
            )
            .group_by(Job.status)
        )
        return {status: count for status, count in rows.all()}

    curr = await counts_in(period_start, now)
    prev = await counts_in(prev_start, period_start)

    def total(d: dict[str, int]) -> int:
        return sum(d.values())

    def reached_response(d: dict[str, int]) -> int:
        # 'Response' = the user heard something back: any non-applied status.
        return d.get("interview", 0) + d.get("offer", 0) + d.get("rejected", 0)

    def reached_interview(d: dict[str, int]) -> int:
        return d.get("interview", 0) + d.get("offer", 0)

    total_curr = total(curr)
    total_prev = total(prev)
    response_rate_curr = _pct(reached_response(curr), total_curr)
    response_rate_prev = _pct(reached_response(prev), total_prev)
    interview_rate_curr = _pct(reached_interview(curr), total_curr)
    interview_rate_prev = _pct(reached_interview(prev), total_prev)

    # --- Weekly time series for the current period. ---
    weekly_rows = await db.execute(
        select(
            func.to_char(Job.created_at, "IYYY-\"W\"IW").label("week"),
            func.count(Job.id).label("count"),
        )
        .where(Job.user_id == user_id, Job.created_at >= period_start)
        .group_by("week")
        .order_by("week")
    )
    weekly = [{"week": w, "count": c} for w, c in weekly_rows.all()]

    # --- Funnel (totals all-time, ordered). ---
    all_rows = await db.execute(
        select(Job.status, func.count(Job.id))
        .where(Job.user_id == user_id)
        .group_by(Job.status)
    )
    all_counts = {status: c for status, c in all_rows.all()}
    funnel = [
        {"stage": "Applied", "count": sum(all_counts.values())},
        {
            "stage": "Interview",
            "count": all_counts.get("interview", 0) + all_counts.get("offer", 0),
        },
        {"stage": "Offer", "count": all_counts.get("offer", 0)},
    ]

    return {
        "total_applications": total_curr,
        "applications_delta": _delta(total_curr, total_prev),
        "response_rate": response_rate_curr,
        "response_delta": _delta(response_rate_curr, response_rate_prev),
        "interview_rate": interview_rate_curr,
        "interview_delta": _delta(interview_rate_curr, interview_rate_prev),
        "weekly": weekly,
        "funnel": funnel,
    }
