"""Pydantic schemas for ResumeMatch."""

from datetime import datetime

from pydantic import Field

from app.schemas._base import CamelModel


class ResumeMatchResult(CamelModel):
    """Response of POST /ai/resume-match — what the frontend renders."""

    score: int = Field(ge=0, le=100)
    strengths: list[str] = []
    gaps: list[str] = []


class ResumeMatchOut(ResumeMatchResult):
    """Stored history record."""

    id: int
    user_id: int
    job_id: int | None = None
    created_at: datetime
