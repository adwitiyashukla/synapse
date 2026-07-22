"""Chat session CRUD endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, get_owned_session
from app.models import ChatSession, Message
from app.schemas import MessageOut, SessionCreate, SessionOut, SessionUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
async def list_sessions(user: CurrentUser, db: DB) -> list[SessionOut]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return [SessionOut.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate, user: CurrentUser, db: DB) -> SessionOut:
    session = ChatSession(
        user_id=user.id,
        title=(body.title or "New chat").strip()[:200] or "New chat",
        model=body.model,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut.model_validate(session)


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session: ChatSession = Depends(get_owned_session),
) -> SessionOut:
    return SessionOut.model_validate(session)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    db: DB, session: ChatSession = Depends(get_owned_session)
) -> list[MessageOut]:
    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.id)
    )
    return [MessageOut.model_validate(m) for m in result.scalars().all()]


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(
    body: SessionUpdate, db: DB, session: ChatSession = Depends(get_owned_session)
) -> SessionOut:
    if body.title is not None:
        session.title = body.title.strip()[:200] or session.title
    if body.model is not None:
        session.model = body.model
    await db.commit()
    await db.refresh(session)
    return SessionOut.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    db: DB, session: ChatSession = Depends(get_owned_session)
) -> None:
    await db.delete(session)
    await db.commit()
