"""TalentFlow AI — FastAPI application entry point.

    uvicorn app.main:app --port 8000      (from backend/)
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("httpx", "mcp.client.streamable_http", "chromadb", "crewai", "LiteLLM"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Reconcile runs on startup: anything not resumable from the checkpointer is marked interrupted."""
    from sqlalchemy import select

    from app.agents import graph as agent_graph
    from app.storage.relational import MatchRun, session
    with session() as s:
        stale = s.execute(select(MatchRun).where(MatchRun.status.in_(["running", "awaiting_review", "finalizing"]))).scalars().all()
        for run in stale:
            st = await agent_graph.run_state(run.run_id)
            if run.status != "awaiting_review" or not st["next"]:
                run.status = "interrupted"
        s.commit()
    yield


app = FastAPI(lifespan=lifespan, title="TalentFlow AI — Internal Talent Marketplace", version="1.0.0",
              description="Agentic matching (LangGraph + CrewAI + Swarm) over MCP employee data.")
app.add_middleware(CORSMiddleware, allow_origins=list(get_settings().cors_origins), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def timing(request: Request, call_next):
    t = time.perf_counter()
    resp = await call_next(request)
    resp.headers["X-Response-Time-ms"] = str(int((time.perf_counter() - t) * 1000))
    return resp


@app.get("/api/health")
async def health():
    from app import mcp_client
    return {"status": "ok", "mcp": await mcp_client.health()}


app.include_router(router)
