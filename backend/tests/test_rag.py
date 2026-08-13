import json

from httpx import AsyncClient

from app.rag.retriever import rrf_fuse
from app.rag.splitter import split_text
from tests.conftest import FakeProvider, register_and_login


def test_split_short_text_returns_single_chunk() -> None:
    assert split_text("Hello world.", chunk_size=100, overlap=10) == ["Hello world."]


def test_split_respects_chunk_size() -> None:
    text = " ".join(f"word{i}" for i in range(2000))
    chunks = split_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 400 for chunk in chunks)


def test_split_creates_overlap() -> None:
    paragraphs = "\n\n".join(f"Paragraph {i}. " + "content " * 30 for i in range(10))
    chunks = split_text(paragraphs, chunk_size=400, overlap=100)
    assert len(chunks) >= 3


def test_split_empty_text() -> None:
    assert split_text("   \n\n  ") == []


def test_rrf_prefers_ids_ranked_high_in_both_lists() -> None:
    fused = rrf_fuse([["a", "b", "c"], ["b", "a", "d"]])
    ordered = [cid for cid, _ in fused]
    assert set(ordered[:2]) == {"a", "b"}
    assert ordered.index("d") > ordered.index("b")


def test_rrf_single_ranking_preserves_order() -> None:
    fused = rrf_fuse([["x", "y", "z"]])
    assert [cid for cid, _ in fused] == ["x", "y", "z"]


async def test_upload_and_retrieve(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    headers = await register_and_login(client)

    content = (
        "Synapse quarterly report. Revenue grew 45 percent year over year. "
        "The flagship product launched in March. " * 20
        + "\n\nThe engineering team adopted hybrid retrieval with reciprocal rank fusion. "
        * 10
    )
    upload = await client.post(
        "/api/documents",
        files={"file": ("report.txt", content.encode(), "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    assert document["status"] == "ready"
    assert document["chunk_count"] > 0

    fake_provider.turns = [
        {"tool_calls": [("search_documents", '{"query": "revenue growth"}')]},
        {"text": "Revenue grew 45 percent (source: report.txt)."},
    ]
    session = await client.post("/api/sessions", json={}, headers=headers)
    session_id = session.json()["id"]
    response = await client.post(
        f"/api/chat/{session_id}",
        json={"content": "What was revenue growth?"},
        headers=headers,
    )
    assert response.status_code == 200
    raw = response.text
    assert "citations" in raw
    citation_event = next(
        json.loads(block[len("data: ") :])
        for block in raw.split("\n\n")
        if block.strip().startswith("data: ") and '"citations"' in block
    )
    assert citation_event["citations"][0]["source"] == "report.txt"


async def test_upload_rejects_unknown_extension(client: AsyncClient) -> None:
    headers = await register_and_login(client)
    response = await client.post(
        "/api/documents",
        files={"file": ("virus.exe", b"binary", "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 415


async def test_document_delete_removes_chunks(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    headers = await register_and_login(client)
    upload = await client.post(
        "/api/documents",
        files={"file": ("notes.md", b"# Notes\nAlpha beta gamma. " * 50, "text/markdown")},
        headers=headers,
    )
    document_id = upload.json()["id"]

    deleted = await client.delete(f"/api/documents/{document_id}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/documents", headers=headers)).json() == []


async def test_documents_isolated_between_users(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    headers_a = await register_and_login(client, "a@example.com")
    headers_b = await register_and_login(client, "b@example.com")
    upload = await client.post(
        "/api/documents",
        files={"file": ("secret.txt", b"user a private data " * 30, "text/plain")},
        headers=headers_a,
    )
    document_id = upload.json()["id"]

    assert (await client.get("/api/documents", headers=headers_b)).json() == []
    stolen = await client.delete(f"/api/documents/{document_id}", headers=headers_b)
    assert stolen.status_code == 404
