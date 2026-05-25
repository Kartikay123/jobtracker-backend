"""Re-export every ORM model so importing `app.models` registers them all
on `Base.metadata` (which Alembic reads to autogenerate migrations).
"""

from app.models.interview import (  # noqa: F401
    InterviewAnswer,
    InterviewQuestion,
    InterviewSession,
)
from app.models.job import Job  # noqa: F401
from app.models.resume_match import ResumeMatch  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "User",
    "Job",
    "InterviewSession",
    "InterviewQuestion",
    "InterviewAnswer",
    "ResumeMatch",
]
