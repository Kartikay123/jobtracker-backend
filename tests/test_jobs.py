"""Jobs CRUD tests + ownership isolation + filters."""

from httpx import AsyncClient


# --- Create / list ----------------------------------------------------------
async def test_create_job(client: AsyncClient, alice: dict) -> None:
    resp = await client.post(
        "/api/jobs",
        headers=alice["headers"],
        json={
            "title": "Senior Engineer",
            "company": "Acme",
            "status": "applied",
            "appliedAt": "2026-04-15T10:00:00Z",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Senior Engineer"
    assert body["company"] == "Acme"
    assert body["status"] == "applied"
    assert body["appliedAt"] == "2026-04-15T10:00:00Z"
    # camelCase serialization works
    assert "userId" in body and "createdAt" in body


async def test_list_returns_only_my_jobs(
    client: AsyncClient, alice: dict, bob: dict
) -> None:
    await client.post(
        "/api/jobs", headers=alice["headers"],
        json={"title": "Alice's Job", "company": "Alice Co", "status": "applied"},
    )
    await client.post(
        "/api/jobs", headers=bob["headers"],
        json={"title": "Bob's Job", "company": "Bob Co", "status": "applied"},
    )

    alice_list = await client.get("/api/jobs", headers=alice["headers"])
    assert alice_list.status_code == 200
    titles = [j["title"] for j in alice_list.json()]
    assert titles == ["Alice's Job"]


# --- Filters ----------------------------------------------------------------
async def test_search_filter(client: AsyncClient, alice: dict) -> None:
    payload = lambda t, c: {"title": t, "company": c, "status": "applied"}
    await client.post("/api/jobs", headers=alice["headers"], json=payload("Backend Dev", "Acme"))
    await client.post("/api/jobs", headers=alice["headers"], json=payload("Frontend Dev", "Globex"))
    await client.post("/api/jobs", headers=alice["headers"], json=payload("PM", "Initech"))

    resp = await client.get(
        "/api/jobs", headers=alice["headers"], params={"search": "Dev"}
    )
    assert resp.status_code == 200
    titles = sorted(j["title"] for j in resp.json())
    assert titles == ["Backend Dev", "Frontend Dev"]


async def test_company_filter_exact_match(client: AsyncClient, alice: dict) -> None:
    payload = lambda c: {"title": "X", "company": c, "status": "applied"}
    await client.post("/api/jobs", headers=alice["headers"], json=payload("Acme"))
    await client.post("/api/jobs", headers=alice["headers"], json=payload("Acme Corp"))

    resp = await client.get(
        "/api/jobs", headers=alice["headers"], params={"company": "Acme"}
    )
    assert resp.status_code == 200
    assert {j["company"] for j in resp.json()} == {"Acme"}


# --- Get / Patch / Status / Delete -----------------------------------------
async def test_full_lifecycle(client: AsyncClient, alice: dict) -> None:
    # Create
    create = await client.post(
        "/api/jobs", headers=alice["headers"],
        json={"title": "Temp", "company": "Acme", "status": "applied"},
    )
    job_id = create.json()["id"]

    # Get
    got = await client.get(f"/api/jobs/{job_id}", headers=alice["headers"])
    assert got.status_code == 200
    assert got.json()["title"] == "Temp"

    # Patch
    patched = await client.patch(
        f"/api/jobs/{job_id}",
        headers=alice["headers"],
        json={"title": "Renamed", "notes": "From recruiter"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed"
    assert patched.json()["notes"] == "From recruiter"

    # Status (kanban drag)
    moved = await client.patch(
        f"/api/jobs/{job_id}/status",
        headers=alice["headers"],
        json={"status": "interview"},
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "interview"

    # Delete
    deleted = await client.delete(f"/api/jobs/{job_id}", headers=alice["headers"])
    assert deleted.status_code == 204

    gone = await client.get(f"/api/jobs/{job_id}", headers=alice["headers"])
    assert gone.status_code == 404


# --- Ownership isolation ---------------------------------------------------
async def test_bob_cannot_read_alices_job(
    client: AsyncClient, alice: dict, bob: dict
) -> None:
    create = await client.post(
        "/api/jobs", headers=alice["headers"],
        json={"title": "Secret", "company": "Acme", "status": "applied"},
    )
    job_id = create.json()["id"]

    resp = await client.get(f"/api/jobs/{job_id}", headers=bob["headers"])
    # 404 not 403 — don't leak existence.
    assert resp.status_code == 404


async def test_bob_cannot_modify_alices_job(
    client: AsyncClient, alice: dict, bob: dict
) -> None:
    create = await client.post(
        "/api/jobs", headers=alice["headers"],
        json={"title": "Secret", "company": "Acme", "status": "applied"},
    )
    job_id = create.json()["id"]

    patch = await client.patch(
        f"/api/jobs/{job_id}",
        headers=bob["headers"],
        json={"title": "Hijacked"},
    )
    assert patch.status_code == 404

    delete = await client.delete(f"/api/jobs/{job_id}", headers=bob["headers"])
    assert delete.status_code == 404


# --- Validation -------------------------------------------------------------
async def test_invalid_status_rejected(client: AsyncClient, alice: dict) -> None:
    resp = await client.post(
        "/api/jobs",
        headers=alice["headers"],
        json={"title": "X", "company": "Y", "status": "ghosted"},
    )
    assert resp.status_code == 422


async def test_create_job_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/jobs", json={"title": "X", "company": "Y", "status": "applied"}
    )
    assert resp.status_code == 401
