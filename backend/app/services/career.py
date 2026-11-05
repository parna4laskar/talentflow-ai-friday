"""Employee-side intelligence: reverse matching (open roles ranked for me), skill gaps and learning paths."""
from __future__ import annotations

import asyncio

from app import mcp_client
from app.agents import scoring
from app.ml import outcome_model

_NEIGHBORS: dict[str, dict[str, float]] = {}


async def neighbors_for(skills: set[str]) -> dict[str, dict[str, float]]:
    missing = [s for s in skills if s not in _NEIGHBORS]
    results = await asyncio.gather(*[mcp_client.call("knowledge", "skill_graph_neighbors", {"skill": s, "min_weight": 0.4})
                                     for s in missing], return_exceptions=True)
    for s, r in zip(missing, results):
        _NEIGHBORS[s] = {} if isinstance(r, Exception) else {x["skill"]: x["weight"] for x in r}
    return {s: _NEIGHBORS.get(s, {}) for s in skills}


async def my_matches(employee_id: str, limit: int = 12) -> dict:
    me, jobs, apps = await asyncio.gather(
        mcp_client.call("employee", "get_employee", {"employee_id": employee_id}, role="employee", user=employee_id),
        mcp_client.call("jobs", "list_jobs", {"status": "Open", "limit": 200}),
        mcp_client.call("jobs", "list_jobs", {"status": "In Review", "limit": 200}))
    jobs = jobs + apps
    nb = await neighbors_for({r["name"] for j in jobs for r in j["required_skills"]})
    my_skills = {s["name"] for s in me["skills"]}
    rows = []
    for j in jobs:
        if j["hiring_manager_id"] == employee_id:
            continue
        sf = scoring.skill_fit(me, j["required_skills"], j.get("nice_to_have_skills", []))
        adj = scoring.adjacency_score(sf["gaps"], nb, my_skills)
        av = scoring.availability_fit(me, j["start_date"])
        loc = scoring.location_fit(me, j)
        it = scoring.interest_signal(me, j, set())
        rows.append((j, sf, adj, av, loc, it, scoring.ml_features(me, j, sf, adj, av, loc, set())))
    probs = outcome_model.predict([r[6] for r in rows])
    out = []
    for (j, sf, adj, av, loc, it, _), p in zip(rows, probs):
        parts = {"skill": sf["score"], "adjacency": adj["score"], "availability": av["score"], "location": loc["score"],
                 "interest": it["score"], "success": p}
        out.append({"job": j, "score": scoring.combine(parts), "components": {k: round(v, 3) for k, v in parts.items()},
                    "gaps": sf["gaps"], "strengths": sf["strengths"], "bridges": adj["bridges"], "location": loc["reason"],
                    "availability": av, "level_ok": scoring.level_ok(me, j)})
    out.sort(key=lambda r: (-r["level_ok"], -r["score"]))
    return {"employee": me, "matches": out[:limit]}


async def skill_gap_plan(employee_id: str, job_id: str) -> dict:
    me, job = await asyncio.gather(
        mcp_client.call("employee", "get_employee", {"employee_id": employee_id}, role="employee", user=employee_id),
        mcp_client.call("jobs", "get_job", {"job_id": job_id}))
    sf = scoring.skill_fit(me, job["required_skills"], job.get("nice_to_have_skills", []))
    plan = []
    for g in sf["gaps"]:
        adj = await mcp_client.call("knowledge", "skill_adjacency", {"candidate_skills": [s["name"] for s in me["skills"]], "target_skill": g["skill"]})
        weeks = 4 + 3 * (g["need"] - g["have"]) - int(6 * adj["transfer_weight"])
        plan.append({**g, "via": adj["via"], "transfer_weight": adj["transfer_weight"], "path": adj["path"], "estimated_weeks": max(2, weeks)})
    intel = await mcp_client.call("knowledge", "market_intel", {"skill": plan[0]["skill"]}) if plan else None
    return {"job": {k: job[k] for k in ("job_id", "title", "level", "location", "work_mode", "start_date")}, "coverage": sf["coverage"],
            "strengths": sf["strengths"], "plan": plan, "market_signal": intel["results"][0]["snippet"] if intel and intel.get("results") else None}
