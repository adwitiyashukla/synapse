import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from starlette.background import BackgroundTask

from app.agent.memory import maybe_summarize
from app.agent.orchestrator import run_agent
from app.api.deps import DB, CurrentUser, get_owned_session, rate_limit_chat
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.llm.pricing import estimate_cost
from app.llm.registry import get_provider
from app.models import ChatSession, Document, Message, utcnow
from app.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(rate_limit_chat)])
logger = logging.getLogger("synapse.api.chat")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _generate_title(first_message: str) -> str | None:
    settings = get_settings()
    try:
        title = await get_provider().complete(
            [
                {
                    "role": "user",
                    "content": (
                        "Write a title of at most 6 words for a conversation that "
                        f"starts with this message. Return only the title, no quotes.\n\n"
                        f"Message: {first_message[:500]}"
                    ),
                }
            ],
            model=settings.utility_model,
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("title generation failed: %s", exc)
        return None
    title = title.strip().strip('"').strip()
    return title[:80] or None


async def _summarize_in_background(session_id: str) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await maybe_summarize(db, session_id)
        except Exception as exc:
            logger.warning("background summarization failed: %s", exc)


@router.post("/{session_id}")
async def chat(
    body: ChatRequest,
    user: CurrentUser,
    db: DB,
    session: ChatSession = Depends(get_owned_session),
) -> StreamingResponse:
    settings = get_settings()
    model = body.model or session.model or settings.chat_model
    if model not in settings.model_list:
        model = settings.chat_model

    doc_count = (
        await db.execute(
            select(Document.id)
            .where(Document.user_id == user.id, Document.status == "ready")
            .limit(1)
        )
    ).first()
    has_documents = doc_count is not None

    user_message = Message(session_id=session.id, role="user", content=body.content)
    db.add(user_message)
    session.updated_at = utcnow()
    await db.commit()

    needs_title = session.title == "New chat"

    async def event_stream() -> AsyncIterator[str]:
        started = time.perf_counter()
        final: dict = {}
        try:
            async for event in run_agent(
                db=db,
                user=user,
                session=session,
                user_content=body.content,
                model=model,
                temperature=body.temperature,
                use_rag=body.use_rag,
                has_documents=has_documents,
            ):
                if event["type"] == "final":
                    final = event
                else:
                    yield _sse(event)
        except Exception as exc:
            logger.exception("chat stream failed")
            yield _sse({"type": "error", "message": f"Something went wrong: {exc}"})
            return

        latency_ms = round((time.perf_counter() - started) * 1000)
        cost = estimate_cost(model, final.get("input_tokens", 0), final.get("output_tokens", 0))
        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content=final.get("content", ""),
            tool_calls_json=json.dumps(final.get("tool_calls", [])) if final.get("tool_calls") else None,
            citations_json=json.dumps(final.get("citations", [])) if final.get("citations") else None,
            model=model,
            input_tokens=final.get("input_tokens", 0),
            output_tokens=final.get("output_tokens", 0),
            cost_usd=cost,
            latency_ms=latency_ms,
        )
        db.add(assistant_message)
        session.updated_at = utcnow()
        await db.commit()
        await db.refresh(assistant_message)

        if final.get("citations"):
            yield _sse({"type": "citations", "citations": final["citations"]})
        yield _sse(
            {
                "type": "usage",
                "input_tokens": final.get("input_tokens", 0),
                "output_tokens": final.get("output_tokens", 0),
                "cost_usd": cost,
                "latency_ms": latency_ms,
                "model": model,
            }
        )

        if needs_title:
            title = await _generate_title(body.content)
            if title:
                session.title = title
                await db.commit()
                yield _sse({"type": "title", "title": title})

        yield _sse({"type": "done", "message_id": assistant_message.id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
        background=BackgroundTask(_summarize_in_background, session.id),
    )
