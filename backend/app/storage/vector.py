"""Vector store (ChromaDB, persistent, cosine space).

Collections: resumes, jobs, skills, policies.
"""
from __future__ import annotations

import threading

import chromadb

from app.core.config import get_settings
from app.ml.embeddings import embed_documents, embed_query

_client = None
_lock = threading.Lock()
COLLECTIONS = ("resumes", "jobs", "skills", "policies")


def client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = chromadb.PersistentClient(path=str(get_settings().runtime_dir / "vector"))
    return _client


def collection(name: str):
    return client().get_or_create_collection(name, metadata={"hnsw:space": "cosine"}, embedding_function=None)


def reset(name: str):
    try:
        client().delete_collection(name)
    except Exception:
        pass
    return collection(name)


def upsert(name: str, ids: list[str], texts: list[str], metadatas: list[dict], batch: int = 256):
    col = collection(name)
    for i in range(0, len(ids), batch):
        sl = slice(i, i + batch)
        col.upsert(ids=ids[sl], documents=texts[sl], metadatas=metadatas[sl], embeddings=embed_documents(texts[sl]))


def search(name: str, query: str, k: int = 10, where: dict | None = None) -> list[dict]:
    res = collection(name).query(query_embeddings=[embed_query(query)], n_results=k, where=where or None,
                                 include=["documents", "metadatas", "distances"])
    out = []
    for i, _id in enumerate(res["ids"][0]):
        out.append({"id": _id, "score": round(1 - res["distances"][0][i], 4), "text": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i]})
    return out


def similarity_for_ids(name: str, query: str, ids: list[str]) -> dict[str, float]:
    """Cosine similarity between a query and a specific set of stored documents."""
    import numpy as np
    if not ids:
        return {}
    got = collection(name).get(ids=ids, include=["embeddings"])
    q = np.asarray(embed_query(query))
    out = {}
    for _id, emb in zip(got["ids"], got["embeddings"]):
        e = np.asarray(emb)
        out[_id] = float(e @ q / (np.linalg.norm(e) * np.linalg.norm(q) + 1e-9))
    return out


def count(name: str) -> int:
    return collection(name).count()
