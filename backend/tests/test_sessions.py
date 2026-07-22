"""Session CRUD and user isolation tests."""

from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_session_crud(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    created = await client.post("/api/sessions", json={}, headers=headers)
    assert created.status_code == 201
    session = created.json()
    assert session["title"] == "New chat"

    listed = await client.get("/api/sessions", headers=headers)
    assert len(listed.json()) == 1

    renamed = await client.patch(
        f"/api/sessions/{session['id']}",
        json={"title": "Research notes"},
        headers=headers,
    )
    assert renamed.json()["title"] == "Research notes"

    deleted = await client.delete(f"/api/sessions/{session['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/sessions", headers=headers)).json() == []


async def test_sessions_are_isolated_between_users(client: AsyncClient) -> None:
    headers_a = await register_and_login(client, "a@example.com")
    headers_b = await register_and_login(client, "b@example.com")

    created = await client.post("/api/sessions", json={}, headers=headers_a)
    session_id = created.json()["id"]

    stolen = await client.get(f"/api/sessions/{session_id}", headers=headers_b)
    assert stolen.status_code == 404
    stolen_messages = await client.get(
        f"/api/sessions/{session_id}/messages", headers=headers_b
    )
    assert stolen_messages.status_code == 404
    assert (await client.get("/api/sessions", headers=headers_b)).json() == []
