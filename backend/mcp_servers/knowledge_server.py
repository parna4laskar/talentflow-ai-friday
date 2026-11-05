"""knowledge-mcp: RAG, skills graph and market intelligence.

Tools: semantic_search_resumes, semantic_similarity, normalize_skills, skill_graph_neighbors, skill_adjacency,
       skill_path, search_policies (RAG), market_intel (Google Search, cached), skill_catalog
"""
from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

from common import serve
from app.core.config import get_settings
from app.storage import graph, vector
from app.storage.cache import cached, get as cache_get, make_key, set as cache_set
from app.storage.relational import Skill, session

mcp = FastMCP("knowledge-mcp", instructions="Semantic search over résumés and policies, skills-graph reasoning and market intel.",
              host=get_settings().mcp_host, stateless_http=True, json_response=True)

_SEED_INTEL = None
ALIASES = {"k8s": "Kubernetes", "kube": "Kubernetes", "js": "JavaScript", "ts": "TypeScript", "reactjs": "React", "react.js": "React",
           "nodejs": "Node.js", "node": "Node.js", "golang": "Go", "ml": "Machine Learning", "dl": "Deep Learning",
           "genai": "Generative AI", "gen ai": "Generative AI", "llm": "LLM Engineering", "llms": "LLM Engineering", "rag": "LLM Engineering",
           "agents": "Agentic AI", "ai agents": "Agentic AI", "langgraph": "Agentic AI", "crewai": "Agentic AI", "pyspark": "Apache Spark",
           "spark": "Apache Spark", "gcp": "GCP", "google cloud": "GCP", "aws": "AWS", "azure": "Azure", "iac": "Terraform",
           "devops": "CI/CD", "sre": "Site Reliability Engineering", "scrum": "Agile/Scrum", "agile": "Agile/Scrum", "pm": "Project Management",
           "powerbi": "Power BI", "bi": "Data Visualization", "ux": "UX Research", "ui": "UI Design", "iam": "Identity & Access Management",
           "appsec": "Application Security", "s/4": "SAP S/4HANA", "sfdc": "Salesforce", "mlops": "MLOps", "nlp": "NLP", "sql": "SQL"}
STOP = {"the", "a", "an", "i", "my", "to", "of", "in", "for", "and", "or", "is", "do", "can", "how", "what", "be", "must", "before", "?"}


def _tokens(text: str) -> set[str]:
    import re
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t) > 2}


@mcp.tool()
@cached("mcp:semantic_search_resumes", ttl=300)
def semantic_search_resumes(query: str, k: int = 50, region: str | None = None, eligible_only: bool = True) -> list[dict]:
    """Vector search over 3,000 employee résumés. Returns employee ids with cosine similarity."""
    where = {}
    if region and eligible_only:
        where = {"$and": [{"region": region}, {"eligible": True}]}
    elif region:
        where = {"region": region}
    elif eligible_only:
        where = {"eligible": True}
    return [{"employee_id": r["id"], "similarity": r["score"], "role_family": r["metadata"]["role_family"],
             "city": r["metadata"]["city"]} for r in vector.search("resumes", query, k=k, where=where)]


@mcp.tool()
def semantic_similarity(query: str, employee_ids: list[str]) -> dict:
    """Cosine similarity between a job query and specific employees' résumé embeddings."""
    return {k: round(v, 4) for k, v in vector.similarity_for_ids("resumes", query, employee_ids).items()}


@mcp.tool()
@cached("mcp:normalize_skills", ttl=3600)
def normalize_skills(terms: list[str]) -> list[dict]:
    """Map free-text skill mentions (e.g. 'k8s', 'LLM apps') onto the canonical skills taxonomy."""
    with session() as s:
        names = {n.lower(): n for (n,) in s.query(Skill.name).all()}
    out = []
    for t in terms:
        if t.lower().strip() in ALIASES:
            out.append({"term": t, "skill": ALIASES[t.lower().strip()], "confidence": 0.98})
            continue
        if t.lower() in names:
            out.append({"term": t, "skill": names[t.lower()], "confidence": 1.0})
            continue
        hit = vector.search("skills", t, k=1)
        if hit:
            out.append({"term": t, "skill": hit[0]["metadata"]["name"], "confidence": hit[0]["score"]})
    return out


@mcp.tool()
def skill_graph_neighbors(skill: str, min_weight: float = 0.4) -> list[dict]:
    """Adjacent (transferable) skills from the skills graph with transfer weights."""
    return graph.neighbors(skill, min_weight)


@mcp.tool()
def skill_adjacency(candidate_skills: list[str], target_skill: str) -> dict:
    """How transferable a candidate's existing skills are to a missing target skill (0-1) and via which skill."""
    best, via = 0.0, None
    for s in candidate_skills:
        w = graph.adjacency_weight(s, target_skill)
        if w > best:
            best, via = w, s
    return {"target": target_skill, "transfer_weight": best, "via": via,
            "path": graph.skill_path(via, target_skill) if via else []}


@mcp.tool()
def skill_path(from_skill: str, to_skill: str) -> list[str]:
    """Shortest learning path between two skills in the adjacency graph."""
    return graph.skill_path(from_skill, to_skill)


@mcp.tool()
@cached("mcp:search_policies", ttl=600)
def search_policies(query: str, k: int = 4) -> list[dict]:
    """Hybrid RAG retrieval (vector + keyword re-rank) over mobility, relocation, learning and Responsible-AI policies."""
    q = _tokens(query)
    hits = vector.search("policies", query, k=max(10, k * 3))
    for h in hits:
        overlap = len(q & _tokens(h["text"])) / (len(q) or 1)
        h["hybrid"] = round(0.6 * h["score"] + 0.4 * overlap, 4)
    hits.sort(key=lambda h: -h["hybrid"])
    return [{"source": r["metadata"]["source"], "document": r["metadata"]["document"], "section": r["metadata"]["section"],
             "score": r["hybrid"], "text": r["text"]} for r in hits[:k]]


def _seed_intel() -> dict:
    global _SEED_INTEL
    if _SEED_INTEL is None:
        import json
        _SEED_INTEL = json.loads((get_settings().seed_dir / "market_intel.json").read_text(encoding="utf-8"))
    return _SEED_INTEL


@mcp.tool()
def market_intel(skill: str) -> dict:
    """Google Search for external market demand of a skill. Uses Google Programmable Search when
    GOOGLE_CSE_KEY/GOOGLE_CSE_ID are configured, otherwise returns cached sample results."""
    key = make_key("google_search", skill)
    hit = cache_get(key)
    if hit:
        return {**hit, "cache": "hit"}
    api_key, cx = os.getenv("GOOGLE_CSE_KEY"), os.getenv("GOOGLE_CSE_ID")
    if api_key and cx:
        try:
            r = httpx.get("https://www.googleapis.com/customsearch/v1", timeout=10,
                          params={"key": api_key, "cx": cx, "q": f"{skill} skills demand 2026 hiring trends", "num": 3})
            r.raise_for_status()
            items = r.json().get("items", [])
            out = {"query": f"{skill} skills demand 2026", "provider": "google-cse (live)",
                   "results": [{"title": i["title"], "snippet": i.get("snippet", ""), "source": i.get("displayLink", "")} for i in items]}
            cache_set(key, out, ttl=86400)
            return {**out, "cache": "miss"}
        except Exception as exc:  # fall through to cached results
            fallback_reason = str(exc)[:80]
    else:
        fallback_reason = "no live search key configured"
    out = _seed_intel().get(skill) or {"query": skill, "provider": "none", "results": []}
    out = {**out, "note": f"cached sample results ({fallback_reason})"}
    cache_set(key, out, ttl=86400)
    return {**out, "cache": "miss"}


@mcp.tool()
@cached("mcp:skill_catalog", ttl=3600)
def skill_catalog() -> list[dict]:
    """Canonical skills taxonomy with category and market trend."""
    with session() as s:
        return [{"name": k.name, "category": k.category, "trend": k.demand_trend, "growth": k.market_growth_index}
                for k in s.query(Skill).all()]


def _warmup():
    """Load the embedding model, vector index and skills graph before the first request."""
    try:
        vector.search("skills", "python", k=1)
        graph.neighbors("Python")
    except Exception as exc:  # warm-up is best effort
        print(f"warm-up skipped: {exc}")


if __name__ == "__main__":
    _warmup()
    serve(mcp, get_settings().mcp_ports["knowledge"])
