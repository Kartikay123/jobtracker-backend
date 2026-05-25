"""Smoke tests."""

from httpx import AsyncClient


async def test_root_returns_metadata(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "JobTracker API"
    assert "docs" in body


async def test_health_reports_db_and_redis_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "status": "ok",
        "environment": "development",
        "database": "ok",
        "redis": "ok",
    }
