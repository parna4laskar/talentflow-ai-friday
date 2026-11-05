"""Graph store: property graph of skills, employees, sites and roles (NetworkX, persisted).

Schema (Neo4j-compatible labels):
  (Employee)-[:HAS_SKILL {level}]->(Skill)
  (Skill)-[:ADJACENT_TO {weight}]->(Skill)
  (Employee)-[:LOCATED_IN]->(Site)
  (Employee)-[:REPORTS_TO]->(Employee)
  (Role)-[:REQUIRES]->(Skill)
"""
from __future__ import annotations

import pickle
import threading

import networkx as nx

from app.core.config import get_settings

_G: nx.MultiDiGraph | None = None
_lock = threading.Lock()


def _path():
    return get_settings().runtime_dir / "graph" / "talent_graph.pkl"


def graph() -> nx.MultiDiGraph:
    global _G
    if _G is None:
        with _lock:
            if _G is None:
                p = _path()
                _G = pickle.loads(p.read_bytes()) if p.exists() else nx.MultiDiGraph()
    return _G


def save(G: nx.MultiDiGraph):
    global _G
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(pickle.dumps(G))
    _G = G


def skill_node(name: str) -> str:
    return f"skill:{name}"


def neighbors(skill: str, min_weight: float = 0.0) -> list[dict]:
    G = graph()
    node = skill_node(skill)
    if node not in G:
        return []
    out = []
    for _, tgt, data in G.out_edges(node, data=True):
        if data.get("type") == "ADJACENT_TO" and data["weight"] >= min_weight:
            out.append({"skill": tgt.split(":", 1)[1], "weight": data["weight"]})
    return sorted(out, key=lambda x: -x["weight"])


def adjacency_weight(a: str, b: str) -> float:
    """Best transfer weight from skill a to b: direct edge, or a 2-hop path (product of weights)."""
    if a == b:
        return 1.0
    G = graph()
    na, nb = skill_node(a), skill_node(b)
    if na not in G or nb not in G:
        return 0.0
    best = 0.0
    for _, mid, d1 in G.out_edges(na, data=True):
        if d1.get("type") != "ADJACENT_TO":
            continue
        if mid == nb:
            best = max(best, d1["weight"])
            continue
        for _, tgt, d2 in G.out_edges(mid, data=True):
            if tgt == nb and d2.get("type") == "ADJACENT_TO":
                best = max(best, d1["weight"] * d2["weight"] * 0.8)
    return round(best, 3)


def skill_path(a: str, b: str) -> list[str]:
    G = graph()
    sub = nx.DiGraph((u, v) for u, v, d in G.edges(data=True) if d.get("type") == "ADJACENT_TO")
    try:
        return [n.split(":", 1)[1] for n in nx.shortest_path(sub, skill_node(a), skill_node(b))]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def stats() -> dict:
    G = graph()
    kinds: dict[str, int] = {}
    for _, d in G.nodes(data=True):
        kinds[d.get("label", "?")] = kinds.get(d.get("label", "?"), 0) + 1
    return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "by_label": kinds}
