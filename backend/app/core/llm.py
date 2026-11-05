"""LLM gateway for Gemini.

- Model chain with automatic fallback (primary -> fallbacks) on 429/503/timeouts
- Client-side rate limiter (free-tier friendly)
- Exact-match response cache (diskcache) keyed by model tier + prompt
- PII redaction on every prompt (guardrail)
- JSON mode with Pydantic validation and json-repair
- Telemetry counters for the governance dashboard
Callers must handle `LLMUnavailable` with a deterministic fallback, so the platform never stalls.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.guardrails.checks import redact_pii
from app.storage import cache

_client = None
_calls: dict[str, deque] = {}
_rl_lock = threading.Lock()  # thread-safe: CrewAI runs agents in worker threads / other loops


class LLMUnavailable(RuntimeError):
    pass


def client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types
        _client = genai.Client(api_key=get_settings().gemini_api_key,
                               http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)))
    return _client


def model_chain(tier: str) -> list[str]:
    s = get_settings()
    first = s.primary_model if tier == "primary" else s.fast_model
    return list(dict.fromkeys([first, *s.fallback_models]))


def _window(model: str) -> deque:
    q = _calls.setdefault(model, deque())
    now = time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    return q


def reserve(model: str, n: int = 1) -> float:
    """Reserve n request slots in a model's per-minute window (free tier: 5 RPM per model).
    Returns seconds to wait before the first slot is available."""
    rpm = get_settings().llm_max_rpm
    with _rl_lock:
        q = _window(model)
        now = time.monotonic()
        wait = 0.0
        for _ in range(n):
            slot = now if len(q) < rpm else max(now, q[-rpm] + 60)
            q.append(slot)
            wait = wait or (slot - now)
        return max(0.0, wait)


def headroom(model: str) -> int:
    with _rl_lock:
        return get_settings().llm_max_rpm - len([t for t in _window(model) if t <= time.monotonic()])


async def _rate_limit(model: str):
    wait = reserve(model)
    if wait > 0:
        await asyncio.sleep(wait)


async def generate(prompt: str, *, system: str = "", tier: str = "primary", json_mode: bool = False,
                   schema: Type[BaseModel] | None = None, temperature: float = 0.2, use_cache: bool = True,
                   timeout: float | None = None, max_output_tokens: int = 4096) -> dict:
    """Returns {"text", "data" (parsed JSON / model), "model", "cached", "ms"}. Raises LLMUnavailable."""
    s = get_settings()
    if not s.llm_enabled or not s.gemini_api_key:
        raise LLMUnavailable("LLM disabled or no API key")
    prompt, pii = redact_pii(prompt)
    if pii:
        cache.bump("llm_pii_redactions", sum(pii.values()))
    key = cache.make_key("llm", {"t": tier, "s": system, "p": prompt, "j": json_mode or bool(schema), "temp": temperature})
    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            cache.bump("llm_cache_hits")
            return {**hit, "cached": True}

    from google.genai import types
    cfg = types.GenerateContentConfig(system_instruction=system or None, temperature=temperature, max_output_tokens=max_output_tokens,
                                      response_mime_type="application/json" if (json_mode or schema) else None,
                                      response_schema=schema)
    errors = []
    chain = sorted(model_chain(tier), key=lambda m: not _is_healthy(m))  # healthy models first, order kept
    for i, model in enumerate(chain):
        if not _is_healthy(model) and i < len(chain) - 1:
            continue
        await _rate_limit(model)
        t = time.perf_counter()
        try:
            resp = await asyncio.wait_for(client().aio.models.generate_content(model=model, contents=prompt, config=cfg),
                                          timeout=timeout or s.llm_timeout_s)
            text = (resp.text or "").strip()
            if not text:
                raise ValueError("empty response")
            data = _parse(text, schema) if (json_mode or schema) else None
            ms = int((time.perf_counter() - t) * 1000)
            cache.bump("llm_calls")
            cache.bump("llm_ms", ms)
            cache.bump(f"llm_model:{model}")
            if i > 0:
                cache.bump("llm_fallbacks")
            out = {"text": text, "data": data.model_dump() if isinstance(data, BaseModel) else data, "model": model, "ms": ms}
            if use_cache:
                cache.set(key, out, ttl=72 * 3600)  # rehearsal runs pre-warm demo answers
            return {**out, "cached": False}
        except Exception as exc:  # 429 / 503 / timeout / bad JSON -> next model
            errors.append(f"{model}: {type(exc).__name__}: {str(exc)[:120]}")
            if any(c in str(exc) for c in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
                mark_unhealthy(model, 45)
            if "PERMISSION_DENIED" in str(exc) or "API_KEY_INVALID" in str(exc):
                break
    cache.bump("llm_failures")
    raise LLMUnavailable("; ".join(errors))


def _parse(text: str, schema: Type[BaseModel] | None):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        from json_repair import repair_json
        data = json.loads(repair_json(text))
    if schema:
        try:
            return schema.model_validate(data)
        except ValidationError:
            if isinstance(data, list) and data:
                return schema.model_validate(data[0])
            raise
    return data


_HEALTH: dict[str, float] = {}  # model -> monotonic time until which it is considered unhealthy


def mark_unhealthy(model: str, seconds: float = 60) -> None:
    _HEALTH[model] = time.monotonic() + seconds


def _is_healthy(model: str) -> bool:
    return _HEALTH.get(model, 0) <= time.monotonic()


async def healthy_model(tier: str, exclude: set[str] | None = None) -> str:
    """Pick a model for framework-managed agents (CrewAI, langgraph-swarm) from real call outcomes
    (no ping probes, which would spend free-tier quota): healthy first, most rate headroom first."""
    s = get_settings()
    if not s.llm_enabled or not s.gemini_api_key:
        raise LLMUnavailable("LLM disabled or no API key")
    cands = [m for m in model_chain(tier) if m not in (exclude or set()) and _is_healthy(m)]
    if not cands:
        raise LLMUnavailable(f"no healthy model in {tier} chain")
    return max(cands, key=headroom)


def spread_models(tier: str, n: int) -> list[str]:
    """Distinct models (round-robin over healthy ones) so parallel agents use separate per-model quotas."""
    healthy = [m for m in model_chain(tier) if _is_healthy(m)] or model_chain(tier)
    healthy.sort(key=headroom, reverse=True)
    return [healthy[i % len(healthy)] for i in range(n)]


def chat_model(model: str):
    """LangChain chat model (used by langgraph-swarm agents)."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    s = get_settings()
    return ChatGoogleGenerativeAI(model=model, api_key=s.gemini_api_key, temperature=0.1, max_retries=1, timeout=s.llm_timeout_s)


def crew_llm(model: str):
    """CrewAI LLM handle (native Gemini provider)."""
    from crewai import LLM
    s = get_settings()
    return LLM(model=f"gemini/{model}", api_key=s.gemini_api_key, temperature=0.2, timeout=s.llm_timeout_s)


def stats() -> dict:
    calls = cache.counter("llm_calls")
    models = list(dict.fromkeys(model_chain("primary") + model_chain("fast")))
    return {"calls": calls, "cache_hits": cache.counter("llm_cache_hits"), "fallbacks": cache.counter("llm_fallbacks"),
            "failures": cache.counter("llm_failures"), "pii_redactions": cache.counter("llm_pii_redactions"),
            "by_model": {m: cache.counter(f"llm_model:{m}") for m in models if cache.counter(f"llm_model:{m}")},
            "avg_latency_ms": int(cache.counter("llm_ms") / calls) if calls else 0,
            "unhealthy_now": [m for m in _HEALTH if not _is_healthy(m)],
            "models": {"primary": model_chain("primary"), "fast": model_chain("fast")}}
