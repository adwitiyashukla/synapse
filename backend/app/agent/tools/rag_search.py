import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.retriever import retrieve


async def run(db: AsyncSession, user_id: int, query: str) -> str:
    chunks = await retrieve(db, user_id, query)
    if not chunks:
        return json.dumps(
            {"results": [], "note": "No relevant passages found in the user's documents."}
        )
    results = [
        {
            "source": chunk.filename,
            "chunk_id": chunk.chunk_id,
            "excerpt": chunk.text,
        }
        for chunk in chunks
    ]
    payload = {
        "results": results,
        "instruction": "Cite sources inline using the source filename when you use these excerpts.",
    }
    return json.dumps(payload, ensure_ascii=False)
