"""Usage analytics endpoints: tokens, cost, latency, tools, models."""

import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models import ChatSession, Document, Message
from app.schemas import (
    AnalyticsOverview,
    DailyPoint,
    ModelUsage,
    ToolUsage,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(user: CurrentUser, db: DB) -> AnalyticsOverview:
    session_ids = select(ChatSession.id).where(ChatSession.user_id == user.id)

    totals = (
        await db.execute(
            select(
                func.count(Message.id),
                func.coalesce(func.sum(Message.input_tokens), 0),
                func.coalesce(func.sum(Message.output_tokens), 0),
                func.coalesce(func.sum(Message.cost_usd), 0.0),
            ).where(Message.session_id.in_(session_ids))
        )
    ).one()

    avg_latency = (
        await db.execute(
            select(func.coalesce(func.avg(Message.latency_ms), 0)).where(
                Message.session_id.in_(session_ids),
                Message.role == "assistant",
                Message.latency_ms > 0,
            )
        )
    ).scalar_one()

    total_sessions = (
        await db.execute(
            select(func.count(ChatSession.id)).where(ChatSession.user_id == user.id)
        )
    ).scalar_one()
    total_documents = (
        await db.execute(
            select(func.count(Document.id)).where(Document.user_id == user.id)
        )
    ).scalar_one()

    # Last 30 days of assistant messages for the daily series and breakdowns
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent = (
        (
            await db.execute(
                select(Message).where(
                    Message.session_id.in_(session_ids),
                    Message.created_at >= cutoff,
                )
            )
        )
        .scalars()
        .all()
    )

    daily_map: dict[str, DailyPoint] = {}
    for offset in range(29, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).strftime("%Y-%m-%d")
        daily_map[day] = DailyPoint(date=day, messages=0, tokens=0, cost_usd=0.0)
    model_counter: dict[str, ModelUsage] = {}
    tool_counter: Counter[str] = Counter()

    for message in recent:
        day = message.created_at.strftime("%Y-%m-%d")
        if day in daily_map:
            point = daily_map[day]
            point.messages += 1
            point.tokens += message.input_tokens + message.output_tokens
            point.cost_usd = round(point.cost_usd + message.cost_usd, 6)
        if message.role == "assistant" and message.model:
            usage = model_counter.setdefault(
                message.model, ModelUsage(model=message.model, messages=0, cost_usd=0.0)
            )
            usage.messages += 1
            usage.cost_usd = round(usage.cost_usd + message.cost_usd, 6)
        if message.tool_calls_json:
            try:
                for call in json.loads(message.tool_calls_json):
                    tool_counter[call.get("name", "unknown")] += 1
            except json.JSONDecodeError:
                pass

    return AnalyticsOverview(
        total_messages=totals[0],
        total_sessions=total_sessions,
        total_documents=total_documents,
        input_tokens=totals[1],
        output_tokens=totals[2],
        cost_usd=round(totals[3], 6),
        avg_latency_ms=round(avg_latency),
        daily=list(daily_map.values()),
        models=sorted(
            model_counter.values(), key=lambda m: m.messages, reverse=True
        ),
        tools=[
            ToolUsage(name=name, count=count)
            for name, count in tool_counter.most_common()
        ],
    )
