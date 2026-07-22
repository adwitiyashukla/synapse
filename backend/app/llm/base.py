"""Provider abstraction so any OpenAI-compatible LLM API can power the app.

Providers translate their native streaming format into a small set of
normalized events consumed by the agent orchestrator:

    {"type": "delta", "text": "..."}                       incremental text
    {"type": "tool_calls", "calls": [ToolCallRequest...]}  model wants tools
    {"type": "usage", "input_tokens": int, "output_tokens": int}
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

StreamEvent = dict[str, Any]


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: str  # raw JSON string as produced by the model


@dataclass
class ChatOptions:
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(ABC):
    """Interface implemented by every model provider."""

    @abstractmethod
    def stream_chat(
        self, messages: list[dict[str, Any]], options: ChatOptions
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat completion as normalized events."""

    @abstractmethod
    async def complete(
        self, messages: list[dict[str, Any]], model: str, temperature: float = 0.3
    ) -> str:
        """Non-streaming completion used for titles, summaries and reranking."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
