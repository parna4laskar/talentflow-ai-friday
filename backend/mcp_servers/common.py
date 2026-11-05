"""Shared helpers for TalentFlow MCP servers: caller identity, RBAC and tool-call auditing.

Callers identify themselves with HTTP headers on the streamable-HTTP transport:
  X-TalentFlow-Role   hr_admin | hiring_manager | employee | leadership | agent | fairness_auditor
  X-TalentFlow-User   username / employee id / agent name
Over stdio (e.g. Claude Desktop or an IDE), the caller defaults to a read-only "agent" role.
"""
from __future__ import annotations

import sys
import time
from functools import wraps
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import Context  # noqa: E402

from app.storage.relational import audit  # noqa: E402

WRITE_ROLES = {"hr_admin"}


class Forbidden(Exception):
    pass


def caller(ctx: Context | None) -> dict:
    role, user = "agent", "anonymous-agent"
    try:
        req = ctx.request_context.request if ctx else None
        if req is not None:
            role = req.headers.get("x-talentflow-role", role)
            user = req.headers.get("x-talentflow-user", user)
    except Exception:
        pass
    return {"role": role, "user": user}


def require(ctx: Context | None, roles: set[str], self_employee_id: str | None = None) -> dict:
    who = caller(ctx)
    if who["role"] in roles:
        return who
    if self_employee_id and who["role"] == "employee" and who["user"] == self_employee_id:
        return who
    raise Forbidden(f"Role '{who['role']}' is not permitted to call this tool")


def audited(server: str):
    """Decorator: log write operations to the relational audit log."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ctx = kwargs.get("ctx")
            who = caller(ctx)
            t = time.time()
            result = fn(*args, **kwargs)
            audit(who["user"], f"mcp:{server}:{fn.__name__}", str({k: v for k, v in kwargs.items() if k != "ctx"})[:80],
                  role=who["role"], ms=int((time.time() - t) * 1000))
            return result
        return wrapper
    return deco


def serve(mcp, default_port: int):
    """Run over streamable HTTP by default; `--stdio` for desktop/IDE MCP clients."""
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        mcp.settings.port = default_port
        mcp.run(transport="streamable-http")
