"""MCP client used by agents and API: every employee / job / knowledge access goes through MCP.

- `call(server, tool, args, role=..., user=...)`  async, returns parsed JSON (structured content)
- `langchain_tools(servers, role)`               MCP tools as LangChain tools (for LLM tool-calling agents)
Every call is recorded in a per-run trace (for the Live Agent Theater) with latency.
"""
from __future__ import annotations

import asyncio
import json
import time
from contextvars import ContextVar
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import get_settings
from app.storage.cache import bump

SERVERS = ("employee", "jobs", "knowledge")
# Per-run hook so agent nodes can stream MCP calls to the UI
tool_call_listener: ContextVar = ContextVar("tool_call_listener", default=None)


def stats() -> dict:
    from app.storage.cache import counter
    calls = counter("mcp_calls")
    return {"calls": calls, "errors": counter("mcp_errors"), "total_ms": counter("mcp_ms"),
            "avg_ms": int(counter("mcp_ms") / calls) if calls else 0}


class MCPError(RuntimeError):
    pass


def _headers(role: str, user: str) -> dict:
    return {"X-TalentFlow-Role": role, "X-TalentFlow-User": user}


def _parse(result) -> Any:
    if result.isError:
        raise MCPError(" ".join(getattr(c, "text", "") for c in result.content)[:500])
    sc = getattr(result, "structuredContent", None)
    if sc is not None:
        return sc["result"] if isinstance(sc, dict) and set(sc) == {"result"} else sc
    texts = [getattr(c, "text", "") for c in result.content]
    parsed = []
    for t in texts:
        try:
            parsed.append(json.loads(t))
        except (json.JSONDecodeError, TypeError):
            parsed.append(t)
    return parsed[0] if len(parsed) == 1 else parsed


async def call(server: str, tool: str, args: dict | None = None, role: str = "agent", user: str = "talentflow-agent",
               timeout: float = 60) -> Any:
    url = get_settings().mcp_url(server)
    t = time.perf_counter()
    listener = tool_call_listener.get()
    try:
        async with streamablehttp_client(url, headers=_headers(role, user), timeout=timeout) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                res = await asyncio.wait_for(s.call_tool(tool, args or {}), timeout=timeout)
        out = _parse(res)
        ms = int((time.perf_counter() - t) * 1000)
        bump("mcp_calls")
        bump("mcp_ms", ms)
        if listener:
            listener({"server": f"{server}-mcp", "tool": tool, "ms": ms, "ok": True, "args": _short(args)})
        return out
    except Exception as exc:
        bump("mcp_errors")
        if listener:
            listener({"server": f"{server}-mcp", "tool": tool, "ms": int((time.perf_counter() - t) * 1000), "ok": False,
                      "error": str(exc)[:200], "args": _short(args)})
        if isinstance(exc, MCPError):
            raise
        raise MCPError(f"{server}-mcp/{tool} failed: {exc}") from exc


def call_sync(server: str, tool: str, args: dict | None = None, **kw) -> Any:
    return asyncio.run(call(server, tool, args, **kw))


def _short(args: dict | None) -> dict:
    out = {}
    for k, v in (args or {}).items():
        out[k] = v if not isinstance(v, list) or len(v) <= 6 else v[:6] + [f"…+{len(v) - 6}"]
    return out


async def list_tools(server: str) -> list[dict]:
    async with streamablehttp_client(get_settings().mcp_url(server), headers=_headers("agent", "catalog")) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
    return [{"name": t.name, "description": (t.description or "").strip().split("\n")[0]} for t in tools.tools]


async def health() -> dict:
    out = {}
    for s in SERVERS:
        try:
            out[s] = {"ok": True, "tools": len(await asyncio.wait_for(list_tools(s), 10))}
        except Exception as exc:
            out[s] = {"ok": False, "error": str(exc)[:120]}
    return out


async def langchain_tools(servers: list[str], role: str = "agent", user: str = "talentflow-agent",
                          include: set[str] | None = None):
    """Load MCP tools as LangChain BaseTools via langchain-mcp-adapters."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient({s: {"transport": "streamable_http", "url": get_settings().mcp_url(s),
                                       "headers": _headers(role, user)} for s in servers})
    tools = await client.get_tools()
    return [t for t in tools if include is None or t.name in include]
