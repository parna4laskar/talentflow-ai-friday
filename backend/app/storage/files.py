"""File storage (local filesystem; swap for S3/MinIO in production): résumés, policies, generated reports."""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def _root() -> Path:
    return get_settings().files_dir


def resume_path(employee_id: str) -> Path:
    return _root() / "resumes" / f"{employee_id}.txt"


def read_resume(employee_id: str) -> str | None:
    p = resume_path(employee_id)
    return p.read_text(encoding="utf-8") if p.exists() else None


def policy_files() -> list[Path]:
    return sorted((_root() / "policies").glob("*.md"))


def reports_dir() -> Path:
    d = get_settings().runtime_dir / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stats() -> dict:
    res = list((_root() / "resumes").glob("*.txt"))
    reps = list(reports_dir().glob("*"))
    return {"resumes": len(res), "policies": len(policy_files()), "reports": len(reps),
            "bytes": sum(p.stat().st_size for p in res + reps)}
