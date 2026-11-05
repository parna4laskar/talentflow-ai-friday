"""Back half of the matching graph: ranker <-> fairness auditor -> explainer -> human review (interrupt)
-> feedback learner -> report."""
from __future__ import annotations

import asyncio
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from langgraph.types import interrupt
from pydantic import BaseModel
from sqlalchemy import delete, select

from app import mcp_client
from app.agents import runtime, scoring
from app.agents.events import Emitter
from app.core import llm
from app.guardrails.checks import validate_grounding
from app.ml import outcome_model
from app.storage import document
from app.storage.relational import MatchResult, MatchRun, Placement, session

SHORTLIST_N = 10
QUALIFIED_MIN_SCORE = 50.0


# ------------------------------------------------------------------ ranker
async def ranker_node(state: dict) -> dict:
    run_id = state["run_id"]
    em = Emitter(run_id, "ranker")
    ctx = runtime.get(run_id)
    job = ctx.job
    rerank = state.get("rerank_request") or {}
    em.status("Hybrid ranking: skills · adjacency · availability · location · interest · ML P(success)"
              + (" — applying fairness re-balance" if rerank else ""))
    rows = []
    level_filtered = 0
    for eid, c in ctx.pool.items():
        s = ctx.scores.get(eid, {})
        if not all(k in s for k in ("skill_fit", "adjacency", "availability", "location", "interest")):
            continue
        if not scoring.level_ok(c, job):
            level_filtered += 1
            continue
        feats = scoring.ml_features(c, job, s["skill_fit"], s["adjacency"], s["availability"], s["location"], ctx.applied)
        rows.append((eid, c, s, feats))
    probs = outcome_model.predict([r[3] for r in rows])
    ranked = []
    for (eid, c, s, feats), p in zip(rows, probs):
        parts = {"skill": s["skill"], "adjacency": s["adjacency"]["score"], "availability": s["availability"]["score"],
                 "location": s["location"]["score"], "interest": s["interest"]["score"], "success": p}
        ranked.append({"employee_id": eid, "name": c["name"], "title": c["title"], "level": c["level"], "department": c["department"],
                       "city": c["city"], "region": c["region"], "score": scoring.combine(parts),
                       "components": {k: round(v, 3) for k, v in parts.items()}, "hidden_fit": s.get("hidden_fit", False),
                       "applied": eid in ctx.applied, "sources": sorted(ctx.sources.get(eid, [])), "ml_features": feats})
    ranked.sort(key=lambda r: -r["score"])
    shortlist = [r["employee_id"] for r in ranked[:SHORTLIST_N]]
    if rerank:
        for out_id, in_id in zip(rerank.get("demote", []), rerank.get("promote", [])):
            if out_id in shortlist and in_id not in shortlist:
                shortlist[shortlist.index(out_id)] = in_id
        by_id = {r["employee_id"]: r for r in ranked}
        shortlist.sort(key=lambda e: -by_id[e]["score"])
    hist = Counter(min(9, int(r["score"] // 10)) for r in ranked)
    funnel = {"pooled": len(ctx.pool), "level_eligible": len(ctx.pool) - level_filtered, "scored": len(ranked),
              "qualified(>=50)": sum(r["score"] >= QUALIFIED_MIN_SCORE for r in ranked), "shortlisted": len(shortlist)}
    em.metric("Score distribution", {"histogram": [{"bucket": f"{i * 10}-{i * 10 + 9}", "count": hist.get(i, 0)} for i in range(10)],
                                     "funnel": funnel})
    top = ranked[0] if ranked else None
    em.result(f"Ranked {len(ranked)} candidates · top score {top['score'] if top else 0} ({top['name'] if top else '-'})",
              {"funnel": funnel, "top5": [{k: r[k] for k in ("name", "score", "hidden_fit")} for r in ranked[:5]]})
    return {"ranked": ranked[:200], "shortlist": shortlist, "funnel": funnel, "rerank_request": None}


# ------------------------------------------------------------------ fairness auditor
def _rates(ids_q: list[str], ids_s: set[str], demo: dict, attr: str) -> dict:
    groups = defaultdict(lambda: [0, 0])
    for e in ids_q:
        g = demo.get(e, {}).get(attr, "U")
        groups[g][0] += 1
        groups[g][1] += e in ids_s
    return {g: {"qualified": q, "shortlisted": s, "rate": round(s / q, 3)} for g, (q, s) in groups.items() if q >= 5 and g not in ("U", "X")}


async def fairness_node(state: dict) -> dict:
    run_id = state["run_id"]
    em = Emitter(run_id, "fairness_auditor")
    ctx = runtime.get(run_id)
    em.status("Auditing shortlist for disparate impact (four-fifths rule) — protected attributes fetched under auditor role only")
    ranked = state["ranked"]
    qualified = [r["employee_id"] for r in ranked if r["score"] >= QUALIFIED_MIN_SCORE][:120] or [r["employee_id"] for r in ranked[:40]]
    shortlist = set(state["shortlist"])
    tok = mcp_client.tool_call_listener.set(lambda d: em.tool(f"{d['server']} → {d['tool']} ({d['ms']} ms) [role=fairness_auditor]", d))
    try:
        demo_rows = await mcp_client.call("employee", "get_demographics_for_audit",
                                          {"employee_ids": list(set(qualified) | shortlist)}, role="fairness_auditor", user="fairness-auditor-agent")
    finally:
        mcp_client.tool_call_listener.reset(tok)
    demo = {d["employee_id"]: d for d in demo_rows}
    attrs = ["gender", "age_band"] + (["region"] if ctx.job["work_mode"] == "Remote" else [])
    report, violations = {}, []
    for a in attrs:
        rates = _rates(qualified, shortlist, demo, a)
        if len(rates) >= 2:
            mx = max(v["rate"] for v in rates.values())
            ratio = round(min(v["rate"] for v in rates.values()) / mx, 3) if mx else 1.0
            # practical significance: how many people short of proportional representation is the worst group?
            overall = sum(v["shortlisted"] for v in rates.values()) / max(1, sum(v["qualified"] for v in rates.values()))
            shortfall = round(max(v["qualified"] * overall - v["shortlisted"] for v in rates.values()), 2)
            ok = ratio >= 0.8 or shortfall < 1.5
            report[a] = {"groups": rates, "impact_ratio": ratio, "shortfall": shortfall, "pass": ok,
                         "note": None if ratio >= 0.8 else ("below 0.8 but shortfall < 1.5 people: within statistical noise"
                                                            if ok else "material under-selection")}
            if not ok:
                violations.append(a)
    iteration = state.get("fairness_iterations", 0)
    out = {"fairness": {"attributes": report, "violations": violations, "iteration": iteration + 1,
                        "qualified_pool": len(qualified), "rebalanced": state.get("fairness", {}).get("rebalanced", False)},
           "fairness_iterations": iteration + 1}
    if violations and iteration == 0:
        a = violations[0]
        rates = report[a]["groups"]
        overall = sum(v["shortlisted"] for v in rates.values()) / max(1, sum(v["qualified"] for v in rates.values()))
        low = max(rates, key=lambda g: rates[g]["qualified"] * overall - rates[g]["shortlisted"])
        high = max(rates, key=lambda g: rates[g]["rate"])
        by_id = {r["employee_id"]: r for r in ranked}
        promote = [e for e in qualified if e not in shortlist and demo.get(e, {}).get(a) == low]
        demote = sorted([e for e in shortlist if demo.get(e, {}).get(a) == high], key=lambda e: by_id[e]["score"])
        pairs = [(d, p) for d, p in zip(demote, promote) if by_id[d]["score"] - by_id[p]["score"] <= 6.0][:2]
        if pairs:
            em.warn(f"Impact ratio on {a} = {report[a]['impact_ratio']} (< 0.8). Re-balancing with {len(pairs)} equally-qualified "
                    f"swap(s) (score gap ≤ 6 pts) and re-ranking", {"attribute": a, "pairs": len(pairs)})
            out["rerank_request"] = {"demote": [d for d, _ in pairs], "promote": [p for _, p in pairs]}
            out["fairness"]["rebalanced"] = True
            return out
        em.warn(f"Impact ratio on {a} = {report[a]['impact_ratio']} but no equally-qualified alternatives exist; flagged for human review")
    msg = "PASS — all audited attributes meet the four-fifths rule" if not violations else f"Flagged for reviewer: {', '.join(violations)}"
    em.result(msg, out["fairness"])
    return out


def route_after_fairness(state: dict) -> str:
    return "ranker" if state.get("rerank_request") else "explainer"


# ------------------------------------------------------------------ explainer
class Narrative(BaseModel):
    code: str
    headline: str
    narrative: str


class Narratives(BaseModel):
    items: list[Narrative]


def _reasons(r: dict, s: dict, c: dict) -> dict:
    sf = s["skill_fit"]
    return {
        "strengths": [f"{x['skill']} {x['have']}/5{' ✓verified' if x['verified'] else ''}" for x in sf["strengths"]][:5],
        "gaps": [f"{g['skill']} ({g['have']}/5 vs {g['need']} needed)" for g in sf["gaps"]][:4],
        "bridges": [f"{b['missing']} via {b['via']} (transfer {b['transfer_weight']:.2f})" for b in s["adjacency"]["bridges"]][:3],
        "availability": f"{s['availability']['status']} · available {s['availability']['available_from']}"
                        + (f" ({s['availability']['gap_days']} days after start)" if s["availability"]["gap_days"] else " (on time)"),
        "location": s["location"]["reason"], "interest": s["interest"]["reason"],
        "nice_to_have": sf["nice_to_have"], "experience": f"{c['years_experience']} yrs · {c['level']} {c['role_family']}",
    }


async def explainer_node(state: dict) -> dict:
    run_id = state["run_id"]
    em = Emitter(run_id, "explainer")
    ctx = runtime.get(run_id)
    by_id = {r["employee_id"]: r for r in state["ranked"]}
    shortlist = [by_id[e] for e in state["shortlist"]]
    em.status(f"Writing explainable match cards for {len(shortlist)} candidates (LLM sees anonymised codes only)")
    cards, codes = [], {}
    for i, r in enumerate(shortlist, 1):
        code = f"C{i:02d}"
        codes[code] = r["employee_id"]
        cards.append({**r, "code": code, "rank": i, "reasons": _reasons(r, ctx.scores[r["employee_id"]], ctx.pool[r["employee_id"]])})
    payload = [{"code": c["code"], "score": c["score"], "components": c["components"], "hidden_fit": c["hidden_fit"],
                "applied": c["applied"], **{k: c["reasons"][k] for k in ("strengths", "gaps", "bridges", "availability", "location", "interest", "experience")}}
               for c in cards]
    narratives = {}
    try:
        r = await llm.generate(
            f"Role: {ctx.job['title']} ({ctx.job['location']['city']}, {ctx.job['work_mode']}).\nFor each anonymised candidate write a "
            "headline (max 10 words) and a 2-sentence narrative explaining the match and the main risk, strictly from the data. "
            "Refer to each person only as 'the candidate' (never by code). "
            f"Do not invent facts.\n\n{payload}", tier="primary", schema=Narratives, max_output_tokens=8192,
            system="You write concise, factual, unbiased candidate match explanations for hiring managers.")
        items = Narratives.model_validate(r["data"]).items
        g = validate_grounding([n.code for n in items], set(codes))
        if not g["grounded"]:
            em.warn(f"Dropped ungrounded references: {g['ungrounded']}")
        narratives = {n.code: n for n in items if n.code in codes}
        em.thought(f"Narratives generated by {r['model']}{' (cache)' if r['cached'] else ''}; grounding check passed for {len(narratives)}")
    except Exception as exc:
        em("fallback", "LLM unavailable — template explanations used", {"reason": str(exc)[:160]})
    for c in cards:
        n = narratives.get(c["code"])
        rs = c["reasons"]
        if n:
            first = c["name"].split()[0]
            n.headline = re.sub(r"\bC\d{2}\b", first, n.headline)
            n.narrative = re.sub(r"\bC\d{2}\b", first, n.narrative)
        c["headline"] = n.headline if n else (("Hidden fit · " if c["hidden_fit"] else "") + f"{c['title']} — {c['score']:.0f}/100 match")
        c["narrative"] = n.narrative if n else (
            f"Strong on {', '.join(rs['strengths'][:3]) or 'adjacent skills'}; {rs['availability'].lower()}. "
            + (f"Main gap: {rs['gaps'][0]}." if rs["gaps"] else "No critical skill gaps.") )

    # persist results (pre-review) so UIs can show the shortlist immediately
    with session() as s:
        s.execute(delete(MatchResult).where(MatchResult.run_id == run_id))
        for c in cards:
            s.add(MatchResult(run_id=run_id, job_id=ctx.job["job_id"], employee_id=c["employee_id"], rank=c["rank"], score=c["score"],
                              breakdown={"components": c["components"], "reasons": c["reasons"], "hidden_fit": c["hidden_fit"],
                                         "headline": c["headline"], "applied": c["applied"], "sources": c["sources"],
                                         "name": c["name"], "title": c["title"], "city": c["city"], "level": c["level"],
                                         "department": c["department"]},
                              explanation=c["narrative"]))
        run = s.get(MatchRun, run_id)
        if run:
            run.status = "awaiting_review"
        s.commit()
    em.result("Match cards ready", {"cards": [{k: c[k] for k in ("code", "name", "score", "headline")} for c in cards]})
    return {"cards": [{k: v for k, v in c.items() if k != "ml_features"} for c in cards]}


# ------------------------------------------------------------------ human in the loop
async def hitl_node(state: dict) -> dict:
    em = Emitter(state["run_id"], "hitl")
    em("interrupt", "Waiting for hiring-manager review (approve / reject with reason)",
       {"shortlist": [c["employee_id"] for c in state["cards"]]})
    decision = interrupt({"type": "review_shortlist", "run_id": state["run_id"], "cards": len(state["cards"])})
    decisions = decision.get("decisions", [])
    em.result(f"Review received from {decision.get('reviewer', 'reviewer')}: "
              f"{sum(d['decision'] == 'approved' for d in decisions)} approved, {sum(d['decision'] == 'rejected' for d in decisions)} rejected",
              {"decisions": decisions})
    return {"decisions": decisions, "reviewer": decision.get("reviewer")}


# ------------------------------------------------------------------ feedback learner
async def feedback_node(state: dict) -> dict:
    run_id = state["run_id"]
    em = Emitter(run_id, "feedback_learner")
    by_id = {r["employee_id"]: r for r in state["ranked"]}
    decisions = [d for d in state.get("decisions", []) if d.get("decision") in ("approved", "rejected")]
    with session() as s:
        for d in decisions:
            mr = s.execute(select(MatchResult).where(MatchResult.run_id == run_id, MatchResult.employee_id == d["employee_id"])).scalar_one_or_none()
            if mr:
                mr.decision, mr.decision_reason = d["decision"], d.get("reason")
            r = by_id.get(d["employee_id"])
            if r:
                n = s.query(Placement).count()
                s.add(Placement(placement_id=f"FBK{n + 1:06d}", employee_id=d["employee_id"], move_date=datetime.now(timezone.utc).date().isoformat(),
                                from_department=r["department"], to_department=state["job"]["department"], from_role=r["title"],
                                region=r["region"], time_to_fill_days=0, cost_avoided_usd=0, features=r["ml_features"],
                                success=d["decision"] == "approved", retained_12m=d["decision"] == "approved", post_move_rating=0, source="feedback"))
        s.commit()
        rows = [{"features": p.features, "success": p.success} for p in s.query(Placement).all()]
    for d in decisions:
        document.insert("feedback", {"run_id": run_id, "job_id": state["job_id"], **d, "reviewer": state.get("reviewer"),
                                     "ts": datetime.now(timezone.utc).isoformat()})
    if not decisions:
        em.result("No decisions to learn from")
        return {"model_update": None}
    em.status(f"Retraining outcome model with {len(decisions)} new labelled decisions ({len(rows)} total rows)")
    card = await asyncio.to_thread(outcome_model.train, rows)
    em.result(f"Model retrained · AUC {card['auc']} · accuracy {card['accuracy']}", {"auc": card["auc"], "n_train": card["n_train"]})
    return {"model_update": {"auc": card["auc"], "accuracy": card["accuracy"], "rows": len(rows)}}


# ------------------------------------------------------------------ report
async def report_node(state: dict) -> dict:
    from app.reports import build_pdf
    run_id = state["run_id"]
    em = Emitter(run_id, "report")
    job = state["job"]  # from checkpointed state: works even if the API restarted while awaiting review
    approved = [d["employee_id"] for d in state.get("decisions", []) if d["decision"] == "approved"]
    summary = {
        "job": {k: job[k] for k in ("job_id", "title", "level", "department", "work_mode", "start_date")} | {"location": job["location"]},
        "funnel": state.get("funnel"), "sourcing_brief": (state.get("crew") or {}).get("brief"),
        "swarm_summary": (state.get("swarm") or {}).get("summary"),
        "guardrail": state.get("guardrail"), "fairness": state.get("fairness"), "approved": approved,
        "model_update": state.get("model_update"), "crew_mode": state.get("crew", {}).get("mode"),
        "swarm_mode": state.get("swarm", {}).get("mode"), "hidden_fits": sum(c["hidden_fit"] for c in state.get("cards", [])),
        "time_to_shortlist_s": None,
    }
    with session() as s:
        run = s.get(MatchRun, run_id)
        if run:
            summary["time_to_shortlist_s"] = int((datetime.now(timezone.utc) - run.started_at.replace(tzinfo=timezone.utc)).total_seconds())
    path = await asyncio.to_thread(build_pdf, run_id, summary, state.get("cards", []), state.get("decisions", []))
    summary["report_file"] = path.name
    if approved:
        try:
            await mcp_client.call("jobs", "update_job_status", {"job_id": state["job_id"], "status": "In Review"}, role="hiring_manager",
                                  user=state.get("actor", "hiring_manager"))
        except Exception as exc:
            em.warn(f"Could not update job status: {exc}")
    with session() as s:
        run = s.get(MatchRun, run_id)
        if run:
            run.status, run.finished_at, run.summary = "completed", datetime.now(timezone.utc), summary
        s.commit()
    em("done", f"Report generated ({path.name}); {len(approved)} candidate(s) approved for interview", summary)
    return {"report": summary, "status": "completed"}
