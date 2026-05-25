"""Job model — one card on the kanban board."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.resume_match import ResumeMatch
    from app.models.user import User


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # 'applied' | 'interview' | 'offer' | 'rejected'
    # Stored as varchar — Pydantic Literal enforces values at the API layer.
    # See app/schemas/job.py for the enforced set.
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    salary: Mapped[str | None] = mapped_column(String(100), nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --- Relationships ---
    user: Mapped["User"] = relationship(back_populates="jobs")
    resume_matches: Mapped[list["ResumeMatch"]] = relationship(
        back_populates="job",
        # Don't cascade-delete matches when a job is removed — they belong to
        # the user and are useful as history. Just null out the FK.
    )

    __table_args__ = (
        # Common kanban query: list all of a user's jobs filtered by status.
        Index("ix_jobs_user_status", "user_id", "status"),
    )
