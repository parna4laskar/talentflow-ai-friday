"""Central configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    repo_root: Path = REPO_ROOT
    data_dir: Path = REPO_ROOT / "data"
    seed_dir: Path = REPO_ROOT / "data" / "seed"
    files_dir: Path = REPO_ROOT / "data" / "files"
    runtime_dir: Path = REPO_ROOT / "data" / "runtime"

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    primary_model: str = os.getenv("LLM_PRIMARY_MODEL", "gemini-3.5-flash")
    fast_model: str = os.getenv("LLM_FAST_MODEL", "gemini-3.5-flash-lite")
    fallback_models: tuple[str, ...] = tuple(
        m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "gemini-3-flash-preview,gemini-3.5-flash-lite").split(",") if m.strip())
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "45"))
    llm_max_rpm: int = int(os.getenv("LLM_MAX_RPM", "5"))  # per model (Gemini free tier)
    llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"

    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret")
    jwt_ttl_minutes: int = int(os.getenv("JWT_TTL_MINUTES", "720"))

    mcp_host: str = os.getenv("MCP_HOST", "127.0.0.1")
    mcp_ports: dict = field(default_factory=lambda: {
        "employee": int(os.getenv("MCP_EMPLOYEE_PORT", "8101")),
        "jobs": int(os.getenv("MCP_JOBS_PORT", "8102")),
        "knowledge": int(os.getenv("MCP_KNOWLEDGE_PORT", "8103")),
    })
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{(self.runtime_dir / 'talentflow.db').as_posix()}"

    def mcp_url(self, server: str) -> str:
        return f"http://{self.mcp_host}:{self.mcp_ports[server]}/mcp"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.runtime_dir.mkdir(parents=True, exist_ok=True)
    return s
