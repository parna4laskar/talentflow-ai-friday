"""Leadership & dashboard analytics: KPIs, trends, supply/demand, mobility flows."""
from __future__ import annotations

import asyncio
from collections import defaultdict

from sqlalchemy import func, select

from app import mcp_client
from app.storage.cache import cached
from app.storage.relational import MatchResult, MatchRun, Placement, Skill, session


@cached("insights:history", ttl=120)
def _history() -> dict:
    with session() as s:
        hist = [p for p in s.execute(select(Placement).where(Placement.source == "historical")).scalars()]
        growth = {k.name: k.market_growth_index for k in s.execute(select(Skill)).scalars()}
        runs = s.scalar(select(func.count()).select_from(MatchRun))
        approved = s.scalar(select(func.count()).select_from(MatchResult).where(MatchResult.decision == "approved"))
        reviewed = s.scalar(select(func.count()).select_from(MatchResult).where(MatchResult.decision != "pending"))
        hidden = sum(1 for (b,) in s.execute(select(MatchResult.breakdown)) if b.get("hidden_fit"))
    monthly = defaultdict(lambda: {"moves": 0, "ttf": 0, "success": 0, "cost": 0})
    flows = defaultdict(int)
    for p in hist:
        m = monthly[p.move_date[:7]]
        m["moves"] += 1
        m["ttf"] += p.time_to_fill_days
        m["success"] += p.success
        m["cost"] += p.cost_avoided_usd
        if p.from_department != p.to_department:
            flows[(p.from_department, p.to_department)] += 1
    if monthly:  # drop the trailing partial month so the trend does not show a false dip
        last = max(monthly)
        if monthly[last]["moves"] < 0.5 * (sum(v["moves"] for v in monthly.values()) / len(monthly)):
            monthly.pop(last)
    trend = [{"month": k, "internal_moves": v["moves"], "avg_time_to_fill_days": round(v["ttf"] / v["moves"], 1),
              "success_rate": round(v["success"] / v["moves"], 3), "cost_avoided_usd": v["cost"]} for k, v in sorted(monthly.items())]
    return {"trend": trend, "flows": sorted(({"from": a, "to": b, "moves": n} for (a, b), n in flows.items()), key=lambda d: -d["moves"])[:20],
            "growth": growth, "runs": runs, "approved": approved, "reviewed": reviewed, "hidden_fits": hidden,
            "total_cost_avoided": sum(p.cost_avoided_usd for p in hist), "total_moves": len(hist),
            "avg_ttf": round(sum(p.time_to_fill_days for p in hist) / max(1, len(hist)), 1),
            "success_rate": round(sum(p.success for p in hist) / max(1, len(hist)), 3)}


async def overview() -> dict:
    emp, jobs = await asyncio.gather(mcp_client.call("employee", "employee_stats", {}), mcp_client.call("jobs", "job_stats", {}))
    h = await asyncio.to_thread(_history)
    supply = {r["skill"]: r for r in emp["skill_supply"]}
    demand = jobs["skill_demand"][:16]
    sd = [{"skill": d["skill"], "open_roles": d["open_roles"], "employees": supply.get(d["skill"], {}).get("employees", 0),
           "avg_proficiency": supply.get(d["skill"], {}).get("avg_proficiency", 0), "growth": h["growth"].get(d["skill"], 1.0)} for d in demand]
    filled = jobs["by_status"].get("Filled", 0)
    closed = jobs["by_status"].get("Closed", 0)
    hot = sorted(({"skill": k, "growth": v, "employees": supply.get(k, {}).get("employees", 0)} for k, v in h["growth"].items() if v >= 1.15),
                 key=lambda d: -d["growth"])[:10]
    return {
        "kpis": {"headcount": emp["headcount"], "eligible_for_move": emp["eligible_for_move"],
                 "open_roles": jobs["by_status"].get("Open", 0) + jobs["by_status"].get("In Review", 0),
                 "internal_fill_rate": round(filled / max(1, filled + closed), 3), "avg_time_to_fill_days": h["avg_ttf"],
                 "cost_avoided_usd": h["total_cost_avoided"], "internal_moves_36m": h["total_moves"], "move_success_rate": h["success_rate"],
                 "matching_runs": h["runs"], "hidden_fits_surfaced": h["hidden_fits"],
                 "approval_rate": round(h["approved"] / h["reviewed"], 3) if h["reviewed"] else None},
        "trend": h["trend"], "flows": h["flows"], "supply_demand": sd, "hot_skills": hot,
        "by_department": emp["by_department"], "by_region": emp["by_region"], "by_availability": emp["by_availability"],
        "by_level": emp["by_level"], "by_retention_risk": emp["by_retention_risk"], "open_by_department": jobs["open_by_department"],
        "applications_by_status": jobs["applications_by_status"],
    }
