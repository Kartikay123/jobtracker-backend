"""ResumeMatch — record of a single resume-vs-job-description AI scoring call.

We store every match so the user can see history and so we can show usage
counters / power an analytics page later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


class ResumeMatch(Base):
    __tablename__ = "resume_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional FK to a job — if the user matched against a saved job we link it.
    # SET NULL on delete because match history shouldn't disappear when a job does.
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)

    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100

    # JSONB lets us query into these later (e.g. "matches mentioning Python").
    strengths: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # No updated_at — matches are immutable once created.
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    user: Mapped["User"] = relationship(back_populates="resume_matches")
    job: Mapped["Job | None"] = relationship(back_populates="resume_matches")
