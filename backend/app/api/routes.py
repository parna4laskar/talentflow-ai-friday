"""REST + SSE API for the React UI. Data access goes through MCP using the caller's role."""
from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app import mcp_client
from app.agents import graph as agent_graph
from app.agents.events import AGENTS, bus
from app.api.deps import Principal, authenticate, current_user, decode_token, issue_token, require_roles
from app.core import llm
from app.guardrails.checks import input_guardrail
from app.ml import outcome_model
from app.services import assistant, career, insights
from app.storage import cache, document, files, graph as graph_store, vector
from app.storage.relational import AuditLog, MatchResult, MatchRun, audit, session

router = APIRouter(prefix="/api")
MANAGERS = ("hiring_manager", "hr_admin")


async def mcp(user: Principal, server: str, tool: str, args: dict | None = None):
    try:
        return await mcp_client.call(server, tool, args or {}, role=user.role, user=user.mcp_user)
    except mcp_client.MCPError as exc:
        code = 403 if "not permitted" in str(exc) else 502
        raise HTTPException(code, str(exc)) from exc


# ------------------------------------------------------------------ auth
class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn):
    p = authenticate(body.username, body.password)
    if not p:
        raise HTTPException(401, "Invalid credentials")
    audit(p.username, "login", p.role)
    return {"token": issue_token(p), "user": p.model_dump()}


@router.get("/auth/me")
def me(user: Principal = Depends(current_user)):
    return user.model_dump()


# ------------------------------------------------------------------ jobs
class JobIn(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=40)
    role_family: str
    level: str
    department: str
    city: str
    country: str
    region: str
    work_mode: str = "Hybrid"
    required_skills: list[dict]
    nice_to_have_skills: list[str] = []
    start_date: str | None = None
    min_years_experience: int = 0
    relocation_supported: bool = False
    priority: str = "Medium"
    openings: int = 1
    auto_match: bool = True


class PrecheckIn(BaseModel):
    title: str = ""
    description: str


@router.get("/jobs")
async def list_jobs(status: str | None = None, mine: bool = False, user: Principal = Depends(current_user)):
    args = {"status": status, "limit": 200}
    if mine and user.employee_id:
        args["hiring_manager_id"] = user.employee_id
    return await mcp(user, "jobs", "list_jobs", args)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: Principal = Depends(current_user)):
    return await mcp(user, "jobs", "get_job", {"job_id": job_id})


@router.get("/jobs/{job_id}/applications")
async def job_applications(job_id: str, user: Principal = Depends(require_roles(*MANAGERS, "leadership"))):
    return await mcp(user, "jobs", "list_applications", {"job_id": job_id})


@router.post("/jobs/precheck")
def precheck(body: PrecheckIn, user: Principal = Depends(current_user)):
    g = input_guardrail(f"{body.title}\n{body.description}")
    return {"decision": g["decision"], "inclusive_language": g["inclusive_language"], "injection": g["injection"], "pii_redacted": g["pii_redacted"]}


@router.post("/jobs")
async def create_job(body: JobIn, user: Principal = Depends(require_roles(*MANAGERS))):
    g = input_guardrail(f"{body.title}\n{body.description}")
    if g["decision"] == "block":
        raise HTTPException(422, {"message": "Job post blocked by guardrail", "guardrail": g["injection"]})
    args = body.model_dump(exclude={"auto_match"})
    args.update(hiring_manager_id=user.employee_id or "", hiring_manager_name=user.display_name,
                start_date=body.start_date or date.today().isoformat())
    created = await mcp(user, "jobs", "create_job", args)
    run_id = agent_graph.start_run(created["created"], user.username) if body.auto_match else None
    return {"job_id": created["created"], "run_id": run_id, "guardrail": {"decision": g["decision"], "findings": g["inclusive_language"]["findings"]}}


@router.get("/catalog/skills")
async def skills_catalog(user: Principal = Depends(current_user)):
    return await mcp(user, "knowledge", "skill_catalog")


# ------------------------------------------------------------------ matching runs
class RunIn(BaseModel):
    job_id: str


class Decision(BaseModel):
    employee_id: str
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str = ""


class ReviewIn(BaseModel):
    decisions: list[Decision]


@router.post("/runs")
async def start_run(body: RunIn, user: Principal = Depends(require_roles(*MANAGERS))):
    return {"run_id": agent_graph.start_run(body.job_id, user.username)}


@router.get("/runs")
def list_runs(job_id: str | None = None, user: Principal = Depends(require_roles(*MANAGERS, "leadership"))):
    with session() as s:
        q = select(MatchRun).order_by(MatchRun.started_at.desc()).limit(50)
        if job_id:
            q = q.where(MatchRun.job_id == job_id)
        return [{"run_id": r.run_id, "job_id": r.job_id, "status": r.status, "started_by": r.started_by,
                 "started_at": r.started_at.isoformat(), "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                 "summary": {k: (r.summary or {}).get(k) for k in ("funnel", "approved", "time_to_shortlist_s", "hidden_fits")}}
                for r in s.execute(q).scalars()]


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user: Principal = Depends(require_roles(*MANAGERS, "leadership"))):
    with session() as s:
        run = s.get(MatchRun, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        results = s.execute(select(MatchResult).where(MatchResult.run_id == run_id).order_by(MatchResult.rank)).scalars().all()
        out = {"run_id": run.run_id, "job_id": run.job_id, "status": run.status, "started_at": run.started_at.isoformat(),
               "summary": run.summary,
               "results": [{"employee_id": r.employee_id, "rank": r.rank, "score": r.score, "explanation": r.explanation,
                            "decision": r.decision, "decision_reason": r.decision_reason, **r.breakdown} for r in results]}
    try:
        st = (await agent_graph.run_state(run_id))["values"]
        out["live"] = {k: st.get(k) for k in ("guardrail", "intent", "requirements", "crew", "swarm", "funnel", "fairness", "trail", "model_update")}
    except Exception:
        out["live"] = None
    return out


@router.post("/runs/{run_id}/review")
async def review(run_id: str, body: ReviewIn, user: Principal = Depends(require_roles(*MANAGERS))):
    missing = [d for d in body.decisions if d.decision == "rejected" and not d.reason.strip()]
    if missing:
        raise HTTPException(422, "Policy: a reason is required for every rejection")
    try:
        await agent_graph.resume_run(run_id, [d.model_dump() for d in body.decisions], user.username)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, token: str = Query(...)):
    decode_token(token)  # EventSource cannot send headers; token passed as query param

    async def gen():
        last = 0
        history = bus.history(run_id) or sorted(document.find("agent_traces", run_id=run_id), key=lambda e: e["seq"])
        for ev in history:
            last = ev["seq"]
            yield {"event": "agent", "data": json.dumps(ev, default=str)}
        q = bus.subscribe(run_id)
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                if ev["seq"] <= last:
                    continue
                last = ev["seq"]
                yield {"event": "agent", "data": json.dumps(ev, default=str)}
        finally:
            bus.unsubscribe(run_id, q)
    return EventSourceResponse(gen())


@router.get("/runs/{run_id}/report")
def run_report(run_id: str, token: str = Query(...)):
    decode_token(token)
    p = files.reports_dir() / f"shortlist_{run_id}.pdf"
    if not p.exists():
        raise HTTPException(404, "report not ready")
    return FileResponse(p, media_type="application/pdf", filename=p.name)


# ------------------------------------------------------------------ employees (HR / managers) via MCP
class SkillIn(BaseModel):
    skill: str
    proficiency: int = Field(ge=1, le=5)
    verified: bool = False


class AvailabilityIn(BaseModel):
    status: str
    available_from: str
    allocation_pct: int = 100


class EmployeeIn(BaseModel):
    full_name: str
    email: str
    title: str
    role_family: str
    department: str
    level: str
    city: str
    country: str
    region: str
    skills: list[dict] = []


@router.get("/employees")
async def employees(q: str = "", department: str | None = None, availability: str | None = None, page: int = 1, page_size: int = 25,
                    user: Principal = Depends(require_roles(*MANAGERS, "leadership"))):
    return await mcp(user, "employee", "list_employees", {"query": q, "department": department, "availability": availability,
                                                          "page": page, "page_size": min(page_size, 100)})


@router.get("/employees/{employee_id}")
async def employee(employee_id: str, user: Principal = Depends(current_user)):
    if user.role == "employee" and user.employee_id != employee_id:
        raise HTTPException(403, "Employees can only view their own profile")
    return await mcp(user, "employee", "get_employee", {"employee_id": employee_id})


@router.post("/employees")
async def create_employee(body: EmployeeIn, user: Principal = Depends(require_roles("hr_admin"))):
    return await mcp(user, "employee", "create_employee", body.model_dump())


@router.put("/employees/{employee_id}/skills")
async def upsert_skill(employee_id: str, body: SkillIn, user: Principal = Depends(current_user)):
    return await mcp(user, "employee", "update_employee_skill", {"employee_id": employee_id, **body.model_dump()})


@router.put("/employees/{employee_id}/availability")
async def set_availability(employee_id: str, body: AvailabilityIn, user: Principal = Depends(require_roles("hr_admin"))):
    return await mcp(user, "employee", "update_availability", {"employee_id": employee_id, **body.model_dump()})


@router.delete("/employees/{employee_id}")
async def deactivate(employee_id: str, user: Principal = Depends(require_roles("hr_admin"))):
    return await mcp(user, "employee", "deactivate_employee", {"employee_id": employee_id})


# ------------------------------------------------------------------ employee career hub
class ApplyIn(BaseModel):
    job_id: str
    cover_note: str = ""


@router.get("/me/matches")
async def my_matches(user: Principal = Depends(require_roles("employee"))):
    return await career.my_matches(user.employee_id)


@router.get("/me/skill-gap/{job_id}")
async def my_skill_gap(job_id: str, user: Principal = Depends(require_roles("employee"))):
    return await career.skill_gap_plan(user.employee_id, job_id)


@router.post("/me/apply")
async def apply(body: ApplyIn, user: Principal = Depends(require_roles("employee"))):
    r = await mcp(user, "jobs", "apply_to_job", {"job_id": body.job_id, "employee_id": user.employee_id, "cover_note": body.cover_note})
    if "error" in r:
        raise HTTPException(409, r["error"])
    return r


# ------------------------------------------------------------------ assistant
class ChatIn(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


@router.post("/assistant/chat")
async def chat(body: ChatIn, user: Principal = Depends(current_user)):
    out = await assistant.chat(body.message, user)
    document.insert("chat_sessions", {"user": user.username, "message": body.message, "intent": out.get("intent"), "ts": time.time()})
    return out


# ------------------------------------------------------------------ insights & governance
@router.get("/insights/overview")
async def overview(user: Principal = Depends(current_user)):
    return await insights.overview()


@router.get("/insights/live")
async def live(token: str = Query(...)):
    """Live platform telemetry stream (real counters) + a simulated marketplace activity feed for the dashboard ticker."""
    decode_token(token)
    rng = random.Random()
    cities = ["Pune", "Bengaluru", "Hyderabad", "London", "Kraków", "New York", "Singapore", "Toronto"]
    skills = ["Python", "Kubernetes", "Generative AI", "SQL", "React", "Terraform", "Data Engineering", "Product Management"]

    async def gen():
        while True:
            ls, cs, ms = llm.stats(), cache.stats(), mcp_client.stats()
            yield {"event": "tick", "data": json.dumps({
                "ts": time.time(),
                "telemetry": {"llm_calls": ls["calls"], "llm_cache_hits": ls["cache_hits"], "llm_fallbacks": ls["fallbacks"],
                              "mcp_calls": ms["calls"], "cache_hit_ratio": cs["hit_ratio"], "avg_mcp_ms": ms["avg_ms"]},
                "activity": {"simulated": True, "applications_per_min": rng.randint(3, 14), "profile_updates_per_min": rng.randint(5, 25),
                             "event": rng.choice([f"New application · {rng.choice(skills)} role · {rng.choice(cities)}",
                                                  f"Skill verified · {rng.choice(skills)}", f"Employee rolling off · {rng.choice(cities)}",
                                                  f"Role posted · {rng.choice(skills)} · {rng.choice(cities)}"])}})}
            await asyncio.sleep(2)
    return EventSourceResponse(gen())


@router.get("/governance")
async def governance(user: Principal = Depends(require_roles("hr_admin", "leadership"))):
    traces = document.find("agent_traces")
    by_type: dict[str, int] = {}
    guard = {"blocked": 0, "warnings": 0, "fallbacks": 0}
    for t in traces:
        by_type[t["type"]] = by_type.get(t["type"], 0) + 1
        if t["agent"] == "guardrail" and t["type"] == "error":
            guard["blocked"] += 1
        if t["type"] == "warning":
            guard["warnings"] += 1
        if t["type"] == "fallback":
            guard["fallbacks"] += 1
    with session() as s:
        runs = s.execute(select(MatchRun).order_by(MatchRun.started_at.desc()).limit(15)).scalars().all()
        fairness = [{"run_id": r.run_id, "job_id": r.job_id, "fairness": (r.summary or {}).get("fairness")} for r in runs if (r.summary or {}).get("fairness")]
        logs = s.execute(select(AuditLog).order_by(AuditLog.ts.desc()).limit(60)).scalars().all()
        audit_rows = [{"ts": a.ts.isoformat(), "actor": a.actor, "action": a.action, "target": a.target, "details": a.details} for a in logs]
    return {
        "llm": llm.stats(), "cache": cache.stats(), "mcp": {**mcp_client.stats(), "servers": await mcp_client.health()},
        "guardrails": guard, "trace_events": by_type, "fairness_runs": fairness, "model_card": outcome_model.card(), "audit": audit_rows,
        "storage": {"relational": "SQLite (talentflow.db)", "vector": {c: vector.count(c) for c in vector.COLLECTIONS},
                    "graph": graph_store.stats(), "files": files.stats(),
                    "nosql": {c: len(document.db(c)) for c in ("profiles", "agent_traces", "feedback", "chat_sessions")}},
    }


@router.get("/governance/traces")
def traces(run_id: str, user: Principal = Depends(require_roles("hr_admin", "leadership", "hiring_manager"))):
    return bus.history(run_id) or document.find("agent_traces", run_id=run_id)


@router.get("/system/architecture")
async def architecture(user: Principal = Depends(current_user)):
    servers = {}
    for s in mcp_client.SERVERS:
        try:
            servers[s] = await mcp_client.list_tools(s)
        except Exception as exc:
            servers[s] = [{"name": "unavailable", "description": str(exc)[:100]}]
    return {"langgraph_mermaid": agent_graph.mermaid(), "agents": [{"id": k, "name": v[0], "framework": v[1]} for k, v in AGENTS.items()],
            "mcp_tools": servers}
