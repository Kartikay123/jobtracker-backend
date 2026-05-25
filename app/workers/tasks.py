"""Background task definitions — pure functions, called by the arq worker.

The first arg of every task is `ctx: dict` (arq passes worker state in here).
We don't currently put anything in ctx, but if we needed to share state
(e.g. an HTTP client), the `on_startup` hook in worker.py would populate it.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.job import Job
from app.models.user import User
from app.services.email import send_email

logger = logging.getLogger("jt.tasks")

# A job is "stale" if it's been in `applied` for this many days without progress.
STALE_DAYS = 7


async def send_followup_reminder(ctx: dict, user_id: int, job_id: int) -> str:
    """Email the user: 'follow up on your application to Acme?'.

    Returns a short status string so it shows up in `arq` job results.
    """
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        job = await db.get(Job, job_id)

    if user is None or job is None:
        return "skipped: user or job missing"
    if job.user_id != user_id:
        return "skipped: ownership mismatch"
    if job.status != "applied":
        return "skipped: status changed"

    await send_email(
        to=user.email,
        subject=f"Follow up on your application to {job.company}?",
        body=(
            f"Hi {user.name},\n\n"
            f"It's been a while since you applied to {job.title} at "
            f"{job.company}. Considering a polite follow-up?\n\n"
            f"— JobTracker"
        ),
    )
    return f"reminded user={user_id} job={job_id}"


async def scan_stale_jobs(ctx: dict) -> str:
    """Find every stale 'applied' job and enqueue a per-job reminder."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Job.id, Job.user_id).where(
                Job.status == "applied",
                Job.applied_at.is_not(None),
                Job.applied_at < cutoff,
            )
        )
        stale = rows.all()

    if not stale:
        logger.info("scan_stale_jobs: no stale jobs found (cutoff %s)", cutoff)
        return "found 0 stale jobs"

    logger.info("scan_stale_jobs: enqueueing %d reminders", len(stale))
    redis = ctx["redis"]  # arq exposes its own ArqRedis pool here
    for job_id, user_id in stale:
        await redis.enqueue_job("send_followup_reminder", user_id, job_id)
    return f"found {len(stale)} stale jobs"
