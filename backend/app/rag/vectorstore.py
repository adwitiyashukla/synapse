import logging
from abc import ABC, abstractmethod

import numpy as np

from app.config import get_settings

logger = logging.getLogger("synapse.rag.vectorstore")


class VectorStore(ABC):
    @abstractmethod
    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None: ...

    @abstractmethod
    def query(
        self, embedding: list[float], user_id: int, top_k: int
    ) -> list[tuple[str, float]]: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_dir: str) -> None:
        import chromadb

        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="synapse_chunks", metadata={"hnsw:space": "cosine"}
        )

    def add(self, ids, embeddings, metadatas) -> None:
        if not ids:
            return
        self.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def query(self, embedding, user_id, top_k) -> list[tuple[str, float]]:
        if self.collection.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"user_id": user_id},
        )
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [(cid, 1.0 - dist) for cid, dist in zip(ids, distances, strict=True)]

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})


class MemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._vectors: dict[str, np.ndarray] = {}
        self._meta: dict[str, dict] = {}

    def add(self, ids, embeddings, metadatas) -> None:
        for cid, emb, meta in zip(ids, embeddings, metadatas, strict=True):
            vector = np.asarray(emb, dtype=np.float32)
            norm = np.linalg.norm(vector)
            self._vectors[cid] = vector / norm if norm > 0 else vector
            self._meta[cid] = meta

    def query(self, embedding, user_id, top_k) -> list[tuple[str, float]]:
        candidates = [
            (cid, vec)
            for cid, vec in self._vectors.items()
            if self._meta.get(cid, {}).get("user_id") == user_id
        ]
        if not candidates:
            return []
        query_vec = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm
        scored = [(cid, float(np.dot(vec, query_vec))) for cid, vec in candidates]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def delete_document(self, document_id: str) -> None:
        doomed = [
            cid
            for cid, meta in self._meta.items()
            if meta.get("document_id") == document_id
        ]
        for cid in doomed:
            self._vectors.pop(cid, None)
            self._meta.pop(cid, None)


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        settings = get_settings()
        if settings.vector_store == "chroma":
            try:
                _store = ChromaVectorStore(settings.chroma_dir)
            except Exception as exc:
                logger.warning("ChromaDB unavailable (%s); using in-memory store", exc)
                _store = MemoryVectorStore()
        else:
            _store = MemoryVectorStore()
    return _store


def set_vector_store(store: VectorStore | None) -> None:
    global _store
    _store = store
