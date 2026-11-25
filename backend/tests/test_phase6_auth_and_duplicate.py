import httpx
import pytest

from app.core.config import settings
from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_auth_login_and_duplicate_project(client: httpx.AsyncClient, monkeypatch):
    # 1. Auth login & token verification
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"username": settings.STUDIO_USERNAME, "password": "wrong"},
    )
    assert bad_login.status_code == 401

    good_login = await client.post(
        "/api/v1/auth/login",
        json={"username": settings.STUDIO_USERNAME, "password": settings.STUDIO_PASSWORD},
    )
    assert good_login.status_code == 200
    token = good_login.json()["access_token"]

    # Enforce AUTH_REQUIRED=True temporarily
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    unauth = await client.get("/api/v1/auth/me")
    assert unauth.status_code == 401

    authed = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert authed.status_code == 200
    assert authed.json()["authenticated"] is True
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)

    # 2. Project duplicate preserves scripts
    orig = (
        await client.post(
            "/api/v1/projects",
            json={"title": "Original Lesson", "target_duration_sec": 120},
        )
    ).json()
    await client.post(
        f"/api/v1/projects/{orig['id']}/scripts",
        json={"raw_text": "This is a duplicated lesson script with enough words."},
    )

    dup_res = await client.post(f"/api/v1/projects/{orig['id']}/duplicate")
    assert dup_res.status_code == 201
    dup = dup_res.json()
    assert dup["title"] == "Original Lesson (Copy)"
    dup_scripts = (await client.get(f"/api/v1/projects/{dup['id']}/scripts")).json()
    assert len(dup_scripts) == 1
