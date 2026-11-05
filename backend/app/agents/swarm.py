"""Swarm of matching specialists (langgraph-swarm): agents decide among themselves who acts next
by handing off control, instead of a fixed pipeline.

  Skill Matcher      exact + semantic skill fit for every pooled candidate
  Hidden-Fit Finder  skills-graph adjacency: who can close their gaps quickly
  Mobility Matcher   availability window, location / relocation and career-interest fit

Scores are computed by grounded tools that write into the run context; agents receive compact summaries.
"""
from __future__ import annotations

import asyncio
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from app import mcp_client
from app.agents import scoring
from app.agents.events import Emitter
from app.agents.runtime import RunContext
from app.core import llm

SWARM_TIMEOUT_S = 120


async def op_skill_fit(ctx: RunContext, emit: Emitter) -> dict:
    tok = mcp_client.tool_call_listener.set(lambda d: emit.tool(f"{d['server']} → {d['tool']} ({d['ms']} ms)", d))
    try:
        missing = [e for e in ctx.pool if e not in ctx.semantic]
        for i in range(0, len(missing), 200):
            sims = await mcp_client.call("knowledge", "semantic_similarity",
                                         {"query": ctx.requirements.get("search_query") or ctx.job["title"], "employee_ids": missing[i:i + 200]})
            ctx.semantic.update(sims)
    finally:
        mcp_client.tool_call_listener.reset(tok)
    req, nice = ctx.requirements["required_skills"], ctx.requirements.get("nice_to_have", [])
    buckets = {"strong(>=0.8)": 0, "good(0.6-0.8)": 0, "partial(0.4-0.6)": 0, "weak(<0.4)": 0}
    for eid, c in ctx.pool.items():
        sf = scoring.skill_fit(c, req, nice)
        sem = scoring.semantic_norm(ctx.semantic.get(eid))
        s = ctx.scores.setdefault(eid, {})
        s["skill_fit"], s["semantic"] = sf, round(sem, 4)
        s["skill"] = round(0.75 * sf["score"] + 0.25 * sem, 4)
        if sf["gaps"]:
            s["skill"] = min(s["skill"], 0.94)
        v = sf["score"]
        buckets["strong(>=0.8)" if v >= .8 else "good(0.6-0.8)" if v >= .6 else "partial(0.4-0.6)" if v >= .4 else "weak(<0.4)"] += 1
    ctx.tools_run.add("skill_fit")
    top = sorted(ctx.scores.items(), key=lambda kv: -kv[1]["skill"])[:5]
    return {"scored": len(ctx.pool), "skill_fit_distribution": buckets,
            "top5": [{"employee_id": k, "name": ctx.pool[k]["name"], "skill_score": v["skill"]} for k, v in top],
            "candidates_with_gaps": sum(1 for v in ctx.scores.values() if v["skill_fit"]["gaps"])}


async def op_hidden_fit(ctx: RunContext, emit: Emitter) -> dict:
    if not ctx.neighbors:
        tok = mcp_client.tool_call_listener.set(lambda d: emit.tool(f"{d['server']} → {d['tool']} ({d['ms']} ms)", d))
        try:
            for r in ctx.requirements["required_skills"]:
                nb = await mcp_client.call("knowledge", "skill_graph_neighbors", {"skill": r["name"], "min_weight": 0.4})
                ctx.neighbors[r["name"]] = {x["skill"]: x["weight"] for x in nb}
        finally:
            mcp_client.tool_call_listener.reset(tok)
    if "skill_fit" not in ctx.tools_run:
        await op_skill_fit(ctx, emit)
    hidden = []
    for eid, c in ctx.pool.items():
        s = ctx.scores[eid]
        adj = scoring.adjacency_score(s["skill_fit"]["gaps"], ctx.neighbors, {k["name"] for k in c["skills"]})
        s["adjacency"] = adj
        # hidden fit: a strong candidate from a DIFFERENT role family (missed by title/keyword search),
        # whose remaining gaps are bridgeable through adjacent skills in the graph
        s["hidden_fit"] = (c["role_family"] != ctx.job["role_family"] and s["skill_fit"]["coverage"] >= 0.6
                           and adj["score"] >= 0.6 and (bool(adj["bridges"]) or not s["skill_fit"]["gaps"]))
        if s["hidden_fit"]:
            hidden.append((eid, adj))
    ctx.tools_run.add("hidden_fit")
    hidden.sort(key=lambda x: -x[1]["score"])
    return {"hidden_fit_candidates": len(hidden),
            "examples": [{"employee_id": e, "name": ctx.pool[e]["name"], "bridges": a["bridges"][:2]} for e, a in hidden[:5]]}


async def op_mobility(ctx: RunContext, emit: Emitter) -> dict:
    start = ctx.requirements.get("start_date") or ctx.job["start_date"]
    ready = reloc = interested = 0
    for eid, c in ctx.pool.items():
        s = ctx.scores.setdefault(eid, {})
        s["availability"] = scoring.availability_fit(c, start)
        s["location"] = scoring.location_fit(c, ctx.job)
        s["interest"] = scoring.interest_signal(c, ctx.job, ctx.applied)
        ready += s["availability"]["score"] >= 1.0
        reloc += s["location"]["relocation"]
        interested += s["interest"]["score"] >= 0.7
    ctx.tools_run.add("mobility")
    return {"assessed": len(ctx.pool), "ready_by_start": ready, "would_need_relocation": reloc, "applied_or_career_aligned": interested}


OPS = {"skill_fit": ("skill_matcher", op_skill_fit), "hidden_fit": ("hidden_fit_finder", op_hidden_fit),
       "mobility": ("mobility_matcher", op_mobility)}


def build_swarm(ctx: RunContext, run_id: str, model_name: str):
    from langgraph.prebuilt import create_react_agent
    from langgraph_swarm import create_handoff_tool, create_swarm

    def make(op_name: str, desc: str):
        agent, fn = OPS[op_name]
        em = Emitter(run_id, agent)

        @tool(op_name, description=desc)
        async def _t() -> str:
            if op_name not in ctx.tools_run:
                em.status(f"Running `{op_name}` over {len(ctx.pool)} candidates")
                out = await fn(ctx, em)
                em.result(f"{op_name} complete", out)
            else:
                out = {"note": f"{op_name} was already completed"}
            remaining = [OPS[o][0] for o in OPS if o not in ctx.tools_run]
            out["specialists_remaining"] = remaining
            out["next_step"] = (f"Hand off to {remaining[0]}." if remaining else
                                "All specialists are done. Do NOT call any tool or hand off; write the final 3-sentence summary now.")
            return json.dumps(out, default=str)
        return _t

    model = llm.chat_model(model_name)
    h = {n: create_handoff_tool(agent_name=n, description=f"Hand off to the {n.replace('_', ' ')}") for n in OPS_AGENTS}
    common = (" You are part of a matching swarm with skill_matcher, hidden_fit_finder and mobility_matcher. "
              "Each specialist runs its own tool exactly once. Look at the conversation to see which specialists already ran. "
              "After running your tool, follow its `next_step` field exactly: hand off to the named remaining specialist, or, "
              "if none remain, reply with a final matching summary of at most 3 sentences and do not call any tool.")
    skill = create_react_agent(model, [make("skill_fit", "Score exact + semantic skill fit for all candidates."), h["hidden_fit_finder"], h["mobility_matcher"]],
                               prompt="You are the Skill Matcher." + common, name="skill_matcher")
    hidden = create_react_agent(model, [make("hidden_fit", "Find hidden-fit candidates whose skill gaps are bridged by adjacent skills."), h["skill_matcher"], h["mobility_matcher"]],
                                prompt="You are the Hidden-Fit Finder." + common, name="hidden_fit_finder")
    mobility = create_react_agent(model, [make("mobility", "Assess availability, location/relocation and interest fit."), h["skill_matcher"], h["hidden_fit_finder"]],
                                  prompt="You are the Mobility Matcher." + common, name="mobility_matcher")
    return create_swarm([skill, hidden, mobility], default_active_agent="skill_matcher").compile()


OPS_AGENTS = ("skill_matcher", "hidden_fit_finder", "mobility_matcher")


async def run_swarm(ctx: RunContext, run_id: str) -> dict:
    lead = Emitter(run_id, "skill_matcher")
    lead.status(f"Swarm activated for {len(ctx.pool)} candidates (Skill Matcher ⇄ Hidden-Fit Finder ⇄ Mobility Matcher)")
    mode, summary, handoffs, tried = "llm", "", [], set()
    brief = (f"Match internal candidates for '{ctx.job['title']}' ({ctx.job['level']}, {ctx.job['location']['city']}, "
             f"{ctx.job['work_mode']}). Required: {', '.join(r['name'] for r in ctx.requirements['required_skills'])}. "
             f"Pool: {len(ctx.pool)} candidates. Start with your tool.")
    for attempt in range(2):  # retry once on the next healthy model; already-run tools are skipped
        current = None
        try:
            model_name = await llm.healthy_model("fast", exclude=tried)
            tried.add(model_name)
            current = model_name
            wait = llm.reserve(model_name, 4)
            if wait > 0:
                lead.thought(f"Waiting {wait:.0f}s for {model_name} rate window (free tier: 5 req/min per model)")
                await asyncio.sleep(min(wait, 8))
            lead.thought(f"Swarm agents will use {model_name}" + (" (retry)" if attempt else ""))
            app = build_swarm(ctx, run_id, model_name)

            async def drive():
                nonlocal summary
                async for update in app.astream({"messages": [HumanMessage(content=brief)]}, {"recursion_limit": 16}, stream_mode="updates"):
                    for node, delta in update.items():
                        for m in (delta or {}).get("messages", []) if isinstance(delta, dict) else []:
                            if isinstance(m, AIMessage):
                                for tc in m.tool_calls or []:
                                    if tc["name"].startswith("transfer_to_"):
                                        tgt = tc["name"].removeprefix("transfer_to_")
                                        handoffs.append((node, tgt))
                                        Emitter(run_id, node)("handoff", f"Handing off to {tgt.replace('_', ' ').title()}", {"from": node, "to": tgt})
                                text = m.content if isinstance(m.content, str) else " ".join(
                                    p.get("text", "") for p in m.content if isinstance(p, dict))
                                if text.strip():
                                    summary = text.strip()
                                    Emitter(run_id, node).thought(text.strip()[:500])
            await asyncio.wait_for(drive(), timeout=SWARM_TIMEOUT_S)
            break
        except Exception as exc:
            if current and any(c in str(exc) for c in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
                llm.mark_unhealthy(current, 45)
            if attempt == 1 or isinstance(exc, (llm.LLMUnavailable, asyncio.TimeoutError)):
                mode = "deterministic"
                lead("fallback", f"Swarm LLM unavailable ({type(exc).__name__}); remaining specialists run in default order", {"error": str(exc)[:300]})
                break
            lead.warn(f"{type(exc).__name__} from model — retrying swarm on another model")

    for op_name in ("skill_fit", "hidden_fit", "mobility"):
        if op_name not in ctx.tools_run:
            agent, fn = OPS[op_name]
            em = Emitter(run_id, agent)
            if mode == "llm":
                em.warn(f"Swarm did not run `{op_name}` — executing to guarantee complete scoring")
            em.result(f"{op_name} complete", await fn(ctx, em))
    if not summary:
        hf = sum(1 for s in ctx.scores.values() if s.get("hidden_fit"))
        summary = f"Scored {len(ctx.pool)} candidates on skills, adjacency and mobility; {hf} hidden-fit candidates identified."
    ctx.insights["swarm_summary"] = summary
    return {"mode": mode, "handoffs": handoffs, "summary": summary}
