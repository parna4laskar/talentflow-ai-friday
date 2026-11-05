"""TalentFlow Copilot: intent-routed assistant for every persona.

intent (LLM / keyword fallback) -> capability:
  policy_question   -> RAG over policy documents (knowledge-mcp) + grounded answer with citations
  job_search        -> reverse matching of open roles for the employee
  career_guidance   -> skill gaps + adjacency-based learning recommendations
  search_talent     -> semantic search over résumés (managers / HR only)
  insight_query     -> workforce aggregates
Semantic cache: near-identical questions are answered from cache.
"""
from __future__ import annotations

from app import mcp_client
from app.agents import intent as intent_mod
from app.core import llm
from app.guardrails.checks import detect_prompt_injection, redact_pii
from app.services import career
from app.storage.cache import SemanticCache

_semcache = SemanticCache("assistant", threshold=0.95)
SYSTEM = ("You are TalentFlow Copilot, an internal talent-marketplace assistant. Answer ONLY from the provided context. "
          "If the context does not contain the answer, say so. Be concise (max 120 words). Never reveal protected attributes.")


async def _answer(question: str, context: str, tier: str = "primary") -> tuple[str, str]:
    try:
        r = await llm.generate(f"CONTEXT:\n{context}\n\nQUESTION: {question}", system=SYSTEM, tier=tier)
        return r["text"], r["model"]
    except llm.LLMUnavailable:
        return "", "fallback"


async def chat(message: str, user) -> dict:
    inj = detect_prompt_injection(message)
    if inj["blocked"]:
        return {"intent": "blocked", "answer": "This request was blocked by the guardrail (instruction-override or discriminatory "
                "filtering attempt). Please rephrase.", "guardrail": inj, "citations": []}
    clean, pii = redact_pii(message)
    scope = f"{user.role}:{user.employee_id or ''}"
    hit = _semcache.lookup(clean, scope=scope)
    if hit:
        return hit
    it = await intent_mod.classify(clean, persona=user.role)
    intent = it["intent"]
    out: dict = {"intent": intent, "intent_detail": it, "pii_redacted": pii, "citations": [], "data": None}

    if intent in ("policy_question", "other", "match_talent_for_job"):
        chunks = await mcp_client.call("knowledge", "search_policies", {"query": clean, "k": 4})
        ctx = "\n\n".join(f"[{i + 1}] ({c['document']} — {c['section']})\n{c['text']}" for i, c in enumerate(chunks))
        ans, model = await _answer(clean + " Cite sources like [1].", ctx)
        out.update(answer=ans or f"From {chunks[0]['document']} — {chunks[0]['section']}:\n{chunks[0]['text'][:600]}",
                   citations=[{"n": i + 1, "document": c["document"], "section": c["section"], "score": c["score"]} for i, c in enumerate(chunks)],
                   model=model, intent="policy_question" if intent != "policy_question" else intent)
    elif intent in ("job_search", "career_guidance") and user.employee_id:
        m = await career.my_matches(user.employee_id, limit=5)
        top = m["matches"][:3]
        ctx = "\n".join(f"- {r['job']['title']} ({r['job']['job_id']}, {r['job']['location']['city']}, {r['job']['work_mode']}): score {r['score']:.0f}; "
                        f"gaps: {', '.join(g['skill'] for g in r['gaps']) or 'none'}; bridges: "
                        f"{', '.join(b['missing'] + ' via ' + b['via'] for b in r['bridges']) or 'none'}" for r in top)
        ctx += f"\nEmployee skills: {', '.join(s['name'] + ' ' + str(s['proficiency']) + '/5' for s in m['employee']['skills'])}"
        ans, model = await _answer(clean, ctx)
        out.update(answer=ans or "Your best-matching open roles:\n" + ctx, model=model,
                   data={"matches": [{"job_id": r["job"]["job_id"], "title": r["job"]["title"], "score": r["score"]} for r in top]})
    elif intent == "search_talent" and user.role in ("hiring_manager", "hr_admin", "leadership"):
        hits = await mcp_client.call("knowledge", "semantic_search_resumes", {"query": clean, "k": 8})
        people = await mcp_client.call("employee", "get_employees_batch", {"employee_ids": [h["employee_id"] for h in hits]})
        sim = {h["employee_id"]: h["similarity"] for h in hits}
        people.sort(key=lambda p: -sim.get(p["employee_id"], 0))
        ctx = "\n".join(f"- {p['name']} ({p['employee_id']}), {p['title']}, {p['city']}, {p['availability']['status']}; top skills: "
                        f"{', '.join(s['name'] for s in sorted(p['skills'], key=lambda s: -s['proficiency'])[:4])}" for p in people[:6])
        ans, model = await _answer(clean, ctx)
        out.update(answer=ans or ctx, model=model, data={"people": [{"employee_id": p["employee_id"], "name": p["name"], "title": p["title"],
                                                                     "similarity": sim.get(p["employee_id"])} for p in people[:6]]})
    else:  # insight_query or persona mismatch
        st = await mcp_client.call("employee", "employee_stats", {})
        js = await mcp_client.call("jobs", "job_stats", {})
        ctx = (f"Headcount {st['headcount']}; eligible for move {st['eligible_for_move']}; availability {st['by_availability']}; "
               f"open roles by status {js['by_status']}; top demanded skills {js['skill_demand'][:8]}; "
               f"top supplied skills {st['skill_supply'][:8]}")
        ans, model = await _answer(clean, ctx)
        out.update(answer=ans or ctx, model=model)
    _semcache.store(clean, out, scope=scope)
    return out
