"""Run-scoped event bus: every agent thought, tool call, handoff and metric is published here,
streamed to the UI over SSE (Live Agent Theater) and persisted to the NoSQL trace store."""
from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict
from typing import Any

from app.storage import document

AGENTS = {
    "guardrail": ("Input Guardrail", "LangGraph"), "intent": ("Intent Agent", "LangGraph"), "jd_parser": ("JD Parser", "LangGraph"),
    "crew_manager": ("Crew Manager", "CrewAI"), "skills_analyst": ("Skills Analyst", "CrewAI"),
    "availability_analyst": ("Availability & Location Analyst", "CrewAI"), "applications_screener": ("Applications Screener", "CrewAI"),
    "market_intel": ("Market Intel Agent", "CrewAI"), "skill_matcher": ("Skill Matcher", "Swarm"),
    "hidden_fit_finder": ("Hidden-Fit Finder", "Swarm"), "mobility_matcher": ("Mobility Matcher", "Swarm"),
    "ranker": ("Ranker", "LangGraph"), "fairness_auditor": ("Fairness Auditor", "Responsible AI"),
    "explainer": ("Explainer", "LangGraph"), "hitl": ("Human Review", "LangGraph"),
    "feedback_learner": ("Feedback Learner", "ML"), "report": ("Report Agent", "LangGraph"),
}


class EventBus:
    def __init__(self):
        self._events: dict[str, list[dict]] = defaultdict(list)
        self._subs: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = defaultdict(list)
        self._lock = threading.Lock()

    def publish(self, run_id: str, agent: str, type_: str, message: str, data: Any = None) -> dict:
        name, framework = AGENTS.get(agent, (agent, ""))
        with self._lock:
            ev = {"run_id": run_id, "seq": len(self._events[run_id]) + 1, "ts": time.time(), "agent": agent, "agent_name": name,
                  "framework": framework, "type": type_, "message": message, "data": data}
            self._events[run_id].append(ev)
            subs = list(self._subs[run_id])
        for loop, q in subs:
            try:
                loop.call_soon_threadsafe(q.put_nowait, ev)
            except RuntimeError:
                pass
        if type_ in ("result", "handoff", "tool_call", "warning", "error", "interrupt", "done", "fallback"):
            try:
                document.insert("agent_traces", {k: v for k, v in ev.items() if k != "data"} | {"data": _trim(data)})
            except Exception:
                pass
        return ev

    def history(self, run_id: str, after: int = 0) -> list[dict]:
        return [e for e in self._events.get(run_id, []) if e["seq"] > after]

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subs[run_id].append((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue):
        with self._lock:
            self._subs[run_id] = [(lp, x) for lp, x in self._subs[run_id] if x is not q]


def _trim(data: Any, limit: int = 4000):
    import json
    try:
        s = json.dumps(data, default=str)
        return data if len(s) <= limit else {"truncated": s[:limit]}
    except Exception:
        return str(data)[:limit]


bus = EventBus()


class Emitter:
    """Convenience wrapper bound to one run and one agent."""

    def __init__(self, run_id: str, agent: str):
        self.run_id, self.agent = run_id, agent

    def __call__(self, type_: str, message: str, data: Any = None):
        return bus.publish(self.run_id, self.agent, type_, message, data)

    def status(self, msg, data=None):
        return self("status", msg, data)

    def thought(self, msg, data=None):
        return self("thought", msg, data)

    def result(self, msg, data=None):
        return self("result", msg, data)

    def metric(self, msg, data=None):
        return self("metric", msg, data)

    def tool(self, msg, data=None):
        return self("tool_call", msg, data)

    def warn(self, msg, data=None):
        return self("warning", msg, data)
