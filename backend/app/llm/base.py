from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

StreamEvent = dict[str, Any]


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: str
    extra: dict[str, Any] = field(default_factory=dict)
    function_extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatOptions:
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(ABC):
    @abstractmethod
    def stream_chat(
        self, messages: list[dict[str, Any]], options: ChatOptions
    ) -> AsyncIterator[StreamEvent]:
        ...

    @abstractmethod
    async def complete(
        self, messages: list[dict[str, Any]], model: str, temperature: float = 0.3
    ) -> str:
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...
