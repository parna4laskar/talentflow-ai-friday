"""Relational store (SQLite via SQLAlchemy 2.0; swap the URL for PostgreSQL in production)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "employees"
    employee_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    gender: Mapped[str] = mapped_column(String(2))           # protected attribute - never sent to LLM
    age_band: Mapped[str] = mapped_column(String(8))         # protected attribute - never sent to LLM
    department: Mapped[str] = mapped_column(String(60), index=True)
    role_family: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(4), index=True)
    years_experience: Mapped[float] = mapped_column(Float)
    hire_date: Mapped[str] = mapped_column(String(10))
    tenure_years: Mapped[float] = mapped_column(Float)
    months_in_role: Mapped[int] = mapped_column(Integer)
    city: Mapped[str] = mapped_column(String(40), index=True)
    country: Mapped[str] = mapped_column(String(40))
    region: Mapped[str] = mapped_column(String(8), index=True)
    work_mode_preference: Mapped[str] = mapped_column(String(10))
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean)
    relocation_preferences: Mapped[list] = mapped_column(JSON, default=list)
    manager_id: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    is_people_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    availability_status: Mapped[str] = mapped_column(String(24), index=True)
    allocation_pct: Mapped[int] = mapped_column(Integer)
    project_end: Mapped[str] = mapped_column(String(10))
    available_from: Mapped[str] = mapped_column(String(10), index=True)
    notice_weeks: Mapped[int] = mapped_column(Integer)
    on_performance_plan: Mapped[bool] = mapped_column(Boolean)
    eligible_for_move: Mapped[bool] = mapped_column(Boolean, index=True)
    retention_risk: Mapped[str] = mapped_column(String(8))
    last_rating: Mapped[int] = mapped_column(Integer)
    open_to_move: Mapped[bool] = mapped_column(Boolean)
    target_roles: Mapped[list] = mapped_column(JSON, default=list)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    education: Mapped[str] = mapped_column(String(80))
    resume_summary: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    skills: Mapped[list["EmployeeSkill"]] = relationship(back_populates="employee", cascade="all, delete-orphan", lazy="selectin")


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    skill: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str] = mapped_column(String(40))
    proficiency: Mapped[int] = mapped_column(Integer)
    years: Mapped[float] = mapped_column(Float)
    last_used: Mapped[int] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(20))
    employee: Mapped[Employee] = relationship(back_populates="skills")


class Skill(Base):
    __tablename__ = "skills"
    skill_id: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    market_growth_index: Mapped[float] = mapped_column(Float)
    demand_trend: Mapped[str] = mapped_column(String(12))


class Job(Base):
    __tablename__ = "jobs"
    job_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    role_family: Mapped[str] = mapped_column(String(60), index=True)
    level: Mapped[str] = mapped_column(String(4))
    department: Mapped[str] = mapped_column(String(60), index=True)
    hiring_manager_id: Mapped[str] = mapped_column(String(12), index=True)
    hiring_manager_name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(40))
    country: Mapped[str] = mapped_column(String(40))
    region: Mapped[str] = mapped_column(String(8))
    work_mode: Mapped[str] = mapped_column(String(10))
    relocation_supported: Mapped[bool] = mapped_column(Boolean)
    posted_on: Mapped[str] = mapped_column(String(10), index=True)
    start_date: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12), index=True)
    priority: Mapped[str] = mapped_column(String(10))
    openings: Mapped[int] = mapped_column(Integer)
    min_years_experience: Mapped[int] = mapped_column(Integer)
    required_skills: Mapped[list] = mapped_column(JSON)
    nice_to_have_skills: Mapped[list] = mapped_column(JSON)
    domain: Mapped[str] = mapped_column(String(40))
    client: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    contains_biased_language: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Base):
    __tablename__ = "applications"
    application_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.job_id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    applied_on: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(30))
    cover_note: Mapped[str] = mapped_column(Text)


class Placement(Base):
    __tablename__ = "placements"
    placement_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(12), index=True)
    move_date: Mapped[str] = mapped_column(String(10), index=True)
    from_department: Mapped[str] = mapped_column(String(60))
    to_department: Mapped[str] = mapped_column(String(60))
    from_role: Mapped[str] = mapped_column(String(60))
    region: Mapped[str] = mapped_column(String(8))
    time_to_fill_days: Mapped[int] = mapped_column(Integer)
    cost_avoided_usd: Mapped[int] = mapped_column(Integer)
    features: Mapped[dict] = mapped_column(JSON)
    success: Mapped[bool] = mapped_column(Boolean)
    retained_12m: Mapped[bool] = mapped_column(Boolean)
    post_move_rating: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16), default="historical")


class User(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    employee_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    title: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(100))


class MatchRun(Base):
    __tablename__ = "match_runs"
    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(20))
    started_by: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)


class MatchResult(Base):
    __tablename__ = "match_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("match_runs.run_id"), index=True)
    job_id: Mapped[str] = mapped_column(String(16), index=True)
    employee_id: Mapped[str] = mapped_column(String(12), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(12), default="pending")   # pending/approved/rejected
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


_engine = None
_Session = None


def engine():
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(get_settings().sqlite_url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(_engine, "connect")
        def _pragmas(conn, _):
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def session():
    engine()
    return _Session()


def init_db(drop: bool = False):
    if drop:
        Base.metadata.drop_all(engine())
    Base.metadata.create_all(engine())


def audit(actor: str, action: str, target: str, **details):
    with session() as s:
        s.add(AuditLog(actor=actor, action=action, target=target, details=details))
        s.commit()
