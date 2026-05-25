"""Schemas for user profile and saved resume."""
from app.schemas._base import CamelModel


class ProfileOut(CamelModel):
    id: int
    name: str
    email: str
    has_resume: bool
    resume_filename: str | None = None


class ProfileUpdate(CamelModel):
    name: str | None = None
