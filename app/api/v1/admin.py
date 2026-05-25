"""Admin / dev-only endpoints — hidden from /docs.

Currently a single endpoint to manually trigger the stale-job scan so you
don't have to wait for the cron schedule when testing.

Real "admin" auth (role check) lands later — for now any logged-in user
can hit these. Acceptable because they only operate on their own data.
"""

from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Depends

from app.api.deps import CurrentUser
from app.api.utils import CamelAPIRouter
from app.core.queue import get_arq

router = CamelAPIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)


@router.post("/scan-followups")
async def trigger_followup_scan(
    current_user: CurrentUser,
    arq: Annotated[ArqRedis, Depends(get_arq)],
) -> dict:
    """Enqueue scan_stale_jobs immediately. Returns the arq job id."""
    job = await arq.enqueue_job("scan_stale_jobs")
    return {
        "queued": True,
        "jobId": job.job_id if job else None,
        "triggeredBy": current_user.email,
    }
