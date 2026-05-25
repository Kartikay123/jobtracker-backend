"""AI endpoints — rate-limited, persist results, return UI-friendly shapes.

The actual AI calls are stubbed in app/services/ai_client.py — see the TODO
there for swapping in a real provider.
"""

from typing import Annotated

from fastapi import Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.api.utils import CamelAPIRouter
from app.core.rate_limit import rate_limit
from app.db.deps import get_db
from app.models.interview import InterviewQuestion, InterviewSession
from app.models.resume_match import ResumeMatch
from app.schemas.interview import (
    InterviewGenerateRequest,
    InterviewGenerateResponse,
    InterviewQuestionOut,
)
from app.schemas.resume_match import ResumeMatchResult
from app.services import ai_client
from app.services.resume_parser import extract_resume_text

router = CamelAPIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/resume-match",
    response_model=ResumeMatchResult,
    summary="Score a resume against a job description",
    dependencies=[
        Depends(rate_limit(scope="resume_match", max_requests=10, window_seconds=3600))
    ],
)
async def resume_match(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    resume: Annotated[UploadFile, File(description="Resume PDF")],
    job_description: Annotated[str, Form(alias="jobDescription")],
) -> dict:
    resume_text = await extract_resume_text(resume)
    result = ai_client.match_resume(resume_text, job_description)

    # Persist for history / future analytics. Not awaited on the response path
    # for speed — but we do commit before returning so the row is durable.
    record = ResumeMatch(
        user_id=current_user.id,
        resume_text=resume_text,
        job_description=job_description,
        score=result["score"],
        strengths=result["strengths"],
        gaps=result["gaps"],
    )
    db.add(record)
    await db.commit()

    return result


@router.post(
    "/interview/questions",
    response_model=InterviewGenerateResponse,
    summary="Generate interview questions for a role",
    dependencies=[
        Depends(rate_limit(scope="interview_gen", max_requests=10, window_seconds=3600))
    ],
)
async def generate_interview_questions(
    payload: InterviewGenerateRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    raw_questions = ai_client.generate_questions(
        role=payload.role,
        job_description=payload.job_description,
        count=payload.count,
    )

    # Persist a session + its questions so the frontend has stable IDs to
    # save answers against.
    sess = InterviewSession(
        user_id=current_user.id,
        title=payload.role,
        role=payload.role,
    )
    db.add(sess)
    await db.flush()  # need sess.id before creating questions

    questions = [
        InterviewQuestion(
            session_id=sess.id,
            text=q["text"],
            category=q["category"],
            difficulty=q["difficulty"],
            position=q["position"],
        )
        for q in raw_questions
    ]
    db.add_all(questions)
    await db.commit()
    for q in questions:
        await db.refresh(q)

    # Build the response objects manually rather than `model_validate(q)` —
    # the latter would try to lazy-load `q.answer` (None here, but the
    # async session can't do lazy loads). We *know* answer is None for
    # freshly created questions, so set it explicitly.
    return {
        "session_id": sess.id,
        "questions": [
            InterviewQuestionOut(
                id=q.id,
                text=q.text,
                category=q.category,
                difficulty=q.difficulty,
                position=q.position,
                answer=None,
            )
            for q in questions
        ],
    }
