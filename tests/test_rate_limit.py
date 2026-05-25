"""End-to-end rate-limit test — proves Redis-backed limiter blocks the 11th call.

Hits /api/ai/interview/questions because it's a JSON endpoint (resume-match
needs a multipart upload — out of scope for this baseline). Same limiter
config: 10 requests per hour per user.
"""

from httpx import AsyncClient


async def test_eleventh_call_returns_429(client: AsyncClient, alice: dict) -> None:
    body = {"role": "Engineer", "count": 1}

    # 10 successful calls
    for i in range(10):
        resp = await client.post(
            "/api/ai/interview/questions",
            headers=alice["headers"],
            json=body,
        )
        assert resp.status_code == 200, f"call {i + 1} unexpectedly failed: {resp.text}"

    # 11th must be 429 with a Retry-After header
    blocked = await client.post(
        "/api/ai/interview/questions",
        headers=alice["headers"],
        json=body,
    )
    assert blocked.status_code == 429
    assert "rate limit" in blocked.json()["detail"].lower()
    assert int(blocked.headers["retry-after"]) > 0


async def test_separate_users_have_separate_limits(
    client: AsyncClient, alice: dict, bob: dict
) -> None:
    body = {"role": "Engineer", "count": 1}

    # Burn alice's 10 + 1 (429)
    for _ in range(10):
        await client.post(
            "/api/ai/interview/questions", headers=alice["headers"], json=body
        )
    blocked = await client.post(
        "/api/ai/interview/questions", headers=alice["headers"], json=body
    )
    assert blocked.status_code == 429

    # Bob's first call should still succeed.
    bobs = await client.post(
        "/api/ai/interview/questions", headers=bob["headers"], json=body
    )
    assert bobs.status_code == 200
