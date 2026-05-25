"""Pydantic schemas for analytics responses."""

from app.schemas._base import CamelModel


class WeeklyPoint(CamelModel):
    week: str   # ISO week label, e.g. "2026-W18"
    count: int


class FunnelPoint(CamelModel):
    stage: str  # "Applied", "Interview", "Offer"
    count: int


class AnalyticsSummary(CamelModel):
    """Response of GET /analytics/summary — exact shape AnalyticsPage.jsx reads."""

    total_applications: int = 0
    applications_delta: int | None = None

    response_rate: int = 0           # % of jobs past 'applied'
    response_delta: int | None = None

    interview_rate: int = 0          # % of jobs that reached 'interview' or beyond
    interview_delta: int | None = None

    weekly: list[WeeklyPoint] = []
    funnel: list[FunnelPoint] = []
