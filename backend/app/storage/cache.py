"""Caching layer: persistent key/value cache (diskcache) + semantic cache over embeddings.

- `cached(namespace, ttl)` decorator for tool / MCP responses
- `llm_cache_get/set` for exact-prompt LLM response caching
- `SemanticCache` returns a previous answer when a new query is semantically near-identical
"""
from __future__ import annotations

import functools
import hashlib
import json
import threading
from typing import Any, Callable

import diskcache
import numpy as np

from app.core.config import get_settings

_cache: diskcache.Cache | None = None
_lock = threading.Lock()


def cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                _cache = diskcache.Cache(str(get_settings().runtime_dir / "cache"), size_limit=512 * 1024 * 1024)
    return _cache


def bump(name: str, n: int = 1) -> None:
    """Atomic, cross-process persistent counter (governance telemetry survives restarts)."""
    try:
        cache().incr(f"ctr:{name}", n, default=0)
    except Exception:
        pass


def counter(name: str) -> int:
    return int(cache().get(f"ctr:{name}", default=0) or 0)


def make_key(namespace: str, payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return f"{namespace}:{hashlib.sha256(raw.encode()).hexdigest()}"


def get(key: str):
    val = cache().get(key, default=None)
    bump("cache_hits" if val is not None else "cache_misses")
    return val


def set(key: str, value: Any, ttl: int | None = None) -> None:  # noqa: A001 - mirrors cache API
    cache().set(key, value, expire=ttl)


def cached(namespace: str, ttl: int = 300) -> Callable:
    """Decorator caching a function's JSON-serialisable result by its arguments."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = make_key(namespace, {"a": args, "k": kwargs})
            hit = get(key)
            if hit is not None:
                return hit
            out = fn(*args, **kwargs)
            set(key, out, ttl)
            return out
        return wrapper
    return deco


class SemanticCache:
    """Embedding-similarity cache for natural-language queries (e.g. assistant answers)."""

    def __init__(self, namespace: str, threshold: float = 0.94, max_items: int = 500):
        self.ns, self.threshold, self.max_items = namespace, threshold, max_items

    def _load(self) -> list[dict]:
        return cache().get(f"semcache:{self.ns}", default=[])

    def lookup(self, query: str, scope: str = ""):
        from app.ml.embeddings import embed_query
        items = [i for i in self._load() if i["scope"] == scope]
        if not items:
            return None
        q = np.asarray(embed_query(query))
        mat = np.asarray([i["vec"] for i in items])
        sims = mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-9)
        best = int(np.argmax(sims))
        if sims[best] >= self.threshold:
            bump("semantic_hits")
            return {**items[best]["value"], "_cache": {"semantic_similarity": round(float(sims[best]), 3), "matched_query": items[best]["query"]}}
        return None

    def store(self, query: str, value: dict, scope: str = "") -> None:
        from app.ml.embeddings import embed_query
        items = self._load()
        items.append({"query": query, "scope": scope, "vec": list(map(float, embed_query(query))), "value": value})
        cache().set(f"semcache:{self.ns}", items[-self.max_items:])


def stats() -> dict:
    hits, misses = counter("cache_hits"), counter("cache_misses")
    total = hits + misses
    return {"hits": hits, "misses": misses, "semantic_hits": counter("semantic_hits"),
            "hit_ratio": round(hits / total, 3) if total else 0.0, "entries": len(cache())}
