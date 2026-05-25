"""Pydantic schemas for Job."""

from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl, field_validator

from app.schemas._base import CamelModel

# Single source of truth for valid statuses (mirrors frontend constants.js).
JobStatus = Literal["applied", "interview", "offer", "rejected"]


class JobBase(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    status: JobStatus = "applied"
    salary: str | None = Field(default=None, max_length=100)
    link: HttpUrl | None = None
    notes: str | None = None

    # Frontend may send an empty string when the user leaves the link blank.
    # Convert "" → None so the HttpUrl validator doesn't reject it.
    @field_validator("link", mode="before")
    @classmethod
    def _empty_link_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class JobCreate(JobBase):
    """Body of POST /jobs. Frontend sends `appliedAt`."""

    applied_at: datetime | None = None


class JobUpdate(CamelModel):
    """Body of PATCH /jobs/:id — every field optional."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    status: JobStatus | None = None
    salary: str | None = None
    link: HttpUrl | None = None
    notes: str | None = None
    applied_at: datetime | None = None

    @field_validator("link", mode="before")
    @classmethod
    def _empty_link_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class JobStatusUpdate(CamelModel):
    """Body of PATCH /jobs/:id/status (kanban drag)."""

    status: JobStatus


class JobOut(JobBase):
    id: int
    user_id: int
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
