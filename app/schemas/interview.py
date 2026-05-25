"""Pydantic schemas for interview prep."""

from datetime import datetime

from pydantic import Field

from app.schemas._base import CamelModel


# --- Question ---
class InterviewQuestionBase(CamelModel):
    text: str
    category: str | None = None
    difficulty: str | None = None
    position: int = 0


class InterviewQuestionOut(InterviewQuestionBase):
    id: int
    answer: "InterviewAnswerOut | None" = None


# --- Answer ---
class InterviewAnswerCreate(CamelModel):
    """Body of POST /interview/answers — frontend sends `{questionId, text}`."""

    question_id: int
    text: str = Field(min_length=1)


class InterviewAnswerOut(CamelModel):
    id: int
    question_id: int
    text: str
    created_at: datetime
    updated_at: datetime


# --- Session ---
class InterviewSessionBase(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    role: str | None = None


class InterviewSessionOut(InterviewSessionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    questions: list[InterviewQuestionOut] = []


# Resolve the forward reference Question -> Answer.
InterviewQuestionOut.model_rebuild()


# --- AI generation request / response ---
class InterviewGenerateRequest(CamelModel):
    """Body of POST /ai/interview/questions."""

    role: str = Field(min_length=1, max_length=200)
    job_description: str | None = None
    count: int = Field(default=15, ge=1, le=30)


class InterviewGenerateResponse(CamelModel):
    """Response of POST /ai/interview/questions — what the page consumes."""

    session_id: int
    questions: list[InterviewQuestionOut]
