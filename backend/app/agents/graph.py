"""LangGraph supervisor: the end-to-end, checkpointed matching workflow.

guardrail ─┬─(blocked)──────────────────────────────────────────────► END
           └► intent ► jd_parser ► sourcing_crew (CrewAI) ► matching_swarm (Swarm)
                 ► ranker ⇄ fairness_auditor (re-balance loop) ► explainer
                 ► human_review (interrupt) ► feedback_learner ► report ► END
"""
from __future__ import annotations

import asyncio
import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents import runtime
from app.agents.events import Emitter, bus
from app.agents.nodes import back, front
from app.core.config import get_settings
from app.storage.relational import MatchRun, audit, session


class TalentState(TypedDict, total=False):
    run_id: str
    job_id: str
    actor: str
    status: str
    error: str
    job: dict
    guardrail: dict
    intent: dict
    requirements: dict
    crew: dict
    swarm: dict
    ranked: list
    shortlist: list
    funnel: dict
    fairness: dict
    fairness_iterations: int
    rerank_request: Any
    cards: list
    decisions: list
    reviewer: str
    model_update: Any
    report: dict
    trail: Annotated[list, operator.add]


def _traced(name, fn):
    async def wrapper(state):
        out = await fn(state)
        return {**(out or {}), "trail": [name]}
    return wrapper


def build_graph(checkpointer=None):
    g = StateGraph(TalentState)
    nodes = {"guardrail": front.guardrail_node, "intent": front.intent_node, "jd_parser": front.jd_parser_node,
             "sourcing_crew": front.sourcing_crew_node, "matching_swarm": front.matching_swarm_node,
             "ranker": back.ranker_node, "fairness_auditor": back.fairness_node, "explainer": back.explainer_node,
             "human_review": back.hitl_node, "feedback_learner": back.feedback_node, "report": back.report_node}
    for name, fn in nodes.items():
        g.add_node(name, _traced(name, fn))
    g.add_edge(START, "guardrail")
    g.add_conditional_edges("guardrail", lambda s: END if s.get("status") in ("blocked", "failed") else "intent", ["intent", END])
    g.add_edge("intent", "jd_parser")
    g.add_edge("jd_parser", "sourcing_crew")
    g.add_edge("sourcing_crew", "matching_swarm")
    g.add_edge("matching_swarm", "ranker")
    g.add_edge("ranker", "fairness_auditor")
    g.add_conditional_edges("fairness_auditor", back.route_after_fairness, ["ranker", "explainer"])
    g.add_edge("explainer", "human_review")
    g.add_edge("human_review", "feedback_learner")
    g.add_edge("feedback_learner", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)


_GRAPH = None
_GRAPH_LOCK = asyncio.Lock()
_TASKS: dict[str, asyncio.Task] = {}


async def graph():
    """Compiled graph with a persistent SQLite checkpointer: runs awaiting human review survive API restarts."""
    global _GRAPH
    async with _GRAPH_LOCK:
        if _GRAPH is None:
            import aiosqlite
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            conn = await aiosqlite.connect(str(get_settings().runtime_dir / "checkpoints.db"))
            saver = AsyncSqliteSaver(conn)
            await saver.setup()
            _GRAPH = build_graph(saver)
    return _GRAPH


def mermaid() -> str:
    return build_graph().get_graph().draw_mermaid()


def _set_status(run_id: str, status: str, **summary):
    with session() as s:
        run = s.get(MatchRun, run_id)
        if run:
            run.status = status
            if summary:
                run.summary = {**(run.summary or {}), **summary}
            if status in ("completed", "failed", "blocked"):
                run.finished_at = datetime.now(timezone.utc)
        s.commit()


async def _drive(run_id: str, payload: Any):
    cfg = {"configurable": {"thread_id": run_id}, "recursion_limit": 40}
    try:
        g = await graph()
        async for _ in g.astream(payload, cfg, stream_mode="updates"):
            pass
        snap = await g.aget_state(cfg)
        if snap.next:
            _set_status(run_id, "awaiting_review")
        else:
            st = snap.values.get("status")
            if st in ("blocked", "failed"):
                _set_status(run_id, st, error=snap.values.get("error"), guardrail=snap.values.get("guardrail"))
                bus.publish(run_id, "guardrail", "done", f"Run ended: {st}")
    except Exception as exc:  # surface any unexpected failure to the UI
        Emitter(run_id, "report")("error", f"Run failed: {type(exc).__name__}: {exc}")
        _set_status(run_id, "failed", error=str(exc)[:500])
        raise


def start_run(job_id: str, actor: str) -> str:
    run_id = f"run-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    with session() as s:
        s.add(MatchRun(run_id=run_id, job_id=job_id, status="running", started_by=actor, summary={}))
        s.commit()
    audit(actor, "start_matching_run", job_id, run_id=run_id)
    runtime.get(run_id)
    bus.publish(run_id, "guardrail", "status", f"Run {run_id} started for {job_id}")
    _TASKS[run_id] = asyncio.create_task(_drive(run_id, {"run_id": run_id, "job_id": job_id, "actor": actor, "trail": []}))
    return run_id


async def resume_run(run_id: str, decisions: list[dict], reviewer: str) -> None:
    cfg = {"configurable": {"thread_id": run_id}}
    snap = await (await graph()).aget_state(cfg)
    if not snap.next:
        raise ValueError("run is not awaiting review")
    audit(reviewer, "review_shortlist", run_id, approved=sum(d["decision"] == "approved" for d in decisions))
    _set_status(run_id, "finalizing")
    _TASKS[run_id] = asyncio.create_task(_drive(run_id, Command(resume={"decisions": decisions, "reviewer": reviewer})))


async def run_state(run_id: str) -> dict:
    snap = await (await graph()).aget_state({"configurable": {"thread_id": run_id}})
    v = dict(snap.values or {})
    v.pop("ranked", None)
    return {"next": list(snap.next or []), "values": v}
