"""NoSQL document store (TinyDB, one JSON file per collection; swap for MongoDB in production).

Collections:
  profiles      full nested employee documents (projects, career interests, parsed résumé)
  agent_traces  every agent step / tool call / handoff of a matching run (replayable)
  feedback      hiring-manager approve/reject decisions used to retrain the outcome model
  chat_sessions employee career-assistant conversations
"""
from __future__ import annotations

import threading
from pathlib import Path

from tinydb import Query, TinyDB
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

from app.core.config import get_settings

_dbs: dict[str, TinyDB] = {}
_lock = threading.RLock()
_index: dict[str, tuple[float, dict]] = {}


def _path(collection: str) -> Path:
    d = get_settings().runtime_dir / "nosql"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{collection}.json"


def db(collection: str) -> TinyDB:
    with _lock:
        if collection not in _dbs:
            storage = CachingMiddleware(JSONStorage) if collection == "profiles" else JSONStorage
            _dbs[collection] = TinyDB(_path(collection), storage=storage, ensure_ascii=False, encoding="utf-8")
        return _dbs[collection]


def insert(collection: str, doc: dict) -> int:
    with _lock:
        return db(collection).insert(doc)


def insert_many(collection: str, docs: list[dict]) -> None:
    with _lock:
        db(collection).insert_multiple(docs)
        if isinstance(db(collection).storage, CachingMiddleware):
            db(collection).storage.flush()


def find(collection: str, **eq) -> list[dict]:
    q = Query()
    cond = None
    for k, v in eq.items():
        c = q[k] == v
        cond = c if cond is None else cond & c
    with _lock:
        return db(collection).search(cond) if cond is not None else db(collection).all()


def upsert(collection: str, key: str, value, doc: dict) -> None:
    with _lock:
        db(collection).upsert(doc, Query()[key] == value)
        if isinstance(db(collection).storage, CachingMiddleware):
            db(collection).storage.flush()


def truncate(collection: str) -> None:
    with _lock:
        db(collection).truncate()


def get_profile(employee_id: str) -> dict | None:
    """Fast keyed lookup with an mtime-aware in-memory index (safe across processes)."""
    p = _path("profiles")
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    cached = _index.get("profiles")
    if cached is None or cached[0] != mtime:
        with _lock:
            if "profiles" in _dbs:
                _dbs.pop("profiles").close()
            idx = {d["employee_id"]: d for d in db("profiles").all()}
            _index["profiles"] = (mtime, idx)
    return _index["profiles"][1].get(employee_id)
