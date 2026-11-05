"""Deterministic, explainable scoring used by the Swarm matchers and the Ranker.

match_score = 0.35*skill + 0.15*adjacency + 0.15*availability + 0.10*location + 0.10*interest + 0.15*P(success)
"""
from __future__ import annotations

from datetime import date

WEIGHTS = {"skill": 0.35, "adjacency": 0.15, "availability": 0.15, "location": 0.10, "interest": 0.10, "success": 0.15}
LEVEL_NUM = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def skill_fit(cand: dict, req: list[dict], nice: list[str]) -> dict:
    sk = {s["name"]: s for s in cand["skills"]}
    total_w = sum(r.get("weight", 1.0) for r in req) or 1.0
    got, gaps, strengths = 0.0, [], []
    shortfall = 0.0
    for r in req:
        need = max(1, int(r.get("min_proficiency", 3)))
        have = sk.get(r["name"])
        if have:
            ratio = min(1.0, have["proficiency"] / need) * (1.0 if have.get("verified") else 0.93)
            got += r.get("weight", 1.0) * ratio
            if have["proficiency"] >= need:
                strengths.append({"skill": r["name"], "have": have["proficiency"], "need": need, "verified": have.get("verified", False)})
            else:
                gaps.append({"skill": r["name"], "have": have["proficiency"], "need": need})
                shortfall += need - have["proficiency"]
        else:
            gaps.append({"skill": r["name"], "have": 0, "need": need})
            shortfall += need
    nice_hits = [n for n in nice if n in sk]
    score = min(1.0, got / total_w + 0.03 * len(nice_hits))
    if gaps:  # never show a perfect skill fit while a required skill is short
        score = min(score, 0.94)
    return {"score": round(score, 4), "coverage": round(got / total_w, 4), "gaps": gaps, "strengths": strengths,
            "nice_to_have": nice_hits, "proficiency_gap": round(shortfall / max(1, len(req)), 3)}


def semantic_norm(sim: float | None) -> float:
    if sim is None:
        return 0.5
    return max(0.0, min(1.0, (sim - 0.15) / 0.35))


def adjacency_score(gaps: list[dict], neighbor_map: dict[str, dict[str, float]], cand_skills: set[str]) -> dict:
    """neighbor_map[target_skill] = {adjacent_skill: weight} (from knowledge-mcp skills graph)."""
    if not gaps:
        return {"score": 1.0, "bridges": []}
    vals, bridges = [], []
    for g in gaps:
        if g["have"] > 0:  # partially there: credit by level + adjacency
            vals.append(0.5 + 0.5 * g["have"] / g["need"])
            continue
        best, via = 0.0, None
        for s, w in neighbor_map.get(g["skill"], {}).items():
            if s in cand_skills and w > best:
                best, via = w, s
        vals.append(best)
        if via:
            bridges.append({"missing": g["skill"], "via": via, "transfer_weight": best})
    return {"score": round(sum(vals) / len(vals), 4), "bridges": bridges}


def availability_fit(cand: dict, start_date: str) -> dict:
    a = cand["availability"]
    gap = (_d(a["available_from"]) - _d(start_date)).days
    score = 1.0 if gap <= 0 else max(0.0, 1 - gap / 90)
    if a["status"] == "Partially available":
        score *= 0.8
    return {"score": round(score, 4), "gap_days": max(0, gap), "status": a["status"], "available_from": a["available_from"]}


def location_fit(cand: dict, job: dict) -> dict:
    jl = job["location"]
    if cand["city"] == jl["city"]:
        return {"score": 1.0, "reason": "Same city", "relocation": False}
    if job["work_mode"] == "Remote":
        same_region = cand["region"] == jl["region"]
        return {"score": 1.0 if same_region else 0.55, "reason": "Remote role, " + ("same region" if same_region else "cross-region"),
                "relocation": False}
    if cand["willing_to_relocate"] and (jl["city"] in cand.get("relocation_preferences", []) or job.get("relocation_supported")):
        return {"score": 0.8, "reason": f"Willing to relocate to {jl['city']}", "relocation": True}
    if cand["willing_to_relocate"]:
        return {"score": 0.6, "reason": "Open to relocation", "relocation": True}
    if cand["country"] == jl["country"]:
        return {"score": 0.45, "reason": "Same country, different city", "relocation": True}
    return {"score": 0.15, "reason": "Different country, not open to relocation", "relocation": True}


def interest_signal(cand: dict, job: dict, applied: set[str]) -> dict:
    if cand["employee_id"] in applied:
        return {"score": 1.0, "reason": "Applied to this role"}
    if job["role_family"] in cand.get("target_roles", []):
        return {"score": 0.7, "reason": f"Career goal: {job['role_family']}"}
    if cand.get("open_to_move"):
        return {"score": 0.4, "reason": "Open to internal move"}
    return {"score": 0.1, "reason": "No stated interest"}


def ml_features(cand: dict, job: dict, sf: dict, adj: dict, av: dict, loc: dict, applied: set[str]) -> dict:
    return {"skill_coverage": sf["coverage"], "proficiency_gap": sf["proficiency_gap"], "adjacency_score": adj["score"],
            "same_location": loc["score"] >= 1.0, "relocated": loc["relocation"], "applied_voluntarily": cand["employee_id"] in applied,
            "last_rating": cand.get("last_rating", 3), "tenure_years": cand.get("tenure_years", 2),
            "level_delta": LEVEL_NUM.get(job["level"], 2) - LEVEL_NUM.get(cand["level"], 2), "availability_gap_days": av["gap_days"]}


def combine(parts: dict) -> float:
    return round(100 * sum(WEIGHTS[k] * parts[k] for k in WEIGHTS), 2)


def level_ok(cand: dict, job: dict) -> bool:
    delta = LEVEL_NUM.get(job["level"], 2) - LEVEL_NUM.get(cand["level"], 2)
    return -1 <= delta <= 1
