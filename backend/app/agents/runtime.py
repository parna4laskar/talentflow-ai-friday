"""Run-scoped working memory shared by the agents of one matching run.

Large artefacts (candidate pool, per-candidate scores, tool evidence) live here rather than in the
LLM context; agents receive compact summaries and act through tools that read and write this store.
That keeps prompts small and every number grounded in MCP evidence.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class RunContext:
    run_id: str
    job: dict = field(default_factory=dict)
    requirements: dict = field(default_factory=dict)
    pool: dict[str, dict] = field(default_factory=dict)          # employee_id -> public profile
    sources: dict[str, set] = field(default_factory=dict)        # employee_id -> {"skill_search","semantic","applied"}
    applied: set[str] = field(default_factory=set)
    semantic: dict[str, float] = field(default_factory=dict)      # employee_id -> cosine similarity
    neighbors: dict[str, dict[str, float]] = field(default_factory=dict)
    scores: dict[str, dict] = field(default_factory=dict)        # employee_id -> component scores
    evidence: dict[str, object] = field(default_factory=dict)    # tool name -> output summary
    insights: dict[str, str] = field(default_factory=dict)       # agent -> narrative
    tools_run: set[str] = field(default_factory=set)

    def add_candidates(self, people: list[dict], source: str):
        for p in people:
            eid = p["employee_id"]
            self.pool.setdefault(eid, p)
            self.sources.setdefault(eid, set()).add(source)


_RUNS: dict[str, RunContext] = {}
_lock = threading.Lock()


def get(run_id: str) -> RunContext:
    with _lock:
        if run_id not in _RUNS:
            _RUNS[run_id] = RunContext(run_id)
        return _RUNS[run_id]


def drop(run_id: str):
    with _lock:
        _RUNS.pop(run_id, None)
