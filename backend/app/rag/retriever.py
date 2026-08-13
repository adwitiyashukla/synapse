import json
import logging
import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.llm.registry import get_provider
from app.models import Chunk, Document
from app.rag.vectorstore import get_vector_store

logger = logging.getLogger("synapse.rag.retriever")

RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    text: str
    score: float


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


async def retrieve(
    db: AsyncSession, user_id: int, query: str
) -> list[RetrievedChunk]:
    settings = get_settings()
    provider = get_provider()

    rows = (
        (
            await db.execute(
                select(Chunk, Document.filename)
                .join(Document, Chunk.document_id == Document.id)
                .where(Chunk.user_id == user_id, Document.status == "ready")
            )
        )
        .all()
    )
    if not rows:
        return []
    chunk_map: dict[str, tuple[Chunk, str]] = {row[0].id: (row[0], row[1]) for row in rows}

    dense_ids: list[str] = []
    try:
        [query_embedding] = await provider.embed([query])
        dense_hits = get_vector_store().query(
            query_embedding, user_id=user_id, top_k=settings.dense_top_k
        )
        dense_ids = [cid for cid, _ in dense_hits if cid in chunk_map]
    except Exception as exc:
        logger.warning("dense retrieval failed, falling back to BM25 only: %s", exc)

    ordered_ids = list(chunk_map.keys())
    corpus = [_tokenize(chunk_map[cid][0].text) for cid in ordered_ids]
    bm25 = BM25Okapi(corpus)
    bm25_scores = bm25.get_scores(_tokenize(query))
    bm25_ranked = sorted(
        zip(ordered_ids, bm25_scores, strict=True), key=lambda pair: pair[1], reverse=True
    )
    bm25_ids = [cid for cid, score in bm25_ranked[: settings.bm25_top_k] if score > 0]

    fused = rrf_fuse([ranking for ranking in (dense_ids, bm25_ids) if ranking])
    top_ids = [cid for cid, _ in fused[: settings.fused_top_k]]
    if not top_ids:
        return []

    candidates = [
        RetrievedChunk(
            chunk_id=cid,
            document_id=chunk_map[cid][0].document_id,
            filename=chunk_map[cid][1],
            chunk_index=chunk_map[cid][0].chunk_index,
            text=chunk_map[cid][0].text,
            score=round(score, 6),
        )
        for cid, score in fused[: settings.fused_top_k]
    ]

    if settings.rerank_enabled and len(candidates) > settings.final_top_k:
        candidates = await _rerank(query, candidates, settings.final_top_k)
    return candidates[: settings.final_top_k]


async def _rerank(
    query: str, candidates: list[RetrievedChunk], top_k: int
) -> list[RetrievedChunk]:
    settings = get_settings()
    provider = get_provider()
    listing = "\n\n".join(
        f"[{i}] (from {c.filename})\n{c.text[:600]}" for i, c in enumerate(candidates)
    )
    prompt = (
        "You are a retrieval reranker. Given a query and numbered passages, "
        "return a JSON array of passage indices ordered from most to least "
        f"relevant. Return at most {top_k} indices and nothing else.\n\n"
        f"Query: {query}\n\nPassages:\n{listing}"
    )
    try:
        raw = await provider.complete(
            [{"role": "user", "content": prompt}],
            model=settings.utility_model,
            temperature=0.0,
        )
        match = re.search(r"\[[\d,\s]*\]", raw)
        if not match:
            return candidates
        order = [
            i for i in json.loads(match.group(0))
            if isinstance(i, int) and 0 <= i < len(candidates)
        ]
        if not order:
            return candidates
        seen = set(order)
        remainder = [i for i in range(len(candidates)) if i not in seen]
        return [candidates[i] for i in order + remainder]
    except Exception as exc:
        logger.warning("rerank failed, using fused order: %s", exc)
        return candidates
