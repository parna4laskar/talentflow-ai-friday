"""Front half of the matching graph: input guardrail -> intent -> JD parser -> sourcing crew -> matching swarm."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app import mcp_client
from app.agents import crew as crew_mod
from app.agents import intent as intent_mod
from app.agents import runtime
from app.agents import swarm as swarm_mod
from app.agents.events import Emitter
from app.core import llm
from app.guardrails.checks import input_guardrail


async def guardrail_node(state: dict) -> dict:
    run_id = state["run_id"]
    em = Emitter(run_id, "guardrail")
    em.status("Screening job post: PII, prompt injection, inclusive language")
    tok = mcp_client.tool_call_listener.set(lambda d: em.tool(f"{d['server']} → {d['tool']} ({d['ms']} ms)", d))
    try:
        job = await mcp_client.call("jobs", "get_job", {"job_id": state["job_id"]})
    finally:
        mcp_client.tool_call_listener.reset(tok)
    if "error" in job:
        em("error", job["error"])
        return {"status": "failed", "error": job["error"]}
    ctx = runtime.get(run_id)
    ctx.job = job
    g = input_guardrail(f"{job['title']}\n{job['description']}")
    summary = {"decision": g["decision"], "pii_redacted": g["pii_redacted"], "injection_score": g["injection"]["score"],
               "inclusivity_score": g["inclusive_language"]["inclusivity_score"], "findings": g["inclusive_language"]["findings"]}
    if g["decision"] == "block":
        em("error", "Blocked: prompt-injection / discriminatory instruction detected in job post", summary)
        return {"job": job, "guardrail": summary, "status": "blocked"}
    if g["inclusive_language"]["flagged"]:
        em.warn(f"{len(g['inclusive_language']['findings'])} exclusionary phrase(s) found — suggestions attached for the hiring manager", summary)
    em.result(f"Guardrail {g['decision'].upper()} · inclusivity {summary['inclusivity_score']}/100", summary)
    return {"job": job, "guardrail": summary, "status": "running"}


async def intent_node(state: dict) -> dict:
    em = Emitter(state["run_id"], "intent")
    em.status("Identifying intent of the request")
    job = state["job"]
    out = await intent_mod.classify(f"{job['title']}\n{job['description']}", persona="hiring_manager")
    if out["source"] != "llm":
        em("fallback", "LLM unavailable — keyword intent classifier used", {"reason": out.get("fallback_reason")})
    if out["intent"] not in ("match_talent_for_job", "search_talent"):
        em.warn(f"Intent '{out['intent']}' is unusual for a job post — continuing as job matching (posted via job workflow)")
        out["intent"] = "match_talent_for_job"
    em.result(f"Intent: {out['intent']} (confidence {out['confidence']:.2f})", out)
    return {"intent": out}


class ParsedSkill(BaseModel):
    name: str
    min_proficiency: int = Field(ge=1, le=5, description="1 beginner … 5 expert")
    importance: Literal["must", "nice"]


class ParsedJD(BaseModel):
    skills: list[ParsedSkill]
    min_years: int
    seniority: str
    responsibilities: list[str]
    search_query: str = Field(description="A one-paragraph résumé-style description of the ideal candidate, for semantic search")
    summary: str = Field(description="One-sentence summary of the role")


async def jd_parser_node(state: dict) -> dict:
    run_id, job = state["run_id"], state["job"]
    em = Emitter(run_id, "jd_parser")
    em.status("Parsing unstructured job description into structured requirements")
    structured = {r["name"]: dict(r) for r in job.get("required_skills", [])}
    parsed, source = None, "llm"
    try:
        r = await llm.generate(
            "Extract structured hiring requirements from this internal job post. Use canonical industry skill names.\n\n"
            f"TITLE: {job['title']} ({job['level']})\n\n{job['description']}", tier="primary", schema=ParsedJD,
            system="You are an expert technical recruiter. Only extract what the text supports.")
        parsed = ParsedJD.model_validate(r["data"])
        em.thought(f"LLM ({r['model']}{', cached' if r['cached'] else ''}) extracted {len(parsed.skills)} skills; summary: {parsed.summary}")
    except Exception as exc:
        source = "regex-fallback"
        em("fallback", "LLM unavailable — extracting skills with taxonomy matching", {"reason": str(exc)[:160]})

    tok = mcp_client.tool_call_listener.set(lambda d: em.tool(f"{d['server']} → {d['tool']} ({d['ms']} ms)", d))
    try:
        if parsed:
            norm = await mcp_client.call("knowledge", "normalize_skills", {"terms": [s.name for s in parsed.skills]})
            mapping = {n["term"]: n for n in norm}
            for s in parsed.skills:
                n = mapping.get(s.name)
                if not n or n["confidence"] < 0.45:
                    continue
                if n["skill"] not in structured and s.importance == "must":
                    structured[n["skill"]] = {"name": n["skill"], "min_proficiency": s.min_proficiency, "weight": 0.6, "source": "llm"}
        else:
            catalog = await mcp_client.call("knowledge", "skill_catalog", {})
            text = job["description"].lower()
            for c in catalog:
                if c["name"] not in structured and re.search(rf"(?<![\w]){re.escape(c['name'].lower())}(?![\w])", text) \
                        and c["name"] not in job.get("nice_to_have_skills", []):
                    structured[c["name"]] = {"name": c["name"], "min_proficiency": 3, "weight": 0.6, "source": "regex"}
    finally:
        mcp_client.tool_call_listener.reset(tok)

    req = list(structured.values())[:10]
    requirements = {
        "required_skills": req, "nice_to_have": job.get("nice_to_have_skills", []),
        "min_years": parsed.min_years if parsed else job.get("min_years_experience", 0),
        "seniority": parsed.seniority if parsed else job["level"], "start_date": job["start_date"],
        "summary": parsed.summary if parsed else job["title"],
        "responsibilities": parsed.responsibilities if parsed else [],
        "search_query": parsed.search_query if parsed else f"{job['title']} with " + ", ".join(r["name"] for r in req),
        "source": source,
    }
    runtime.get(run_id).requirements = requirements
    em.result(f"{len(req)} required skills · {len(requirements['nice_to_have'])} nice-to-have · start {job['start_date']}", requirements)
    return {"requirements": requirements}


async def sourcing_crew_node(state: dict) -> dict:
    ctx = runtime.get(state["run_id"])
    out = await crew_mod.run_crew(ctx, state["run_id"])
    return {"crew": {"mode": out["mode"], "pool_size": out["pool_size"], "brief": out["brief"]}}


async def matching_swarm_node(state: dict) -> dict:
    ctx = runtime.get(state["run_id"])
    out = await swarm_mod.run_swarm(ctx, state["run_id"])
    return {"swarm": out}
