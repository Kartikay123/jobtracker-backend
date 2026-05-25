"""v1 API router — aggregates every feature router under one prefix.

Mounted in app/main.py via `app.include_router(api_router, prefix="/api")`.
When we want versioned URLs later, change that to `prefix="/api/v1"` —
nothing else changes.
"""

from fastapi import APIRouter

from app.api.v1 import admin, ai, analytics, auth, interview, jobs, profile

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(jobs.router)
api_router.include_router(analytics.router)
api_router.include_router(ai.router)
api_router.include_router(interview.router)
api_router.include_router(admin.router)
api_router.include_router(profile.router)
