"""Interview prep endpoints — answer upsert + session listing."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.api.utils import CamelAPIRouter
from app.db.deps import get_db
from app.models.interview import (
    InterviewAnswer,
    InterviewQuestion,
    InterviewSession,
)
from app.schemas.interview import (
    InterviewAnswerCreate,
    InterviewAnswerOut,
    InterviewSessionOut,
)

router = CamelAPIRouter(prefix="/interview", tags=["interview"])


@router.post(
    "/answers",
    response_model=InterviewAnswerOut,
    summary="Upsert the answer for an interview question",
)
async def save_answer(
    payload: InterviewAnswerCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InterviewAnswer:
    # 1. Verify the question exists AND belongs to a session owned by this user.
    question = await db.scalar(
        select(InterviewQuestion)
        .join(InterviewSession, InterviewQuestion.session_id == InterviewSession.id)
        .where(
            InterviewQuestion.id == payload.question_id,
            InterviewSession.user_id == current_user.id,
        )
        .options(selectinload(InterviewQuestion.answer))
    )
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    # 2. Upsert: replace the existing answer's text, or create one.
    if question.answer is not None:
        question.answer.text = payload.text
        answer = question.answer
    else:
        answer = InterviewAnswer(question_id=question.id, text=payload.text)
        db.add(answer)

    await db.commit()
    await db.refresh(answer)
    return answer


@router.get(
    "/sessions",
    response_model=list[InterviewSessionOut],
    summary="List the user's interview sessions (with questions and answers)",
)
async def list_sessions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[InterviewSession]:
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .options(
            # Eager-load the whole tree so the response renders without
            # additional async lazy-load round-trips.
            selectinload(InterviewSession.questions).selectinload(
                InterviewQuestion.answer
            )
        )
        .order_by(InterviewSession.created_at.desc())
    )
    return list(result.scalars().all())
