"""Agent orchestrator: the tool-calling loop at the heart of Synapse.

Streams model output while transparently executing tool calls, then yields
a final aggregate event with usage, tool activity and citations so the API
layer can persist everything.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import toolkit
from app.agent.memory import build_history
from app.config import get_settings
from app.llm.base import ChatOptions, ToolCallRequest
from app.llm.registry import get_provider
from app.models import ChatSession, User

logger = logging.getLogger("synapse.agent")

SYSTEM_PROMPT = """You are Synapse, a capable and warm AI assistant.

Guidelines:
- Use tools whenever they make the answer more accurate or current. Prefer \
web_search for anything after your training cutoff, get_weather for weather, \
calculator for non-trivial arithmetic, and search_documents when the user \
refers to their uploaded files.
- When you use passages from search_documents, cite the source filename \
inline, for example: (source: report.pdf).
- Format responses in Markdown. Use code blocks with language tags for code.
- Be concise by default; expand when the user asks for depth.
- If a tool fails, say so plainly and answer as best you can without it.

Today's date is {today}.{summary_block}"""


def build_system_prompt(session: ChatSession) -> str:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    summary_block = ""
    if session.summary:
        summary_block = (
            "\n\nContext from earlier in this conversation:\n" + session.summary
        )
    return SYSTEM_PROMPT.format(today=today, summary_block=summary_block)


async def run_agent(
    db: AsyncSession,
    user: User,
    session: ChatSession,
    user_content: str,
    model: str,
    temperature: float,
    use_rag: bool,
    has_documents: bool,
) -> AsyncIterator[dict[str, Any]]:
    """Yield streaming events, ending with a single 'final' aggregate event."""
    settings = get_settings()
    provider = get_provider()

    history = await build_history(db, session)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(session)},
        *history,
        {"role": "user", "content": user_content},
    ]
    tools = toolkit.build_tool_schemas(include_documents=use_rag and has_documents)
    options = ChatOptions(model=model, temperature=temperature, tools=tools)

    final_text_parts: list[str] = []
    total_input = 0
    total_output = 0
    tool_log: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []

    for _ in range(settings.max_agent_iterations):
        pending_calls: list[ToolCallRequest] = []
        round_text_parts: list[str] = []

        async for event in provider.stream_chat(messages, options):
            if event["type"] == "delta":
                round_text_parts.append(event["text"])
                yield {"type": "token", "text": event["text"]}
            elif event["type"] == "usage":
                total_input += event["input_tokens"]
                total_output += event["output_tokens"]
            elif event["type"] == "tool_calls":
                pending_calls = event["calls"]

        round_text = "".join(round_text_parts)
        if round_text:
            final_text_parts.append(round_text)

        if not pending_calls:
            break  # the model produced its final answer

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": round_text or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments,
                        **call.function_extra,
                    },
                    # Echo provider-specific fields (e.g. Gemini thought
                    # signatures) exactly as they were received.
                    **call.extra,
                }
                for call in pending_calls
            ],
        }
        messages.append(assistant_message)

        for call in pending_calls:
            yield {
                "type": "tool_start",
                "name": call.name,
                "arguments": _safe_args(call.arguments),
            }

        results = await asyncio.gather(
            *[
                toolkit.dispatch(call.name, call.arguments, db, user.id)
                for call in pending_calls
            ]
        )

        for call, result in zip(pending_calls, results, strict=True):
            tool_log.append(
                {
                    "name": call.name,
                    "arguments": _safe_args(call.arguments),
                    "result_preview": result[:400],
                }
            )
            if call.name == "search_documents":
                citations.extend(_extract_citations(result))
            yield {
                "type": "tool_end",
                "name": call.name,
                "result_preview": result[:300],
            }
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )
    else:
        logger.warning("agent hit max iterations for session %s", session.id)

    yield {
        "type": "final",
        "content": "".join(final_text_parts),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "tool_calls": tool_log,
        "citations": _dedupe_citations(citations),
    }


def _safe_args(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _extract_citations(result: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(result)
        return [
            {
                "source": item.get("source", "document"),
                "chunk_id": item.get("chunk_id", ""),
                "excerpt": (item.get("excerpt") or "")[:300],
            }
            for item in payload.get("results", [])
        ]
    except (json.JSONDecodeError, AttributeError):
        return []


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for citation in citations:
        key = citation.get("chunk_id") or citation.get("excerpt", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(citation)
    return unique
