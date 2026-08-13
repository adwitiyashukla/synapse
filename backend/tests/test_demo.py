import pytest
from httpx import AsyncClient

from app.api import deps
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.demo import (
    GUEST_EMAIL_DOMAIN,
    create_guest_user,
    get_template_user,
    seed_demo_content,
)
from tests.conftest import FakeProvider, register_and_login


@pytest.fixture
def demo_mode():
    settings = get_settings()
    settings.demo_mode = True
    deps.settings.demo_mode = True
    deps.demo_session_limiter.reset()
    deps.demo_chat_limiter.reset()
    deps.demo_daily_quota.reset()
    yield settings
    settings.demo_mode = False
    deps.settings.demo_mode = False


async def test_demo_endpoint_disabled_by_default(client: AsyncClient) -> None:
    response = await client.post("/api/auth/demo")
    assert response.status_code == 404


async def test_demo_session_returns_working_tokens(
    client: AsyncClient, fake_provider: FakeProvider, demo_mode
) -> None:
    response = await client.post("/api/auth/demo")
    assert response.status_code == 201, response.text
    tokens = response.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me = (await client.get("/api/auth/me", headers=headers)).json()
    assert me["username"] == "Guest"
    assert me["email"].endswith(f"@{GUEST_EMAIL_DOMAIN}")

    session = await client.post("/api/sessions", json={}, headers=headers)
    assert session.status_code == 201


async def test_each_guest_is_isolated(
    client: AsyncClient, fake_provider: FakeProvider, demo_mode
) -> None:
    first = (await client.post("/api/auth/demo")).json()
    second = (await client.post("/api/auth/demo")).json()
    headers_a = {"Authorization": f"Bearer {first['access_token']}"}
    headers_b = {"Authorization": f"Bearer {second['access_token']}"}

    created = await client.post("/api/sessions", json={}, headers=headers_a)
    session_id = created.json()["id"]

    assert (await client.get("/api/sessions", headers=headers_b)).json() == []
    stolen = await client.get(f"/api/sessions/{session_id}", headers=headers_b)
    assert stolen.status_code == 404


async def test_seeded_documents_are_cloned_to_each_guest(
    client: AsyncClient, fake_provider: FakeProvider, demo_mode
) -> None:
    async with AsyncSessionLocal() as db:
        await seed_demo_content(db)
        template = await get_template_user(db)
        assert template is not None

    seeded = await client.post("/api/auth/demo")
    headers = {"Authorization": f"Bearer {seeded.json()['access_token']}"}
    documents = (await client.get("/api/documents", headers=headers)).json()

    assert documents, "guest should start with the sample document"
    assert all(d["status"] == "ready" for d in documents)
    assert all(d["chunk_count"] > 0 for d in documents)


async def test_guest_clone_costs_no_provider_calls(
    client: AsyncClient, fake_provider: FakeProvider, demo_mode
) -> None:
    async with AsyncSessionLocal() as db:
        await seed_demo_content(db)

    calls_before = len(fake_provider.embed_calls)
    async with AsyncSessionLocal() as db:
        await create_guest_user(db)
    assert len(fake_provider.embed_calls) == calls_before


async def test_demo_session_rate_limited(
    client: AsyncClient, fake_provider: FakeProvider, demo_mode
) -> None:
    limit = get_settings().demo_sessions_per_hour
    for _ in range(limit):
        assert (await client.post("/api/auth/demo")).status_code == 201
    blocked = await client.post("/api/auth/demo")
    assert blocked.status_code == 429


async def test_demo_daily_quota_blocks_chat(
    client: AsyncClient, fake_provider: FakeProvider, demo_mode
) -> None:
    deps.demo_daily_quota.limit = 1
    try:
        headers = await register_and_login(client)
        session_id = (
            await client.post("/api/sessions", json={}, headers=headers)
        ).json()["id"]

        fake_provider.turns = [{"text": "hello"}, {"text": "hello"}]
        first = await client.post(
            f"/api/chat/{session_id}", json={"content": "hi"}, headers=headers
        )
        assert first.status_code == 200

        second = await client.post(
            f"/api/chat/{session_id}", json={"content": "hi again"}, headers=headers
        )
        assert second.status_code == 429
        assert "daily" in second.json()["detail"].lower()
    finally:
        deps.demo_daily_quota.limit = get_settings().demo_daily_message_cap
