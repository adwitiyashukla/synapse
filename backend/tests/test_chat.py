import json

from httpx import AsyncClient

from tests.conftest import FakeProvider, register_and_login


def parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            events.append(json.loads(block[len("data: ") :]))
    return events


async def create_session(client: AsyncClient, headers: dict) -> str:
    response = await client.post("/api/sessions", json={}, headers=headers)
    return response.json()["id"]


async def test_simple_chat_stream(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    fake_provider.turns = [{"text": "The answer is 42."}]
    headers = await register_and_login(client)
    session_id = await create_session(client, headers)

    response = await client.post(
        f"/api/chat/{session_id}", json={"content": "What is the answer?"}, headers=headers
    )
    assert response.status_code == 200
    events = parse_sse(response.text)
    types = [e["type"] for e in events]

    assert "token" in types
    assert types[-1] == "done"
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "42" in text

    usage = next(e for e in events if e["type"] == "usage")
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 20
    assert usage["cost_usd"] > 0

    title_event = next(e for e in events if e["type"] == "title")
    assert title_event["title"] == "Fake title"

    messages = (
        await client.get(f"/api/sessions/{session_id}/messages", headers=headers)
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["cost_usd"] > 0


async def test_chat_with_tool_call(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    fake_provider.turns = [
        {"tool_calls": [("calculator", '{"expression": "6*7"}')]},
        {"text": "The result is 42."},
    ]
    headers = await register_and_login(client)
    session_id = await create_session(client, headers)

    response = await client.post(
        f"/api/chat/{session_id}", json={"content": "compute 6*7"}, headers=headers
    )
    events = parse_sse(response.text)
    types = [e["type"] for e in events]
    assert "tool_start" in types and "tool_end" in types

    tool_end = next(e for e in events if e["type"] == "tool_end")
    assert tool_end["name"] == "calculator"
    assert "42" in tool_end["result_preview"]

    second_call_messages = fake_provider.calls[1]
    assert any(m.get("role") == "tool" and "42" in m["content"] for m in second_call_messages)

    messages = (
        await client.get(f"/api/sessions/{session_id}/messages", headers=headers)
    ).json()
    tool_log = json.loads(messages[1]["tool_calls_json"])
    assert tool_log[0]["name"] == "calculator"


async def test_provider_extra_fields_are_echoed_back(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    signature = {"extra_content": {"google": {"thought_signature": "sig-abc-123"}}}
    fake_provider.turns = [
        {"tool_calls": [("calculator", '{"expression": "1+1"}', signature)]},
        {"text": "The result is 2."},
    ]
    headers = await register_and_login(client)
    session_id = await create_session(client, headers)

    response = await client.post(
        f"/api/chat/{session_id}", json={"content": "1+1?"}, headers=headers
    )
    assert response.status_code == 200

    second_round = fake_provider.calls[1]
    assistant = next(m for m in second_round if m.get("tool_calls"))
    echoed = assistant["tool_calls"][0]
    assert echoed["extra_content"] == {"google": {"thought_signature": "sig-abc-123"}}


async def test_chat_rejects_foreign_session(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    headers_a = await register_and_login(client, "a@example.com")
    headers_b = await register_and_login(client, "b@example.com")
    session_id = await create_session(client, headers_a)

    response = await client.post(
        f"/api/chat/{session_id}", json={"content": "hi"}, headers=headers_b
    )
    assert response.status_code == 404


async def test_analytics_reflect_chat(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    fake_provider.turns = [{"text": "Hello there."}]
    headers = await register_and_login(client)
    session_id = await create_session(client, headers)
    await client.post(f"/api/chat/{session_id}", json={"content": "hi"}, headers=headers)

    overview = (await client.get("/api/analytics/overview", headers=headers)).json()
    assert overview["total_messages"] == 2
    assert overview["total_sessions"] == 1
    assert overview["input_tokens"] == 100
    assert overview["output_tokens"] == 20
    assert overview["cost_usd"] > 0
    assert overview["models"][0]["model"] == "gpt-5.6-luna"
    assert len(overview["daily"]) == 30
