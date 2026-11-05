"""Embedding model: all-MiniLM-L6-v2 (384-d) running locally on ONNX Runtime.

Runs offline and has no API quota, so 3,000+ résumés can be indexed in seconds.
Query embeddings are cached.
"""
from __future__ import annotations

import functools
import threading

import numpy as np

_ef = None
_lock = threading.Lock()
MODEL_NAME = "all-MiniLM-L6-v2 (ONNX)"


def _model():
    global _ef
    if _ef is None:
        with _lock:
            if _ef is None:
                from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
                _ef = DefaultEmbeddingFunction()
    return _ef


def embed_documents(texts: list[str], batch: int = 128) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        out.extend([list(map(float, v)) for v in _model()(texts[i:i + batch])])
    return out


@functools.lru_cache(maxsize=4096)
def _embed_query_cached(text: str) -> tuple[float, ...]:
    return tuple(float(x) for x in _model()([text])[0])


def embed_query(text: str) -> list[float]:
    return list(_embed_query_cached(text.strip()[:2000]))


def cosine(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
