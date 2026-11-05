"""Input / output guardrails for TalentFlow agents.

- redact_pii              emails, phone numbers, national IDs, card numbers -> placeholders
- detect_prompt_injection heuristic scoring of instruction-override attempts
- scan_inclusive_language exclusionary / biased job-description language with suggested rewrites
- validate_grounding      every candidate & skill an agent cites must exist in tool (MCP) evidence
"""
from __future__ import annotations

import re

PII_PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)\d{3,5}[\s-]?\d{3,5}(?!\w)")),
    ("NATIONAL_ID", re.compile(r"\b(?:\d{4}\s\d{4}\s\d{4}|\d{3}-\d{2}-\d{4}|[A-Z]{5}\d{4}[A-Z])\b")),
    ("CARD", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
]

INJECTION_PATTERNS = [
    (r"ignore (all|any|the)? ?(previous|prior|above) (instructions|rules|prompts?)", 0.9),
    (r"disregard (the|all|your) (rules|instructions|guidelines)", 0.9),
    (r"(reveal|show|print|leak) (your|the) (system )?prompt", 0.8),
    (r"you are now (a|an|the)\b", 0.6),
    (r"\bact as (an? )?(admin|administrator|root|developer mode)", 0.7),
    (r"(jailbreak|do anything now|\bDAN\b)", 0.8),
    (r"</?(system|assistant|instructions?)>", 0.7),
    (r"(include|rank|select|shortlist) only (men|women|males|females|young|people under)", 0.9),
    (r"(exclude|filter out|remove) (all )?(women|men|older|people over|candidates over|pregnant|disabled)", 0.95),
    (r"(gender|age|ethnicity|religion|caste)\b.{0,30}\b(prefer|preference|only|filter)", 0.8),
]

# phrase -> (category, suggestion)
BIAS_LEXICON = {
    r"\byoung\b": ("age", "Describe the skills or energy level needed, not age (e.g. 'motivated')."),
    r"\b(under|below) (30|35|40)\b": ("age", "Remove age limits; specify required experience instead."),
    r"recent graduates?": ("age", "Use 'early-career professionals' or state the experience range."),
    r"digital natives?": ("age", "Use 'comfortable with digital tools'."),
    r"\benergetic\b": ("age", "Consider 'motivated' or 'proactive'."),
    r"native (english )?speakers?": ("national origin", "Use 'fluent in English (professional working proficiency)'."),
    r"\bguys\b": ("gender", "Use 'team' or 'colleagues'."),
    r"\b(he|she) (will|should|must)\b": ("gender", "Use 'you will' or 'they will'."),
    r"\bmanpower\b": ("gender", "Use 'workforce' or 'staffing'."),
    r"\b(rockstar|ninja|guru)\b": ("gender-coded", "Use the concrete role title and skills."),
    r"\baggressive\b": ("gender-coded", "Use 'ambitious' or 'results-driven'."),
    r"culture fit": ("affinity bias", "Use 'values alignment' and describe the values."),
    r"no family commitments": ("family status", "Remove; state travel requirements objectively."),
    r"long hours": ("family status / disability", "Describe workload and flexibility honestly; avoid implying unpaid overtime."),
    r"able-bodied|physically fit": ("disability", "State only essential physical requirements, with accommodations available."),
}


def redact_pii(text: str) -> tuple[str, dict]:
    counts: dict[str, int] = {}
    for label, pat in PII_PATTERNS:
        text, n = pat.subn(f"[{label}]", text)
        if n:
            counts[label] = counts.get(label, 0) + n
    return text, counts


def detect_prompt_injection(text: str) -> dict:
    low = text.lower()
    hits = [{"pattern": p, "weight": w} for p, w in INJECTION_PATTERNS if re.search(p, low, re.I)]
    score = min(1.0, sum(h["weight"] for h in hits))
    return {"score": round(score, 2), "blocked": score >= 0.75, "matches": [h["pattern"] for h in hits]}


def scan_inclusive_language(text: str) -> dict:
    findings = []
    for pat, (cat, suggestion) in BIAS_LEXICON.items():
        for m in re.finditer(pat, text, re.I):
            findings.append({"phrase": m.group(0), "category": cat, "suggestion": suggestion})
    score = max(0, 100 - 15 * len(findings))
    return {"inclusivity_score": score, "findings": findings, "flagged": bool(findings)}


def validate_grounding(cited_ids: list[str], evidence_ids: set[str]) -> dict:
    ungrounded = [c for c in cited_ids if c not in evidence_ids]
    return {"grounded": not ungrounded, "ungrounded": ungrounded}


def input_guardrail(text: str) -> dict:
    redacted, pii = redact_pii(text)
    inj = detect_prompt_injection(text)
    inc = scan_inclusive_language(text)
    return {"redacted_text": redacted, "pii_redacted": pii, "injection": inj, "inclusive_language": inc,
            "decision": "block" if inj["blocked"] else ("warn" if inc["flagged"] or pii else "pass")}
