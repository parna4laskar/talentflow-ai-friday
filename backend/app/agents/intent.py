"""Intent identification (LLM, fast tier) with a keyword fallback classifier.

Used by the matching graph (to confirm a job-matching request) and by the employee/manager assistant
to route questions to the right capability.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.core import llm

Intent = Literal["match_talent_for_job", "search_talent", "policy_question", "career_guidance", "job_search", "insight_query", "other"]

DESCRIPTIONS = {
    "match_talent_for_job": "A job posting / job description that needs internal candidates matched to it.",
    "search_talent": "Looking for employees with certain skills, e.g. 'who knows Kafka in Pune?'.",
    "policy_question": "Question about mobility, relocation, eligibility, learning or AI-use policies.",
    "career_guidance": "Employee asking how to grow, which skills to learn, or why they fit / do not fit.",
    "job_search": "Employee asking which open roles suit them.",
    "insight_query": "Analytics question about workforce, skills supply/demand, trends.",
    "other": "Anything else.",
}


class IntentOut(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    rationale: str
    entities: list[str] = Field(default_factory=list, description="skills, locations, roles mentioned")


KEYWORDS = [
    ("match_talent_for_job", r"(must have|nice to have|responsibilit|what you will do|we are hiring|job description|years of (relevant )?experience)"),
    ("policy_question", r"(policy|eligib|relocat|allowance|manager (know|approv)|how long|notice|pip|rules?|allowed|visa|remote work)"),
    ("job_search", r"(roles? (for|suit) me|open (roles|jobs|positions)|which (jobs|roles)|recommend (a )?(job|role)|jobs? match)"),
    ("career_guidance", r"(learn|upskill|grow|career|skill gap|improve my|next step|certif|why (am|was) i)"),
    ("search_talent", r"(who (knows|has|can)|find (me )?(people|employees|engineers|devs?)|employees with|talent with)"),
    ("insight_query", r"(how many|trend|distribution|supply|demand|dashboard|attrition|headcount|statistics)"),
]


def keyword_intent(text: str) -> IntentOut:
    low = text.lower()
    for intent, pat in KEYWORDS:
        if re.search(pat, low):
            return IntentOut(intent=intent, confidence=0.6, rationale=f"keyword rule matched /{pat[:40]}…/")
    return IntentOut(intent="other", confidence=0.3, rationale="no keyword rule matched")


async def classify(text: str, persona: str = "employee") -> dict:
    prompt = ("Classify the user's message for an internal talent marketplace.\n"
              f"Persona: {persona}\nIntents:\n" + "\n".join(f"- {k}: {v}" for k, v in DESCRIPTIONS.items()) +
              f"\n\nMessage:\n\"\"\"{text[:3000]}\"\"\"")
    try:
        r = await llm.generate(prompt, tier="fast", schema=IntentOut, system="You are a precise intent classifier.")
        return {**r["data"], "source": "llm", "model": r["model"], "cached": r["cached"]}
    except Exception as exc:
        out = keyword_intent(text).model_dump()
        return {**out, "source": "keyword-fallback", "fallback_reason": str(exc)[:160]}
