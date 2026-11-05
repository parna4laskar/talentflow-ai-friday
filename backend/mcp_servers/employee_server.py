"""employee-mcp: the only access path to employee data for agents and apps.

Tools: search_employees, get_employee, get_availability, get_resume, employee_stats,
       get_demographics_for_audit (fairness auditor only),
       create_employee / update_employee_skill / update_availability / deactivate_employee (CRUD, HR only)
Resource: employee://{employee_id}
"""
from __future__ import annotations

import re
from datetime import date

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import func, select

from common import WRITE_ROLES, audited, require, serve
from app.core.config import get_settings
from app.storage import document, files
from app.storage.cache import cached
from app.storage.relational import Employee, EmployeeSkill, session

mcp = FastMCP("employee-mcp", instructions="Internal employee directory: skills, availability, location and career interests. "
              "Protected attributes are only exposed to the fairness auditor.", host=get_settings().mcp_host,
              stateless_http=True, json_response=True)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _public(e: Employee, skills_filter: set[str] | None = None) -> dict:
    """Employee projection WITHOUT protected attributes (gender, age) or contact PII."""
    sk = [{"name": s.skill, "proficiency": s.proficiency, "years": s.years, "verified": s.verified, "last_used": s.last_used}
          for s in e.skills]
    return {
        "employee_id": e.employee_id, "name": e.full_name, "title": e.title, "role_family": e.role_family, "level": e.level,
        "department": e.department, "years_experience": e.years_experience, "months_in_role": e.months_in_role,
        "tenure_years": e.tenure_years, "city": e.city, "country": e.country, "region": e.region,
        "work_mode_preference": e.work_mode_preference, "willing_to_relocate": e.willing_to_relocate,
        "relocation_preferences": e.relocation_preferences,
        "availability": {"status": e.availability_status, "allocation_pct": e.allocation_pct, "available_from": e.available_from,
                         "project_end": e.project_end, "notice_weeks": e.notice_weeks},
        "eligible_for_move": e.eligible_for_move, "open_to_move": e.open_to_move, "target_roles": e.target_roles,
        "last_rating": e.last_rating, "skills": sk, "certifications": [c["name"] for c in e.certifications],
    }


@mcp.tool()
@cached("mcp:search_employees", ttl=120)
def search_employees(skills: list[str], min_proficiency: int = 1, role_families: list[str] | None = None,
                     regions: list[str] | None = None, available_by: str | None = None, eligible_only: bool = True,
                     limit: int = 300) -> dict:
    """Find employees who hold ANY of the given skills (at >= min_proficiency).

    Optional filters: role_families, regions (APAC/EMEA/AMER), available_by (ISO date: available on/before),
    eligible_only (excludes people on a performance plan or < 12 months in role). Results are ordered by
    number of matching skills, then proficiency."""
    with session() as s:
        q = (select(EmployeeSkill.employee_id, func.count().label("hits"), func.sum(EmployeeSkill.proficiency).label("prof"))
             .where(EmployeeSkill.skill.in_(skills), EmployeeSkill.proficiency >= min_proficiency)
             .group_by(EmployeeSkill.employee_id))
        hits = {r.employee_id: (r.hits, r.prof) for r in s.execute(q)}
        if not hits:
            return {"count": 0, "employees": []}
        eq = select(Employee).where(Employee.employee_id.in_(hits), Employee.active.is_(True))
        if eligible_only:
            eq = eq.where(Employee.eligible_for_move.is_(True))
        if role_families:
            eq = eq.where(Employee.role_family.in_(role_families))
        if regions:
            eq = eq.where(Employee.region.in_(regions))
        if available_by:
            eq = eq.where(Employee.available_from <= available_by)
        rows = s.execute(eq).scalars().all()
        rows.sort(key=lambda e: hits[e.employee_id], reverse=True)
        out = [_public(e) for e in rows[:limit]]
        for o in out:
            o["matched_skill_count"] = hits[o["employee_id"]][0]
        return {"count": len(rows), "returned": len(out), "employees": out}


@mcp.tool()
def get_employee(employee_id: str, ctx: Context = None) -> dict:
    """Full employee profile (skills, availability, interests, project history). No protected attributes."""
    with session() as s:
        e = s.get(Employee, employee_id)
        if not e:
            return {"error": f"employee {employee_id} not found"}
        out = _public(e)
    doc = document.get_profile(employee_id) or {}
    out["projects"] = doc.get("projects", [])
    out["aspiration"] = doc.get("career_interests", {}).get("aspiration")
    out["languages"] = doc.get("languages", [])
    out["education"] = doc.get("education")
    out["resume_summary"] = doc.get("resume_summary")
    return out


@mcp.tool()
def list_employees(query: str = "", department: str | None = None, availability: str | None = None, page: int = 1,
                   page_size: int = 25) -> dict:
    """Paged employee directory (name / title / skill text filter, department, availability status)."""
    with session() as s:
        q = select(Employee).where(Employee.active.is_(True))
        if query:
            like = f"%{query}%"
            skill_ids = select(EmployeeSkill.employee_id).where(EmployeeSkill.skill.ilike(like))
            q = q.where(Employee.full_name.ilike(like) | Employee.title.ilike(like) | Employee.employee_id.ilike(like)
                        | Employee.employee_id.in_(skill_ids))
        if department:
            q = q.where(Employee.department == department)
        if availability:
            q = q.where(Employee.availability_status == availability)
        total = s.scalar(select(func.count()).select_from(q.subquery()))
        rows = s.execute(q.order_by(Employee.employee_id).offset((page - 1) * page_size).limit(page_size)).scalars().all()
        return {"total": total, "page": page, "page_size": page_size, "employees": [_public(e) for e in rows]}


@mcp.tool()
def get_employees_batch(employee_ids: list[str], eligible_only: bool = True) -> list[dict]:
    """Profiles (public projection) for a list of employee ids — used to hydrate semantic-search hits."""
    with session() as s:
        q = select(Employee).where(Employee.employee_id.in_(employee_ids), Employee.active.is_(True))
        if eligible_only:
            q = q.where(Employee.eligible_for_move.is_(True))
        return [_public(e) for e in s.execute(q).scalars().all()]


@mcp.tool()
def get_availability(employee_ids: list[str]) -> list[dict]:
    """Availability windows for a list of employees (status, allocation %, available_from, notice)."""
    with session() as s:
        rows = s.execute(select(Employee).where(Employee.employee_id.in_(employee_ids))).scalars().all()
        return [{"employee_id": e.employee_id, "status": e.availability_status, "allocation_pct": e.allocation_pct,
                 "available_from": e.available_from, "project_end": e.project_end, "notice_weeks": e.notice_weeks} for e in rows]


@mcp.tool()
def get_resume(employee_id: str) -> dict:
    """Unstructured résumé text from the file store (email addresses redacted)."""
    txt = files.read_resume(employee_id)
    if txt is None:
        return {"error": "résumé not found"}
    return {"employee_id": employee_id, "resume": EMAIL_RE.sub("[REDACTED_EMAIL]", txt)}


@mcp.tool()
def get_demographics_for_audit(employee_ids: list[str], ctx: Context = None) -> list[dict]:
    """Protected attributes for bias auditing ONLY. Restricted to fairness_auditor and hr_admin roles."""
    require(ctx, {"fairness_auditor", "hr_admin"})
    with session() as s:
        rows = s.execute(select(Employee.employee_id, Employee.gender, Employee.age_band, Employee.region)
                         .where(Employee.employee_id.in_(employee_ids))).all()
        return [{"employee_id": r[0], "gender": r[1], "age_band": r[2], "region": r[3]} for r in rows]


@mcp.tool()
@cached("mcp:employee_stats", ttl=60)
def employee_stats() -> dict:
    """Workforce aggregates: headcount by department / region / availability and skill supply."""
    with session() as s:
        def grp(col):
            return dict(s.execute(select(col, func.count()).where(Employee.active.is_(True)).group_by(col)).all())
        supply = s.execute(select(EmployeeSkill.skill, func.count(), func.avg(EmployeeSkill.proficiency))
                           .group_by(EmployeeSkill.skill).order_by(func.count().desc())).all()
        return {"headcount": s.scalar(select(func.count()).select_from(Employee).where(Employee.active.is_(True))),
                "by_department": grp(Employee.department), "by_region": grp(Employee.region), "by_city": grp(Employee.city),
                "by_availability": grp(Employee.availability_status), "by_level": grp(Employee.level),
                "by_retention_risk": grp(Employee.retention_risk),
                "eligible_for_move": s.scalar(select(func.count()).select_from(Employee).where(Employee.eligible_for_move.is_(True))),
                "skill_supply": [{"skill": r[0], "employees": r[1], "avg_proficiency": round(float(r[2]), 2)} for r in supply]}


# ------------------------------------------------------------------ CRUD (HR admin)
@mcp.tool()
@audited("employee")
def create_employee(full_name: str, email: str, title: str, role_family: str, department: str, level: str, city: str,
                    country: str, region: str, skills: list[dict], ctx: Context = None) -> dict:
    """Create an employee. skills: [{"name": str, "proficiency": 1-5}]. HR admin only."""
    require(ctx, WRITE_ROLES)
    with session() as s:
        n = s.scalar(select(func.count()).select_from(Employee))
        eid = f"EMP{10001 + n}"
        today = date.today().isoformat()
        e = Employee(employee_id=eid, full_name=full_name, email=email, gender="U", age_band="U", department=department,
                     role_family=role_family, title=title, level=level, years_experience=0, hire_date=today, tenure_years=0,
                     months_in_role=0, city=city, country=country, region=region, work_mode_preference="Hybrid",
                     willing_to_relocate=False, relocation_preferences=[], manager_id=None, is_people_manager=False,
                     availability_status="Available", allocation_pct=0, project_end=today, available_from=today, notice_weeks=0,
                     on_performance_plan=False, eligible_for_move=True, retention_risk="Low", last_rating=3, open_to_move=True,
                     target_roles=[role_family], certifications=[], languages=["English"], education="", resume_summary=f"{title} based in {city}.")
        e.skills = [EmployeeSkill(skill=k["name"], category="", proficiency=int(k.get("proficiency", 3)), years=0, last_used=date.today().year,
                                  verified=False, source="hr-entry") for k in skills]
        s.add(e)
        s.commit()
    return {"created": eid}


@mcp.tool()
@audited("employee")
def update_employee_skill(employee_id: str, skill: str, proficiency: int, verified: bool = False, ctx: Context = None) -> dict:
    """Add or update a skill for an employee (HR admin, or the employee for their own profile; self-updates are unverified)."""
    who = require(ctx, WRITE_ROLES, self_employee_id=employee_id)
    if who["role"] == "employee":
        verified = False
    with session() as s:
        row = s.execute(select(EmployeeSkill).where(EmployeeSkill.employee_id == employee_id, EmployeeSkill.skill == skill)).scalar_one_or_none()
        if row:
            row.proficiency, row.verified = int(proficiency), verified
        else:
            s.add(EmployeeSkill(employee_id=employee_id, skill=skill, category="", proficiency=int(proficiency), years=0,
                                last_used=date.today().year, verified=verified, source="hr-entry" if who["role"] != "employee" else "self-declared"))
        s.commit()
    return {"updated": employee_id, "skill": skill, "proficiency": proficiency, "verified": verified}


@mcp.tool()
@audited("employee")
def update_availability(employee_id: str, status: str, available_from: str, allocation_pct: int = 100, ctx: Context = None) -> dict:
    """Update availability (status: Allocated | Rolling off | Partially available | Available). HR admin only."""
    require(ctx, WRITE_ROLES)
    with session() as s:
        e = s.get(Employee, employee_id)
        if not e:
            return {"error": "not found"}
        e.availability_status, e.available_from, e.allocation_pct = status, available_from, allocation_pct
        s.commit()
    return {"updated": employee_id, "status": status, "available_from": available_from}


@mcp.tool()
@audited("employee")
def deactivate_employee(employee_id: str, ctx: Context = None) -> dict:
    """Soft-delete an employee from the marketplace. HR admin only."""
    require(ctx, WRITE_ROLES)
    with session() as s:
        e = s.get(Employee, employee_id)
        if not e:
            return {"error": "not found"}
        e.active = False
        s.commit()
    return {"deactivated": employee_id}


@mcp.resource("employee://{employee_id}")
def employee_resource(employee_id: str) -> dict:
    """Employee profile as an MCP resource."""
    return get_employee(employee_id)


if __name__ == "__main__":
    serve(mcp, get_settings().mcp_ports["employee"])
