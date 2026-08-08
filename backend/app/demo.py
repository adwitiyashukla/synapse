"""Public demo mode.

Powers the one-click guest experience on the hosted Space:

* On startup a hidden template account ingests the sample documents once, so
  embeddings are paid for a single time per container.
* Each visitor gets their own isolated guest account whose knowledge base is a
  pure database clone of the template (no embedding API calls, instant).
* Guest credentials are random and unusable for a normal login.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password
from app.models import ChatSession, Chunk, Document, Message, User
from app.rag.ingest import ingest_document
from app.rag.vectorstore import get_vector_store

logger = logging.getLogger("synapse.demo")

TEMPLATE_EMAIL = "template@demo.invalid"
GUEST_EMAIL_DOMAIN = "guest.demo.invalid"
GUEST_RETENTION_HOURS = 12


async def seed_demo_content(db: AsyncSession) -> None:
    """Create the template account and ingest the sample documents once."""
    settings = get_settings()
    template = await get_template_user(db)
    if template is None:
        template = User(
            email=TEMPLATE_EMAIL,
            username="Synapse demo",
            password_hash=hash_password(secrets.token_urlsafe(32)),
            is_active=False,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

    existing = (
        await db.execute(
            select(func.count(Document.id)).where(
                Document.user_id == template.id, Document.status == "ready"
            )
        )
    ).scalar_one()
    if existing:
        logger.info("demo seed already present (%s documents)", existing)
        return

    seed_dir = Path(settings.demo_seed_dir)
    if not seed_dir.is_dir():
        logger.warning("demo seed directory missing: %s", seed_dir)
        return

    for path in sorted(seed_dir.iterdir()):
        if path.suffix.lower() not in {".pdf", ".docx", ".txt", ".md"}:
            continue
        data = path.read_bytes()
        document = Document(
            user_id=template.id,
            filename=path.name,
            content_type="text/markdown" if path.suffix == ".md" else "text/plain",
            size_bytes=len(data),
            status="processing",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        await ingest_document(db, document, data)
        await db.refresh(document)
        logger.info(
            "seeded demo document %s (%s, %s chunks)",
            document.filename,
            document.status,
            document.chunk_count,
        )


async def get_template_user(db: AsyncSession) -> User | None:
    return (
        await db.execute(select(User).where(User.email == TEMPLATE_EMAIL))
    ).scalar_one_or_none()


async def create_guest_user(db: AsyncSession) -> User:
    """Create an isolated guest account with a cloned knowledge base."""
    guest = User(
        email=f"guest-{uuid.uuid4().hex[:12]}@{GUEST_EMAIL_DOMAIN}",
        username="Guest",
        password_hash=hash_password(secrets.token_urlsafe(32)),
        is_active=True,
    )
    db.add(guest)
    await db.commit()
    await db.refresh(guest)

    await clone_template_documents(db, guest)
    return guest


async def clone_template_documents(db: AsyncSession, guest: User) -> None:
    """Copy the template's documents and chunks to the guest.

    Embeddings are already computed and stored on the template chunk rows, so
    this is a pure database copy plus an in-process vector store insert. No
    provider calls, which keeps guest sign-in instant and free.
    """
    template = await get_template_user(db)
    if template is None:
        return

    documents = (
        (
            await db.execute(
                select(Document).where(
                    Document.user_id == template.id, Document.status == "ready"
                )
            )
        )
        .scalars()
        .all()
    )
    if not documents:
        return

    store = get_vector_store()
    for source in documents:
        copy = Document(
            user_id=guest.id,
            filename=source.filename,
            content_type=source.content_type,
            size_bytes=source.size_bytes,
            status="ready",
            chunk_count=source.chunk_count,
        )
        db.add(copy)
        await db.flush()  # assign the new document id

        chunks = (
            (
                await db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == source.id)
                    .order_by(Chunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )

        ids: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict] = []
        for chunk in chunks:
            chunk_id = f"{copy.id}:{chunk.chunk_index}"
            db.add(
                Chunk(
                    id=chunk_id,
                    document_id=copy.id,
                    user_id=guest.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    embedding=chunk.embedding,
                )
            )
            if chunk.embedding:
                ids.append(chunk_id)
                embeddings.append(
                    np.frombuffer(chunk.embedding, dtype=np.float32).tolist()
                )
                metadatas.append(
                    {
                        "user_id": guest.id,
                        "document_id": copy.id,
                        "chunk_index": chunk.chunk_index,
                    }
                )
        if ids:
            store.add(ids, embeddings, metadatas)

    await db.commit()


async def purge_stale_guests(db: AsyncSession) -> int:
    """Delete guest accounts older than the retention window.

    Keeps the demo database small on long-lived containers. Cascades remove the
    guest's sessions, messages, documents and chunks.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=GUEST_RETENTION_HOURS)
    stale = (
        (
            await db.execute(
                select(User).where(
                    User.email.like(f"%@{GUEST_EMAIL_DOMAIN}"),
                    User.created_at < cutoff,
                )
            )
        )
        .scalars()
        .all()
    )
    if not stale:
        return 0

    store = get_vector_store()
    for user in stale:
        documents = (
            (await db.execute(select(Document).where(Document.user_id == user.id)))
            .scalars()
            .all()
        )
        for document in documents:
            store.delete_document(document.id)
        session_ids = (
            (
                await db.execute(
                    select(ChatSession.id).where(ChatSession.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        if session_ids:
            await db.execute(
                delete(Message).where(Message.session_id.in_(session_ids))
            )
        await db.delete(user)
    await db.commit()
    logger.info("purged %s stale guest accounts", len(stale))
    return len(stale)
