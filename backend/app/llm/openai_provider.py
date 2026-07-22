"""OpenAI provider. Works with any OpenAI-compatible API via base_url,
which includes OpenAI itself, Groq, Together, and local Ollama servers.
"""

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.llm.base import ChatOptions, LLMProvider, StreamEvent, ToolCallRequest


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str, embedding_model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.embedding_model = embedding_model

    async def stream_chat(
        self, messages: list[dict[str, Any]], options: ChatOptions
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": options.model,
            "messages": messages,
            "temperature": options.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if options.tools:
            kwargs["tools"] = options.tools
            kwargs["tool_choice"] = "auto"
        if options.max_tokens:
            kwargs["max_tokens"] = options.max_tokens

        stream = await self.client.chat.completions.create(**kwargs)

        # Tool call fragments arrive incrementally and must be assembled by index.
        pending_calls: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            if chunk.usage is not None:
                yield {
                    "type": "usage",
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                yield {"type": "delta", "text": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    slot = pending_calls.setdefault(
                        tc.index,
                        {
                            "id": "",
                            "name": "",
                            "arguments": "",
                            "extra": {},
                            "function_extra": {},
                        },
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments
                    # Preserve provider-specific fields (Gemini attaches thought
                    # signatures here) so they can be echoed back verbatim.
                    slot["extra"].update(getattr(tc, "model_extra", None) or {})
                    if tc.function is not None:
                        slot["function_extra"].update(
                            getattr(tc.function, "model_extra", None) or {}
                        )

        if pending_calls:
            calls = [
                ToolCallRequest(
                    id=slot["id"] or f"call_{index}",
                    name=slot["name"],
                    arguments=slot["arguments"] or "{}",
                    extra=slot["extra"],
                    function_extra=slot["function_extra"],
                )
                for index, slot in sorted(pending_calls.items())
            ]
            yield {"type": "tool_calls", "calls": calls}

    async def complete(
        self, messages: list[dict[str, Any]], model: str, temperature: float = 0.3
    ) -> str:
        response = await self.client.chat.completions.create(
            model=model, messages=messages, temperature=temperature
        )
        return response.choices[0].message.content or ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.embedding_model, input=texts
        )
        # The API preserves input order. Sort by index only when every item
        # actually has one; some providers (e.g. Gemini's compatibility
        # layer) omit the index field.
        items = list(response.data)
        if all(getattr(item, "index", None) is not None for item in items):
            items.sort(key=lambda item: item.index)
        return [item.embedding for item in items]
