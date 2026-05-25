"""AI endpoints — rate-limited, persist results, return UI-friendly shapes."""

from typing import Annotated

from fastapi import Depends, File, Form, HTTPException, UploadFile
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

    result = await ai_client.match_resume(resume_text, job_description)

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
    raw_questions = await ai_client.generate_questions(
        role=payload.role,
        job_description=payload.job_description,
        count=payload.count,
    )

    sess = InterviewSession(
        user_id=current_user.id,
        title=payload.role,
        role=payload.role,
    )
    db.add(sess)
    await db.flush()

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


@router.post(
    "/cover-letter",
    summary="Generate a cover letter from resume + job description",
    dependencies=[
        Depends(rate_limit(scope="cover_letter", max_requests=10, window_seconds=3600))
    ],
)
async def generate_cover_letter(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    job_description: Annotated[str, Form(alias="jobDescription")],
    resume: Annotated[UploadFile, File(description="Resume PDF (leave empty to use saved resume)")] = None,
) -> dict:
    saved_resume = getattr(current_user, "resume_text", None)
    # Use uploaded file if provided, otherwise fall back to saved resume
    if resume is not None and resume.filename:
        resume_text = await extract_resume_text(resume)
    elif saved_resume:
        resume_text = saved_resume
    else:
        raise HTTPException(
            status_code=422,
            detail="Please upload a resume or save one to your profile first.",
        )

    cover_letter = await ai_client.generate_cover_letter(
        resume_text=resume_text,
        job_description=job_description,
        user_name=current_user.name,
    )
    return {"coverLetter": cover_letter}
