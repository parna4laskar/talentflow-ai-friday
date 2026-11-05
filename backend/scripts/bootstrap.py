"""Load seed data into every store and train the ML outcome model.

    python backend/scripts/bootstrap.py            # full load
    python backend/scripts/bootstrap.py --skip-vector

Stores populated:
  Relational (SQLite)  employees, employee_skills, skills, jobs, applications, placements, users
  NoSQL (TinyDB)       profiles (full nested employee documents)
  Vector (ChromaDB)    resumes, jobs, skills, policies (local MiniLM embeddings)
  Graph (NetworkX)     Employee / Skill / Site / Role property graph
  File store           résumés + policies (already on disk), reports dir
  Model registry       outcome_model.joblib + model card
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bcrypt  # noqa: E402
import networkx as nx  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.ml import outcome_model  # noqa: E402
from app.storage import document, files, graph, vector  # noqa: E402
from app.storage.relational import (Application, Employee, EmployeeSkill, Job, Placement, Skill, User, init_db,  # noqa: E402
                                    session)

DEMO_PASSWORD = "Demo@123"


def load(name):
    return json.loads((get_settings().seed_dir / f"{name}.json").read_text(encoding="utf-8"))


def step(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_relational(emps, skills, jobs, apps, placements, users):
    init_db(drop=True)
    with session() as s:
        s.add_all(Skill(skill_id=k["skill_id"], name=k["name"], category=k["category"], description=k["description"],
                        market_growth_index=k["market_growth_index"], demand_trend=k["demand_trend"]) for k in skills)
        for e in emps:
            a, m, ci = e["availability"], e["mobility"], e["career_interests"]
            row = Employee(
                employee_id=e["employee_id"], full_name=e["full_name"], email=e["email"], gender=e["gender"], age_band=e["age_band"],
                department=e["department"], role_family=e["role_family"], title=e["title"], level=e["level"],
                years_experience=e["years_experience"], hire_date=e["hire_date"], tenure_years=e["tenure_years"],
                months_in_role=e["months_in_role"], city=e["location"]["city"], country=e["location"]["country"],
                region=e["location"]["region"], work_mode_preference=e["work_mode_preference"],
                willing_to_relocate=e["willing_to_relocate"], relocation_preferences=e["relocation_preferences"],
                manager_id=e["manager_id"], is_people_manager=e["is_people_manager"], availability_status=a["status"],
                allocation_pct=a["current_allocation_pct"], project_end=a["current_project_end"], available_from=a["available_from"],
                notice_weeks=a["notice_weeks"], on_performance_plan=m["on_performance_plan"], eligible_for_move=m["eligible_for_move"],
                retention_risk=m["retention_risk"], last_rating=e["performance"][-1]["rating"], open_to_move=ci["open_to_move"],
                target_roles=ci["target_roles"], certifications=e["certifications"], languages=e["languages"],
                education=e["education"], resume_summary=e["resume_summary"])
            row.skills = [EmployeeSkill(skill=k["name"], category=k["category"], proficiency=k["proficiency"], years=k["years"],
                                        last_used=k["last_used"], verified=k["verified"], source=k["source"]) for k in e["skills"]]
            s.add(row)
        for j in jobs:
            s.add(Job(job_id=j["job_id"], title=j["title"], role_family=j["role_family"], level=j["level"], department=j["department"],
                      hiring_manager_id=j["hiring_manager_id"], hiring_manager_name=j["hiring_manager_name"], city=j["location"]["city"],
                      country=j["location"]["country"], region=j["location"]["region"], work_mode=j["work_mode"],
                      relocation_supported=j["relocation_supported"], posted_on=j["posted_on"], start_date=j["start_date"],
                      status=j["status"], priority=j["priority"], openings=j["openings"], min_years_experience=j["min_years_experience"],
                      required_skills=j["required_skills"], nice_to_have_skills=j["nice_to_have_skills"], domain=j["domain"],
                      client=j["client"], description=j["description"], contains_biased_language=j["contains_biased_language"]))
        s.flush()
        s.add_all(Application(**a) for a in apps)
        s.add_all(Placement(placement_id=p["placement_id"], employee_id=p["employee_id"], move_date=p["move_date"],
                            from_department=p["from_department"], to_department=p["to_department"], from_role=p["from_role"],
                            region=p["region"], time_to_fill_days=p["time_to_fill_days"],
                            cost_avoided_usd=p["external_hire_cost_avoided_usd"], features=p["features"],
                            success=p["outcome"]["success"], retained_12m=p["outcome"]["retained_12m"],
                            post_move_rating=p["outcome"]["post_move_rating"]) for p in placements)
        pw = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()
        s.add_all(User(password_hash=pw, **u) for u in users)
        s.commit()


def load_documents(emps):
    document.truncate("profiles")
    document.insert_many("profiles", emps)


def resume_embedding_text(e):
    top = sorted(e["skills"], key=lambda s: -s["proficiency"])
    return (f"{e['title']} in {e['department']}. " + e["resume_summary"] + " Skills: " +
            ", ".join(f"{s['name']} ({s['proficiency']}/5)" for s in top) + ". Projects: " +
            "; ".join(p["name"] for p in e["projects"]) + ". Target roles: " + ", ".join(e["career_interests"]["target_roles"]))


def load_vectors(emps, jobs, skills):
    for name in vector.COLLECTIONS:
        vector.reset(name)
    step("  embedding résumés …")
    vector.upsert("resumes", [e["employee_id"] for e in emps], [resume_embedding_text(e) for e in emps],
                  [{"department": e["department"], "role_family": e["role_family"], "level": e["level"], "city": e["location"]["city"],
                    "region": e["location"]["region"], "availability": e["availability"]["status"],
                    "eligible": e["mobility"]["eligible_for_move"]} for e in emps])
    step("  embedding jobs, skills, policies …")
    vector.upsert("jobs", [j["job_id"] for j in jobs], [f"{j['title']}. {j['description']}" for j in jobs],
                  [{"status": j["status"], "role_family": j["role_family"], "region": j["location"]["region"]} for j in jobs])
    vector.upsert("skills", [k["skill_id"] for k in skills], [f"{k['name']}: {k['description']}" for k in skills],
                  [{"name": k["name"], "category": k["category"]} for k in skills])
    ids, texts, metas = [], [], []
    for p in files.policy_files():
        doc_title = p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        sections = re.split(r"\n(?=## )", p.read_text(encoding="utf-8"))
        for i, sec in enumerate(sections):
            ids.append(f"{p.stem}#{i}")
            texts.append(sec.strip())
            heading = sec.strip().splitlines()[0].lstrip("# ").strip()
            metas.append({"source": p.name, "document": doc_title, "section": heading})
    vector.upsert("policies", ids, texts, metas)


def load_graph(emps, skills, jobs, transitions):
    G = nx.MultiDiGraph()
    for k in skills:
        G.add_node(graph.skill_node(k["name"]), label="Skill", name=k["name"], category=k["category"], growth=k["market_growth_index"])
    for k in skills:
        for a in k["adjacent"]:
            G.add_edge(graph.skill_node(k["name"]), graph.skill_node(a["skill"]), type="ADJACENT_TO", weight=a["weight"])
    for e in emps:
        en = f"emp:{e['employee_id']}"
        G.add_node(en, label="Employee", name=e["full_name"], role=e["role_family"])
        site = f"site:{e['location']['city']}"
        G.add_node(site, label="Site", name=e["location"]["city"], region=e["location"]["region"])
        G.add_edge(en, site, type="LOCATED_IN")
        for s in e["skills"]:
            G.add_edge(en, graph.skill_node(s["name"]), type="HAS_SKILL", level=s["proficiency"])
        if e["manager_id"]:
            G.add_edge(en, f"emp:{e['manager_id']}", type="REPORTS_TO")
    for role, targets in transitions.items():
        G.add_node(f"role:{role}", label="Role", name=role)
        for t in targets:
            G.add_edge(f"role:{role}", f"role:{t}", type="CAREER_PATH")
    for j in jobs:
        for r in j["required_skills"]:
            G.add_edge(f"role:{j['role_family']}", graph.skill_node(r["name"]), type="REQUIRES", weight=r["weight"])
    graph.save(G)
    return G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-vector", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    emps, skills, jobs, apps = load("employees"), load("skills"), load("jobs"), load("applications")
    placements, users, transitions = load("placements"), load("users"), load("role_transitions")
    step(f"Relational: {len(emps)} employees, {len(jobs)} jobs, {len(apps)} applications, {len(placements)} placements")
    load_relational(emps, skills, jobs, apps, placements, users)
    step("NoSQL: profile documents")
    load_documents(emps)
    if not args.skip_vector:
        step("Vector: embeddings (local MiniLM)")
        load_vectors(emps, jobs, skills)
    step("Graph: talent graph")
    G = load_graph(emps, skills, jobs, transitions)
    step(f"  graph nodes={G.number_of_nodes()} edges={G.number_of_edges()}")
    step("ML: training outcome model")
    card = outcome_model.train([{"features": p["features"], "success": p["outcome"]["success"]} for p in placements])
    step(f"  AUC={card['auc']} accuracy={card['accuracy']} top features={[f['feature'] for f in card['feature_importance'][:3]]}")
    step(f"Done in {time.time() - t0:.0f}s. Demo password for all personas: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
