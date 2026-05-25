"""Email sending — stub.

CURRENT STATE: logs the email instead of sending. Visible in worker stdout
(`docker compose logs worker`).

TO PLUG IN REAL SMTP later:
    pip add `aiosmtplib` (or use a transactional provider's SDK — Resend,
    Postmark, Mailgun, SES). Replace the body of `send_email`. Read
    SMTP host/user/pass from app.core.config.settings. Nothing else changes.
"""

import logging

logger = logging.getLogger("jt.email")


async def send_email(*, to: str, subject: str, body: str) -> None:
    """Send an email. Currently logs. Same signature whether stub or real."""
    logger.info(
        "EMAIL [stub] to=%s subject=%r body=%r",
        to,
        subject,
        body[:120] + ("..." if len(body) > 120 else ""),
    )
