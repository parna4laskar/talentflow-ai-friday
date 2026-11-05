"""Grounded sourcing operations (all data via MCP). Used as tools by the CrewAI crew, and run
directly if the LLM is unavailable or an agent skips a tool."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from app import mcp_client
from app.agents.events import Emitter
from app.agents.runtime import RunContext


def _listen(emit: Emitter):
    return mcp_client.tool_call_listener.set(lambda d: emit.tool(f"{d['server']} → {d['tool']} ({d['ms']} ms)", d))


async def skills_search(ctx: RunContext, emit: Emitter) -> dict:
    tok = _listen(emit)
    try:
        req = ctx.requirements
        names = [r["name"] for r in req["required_skills"]]
        res = await mcp_client.call("employee", "search_employees", {"skills": names, "min_proficiency": 1, "limit": 250})
        people = [p for p in res["employees"] if p["employee_id"] != ctx.job.get("hiring_manager_id")]
        ctx.add_candidates(people, "skill_search")
        ctx.tools_run.add("skills_search")
        dist = Counter(p["matched_skill_count"] for p in people)
        out = {"matched_total": res["count"], "added_to_pool": len(people),
               "by_number_of_required_skills_held": dict(sorted(dist.items(), reverse=True)), "required_skills": names}
        ctx.evidence["skills_search"] = out
        return out
    finally:
        mcp_client.tool_call_listener.reset(tok)


async def semantic_search(ctx: RunContext, emit: Emitter) -> dict:
    tok = _listen(emit)
    try:
        query = ctx.requirements.get("search_query") or ctx.job["title"]
        hits = await mcp_client.call("knowledge", "semantic_search_resumes", {"query": query, "k": 150})
        ctx.semantic.update({h["employee_id"]: h["similarity"] for h in hits})
        new_ids = [h["employee_id"] for h in hits if h["employee_id"] not in ctx.pool and h["employee_id"] != ctx.job.get("hiring_manager_id")]
        if new_ids:
            people = await mcp_client.call("employee", "get_employees_batch", {"employee_ids": new_ids})
            ctx.add_candidates(people, "semantic")
        for h in hits:
            if h["employee_id"] in ctx.sources:
                ctx.sources[h["employee_id"]].add("semantic")
        ctx.tools_run.add("semantic_search")
        out = {"semantic_hits": len(hits), "new_candidates_not_found_by_keyword": len(new_ids),
               "top_role_families": Counter(h["role_family"] for h in hits[:40]).most_common(4)}
        ctx.evidence["semantic_search"] = out
        return out
    finally:
        mcp_client.tool_call_listener.reset(tok)


async def applications_screen(ctx: RunContext, emit: Emitter) -> dict:
    tok = _listen(emit)
    try:
        apps = await mcp_client.call("jobs", "list_applications", {"job_id": ctx.job["job_id"]})
        active = [a for a in apps if a["status"] not in ("Withdrawn",)]
        ctx.applied = {a["employee_id"] for a in active}
        missing = [e for e in ctx.applied if e not in ctx.pool]
        if missing:
            people = await mcp_client.call("employee", "get_employees_batch", {"employee_ids": missing})
            ctx.add_candidates(people, "applied")
        for e in ctx.applied:
            if e in ctx.sources:
                ctx.sources[e].add("applied")
        ctx.tools_run.add("applications_screen")
        out = {"applications": len(apps), "active": len(active), "sources": dict(Counter(a["source"] for a in apps)),
               "sample_cover_notes": [a["cover_note"] for a in active[:3]]}
        ctx.evidence["applications_screen"] = out
        return out
    finally:
        mcp_client.tool_call_listener.reset(tok)


async def market_scan(ctx: RunContext, emit: Emitter) -> dict:
    tok = _listen(emit)
    try:
        names = [r["name"] for r in ctx.requirements["required_skills"]]
        intel = {}
        for n in names[:3]:
            r = await mcp_client.call("knowledge", "market_intel", {"skill": n})
            intel[n] = [x["snippet"] for x in r.get("results", [])[:2]]
        for n in names:
            nb = await mcp_client.call("knowledge", "skill_graph_neighbors", {"skill": n, "min_weight": 0.4})
            ctx.neighbors[n] = {x["skill"]: x["weight"] for x in nb}
        ctx.tools_run.add("market_scan")
        out = {"market_signals": intel,
               "adjacent_skills": {k: sorted(v, key=v.get, reverse=True)[:4] for k, v in ctx.neighbors.items()}}
        ctx.evidence["market_scan"] = out
        return out
    finally:
        mcp_client.tool_call_listener.reset(tok)


async def availability_scan(ctx: RunContext, emit: Emitter) -> dict:
    start = date.fromisoformat(ctx.requirements.get("start_date") or ctx.job["start_date"])
    pool = list(ctx.pool.values())
    ready = sum(1 for p in pool if date.fromisoformat(p["availability"]["available_from"]) <= start)
    soon = sum(1 for p in pool if start < date.fromisoformat(p["availability"]["available_from"]) <= start + timedelta(days=45))
    loc = ctx.job["location"]
    same_city = sum(1 for p in pool if p["city"] == loc["city"])
    same_region = sum(1 for p in pool if p["region"] == loc["region"])
    reloc = sum(1 for p in pool if p["willing_to_relocate"])
    ctx.tools_run.add("availability_scan")
    out = {"pool_size": len(pool), "available_by_start": ready, "available_within_45_days_of_start": soon,
           "same_city": same_city, "same_region": same_region, "open_to_relocation": reloc,
           "status_mix": dict(Counter(p["availability"]["status"] for p in pool)), "job_location": loc,
           "work_mode": ctx.job["work_mode"], "start_date": start.isoformat()}
    ctx.evidence["availability_scan"] = out
    return out


ALL = {"skills_search": skills_search, "semantic_search": semantic_search, "applications_screen": applications_screen,
       "market_scan": market_scan, "availability_scan": availability_scan}
