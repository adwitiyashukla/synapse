"""Shared test fixtures: isolated database, fake LLM provider, test client."""

import os
import tempfile

# Configure the environment BEFORE importing any app module.
_TMP_DIR = tempfile.mkdtemp(prefix="synapse-test-")
os.environ.update(
    {
        "SECRET_KEY": "test-secret-key-not-for-production",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP_DIR}/test.db",
        "VECTOR_STORE": "memory",
        "RERANK_ENABLED": "false",
        "OPENAI_API_KEY": "test-key",
        "CHAT_MODEL": "gpt-5.6-luna",
        "AVAILABLE_MODELS": "gpt-5.6-luna,gpt-4o-mini",
        "SUMMARIZE_AFTER_MESSAGES": "1000",
    }
)

import hashlib  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.api import deps  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.llm.base import ChatOptions, LLMProvider, ToolCallRequest  # noqa: E402
from app.llm.registry import set_provider  # noqa: E402
from app.main import app  # noqa: E402
from app.rag.vectorstore import MemoryVectorStore, set_vector_store  # noqa: E402


def deterministic_embedding(text: str, dims: int = 32) -> list[float]:
    """Token-additive embedding: texts sharing words get similar vectors."""
    vector = np.zeros(dims, dtype=np.float64)
    for token in text.lower().split():
        seed = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vector += rng.randn(dims)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector /= norm
    return vector.tolist()


class FakeProvider(LLMProvider):
    """Scripted provider. Each call to stream_chat consumes one scripted turn.

    A turn is either {"text": "..."} or
    {"tool_calls": [("name", '{"arg": 1}'), ...]}.
    """

    def __init__(self, turns: list[dict[str, Any]] | None = None) -> None:
        self.turns = turns or [{"text": "Hello from the fake model."}]
        self.calls: list[list[dict[str, Any]]] = []
        self.complete_response = "Fake title"

    async def stream_chat(
        self, messages: list[dict[str, Any]], options: ChatOptions
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(messages)
        turn = self.turns.pop(0) if self.turns else {"text": "(no script left)"}
        if "text" in turn:
            for word in turn["text"].split(" "):
                yield {"type": "delta", "text": word + " "}
        if "tool_calls" in turn:
            calls = []
            for i, spec in enumerate(turn["tool_calls"]):
                name, args, *rest = spec
                calls.append(
                    ToolCallRequest(
                        id=f"call_{i}",
                        name=name,
                        arguments=args,
                        extra=rest[0] if rest else {},
                        function_extra=rest[1] if len(rest) > 1 else {},
                    )
                )
            yield {"type": "tool_calls", "calls": calls}
        yield {"type": "usage", "input_tokens": 100, "output_tokens": 20}

    async def complete(
        self, messages: list[dict[str, Any]], model: str, temperature: float = 0.3
    ) -> str:
        return self.complete_response

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [deterministic_embedding(text) for text in texts]


@pytest.fixture
async def fake_provider() -> AsyncIterator[FakeProvider]:
    provider = FakeProvider()
    set_provider(provider)
    yield provider
    set_provider(None)


@pytest.fixture
async def client(fake_provider: FakeProvider) -> AsyncIterator[AsyncClient]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    set_vector_store(MemoryVectorStore())
    deps.auth_limiter.reset()
    deps.chat_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    set_vector_store(None)


async def register_and_login(client: AsyncClient, email: str = "adi@example.com") -> dict[str, str]:
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "username": "adi", "password": "supersecret123"},
    )
    assert response.status_code == 201, response.text
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
