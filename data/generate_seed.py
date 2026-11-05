"""Deterministic, high-quality synthetic data generator for TalentFlow AI.

Produces (in data/seed/):
  skills.json          ~120 skills with category, description, market growth, adjacency
  employees.json       3,000 employee profiles (structured)
  jobs.json            180 internal job postings with free-text JDs (unstructured)
  applications.json    ~5,000 applications with cover notes
  placements.json      3,200 historical internal moves (ML training data + trends)
  users.json           persona login accounts
  market_intel.json    cached "Google search" results for market skill demand
and data/files/resumes/<employee_id>.txt (3,000 unstructured résumés).

Run:  python data/generate_seed.py
"""
from __future__ import annotations

import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import (ADJACENCY_GROUPS, DOMAINS, EXTRA_LANGS, FIRST_NAMES, LANGUAGES,  # noqa: E402
                      LAST_NAMES, LEVELS, ROLE_WEIGHTS, ROLES, SITES, SKILLS)

SEED = 20261105
TODAY = date(2026, 11, 5)
N_EMPLOYEES = 3000
N_JOBS = 180
N_PLACEMENTS = 3200

ROOT = Path(__file__).parent
OUT = ROOT / "seed"
RESUMES = ROOT / "files" / "resumes"
rng = random.Random(SEED)

SKILL_CATEGORY = {name: cat for cat, items in SKILLS.items() for name, _, _ in items}
SKILL_GROWTH = {name: g for items in SKILLS.values() for name, _, g in items}
ADJ: dict[str, dict[str, float]] = {}
CLIENT_BY_DOMAIN = {"retail banking": "retail bank", "wealth management": "wealth manager", "insurance claims": "insurer",
                    "healthcare": "hospital network", "telecom billing": "telecom operator", "supply-chain logistics": "logistics company",
                    "e-commerce": "online retailer", "energy trading": "energy company", "payments": "payments provider",
                    "manufacturing IoT": "manufacturer", "public sector": "government agency", "pharma R&D": "pharma company",
                    "media streaming": "streaming platform", "HR tech": "HR software company", "airline operations": "airline",
                    "automotive": "car maker"}


def client_for(domain):
    return f"{rng.choice(['a leading', 'a global', 'a tier-1', 'a fast-growing', 'a European', 'a US', 'an APAC'])} {CLIENT_BY_DOMAIN[domain]}"


def wchoice(items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def rand_date(start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, max(0, (end - start).days)))


# ---------------------------------------------------------------- skills + adjacency
def build_skills():
    adj: dict[str, dict[str, float]] = {s: {} for s in SKILL_CATEGORY}
    for w, group in ADJACENCY_GROUPS:
        for a in group:
            for b in group:
                if a != b:
                    adj[a][b] = max(adj[a].get(b, 0), w)
    skills = []
    for i, (cat, items) in enumerate(SKILLS.items()):
        for name, desc, growth in items:
            skills.append({
                "skill_id": f"SK{len(skills) + 1:03d}", "name": name, "category": cat, "description": desc,
                "market_growth_index": growth,
                "demand_trend": "Hot" if growth >= 1.25 else "Rising" if growth >= 1.08 else "Stable" if growth >= 0.99 else "Declining",
                "adjacent": [{"skill": k, "weight": v} for k, v in sorted(adj[name].items(), key=lambda x: -x[1])],
            })
    return skills, adj


# ---------------------------------------------------------------- role transitions (career paths)
def role_skillset(role):
    r = ROLES[role]
    s = set()
    for c in r["core"]:
        s.update(c.split("|"))
    s.update(r["opt"])
    return s


def build_transitions():
    sets = {r: role_skillset(r) for r in ROLES}
    trans = {}
    for r in ROLES:
        sims = sorted(((len(sets[r] & sets[o]) / len(sets[r] | sets[o]), o) for o in ROLES if o != r), reverse=True)
        trans[r] = [o for _, o in sims[:4]]
    # meaningful upward / lateral paths
    extra = {"Backend Engineer": ["Software Architect", "Engineering Manager", "AI Engineer"],
             "Full Stack Engineer": ["Software Architect", "AI Engineer"], "Data Engineer": ["ML Engineer", "AI Engineer"],
             "Data Scientist": ["AI Engineer", "ML Engineer"], "Data Analyst": ["Data Scientist", "Product Manager"],
             "QA Engineer": ["DevOps Engineer", "Backend Engineer"], "Business Analyst": ["Product Manager", "Scrum Master"],
             "Project Manager": ["Program Manager"], "DevOps Engineer": ["Platform Engineer", "Site Reliability Engineer"],
             "Security Analyst": ["Security Engineer"], "Scrum Master": ["Project Manager", "Program Manager"]}
    for k, v in extra.items():
        trans[k] = list(dict.fromkeys(v + trans[k]))[:5]
    return trans


# ---------------------------------------------------------------- employees
def make_name(country, gender):
    pool = FIRST_NAMES[country]
    g = gender if gender in ("F", "M") else rng.choice(["F", "M"])
    first = rng.choice(pool[g])
    # some cross-region diversity
    last_country = country if rng.random() > 0.12 else rng.choice(list(LAST_NAMES))
    return first, rng.choice(LAST_NAMES[last_country])


def proficiency(level_idx, kind):
    base = {"core": 2.6, "opt": 2.0, "stretch": 1.4}[kind] + level_idx * 0.45
    return int(clamp(round(rng.gauss(base, 0.7)), 1, 5))


TECH_DEPTS = {"Engineering", "Cloud & Infrastructure", "Data & Analytics", "AI Center of Excellence", "Cyber Security",
              "Quality Engineering", "Enterprise Applications"}
P_IMP = {"proc": "reducing processing time by {n}%", "cloud": "cutting cloud spend by {n}%", "conv": "improving conversion by {n}%",
         "nps": "lifting NPS by {n} points", "inc": "reducing production incidents by {n}%", "hrs": "saving ~{n}K hours annually",
         "rel": "accelerating releases by {n}%", "acc": "improving model accuracy by {n}%", "cov": "raising automated test coverage to {k}%",
         "cli": "onboarding {s} new enterprise clients", "risk": "closing {n}% of open audit findings", "cost": "delivering ${s}M in cost savings",
         "time": "cutting time-to-hire by {n}%", "eng": "raising engagement scores by {s} points", "rev": "growing account revenue by {n}%",
         "fc": "improving forecast accuracy by {n}%", "ontime": "delivering on time across {s} workstreams", "lead": "growing qualified leads by {n}%"}
PROJECTS = {
    "Engineering": (["Built", "Led the delivery of", "Modernised", "Designed", "Migrated", "Scaled", "Automated", "Re-architected"],
                    {"customer onboarding platform": ["proc", "conv", "nps"], "claims processing engine": ["proc", "hrs"],
                     "self-service portal": ["nps", "hrs"], "mobile banking app": ["conv", "nps"], "pricing engine": ["conv", "proc"],
                     "order management system": ["proc", "cli"], "payments microservices platform": ["proc", "inc", "rel"]}),
    "Cloud & Infrastructure": (["Built", "Led the delivery of", "Modernised", "Designed", "Migrated", "Scaled", "Automated", "Re-architected"],
                               {"cloud landing zone": ["cloud", "rel"], "observability stack": ["inc", "rel"],
                                "Kubernetes platform": ["cloud", "rel", "inc"], "CI/CD platform": ["rel"], "data-centre exit to cloud": ["cloud", "cost"]}),
    "Data & Analytics": (["Built", "Led the delivery of", "Modernised", "Designed", "Migrated", "Scaled", "Automated", "Re-architected"],
                         {"real-time analytics pipeline": ["proc", "cloud"], "data lakehouse": ["cloud", "proc"],
                          "regulatory reporting suite": ["proc", "hrs"], "executive KPI dashboard suite": ["hrs", "fc"],
                          "customer churn model": ["acc", "conv"]}),
    "AI Center of Excellence": (["Built", "Led the delivery of", "Modernised", "Designed", "Migrated", "Scaled", "Automated", "Re-architected"],
                                {"knowledge assistant (RAG)": ["hrs", "nps"], "fraud detection model": ["acc", "proc"],
                                 "recommendation engine": ["conv", "acc"], "document intelligence pipeline": ["hrs", "proc"],
                                 "agentic customer-service assistant": ["hrs", "nps"]}),
    "Cyber Security": (["Built", "Led the delivery of", "Modernised", "Designed", "Migrated", "Scaled", "Automated", "Re-architected"],
                       {"identity and access platform": ["inc", "risk"], "security operations centre uplift": ["inc", "risk"],
                        "cloud security posture programme": ["risk", "inc"], "secure SDLC rollout": ["inc", "rel"]}),
    "Quality Engineering": (["Built", "Led the delivery of", "Modernised", "Designed", "Migrated", "Scaled", "Automated", "Re-architected"],
                            {"test automation framework": ["cov", "rel"], "performance engineering programme": ["inc", "rel"],
                             "API contract-testing suite": ["cov", "inc"]}),
    "Enterprise Applications": (["Built", "Led the delivery of", "Modernised", "Designed", "Migrated", "Scaled", "Automated", "Re-architected"],
                                {"ERP finance rollout": ["proc", "hrs"], "CRM rollout": ["conv", "proc"], "service desk automation": ["hrs", "proc"]}),
    "Product": (["Owned", "Launched", "Led discovery for", "Defined the roadmap for"],
                {"checkout experience": ["conv", "nps"], "mobile app relaunch": ["nps", "conv"], "B2B analytics product": ["cli", "rev"],
                 "AI-assisted customer journey": ["conv", "hrs"]}),
    "Design": (["Designed", "Redesigned", "Ran research for", "Led UX for"],
               {"customer self-service journey": ["nps", "conv"], "enterprise design system": ["rel", "nps"], "onboarding flow": ["conv", "nps"]}),
    "delivery": (["Led", "Ran", "Delivered", "Coordinated"],
                 {"core banking transformation programme": ["ontime", "cost"], "cloud migration programme": ["ontime", "cloud"],
                  "agile transformation": ["rel", "ontime"], "process re-engineering initiative": ["proc", "cost"],
                  "requirements and UAT for a CRM rollout": ["ontime", "proc"]}),
    "finance": (["Built", "Led", "Owned", "Redesigned"],
                {"rolling forecasting model": ["fc", "hrs"], "cost transformation programme": ["cost"], "risk control framework": ["risk"],
                 "regulatory capital reporting": ["risk", "proc"]}),
    "Human Resources": (["Led", "Designed", "Rolled out", "Ran"],
                        {"graduate hiring programme": ["time"], "performance management redesign": ["eng"], "Workday HCM rollout": ["hrs", "proc"],
                         "leadership development academy": ["eng"], "people analytics dashboard": ["time", "hrs"]}),
    "commercial": (["Led", "Planned", "Ran", "Grew"],
                   {"product launch campaign": ["lead", "conv"], "strategic account growth plan": ["rev"], "SEO content programme": ["lead"],
                    "partner channel strategy": ["rev", "lead"]}),
}
GROUP = {"Product": "Product", "Design": "Design", "Business Consulting": "delivery", "Delivery Excellence": "delivery",
         "Finance": "finance", "Risk & Compliance": "finance", "Human Resources": "Human Resources", "Marketing": "commercial", "Sales": "commercial"}
SMALL = {"and", "for", "of", "a", "the", "in"}


def title_case(text):
    return " ".join(w if (w.isupper() or "(" in w) else (w if w in SMALL and i else w[0].upper() + w[1:]) for i, w in enumerate(text.split()))


def make_projects(role, dept, skills, years_exp, domain_pref):
    n = 2 if years_exp < 3 else rng.randint(3, 4)
    verbs, artefacts = PROJECTS[dept if dept in TECH_DEPTS else GROUP[dept]]
    projects = []
    end = TODAY + timedelta(days=rng.randint(-20, 200))
    for i in range(n):
        start = end - timedelta(days=rng.randint(5, 18) * 30)
        used = rng.sample(skills, k=min(len(skills), rng.randint(2, 4)))
        domain = domain_pref if rng.random() < 0.5 else rng.choice(DOMAINS)
        art = rng.choice(list(artefacts))
        impact = P_IMP[rng.choice(artefacts[art])].format(n=rng.choice([12, 18, 22, 25, 30, 35, 40]), k=rng.choice([70, 80, 85, 90]),
                                                          s=rng.choice([2, 3, 4, 5, 6, 8]))
        client = client_for(domain)
        projects.append({
            "name": title_case(f"{domain} {art}"), "client": client, "domain": domain,
            "role": role, "start": start.isoformat(), "end": end.isoformat() if i > 0 else None, "skills": used,
            "description": f"{rng.choice(verbs)} {'an' if art[0].lower() in 'aeiou' else 'a'} {art} for {client} in {domain} using {', '.join(used[:-1])} and {used[-1]}, {impact}.",
        })
        end = start - timedelta(days=rng.randint(10, 90))
    return projects


EDU = {"Engineering": ["B.Tech Computer Science", "B.E. Information Technology", "M.Tech Software Systems", "BSc Computer Science", "MSc Computer Science"],
       "Cloud & Infrastructure": ["B.E. Electronics & Telecommunication", "B.Tech Computer Science", "BSc Information Systems"],
       "Data & Analytics": ["M.Sc Statistics", "B.Tech Computer Science", "MSc Data Science", "M.Sc Mathematics"],
       "AI Center of Excellence": ["M.Tech Artificial Intelligence", "MSc Machine Learning", "PhD Computer Science", "B.Tech Computer Science"],
       "Cyber Security": ["B.Tech Computer Science", "MSc Cyber Security"], "Quality Engineering": ["B.E. Computer Engineering", "BCA", "B.Sc IT"],
       "Product": ["MBA", "B.Tech + MBA", "BSc Economics"], "Design": ["B.Des Interaction Design", "M.Des", "BA Psychology"],
       "Business Consulting": ["MBA", "B.Com", "BBA"], "Delivery Excellence": ["MBA", "B.E. Mechanical", "B.Tech Computer Science"],
       "Finance": ["Chartered Accountant", "MBA Finance", "B.Com", "MSc Finance"], "Enterprise Applications": ["MBA", "B.Com", "B.Tech"],
       "Human Resources": ["MBA HR", "MA Organisational Psychology", "BBA"], "Marketing": ["MBA Marketing", "BA Communications"],
       "Sales": ["MBA", "BBA"], "Risk & Compliance": ["LLB", "MBA Finance", "MSc Economics"]}


def build_employees(transitions):
    roles = list(ROLE_WEIGHTS)
    rweights = [ROLE_WEIGHTS[r] for r in roles]
    employees = []
    for i in range(N_EMPLOYEES):
        eid = f"EMP{10001 + i}"
        site = wchoice(SITES, [s[3] for s in SITES])
        city, country, region, _ = site
        gender = wchoice(["F", "M", "X"], [41, 57, 2])
        first, last = make_name(country, gender)
        role = wchoice(roles, rweights)
        lvl_i = wchoice(range(5), [l[4] for l in LEVELS])
        if role in ("Engineering Manager", "Program Manager", "Software Architect"):
            lvl_i = max(lvl_i, 3)
        code, prefix, ymin, ymax, _ = LEVELS[lvl_i]
        years = round(rng.uniform(ymin, ymax), 1)
        age = int(22 + years + rng.uniform(0, 4))
        age_band = "20-29" if age < 30 else "30-39" if age < 40 else "40-49" if age < 50 else "50+"
        r = ROLES[role]
        title = f"{prefix} {role}".strip()
        tenure = round(clamp(rng.uniform(0.3, min(years, 14) + 0.3), 0.3, years + 0.3), 1)
        hire_date = TODAY - timedelta(days=int(tenure * 365))
        months_in_role = int(clamp(rng.gauss(20, 11), 2, tenure * 12))

        # skills
        chosen, skills = set(), []
        for c in r["core"]:
            name = rng.choice(c.split("|"))
            if name in chosen:
                continue
            chosen.add(name)
            skills.append((name, proficiency(lvl_i, "core")))
        for name in rng.sample(r["opt"], k=min(len(r["opt"]), rng.randint(2, 5))):
            if name not in chosen:
                chosen.add(name)
                skills.append((name, proficiency(lvl_i, "opt")))
        # stretch / learning skills (often hot skills) — creates hidden-fit candidates
        hot = ["Generative AI", "LLM Engineering", "Agentic AI", "Kubernetes", "Terraform", "Databricks", "Playwright", "FinOps", "Responsible AI"]
        adjacent_pool = [b for a, _ in skills for b, w in ADJ[a].items() if w >= 0.5] or hot
        for _ in range(rng.choice([0, 1, 1, 2])):
            name = rng.choice(hot if rng.random() < 0.4 else adjacent_pool)
            if name not in chosen:
                chosen.add(name)
                skills.append((name, proficiency(lvl_i, "stretch")))
        if lvl_i >= 3:
            for name in ("Mentoring", "Stakeholder Management"):
                if name not in chosen and rng.random() < 0.6:
                    chosen.add(name)
                    skills.append((name, proficiency(lvl_i, "opt")))
        if "Communication" not in chosen and rng.random() < 0.4:
            skills.append(("Communication", proficiency(lvl_i, "opt")))
        skill_objs = []
        for name, p in skills:
            yrs = round(clamp(rng.uniform(0.5, years) * (p / 4), 0.3, years if years > 0.3 else 0.5), 1)
            skill_objs.append({
                "name": name, "category": SKILL_CATEGORY[name], "proficiency": p, "years": yrs,
                "last_used": rng.choice([2026, 2026, 2026, 2025, 2025, 2024]), "verified": rng.random() < 0.55,
                "source": rng.choice(["assessment", "manager", "self-declared", "project-evidence"]),
            })

        certs = []
        for c in r["certs"]:
            if rng.random() < 0.22 + 0.08 * lvl_i:
                certs.append({"name": c, "year": rng.randint(max(2016, TODAY.year - int(min(years, 5))), 2026)})
        langs = list(LANGUAGES[country])
        if rng.random() < 0.3:
            langs.append(rng.choice(EXTRA_LANGS))

        # availability
        a = wchoice(["Allocated", "Rolling off", "Partially available", "Available"], [55, 20, 12, 13])
        if a == "Allocated":
            end = TODAY + timedelta(days=rng.randint(45, 280)); alloc = 100
        elif a == "Rolling off":
            end = TODAY + timedelta(days=rng.randint(3, 44)); alloc = 100
        elif a == "Partially available":
            end = TODAY + timedelta(days=rng.randint(30, 180)); alloc = rng.choice([40, 50, 60])
        else:
            end = TODAY - timedelta(days=rng.randint(1, 40)); alloc = 0
        notice_weeks = rng.choice([0, 2, 2, 4, 4, 6]) if a != "Available" else 0
        available_from = max(TODAY, end) + timedelta(weeks=notice_weeks) if a in ("Allocated", "Rolling off") else TODAY

        perf = [{"cycle": "FY25", "rating": int(clamp(round(rng.gauss(3.3, 0.8)), 1, 5))},
                {"cycle": "FY26", "rating": int(clamp(round(rng.gauss(3.4, 0.8)), 1, 5))}]
        on_pip = perf[-1]["rating"] <= 1 and rng.random() < 0.6
        targets = rng.sample(transitions[role], k=rng.randint(1, 3))
        if rng.random() < 0.35:
            targets.insert(0, role)  # wants same role, new team
        open_to_move = rng.random() < (0.55 if months_in_role > 18 else 0.3)
        pref_mode = wchoice(["Onsite", "Hybrid", "Remote"], [15, 60, 25])
        relocate = rng.random() < 0.28
        reloc_cities = rng.sample([s[0] for s in SITES if s[0] != city], k=rng.randint(1, 3)) if relocate else []
        risk_score = (0.4 if months_in_role > 30 else 0) + (0.3 if open_to_move else 0) + (0.2 if perf[-1]["rating"] >= 4 else 0) + rng.uniform(0, 0.3)
        domain_pref = rng.choice(DOMAINS)

        top = sorted(skill_objs, key=lambda s: -s["proficiency"])[:4]
        summary = (f"{title} with {years:g} years of experience, based in {city}. Strong in "
                   f"{', '.join(s['name'] for s in top[:-1])} and {top[-1]['name']}, with recent work in {domain_pref}. "
                   f"Interested in moving towards {', '.join(targets[:2])} roles"
                   + (f" and open to relocating to {', '.join(reloc_cities)}." if relocate else "."))
        employees.append({
            "employee_id": eid, "first_name": first, "last_name": last, "full_name": f"{first} {last}",
            "email": f"{first.lower().replace(' ', '.')}.{last.lower().replace(' ', '').replace(chr(39), '')}.{10001 + i}@talentflow.ai",
            "gender": gender, "age_band": age_band, "department": r["dept"], "role_family": role, "title": title,
            "level": code, "years_experience": years, "hire_date": hire_date.isoformat(), "tenure_years": tenure,
            "months_in_role": months_in_role,
            "location": {"city": city, "country": country, "region": region},
            "work_mode_preference": pref_mode, "willing_to_relocate": relocate, "relocation_preferences": reloc_cities,
            "manager_id": None, "is_people_manager": False,
            "skills": skill_objs, "certifications": certs, "languages": langs,
            "education": rng.choice(EDU[r["dept"]]),
            "projects": make_projects(title, r["dept"], [s["name"] for s in skill_objs], years, domain_pref),
            "career_interests": {"target_roles": list(dict.fromkeys(targets)), "open_to_move": open_to_move,
                                 "preferred_work_mode": pref_mode,
                                 "aspiration": rng.choice([
                                     "Wants to grow into a technical leadership role.", "Keen to work on AI-driven products.",
                                     "Looking for client-facing exposure.", "Wants to deepen cloud architecture expertise.",
                                     "Interested in mentoring and people management.", "Seeks a role with global stakeholder exposure.",
                                     "Wants to move closer to product and business outcomes.", "Looking to specialise in data and analytics."])},
            "performance": perf,
            "availability": {"status": a, "current_allocation_pct": alloc, "current_project_end": end.isoformat(),
                             "available_from": available_from.isoformat(), "notice_weeks": notice_weeks},
            "mobility": {"on_performance_plan": on_pip, "manager_release_required": a != "Available",
                         "retention_risk": "High" if risk_score > 0.8 else "Medium" if risk_score > 0.45 else "Low",
                         "eligible_for_move": (months_in_role >= 12 or a == "Available") and not on_pip},
            "resume_summary": summary,
        })

    # managers: L4/L5 people get teams within their department
    by_dept: dict[str, list[dict]] = {}
    for e in employees:
        by_dept.setdefault(e["department"], []).append(e)
    for dept, members in by_dept.items():
        mgrs = [e for e in members if e["level"] in ("L4", "L5") and (e["role_family"] in ("Engineering Manager", "Program Manager") or rng.random() < 0.45)]
        if not mgrs:
            mgrs = sorted(members, key=lambda e: -e["years_experience"])[:2]
        for m in mgrs:
            m["is_people_manager"] = True
            if "People Leadership" not in {s["name"] for s in m["skills"]}:
                m["skills"].append({"name": "People Leadership", "category": "Delivery & Leadership", "proficiency": rng.randint(3, 5),
                                    "years": round(rng.uniform(1, 8), 1), "last_used": 2026, "verified": True, "source": "manager"})
        for e in members:
            if e in mgrs:
                continue
            same_region = [m for m in mgrs if m["location"]["region"] == e["location"]["region"]] or mgrs
            e["manager_id"] = rng.choice(same_region)["employee_id"]
    return employees


# ---------------------------------------------------------------- jobs
JD_INTROS = [
    "Our {dept} team is expanding its {domain} practice and is looking for an internal {title} to join a high-visibility programme for {client}.",
    "We are launching a new {domain} initiative and need a {title} who can hit the ground running and help shape the solution from day one.",
    "The {dept} group is hiring internally for a {title} to strengthen a cross-functional squad delivering a strategic {domain} transformation.",
    "Join the {domain} engagement for {client} as a {title}. This is a great opportunity for someone who wants to grow their impact across teams.",
]
BIASED_PHRASES = ["We are looking for a young and energetic rockstar who can work long hours.",
                  "Native English speaker preferred; recent graduates (under 30) will fit best with the team culture.",
                  "Ideal candidate is a culture fit with our guys in the team and has no family commitments limiting travel."]


def build_jobs(employees, transitions):
    mgrs = [e for e in employees if e["is_people_manager"]]
    jobs = []
    status_plan = ["Open"] * 70 + ["In Review"] * 25 + ["Filled"] * 60 + ["Closed"] * 25
    rng.shuffle(status_plan)
    roles = list(ROLE_WEIGHTS)
    weights = [ROLE_WEIGHTS[r] * (1.8 if r in ("AI Engineer", "ML Engineer", "Data Engineer", "Cloud Engineer", "Platform Engineer") else 1) for r in roles]
    for i in range(N_JOBS):
        status = status_plan[i]
        role = wchoice(roles, weights)
        r = ROLES[role]
        lvl_i = wchoice(range(5), [8, 30, 35, 20, 7])
        code, prefix, ymin, _, _ = LEVELS[lvl_i]
        title = f"{prefix} {role}".strip()
        dept_mgrs = [m for m in mgrs if m["department"] == r["dept"]] or mgrs
        hm = rng.choice(dept_mgrs)
        site = wchoice(SITES, [s[3] for s in SITES]) if rng.random() < 0.6 else next(s for s in SITES if s[0] == hm["location"]["city"])
        mode = wchoice(["Onsite", "Hybrid", "Remote"], [20, 60, 20])
        if status == "Open":
            posted = TODAY - timedelta(days=rng.randint(0, 45))
        elif status == "In Review":
            posted = TODAY - timedelta(days=rng.randint(15, 70))
        else:
            posted = rand_date(TODAY - timedelta(days=540), TODAY - timedelta(days=40))
        start = posted + timedelta(days=rng.randint(21, 75))
        req, used = [], set()
        for c in r["core"]:
            n = rng.choice(c.split("|"))
            if n not in used:
                used.add(n)
                req.append({"name": n, "min_proficiency": int(clamp(2 + lvl_i * 0.6 + rng.choice([0, 0, 1]), 2, 5)), "weight": round(rng.uniform(0.7, 1.0), 2)})
        if rng.random() < 0.45:  # many modern roles ask for a hot skill
            for n in rng.sample(["Generative AI", "Kubernetes", "Terraform", "Databricks", "LLM Engineering", "Agentic AI", "Cloud Security"], 1):
                if n not in used:
                    used.add(n)
                    req.append({"name": n, "min_proficiency": rng.choice([2, 3]), "weight": 0.6})
        nice = [n for n in rng.sample(r["opt"], k=min(3, len(r["opt"]))) if n not in used]
        domain = rng.choice(DOMAINS)
        client = client_for(domain)
        intro = rng.choice(JD_INTROS).format(dept=r["dept"], domain=domain, title=title, client=client)
        resp = [f"Own and deliver {req[0]['name']} work for the {domain} platform end to end.",
                f"Collaborate with product, design and engineering stakeholders across {site[2]}.",
                f"Apply {req[1]['name'] if len(req) > 1 else req[0]['name']} best practices and raise the quality bar.",
                "Mentor junior colleagues and contribute to the practice community." if lvl_i >= 2 else "Learn quickly from senior team members and grow your skills.",
                "Communicate progress, risks and trade-offs clearly to leadership."]
        must = [f"{s['name']} (proficiency {s['min_proficiency']}/5 or above)" for s in req]
        min_years = max(0, ymin + rng.choice([0, 1]))
        biased = rng.random() < 0.05
        jd = (f"{intro}\n\nWhat you will do:\n- " + "\n- ".join(resp) +
              f"\n\nMust have:\n- " + "\n- ".join(must) + f"\n- {min_years}+ years of relevant experience" +
              (f"\n\nNice to have:\n- " + "\n- ".join(nice) if nice else "") +
              f"\n\nLocation & logistics: {site[0]}, {site[1]} ({mode}). Expected start {start.strftime('%d %b %Y')}; "
              f"{rng.choice(['12-month assignment', 'permanent internal move', '6-month assignment with extension', '9-month assignment'])}."
              + (f"\n\n{rng.choice(BIASED_PHRASES)}" if biased else "\n\nWe welcome applications from all colleagues; flexible and accessible working arrangements are supported."))
        jobs.append({
            "job_id": f"JOB-{posted.year}-{i + 1:04d}", "title": title, "role_family": role, "level": code,
            "department": r["dept"], "hiring_manager_id": hm["employee_id"], "hiring_manager_name": hm["full_name"],
            "location": {"city": site[0], "country": site[1], "region": site[2]}, "work_mode": mode,
            "relocation_supported": rng.random() < 0.4, "posted_on": posted.isoformat(), "start_date": start.isoformat(),
            "status": status, "priority": wchoice(["Critical", "High", "Medium", "Low"], [10, 30, 45, 15]),
            "openings": wchoice([1, 1, 1, 2, 3], [1, 1, 1, 1, 1]), "min_years_experience": min_years,
            "required_skills": req, "nice_to_have_skills": nice, "domain": domain, "client": client,
            "description": jd, "contains_biased_language": biased,
        })
    return jobs


# ---------------------------------------------------------------- applications
COVER = ["I have spent the last {m} months on {skill} work and would love to apply it to {domain}.",
         "This role matches my goal of moving into {role}. My recent project used {skill} extensively.",
         "My current project ends soon and I am keen to bring my {skill} experience to this team.",
         "I have been upskilling in {skill} and believe this is the right next step for my career.",
         "I would bring strong {skill} skills and experience working with global stakeholders."]


def fit_score(e, job):
    sk = {s["name"]: s["proficiency"] for s in e["skills"]}
    req = job["required_skills"]
    return sum(min(1, sk.get(r["name"], 0) / r["min_proficiency"]) for r in req) / len(req)


def build_applications(employees, jobs):
    apps = []
    by_family: dict[str, list[dict]] = {}
    for e in employees:
        for t in [e["role_family"]] + e["career_interests"]["target_roles"]:
            by_family.setdefault(t, []).append(e)
    n = 0
    for job in jobs:
        pool = by_family.get(job["role_family"], [])
        k = {"Open": rng.randint(8, 30), "In Review": rng.randint(15, 40), "Filled": rng.randint(18, 45), "Closed": rng.randint(5, 20)}[job["status"]]
        cands = rng.sample(pool, k=min(k, len(pool)))
        if rng.random() < 0.5:
            cands += rng.sample(employees, k=rng.randint(1, 5))
        cands = list({c["employee_id"]: c for c in cands}.values())
        cands.sort(key=lambda e: -fit_score(e, job))
        selected = set()
        if job["status"] == "Filled":
            selected = {c["employee_id"] for c in cands[: job["openings"]] if rng.random() < 0.85} or {cands[0]["employee_id"]}
        posted = date.fromisoformat(job["posted_on"])
        for rank, e in enumerate(cands):
            n += 1
            if job["status"] == "Filled":
                st = "Selected" if e["employee_id"] in selected else wchoice(["Rejected", "Withdrawn"], [80, 20])
            elif job["status"] == "Closed":
                st = wchoice(["Rejected", "Withdrawn"], [70, 30])
            elif job["status"] == "In Review":
                st = wchoice(["Screening", "Interview", "Shortlisted", "Rejected"], [35, 25, 15, 25]) if rank < 12 else wchoice(["Screening", "Rejected"], [50, 50])
            else:
                st = wchoice(["Applied", "Screening"], [75, 25])
            top = max(e["skills"], key=lambda s: s["proficiency"])["name"]
            apps.append({
                "application_id": f"APP{100000 + n}", "job_id": job["job_id"], "employee_id": e["employee_id"],
                "applied_on": min(TODAY, posted + timedelta(days=rng.randint(0, 30))).isoformat(), "status": st,
                "source": wchoice(["Self-applied", "Manager referral", "AI-recommended", "Talent partner sourced"], [60, 15, 15, 10]),
                "cover_note": rng.choice(COVER).format(m=rng.randint(6, 30), skill=top, domain=job["domain"], role=job["role_family"]),
            })
    return apps


# ---------------------------------------------------------------- historical placements (ML training)
def build_placements(employees):
    """Historic internal moves with a known 12-month outcome. The outcome is drawn from a
    latent model so the ML outcome model has real signal to learn (plus noise)."""
    depts = sorted({r["dept"] for r in ROLES.values()})
    rows = []
    for i in range(N_PLACEMENTS):
        e = rng.choice(employees)
        move = rand_date(TODAY - timedelta(days=1095), TODAY - timedelta(days=365))
        skill_cov = clamp(rng.betavariate(5, 2), 0, 1)
        prof_gap = clamp(rng.gauss(0.6, 0.6), 0, 3)
        adjacency = clamp(rng.betavariate(2, 3), 0, 1)
        same_loc = rng.random() < 0.62
        relocated = (not same_loc) and rng.random() < 0.5
        applied = rng.random() < 0.7
        perf = int(clamp(round(rng.gauss(3.4, 0.8)), 1, 5))
        tenure = round(rng.uniform(0.5, 12), 1)
        level_delta = wchoice([-1, 0, 1, 2], [5, 65, 27, 3])
        avail_gap = int(clamp(rng.gauss(20, 25), 0, 120))
        z = 1.5 * (-1.75 + 2.6 * skill_cov - 0.7 * prof_gap + 1.1 * adjacency + 0.35 * same_loc - 0.25 * relocated
             + 0.55 * applied + 0.45 * (perf - 3) - 0.6 * max(0, level_delta - 1) - 0.006 * avail_gap + 0.03 * min(tenure, 6)
             + rng.gauss(0, 0.3))
        p = 1 / (1 + math.exp(-z))
        success = rng.random() < p
        from_dept = e["department"]
        to_dept = from_dept if rng.random() < 0.55 else rng.choice(depts)
        rows.append({
            "placement_id": f"PLC{50000 + i}", "employee_id": e["employee_id"], "move_date": move.isoformat(),
            "from_department": from_dept, "to_department": to_dept, "from_role": e["role_family"],
            "region": e["location"]["region"], "time_to_fill_days": int(clamp(rng.gauss(24, 9), 4, 70)),
            "external_hire_cost_avoided_usd": int(clamp(rng.gauss(32000, 9000), 12000, 70000)),
            "features": {"skill_coverage": round(skill_cov, 3), "proficiency_gap": round(prof_gap, 3), "adjacency_score": round(adjacency, 3),
                         "same_location": same_loc, "relocated": relocated, "applied_voluntarily": applied, "last_rating": perf,
                         "tenure_years": tenure, "level_delta": level_delta, "availability_gap_days": avail_gap},
            "outcome": {"success": success, "retained_12m": success or rng.random() < 0.5,
                        "post_move_rating": int(clamp(round(rng.gauss(3.9 if success else 2.8, 0.6)), 1, 5))},
        })
    return rows


# ---------------------------------------------------------------- users + market intel + resumes
def build_users(employees, jobs):
    hm_ids = [j["hiring_manager_id"] for j in jobs if j["status"] == "Open"]
    hm1 = next(e for e in employees if e["employee_id"] == hm_ids[0])
    hm2 = next(e for e in employees if e["employee_id"] == hm_ids[1] and e["employee_id"] != hm1["employee_id"]) if len(hm_ids) > 1 else hm1
    emp = next(e for e in employees if e["role_family"] == "Backend Engineer" and e["career_interests"]["open_to_move"]
               and e["availability"]["status"] == "Rolling off" and e["mobility"]["eligible_for_move"])
    return [
        {"username": "hr.admin", "display_name": "Ritu Malhotra", "role": "hr_admin", "employee_id": None, "title": "HR Admin – Talent Mobility"},
        {"username": "hiring.manager", "display_name": hm1["full_name"], "role": "hiring_manager", "employee_id": hm1["employee_id"], "title": hm1["title"]},
        {"username": "hiring.manager2", "display_name": hm2["full_name"], "role": "hiring_manager", "employee_id": hm2["employee_id"], "title": hm2["title"]},
        {"username": "employee", "display_name": emp["full_name"], "role": "employee", "employee_id": emp["employee_id"], "title": emp["title"]},
        {"username": "leader", "display_name": "Arvind Krishnan", "role": "leadership", "employee_id": None, "title": "Chief People Officer"},
    ]


def build_market_intel(skills):
    out = {}
    for s in skills:
        g = s["market_growth_index"]
        yoy = round((g - 1) * 100)
        out[s["name"]] = {
            "query": f"{s['name']} skills demand 2026 enterprise hiring trends",
            "cached_on": TODAY.isoformat(), "provider": "google-search (cached sample)",
            "results": [
                {"title": f"{s['name']} demand outlook 2026 — sample market digest",
                 "snippet": f"Job postings mentioning {s['name']} changed by {yoy:+d}% year over year; trend classified as {s['demand_trend'].lower()}.",
                 "source": "Sample Market Digest (cached)"},
                {"title": f"Where {s['name']} talent is concentrated",
                 "snippet": f"{s['name']} is most often paired with {', '.join(a['skill'] for a in s['adjacent'][:3]) or 'adjacent skills'} in job descriptions.",
                 "source": "Sample Skills Graph Report (cached)"},
                {"title": f"Upskilling paths into {s['name']}",
                 "snippet": f"Typical ramp-up time to working proficiency in {s['name']} is {rng.randint(6, 20)} weeks for professionals with adjacent experience.",
                 "source": "Sample L&D Benchmark (cached)"},
            ],
        }
    return out


def write_resume(e):
    lines = [e["full_name"].upper(), f"{e['title']} | {e['department']} | {e['location']['city']}, {e['location']['country']}",
             f"Employee ID: {e['employee_id']}", "", "PROFESSIONAL SUMMARY", e["resume_summary"], "", "CORE SKILLS"]
    by_cat: dict[str, list[str]] = {}
    for s in sorted(e["skills"], key=lambda s: -s["proficiency"]):
        by_cat.setdefault(s["category"], []).append(f"{s['name']} ({['', 'Beginner', 'Working', 'Proficient', 'Advanced', 'Expert'][s['proficiency']]}, {s['years']}y)")
    for cat, items in by_cat.items():
        lines.append(f"- {cat}: {', '.join(items)}")
    lines += ["", "EXPERIENCE"]
    for p in e["projects"]:
        lines.append(f"* {p['name']} — {p['client']} ({p['start'][:7]} to {p['end'][:7] if p['end'] else 'present'})")
        lines.append(f"  {p['description']}")
    if e["certifications"]:
        lines += ["", "CERTIFICATIONS"] + [f"- {c['name']} ({c['year']})" for c in e["certifications"]]
    lines += ["", "EDUCATION", f"- {e['education']}", "", "LANGUAGES", ", ".join(e["languages"]),
              "", "CAREER ASPIRATIONS", e["career_interests"]["aspiration"],
              f"Target roles: {', '.join(e['career_interests']['target_roles'])}"]
    (RESUMES / f"{e['employee_id']}.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RESUMES.mkdir(parents=True, exist_ok=True)
    skills, adj = build_skills()
    ADJ.update(adj)
    transitions = build_transitions()
    employees = build_employees(transitions)
    jobs = build_jobs(employees, transitions)
    apps = build_applications(employees, jobs)
    placements = build_placements(employees)
    users = build_users(employees, jobs)
    intel = build_market_intel(skills)
    for name, obj in [("skills", skills), ("employees", employees), ("jobs", jobs), ("applications", apps),
                      ("placements", placements), ("users", users), ("market_intel", intel), ("role_transitions", transitions)]:
        (OUT / f"{name}.json").write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    for e in employees:
        write_resume(e)
    total = len(skills) + len(employees) + len(jobs) + len(apps) + len(placements)
    print(f"skills={len(skills)} employees={len(employees)} jobs={len(jobs)} applications={len(apps)} "
          f"placements={len(placements)} resumes={len(employees)} users={len(users)}  -> {total:,} records")


if __name__ == "__main__":
    main()
