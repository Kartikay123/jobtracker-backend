"""arq worker entrypoint.

Run inside a container with:
    arq app.workers.worker.WorkerSettings

The worker connects to the same Redis that the API uses. Jobs the API enqueues
(`await arq.enqueue_job("name", *args)`) are popped here and executed.

Configuration:
    functions    — every callable that can be enqueued by name
    cron_jobs    — recurring schedules (UTC)
    on_startup / on_shutdown — process-wide setup/teardown
"""

import logging

from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import settings
from app.db.session import engine
from app.workers.tasks import scan_stale_jobs, send_followup_reminder

# arq prints task lifecycle through its own logger — make sure ours show up too.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)


async def on_startup(ctx: dict) -> None:
    logging.getLogger("jt.worker").info(
        "worker started (env=%s)", settings.ENVIRONMENT
    )


async def on_shutdown(ctx: dict) -> None:
    # Dispose the SQLAlchemy engine so connections close cleanly.
    await engine.dispose()
    logging.getLogger("jt.worker").info("worker stopped")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    functions = [send_followup_reminder, scan_stale_jobs]

    cron_jobs = [
        # Every day at 09:00 UTC, scan for stale jobs and enqueue reminders.
        cron(scan_stale_jobs, hour=9, minute=0, run_at_startup=False),
    ]

    on_startup = on_startup
    on_shutdown = on_shutdown

    # Don't keep finished jobs in Redis forever — keep results 1 hour.
    keep_result = 3600
