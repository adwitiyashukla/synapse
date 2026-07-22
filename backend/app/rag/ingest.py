"""Document ingestion pipeline: extract, chunk, embed, index."""

import logging

import numpy as np
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.llm.registry import get_provider
from app.models import Chunk, Document
from app.rag.extract import extract_text
from app.rag.splitter import split_text
from app.rag.vectorstore import get_vector_store

logger = logging.getLogger("synapse.rag.ingest")

EMBED_BATCH_SIZE = 64


async def ingest_document(db: AsyncSession, document: Document, data: bytes) -> None:
    """Process an uploaded file end to end. Updates the document row in place."""
    settings = get_settings()
    provider = get_provider()
    store = get_vector_store()

    try:
        text = extract_text(document.filename, data)
        chunks = split_text(text, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("The document produced no text chunks.")

        embeddings: list[list[float]] = []
        for start in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[start : start + EMBED_BATCH_SIZE]
            embeddings.extend(await provider.embed(batch))

        ids = [f"{document.id}:{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "user_id": document.user_id,
                "document_id": document.id,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        store.add(ids, embeddings, metadatas)

        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            db.add(
                Chunk(
                    id=ids[i],
                    document_id=document.id,
                    user_id=document.user_id,
                    chunk_index=i,
                    text=chunk_text,
                    embedding=np.asarray(embedding, dtype=np.float32).tobytes(),
                )
            )
        document.status = "ready"
        document.chunk_count = len(chunks)
        document.error = None
        logger.info(
            "ingested document %s (%s chunks)", document.filename, len(chunks)
        )
    except Exception as exc:
        document.status = "failed"
        document.error = str(exc)[:2000]
        logger.warning("ingestion failed for %s: %s", document.filename, exc)
    await db.commit()


async def delete_document_data(db: AsyncSession, document: Document) -> None:
    """Remove a document's chunks from both SQLite and the vector store."""
    get_vector_store().delete_document(document.id)
    await db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    await db.delete(document)
    await db.commit()
