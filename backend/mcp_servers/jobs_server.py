"""jobs-mcp: internal job postings and applications.

Tools: list_jobs, get_job, create_job, update_job_status, list_applications, apply_to_job, job_stats
Resource: job://{job_id}
"""
from __future__ import annotations

from datetime import date

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import func, select

from common import audited, require, serve
from app.core.config import get_settings
from app.storage.cache import cached
from app.storage.relational import Application, Employee, Job, session

mcp = FastMCP("jobs-mcp", instructions="Internal job marketplace: postings, applications and pipeline status.",
              host=get_settings().mcp_host, stateless_http=True, json_response=True)


def _job(j: Job, full: bool = True) -> dict:
    d = {"job_id": j.job_id, "title": j.title, "role_family": j.role_family, "level": j.level, "department": j.department,
         "hiring_manager_id": j.hiring_manager_id, "hiring_manager_name": j.hiring_manager_name,
         "location": {"city": j.city, "country": j.country, "region": j.region}, "work_mode": j.work_mode,
         "relocation_supported": j.relocation_supported, "posted_on": j.posted_on, "start_date": j.start_date, "status": j.status,
         "priority": j.priority, "openings": j.openings, "min_years_experience": j.min_years_experience,
         "required_skills": j.required_skills, "nice_to_have_skills": j.nice_to_have_skills, "domain": j.domain}
    if full:
        d["description"] = j.description
    return d


@mcp.tool()
def list_jobs(status: str | None = None, department: str | None = None, hiring_manager_id: str | None = None, limit: int = 100) -> list[dict]:
    """List internal job postings, newest first. status: Open | In Review | Filled | Closed."""
    with session() as s:
        q = select(Job).order_by(Job.posted_on.desc())
        if status:
            q = q.where(Job.status == status)
        if department:
            q = q.where(Job.department == department)
        if hiring_manager_id:
            q = q.where(Job.hiring_manager_id == hiring_manager_id)
        jobs = s.execute(q.limit(limit)).scalars().all()
        counts = dict(s.execute(select(Application.job_id, func.count()).where(Application.job_id.in_([j.job_id for j in jobs]))
                                .group_by(Application.job_id)).all())
        return [{**_job(j, full=False), "applications": counts.get(j.job_id, 0)} for j in jobs]


@mcp.tool()
def get_job(job_id: str) -> dict:
    """Full job posting including the free-text job description."""
    with session() as s:
        j = s.get(Job, job_id)
        return _job(j) if j else {"error": f"job {job_id} not found"}


@mcp.tool()
@audited("jobs")
def create_job(title: str, description: str, role_family: str, level: str, department: str, city: str, country: str, region: str,
               work_mode: str, required_skills: list[dict], nice_to_have_skills: list[str] | None = None, start_date: str | None = None,
               min_years_experience: int = 0, relocation_supported: bool = False, priority: str = "Medium", openings: int = 1,
               hiring_manager_id: str = "", hiring_manager_name: str = "", ctx: Context = None) -> dict:
    """Post a new internal job. required_skills: [{"name", "min_proficiency", "weight"}]. Hiring managers and HR only."""
    require(ctx, {"hiring_manager", "hr_admin", "agent"})
    today = date.today()
    with session() as s:
        n = s.scalar(select(func.count()).select_from(Job)) + 1
        jid = f"JOB-{today.year}-{n:04d}"
        while s.get(Job, jid):
            n += 1
            jid = f"JOB-{today.year}-{n:04d}"
        s.add(Job(job_id=jid, title=title, role_family=role_family, level=level, department=department, hiring_manager_id=hiring_manager_id,
                  hiring_manager_name=hiring_manager_name, city=city, country=country, region=region, work_mode=work_mode,
                  relocation_supported=relocation_supported, posted_on=today.isoformat(), start_date=start_date or today.isoformat(),
                  status="Open", priority=priority, openings=openings, min_years_experience=min_years_experience,
                  required_skills=required_skills, nice_to_have_skills=nice_to_have_skills or [], domain="", client="",
                  description=description))
        s.commit()
    return {"created": jid}


@mcp.tool()
@audited("jobs")
def update_job_status(job_id: str, status: str, ctx: Context = None) -> dict:
    """Change job status (Open | In Review | Filled | Closed)."""
    require(ctx, {"hiring_manager", "hr_admin"})
    with session() as s:
        j = s.get(Job, job_id)
        if not j:
            return {"error": "not found"}
        j.status = status
        s.commit()
    return {"job_id": job_id, "status": status}


@mcp.tool()
def list_applications(job_id: str) -> list[dict]:
    """Applications for a job: employee, status, source and cover note (unstructured)."""
    with session() as s:
        rows = s.execute(select(Application, Employee.full_name, Employee.title)
                         .join(Employee, Employee.employee_id == Application.employee_id)
                         .where(Application.job_id == job_id)).all()
        return [{"application_id": a.application_id, "employee_id": a.employee_id, "name": n, "title": t, "status": a.status,
                 "source": a.source, "applied_on": a.applied_on, "cover_note": a.cover_note} for a, n, t in rows]


@mcp.tool()
@audited("jobs")
def apply_to_job(job_id: str, employee_id: str, cover_note: str = "", ctx: Context = None) -> dict:
    """Submit an application on behalf of an employee (the employee themself, or HR)."""
    require(ctx, {"hr_admin"}, self_employee_id=employee_id)
    with session() as s:
        if s.execute(select(Application).where(Application.job_id == job_id, Application.employee_id == employee_id)).first():
            return {"error": "already applied"}
        open_apps = s.scalar(select(func.count()).select_from(Application).join(Job, Job.job_id == Application.job_id)
                             .where(Application.employee_id == employee_id, Job.status.in_(["Open", "In Review"]),
                                    Application.status.in_(["Applied", "Screening", "Interview", "Shortlisted"])))
        if open_apps >= 3:
            return {"error": "Policy: a maximum of 3 active internal applications is allowed."}
        n = s.scalar(select(func.count()).select_from(Application)) + 1
        aid = f"APP{100000 + n}"
        while s.get(Application, aid):
            n += 1
            aid = f"APP{100000 + n}"
        s.add(Application(application_id=aid, job_id=job_id, employee_id=employee_id, applied_on=date.today().isoformat(),
                          status="Applied", source="Self-applied", cover_note=cover_note))
        s.commit()
    return {"application_id": aid, "status": "Applied"}


@mcp.tool()
@cached("mcp:job_stats", ttl=60)
def job_stats() -> dict:
    """Marketplace aggregates: jobs by status/department and demanded skills across open roles."""
    with session() as s:
        by_status = dict(s.execute(select(Job.status, func.count()).group_by(Job.status)).all())
        by_dept = dict(s.execute(select(Job.department, func.count()).where(Job.status.in_(["Open", "In Review"])).group_by(Job.department)).all())
        demand: dict[str, int] = {}
        for (req,) in s.execute(select(Job.required_skills).where(Job.status.in_(["Open", "In Review"]))):
            for r in req:
                demand[r["name"]] = demand.get(r["name"], 0) + 1
        apps = dict(s.execute(select(Application.status, func.count()).group_by(Application.status)).all())
        return {"by_status": by_status, "open_by_department": by_dept, "applications_by_status": apps,
                "skill_demand": sorted(({"skill": k, "open_roles": v} for k, v in demand.items()), key=lambda d: -d["open_roles"])}


@mcp.resource("job://{job_id}")
def job_resource(job_id: str) -> dict:
    """Job posting as an MCP resource."""
    return get_job(job_id)


if __name__ == "__main__":
    serve(mcp, get_settings().mcp_ports["jobs"])
