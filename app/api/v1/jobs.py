"""Jobs CRUD."""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.api.utils import CamelAPIRouter
from app.core.cache import delete_pattern
from app.db.deps import get_db
from app.models.job import Job
from app.schemas.job import JobCreate, JobOut, JobStatusUpdate, JobUpdate

router = CamelAPIRouter(prefix="/jobs", tags=["jobs"])


async def _invalidate_analytics(user_id: int) -> None:
    """Wipe any cached analytics for this user — call after any job write."""
    await delete_pattern(f"analytics:user:{user_id}:*")


async def _get_owned_job(db: AsyncSession, user_id: int, job_id: int) -> Job:
    """Fetch a job and verify it belongs to the current user (else 404)."""
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        # 404 (not 403) — don't leak whether the id exists at all.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.get("", response_model=list[JobOut], summary="List the current user's jobs")
async def list_jobs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[str | None, Query(description="Match in title or company")] = None,
    company: Annotated[str | None, Query(description="Filter by exact company")] = None,
    tag: Annotated[str | None, Query(description="Reserved; ignored for now")] = None,
) -> list[Job]:
    stmt = select(Job).where(Job.user_id == current_user.id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Job.company.ilike(like)))
    if company:
        stmt = stmt.where(Job.company == company)
    stmt = stmt.order_by(Job.created_at.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new job",
)
async def create_job(
    payload: JobCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    job = Job(
        user_id=current_user.id,
        title=payload.title,
        company=payload.company,
        status=payload.status,
        salary=payload.salary,
        link=str(payload.link) if payload.link else None,
        notes=payload.notes,
        applied_at=payload.applied_at,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await _invalidate_analytics(current_user.id)
    return job


@router.get("/{job_id}", response_model=JobOut, summary="Get a single job")
async def get_job(
    job_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    return await _get_owned_job(db, current_user.id, job_id)


@router.patch("/{job_id}", response_model=JobOut, summary="Partially update a job")
async def update_job(
    job_id: int,
    payload: JobUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    job = await _get_owned_job(db, current_user.id, job_id)
    data = payload.model_dump(exclude_unset=True)
    if "link" in data and data["link"] is not None:
        data["link"] = str(data["link"])
    for field, value in data.items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    await _invalidate_analytics(current_user.id)
    return job


@router.patch(
    "/{job_id}/status",
    response_model=JobOut,
    summary="Change just the status (kanban drag)",
)
async def update_job_status(
    job_id: int,
    payload: JobStatusUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    job = await _get_owned_job(db, current_user.id, job_id)
    job.status = payload.status
    await db.commit()
    await db.refresh(job)
    await _invalidate_analytics(current_user.id)
    return job


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job",
)
async def delete_job(
    job_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    job = await _get_owned_job(db, current_user.id, job_id)
    await db.delete(job)
    await db.commit()
    await _invalidate_analytics(current_user.id)
