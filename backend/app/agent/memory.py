import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.llm.registry import get_provider
from app.models import ChatSession, Message

logger = logging.getLogger("synapse.agent.memory")


async def build_history(
    db: AsyncSession, session: ChatSession
) -> list[dict[str, str]]:
    settings = get_settings()
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.id.desc())
        .limit(settings.history_window_messages)
    )
    recent = list(reversed(result.scalars().all()))
    history: list[dict[str, str]] = []
    for message in recent:
        history.append({"role": message.role, "content": message.content})
    return history


async def maybe_summarize(db: AsyncSession, session_id: str) -> None:
    settings = get_settings()
    provider = get_provider()

    session = await db.get(ChatSession, session_id)
    if session is None:
        return
    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.id)
    )
    messages = result.scalars().all()
    unsummarized = [m for m in messages if m.id > session.summarized_until]
    if len(unsummarized) < settings.summarize_after_messages:
        return

    keep = settings.history_window_messages // 2
    to_compress = unsummarized[:-keep] if keep else unsummarized
    if not to_compress:
        return

    transcript = "\n".join(
        f"{m.role.upper()}: {m.content[:800]}" for m in to_compress
    )
    prompt = (
        "Update the running summary of this conversation. Keep key facts, "
        "decisions, names, numbers and open questions. Be concise (under 250 "
        "words) and neutral.\n\n"
        f"Existing summary:\n{session.summary or '(none)'}\n\n"
        f"New messages:\n{transcript}"
    )
    try:
        summary = await provider.complete(
            [{"role": "user", "content": prompt}],
            model=settings.utility_model,
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("summarization failed: %s", exc)
        return
    session.summary = summary.strip()[:4000]
    session.summarized_until = to_compress[-1].id
    await db.commit()
    logger.info("summarized session %s up to message %s", session.id, session.summarized_until)
