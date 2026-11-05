"""CrewAI Talent Sourcing Crew.

Four role-based agents work in parallel (async tasks), then the Availability & Location
Analyst writes the sourcing brief using the others' outputs as context:
  Skills Analyst          -> employee-mcp search_employees + knowledge-mcp semantic résumé search
  Applications Screener   -> jobs-mcp list_applications (who applied, cover notes)
  Market Intel Agent      -> Google Search (cached) + skills-graph neighbours
  Availability Analyst    -> pool availability / location analysis -> sourcing brief
"""
from __future__ import annotations

import asyncio
import json
import os
import time

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

from pydantic import BaseModel, Field  # noqa: E402

from app.agents import sourcing_tools as st  # noqa: E402
from app.agents.events import Emitter  # noqa: E402
from app.agents.runtime import RunContext  # noqa: E402
from app.core import llm  # noqa: E402

CREW_TIMEOUT_S = 75


class _NoArgs(BaseModel):
    note: str = Field(default="", description="Optional note; the tool already knows the job requirements.")


def _make_tool(name: str, description: str, fn, ctx: RunContext, emit: Emitter, op: str):
    from crewai.tools import BaseTool

    class _Tool(BaseTool):
        args_schema: type[BaseModel] = _NoArgs

        def _run(self, note: str = "") -> str:
            if op in ctx.tools_run and op in ctx.evidence:  # idempotent on agent retries
                return json.dumps(ctx.evidence[op], default=str)[:3500]
            emit.thought(f"Using tool `{name}`")
            out = asyncio.run(fn(ctx, emit))
            emit.result(f"{name} complete", out)
            return json.dumps(out, default=str)[:3500]

    return _Tool(name=name, description=description)


def _brief_context(ctx: RunContext) -> str:
    r = ctx.requirements
    return json.dumps({"job_title": ctx.job["title"], "level": ctx.job["level"], "location": ctx.job["location"],
                       "work_mode": ctx.job["work_mode"], "start_date": r.get("start_date"),
                       "required_skills": [f"{s['name']} (≥{s['min_proficiency']}/5)" for s in r["required_skills"]],
                       "nice_to_have": r.get("nice_to_have", [])})


def build_crew(ctx: RunContext, run_id: str, models: list[str]):
    from crewai import Agent, Crew, Process, Task

    em = {k: Emitter(run_id, k) for k in ("skills_analyst", "applications_screener", "market_intel", "availability_analyst", "crew_manager")}
    job = _brief_context(ctx)

    skills = Agent(role="Skills Analyst", goal="Build the widest relevant internal candidate pool for the role from skills data.",
                   backstory="You know the company skills taxonomy and use exact-skill search plus semantic résumé search to avoid missing anyone.",
                   tools=[_make_tool("skills_search", "Search employees holding the role's required skills via employee-mcp.", st.skills_search, ctx, em["skills_analyst"], "skills_search"),
                          _make_tool("semantic_resume_search", "Semantic search over résumés via knowledge-mcp to find candidates keyword search misses.", st.semantic_search, ctx, em["skills_analyst"], "semantic_search")],
                   llm=llm.crew_llm(models[0]), max_iter=4, allow_delegation=False, verbose=False, max_retry_limit=1)
    screener = Agent(role="Applications Screener", goal="Identify who has applied and what their cover notes signal about motivation.",
                     backstory="You make sure every employee who raised their hand is considered fairly.",
                     tools=[_make_tool("list_applications", "List applications for this job via jobs-mcp.", st.applications_screen, ctx, em["applications_screener"], "applications_screen")],
                     llm=llm.crew_llm(models[1]), max_iter=3, allow_delegation=False, verbose=False, max_retry_limit=1)
    market = Agent(role="Market Intel Agent", goal="Assess external demand for the role's skills and which adjacent skills transfer well.",
                   backstory="You track skill trends with Google Search and the internal skills graph.",
                   tools=[_make_tool("market_and_adjacency_scan", "Google Search market demand + skills-graph adjacent skills via knowledge-mcp.", st.market_scan, ctx, em["market_intel"], "market_scan")],
                   llm=llm.crew_llm(models[2]), max_iter=3, allow_delegation=False, verbose=False, max_retry_limit=1)
    avail = Agent(role="Availability & Location Analyst", goal="Check whether the candidate pool can start on time and where it sits geographically, then write the sourcing brief.",
                  backstory="You balance delivery timelines, mobility policy and relocation realities.",
                  tools=[_make_tool("availability_location_scan", "Availability and location analysis of the current candidate pool.", st.availability_scan, ctx, em["availability_analyst"], "availability_scan")],
                  llm=llm.crew_llm(models[3]), max_iter=3, allow_delegation=False, verbose=False, max_retry_limit=1)

    t1 = Task(description=f"Job: {job}\nCall BOTH of your tools once, then summarise pool size and skill coverage in 3 bullet points.",
              expected_output="3 bullet points on pool size and skill coverage.", agent=skills, async_execution=True)
    t2 = Task(description=f"Job: {job}\nCall your tool once and summarise application volume and motivation signals in 2 bullet points.",
              expected_output="2 bullet points on applications.", agent=screener, async_execution=True)
    t3 = Task(description=f"Job: {job}\nCall your tool once and summarise market demand and best adjacent skills in 2 bullet points.",
              expected_output="2 bullet points on market demand and adjacent skills.", agent=market, async_execution=True)
    t4 = Task(description=f"Job: {job}\nCall your tool once, then write a concise sourcing brief (max 120 words): pool size, readiness by start date, "
                          "location spread, key risks, and one recommendation.",
              expected_output="A sourcing brief of at most 120 words.", agent=avail, context=[t1, t2, t3])

    def on_task(out):
        who = {"Skills Analyst": "skills_analyst", "Applications Screener": "applications_screener", "Market Intel Agent": "market_intel",
               "Availability & Location Analyst": "availability_analyst"}.get(getattr(out, "agent", ""), "crew_manager")
        ctx.insights[who] = out.raw
        Emitter(run_id, who).thought(out.raw[:600])

    return Crew(agents=[skills, screener, market, avail], tasks=[t1, t2, t3, t4], process=Process.sequential,
                task_callback=on_task, verbose=False)


async def run_crew(ctx: RunContext, run_id: str) -> dict:
    mgr = Emitter(run_id, "crew_manager")
    mgr.status("Kicking off the Talent Sourcing Crew (4 agents, parallel tasks)")
    mode = "llm"
    for attempt in range(2):  # one retry after the per-minute window resets (tools are idempotent)
        t_start = time.monotonic()
        try:
            if not [m for m in llm.model_chain("fast") if llm._is_healthy(m)]:
                raise llm.LLMUnavailable("no healthy model in fast chain")
            models = llm.spread_models("fast", 4)
            for m in set(models):
                wait = llm.reserve(m, 2 * models.count(m))  # ~2 calls per agent
                if wait > 0:
                    mgr.thought(f"Waiting {wait:.0f}s for {m} rate window (free tier: 5 req/min per model)")
                    await asyncio.sleep(min(wait, 8))
            mgr.thought("Crew models: " + ", ".join(f"{r}→{m}" for r, m in zip(["skills", "applications", "market", "availability"], models))
                        + (" (retry)" if attempt else ""))
            crew = build_crew(ctx, run_id, models)
            result = await asyncio.wait_for(asyncio.to_thread(crew.kickoff), timeout=CREW_TIMEOUT_S)
            ctx.insights["sourcing_brief"] = str(result.raw if hasattr(result, "raw") else result)
            break
        except Exception as exc:
            rate = any(c in str(exc) for c in ("429", "RESOURCE_EXHAUSTED"))
            if attempt == 0 and rate and time.monotonic() - t_start < 20:  # fail-fast 429 only; never after a long partial run
                mgr.warn("Gemini free-tier rate limit hit — waiting 20s, then retrying the crew")
                await asyncio.sleep(20)
                continue
            mode = "deterministic"
            mgr("fallback", f"Crew LLM unavailable ({type(exc).__name__}); executing remaining crew tools deterministically",
                {"error": str(exc)[:300]})
            break

    # Guarantee grounded coverage: run any tool the agents skipped (availability always last, on final pool)
    owners = {"skills_search": "skills_analyst", "semantic_search": "skills_analyst", "applications_screen": "applications_screener",
              "market_scan": "market_intel", "availability_scan": "availability_analyst"}
    for name, fn in st.ALL.items():
        if name not in ctx.tools_run or name == "availability_scan":
            em = Emitter(run_id, owners[name])
            if name not in ctx.tools_run and mode == "llm":
                em.warn(f"Agent skipped `{name}` — executing it to guarantee coverage")
            out = await fn(ctx, em)
            em.result(f"{name} complete", out)
    if "sourcing_brief" not in ctx.insights:
        a = ctx.evidence["availability_scan"]
        ctx.insights["sourcing_brief"] = (
            f"Pool of {a['pool_size']} eligible employees; {a['available_by_start']} available by the start date and "
            f"{a['available_within_45_days_of_start']} more within 45 days. {a['same_city']} are in {a['job_location']['city']}, "
            f"{a['same_region']} in {a['job_location']['region']}; {a['open_to_relocation']} open to relocation. "
            f"{ctx.evidence.get('applications_screen', {}).get('active', 0)} active applications.")
    mgr.result("Sourcing brief ready", {"brief": ctx.insights["sourcing_brief"], "mode": mode, "pool_size": len(ctx.pool)})
    return {"mode": mode, "pool_size": len(ctx.pool), "brief": ctx.insights["sourcing_brief"], "evidence": ctx.evidence}
