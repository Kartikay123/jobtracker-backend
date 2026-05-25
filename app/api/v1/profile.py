"""Profile endpoints — view profile and manage saved resume."""
from typing import Annotated

from fastapi import Depends, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.api.utils import CamelAPIRouter
from app.db.deps import get_db
from app.schemas.profile import ProfileOut
from app.services.resume_parser import extract_resume_text

router = CamelAPIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut, summary="Get current user profile")
async def get_profile(current_user: CurrentUser) -> dict:
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "has_resume": bool(getattr(current_user, "resume_text", None)),
        "resume_filename": getattr(current_user, "resume_filename", None),
    }


@router.post("/resume", response_model=ProfileOut, summary="Upload and save resume to profile")
async def save_resume(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    resume: Annotated[UploadFile, File(description="Resume PDF")],
) -> dict:
    if not resume.filename:
        raise HTTPException(status_code=422, detail="No file provided.")
    resume_text = await extract_resume_text(resume)
    current_user.resume_text = resume_text
    current_user.resume_filename = resume.filename
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "has_resume": True,
        "resume_filename": current_user.resume_filename,
    }


@router.delete("/resume", response_model=ProfileOut, summary="Remove saved resume")
async def delete_resume(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    current_user.resume_text = None
    current_user.resume_filename = None
    db.add(current_user)
    await db.commit()
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "has_resume": False,
        "resume_filename": None,
    }
