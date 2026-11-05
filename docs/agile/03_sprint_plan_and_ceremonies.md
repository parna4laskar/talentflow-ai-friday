# Sprint Plan, Ceremonies & Definition of Done

Hackathon cadence: **4 time-boxed sprints**, each with a planning session, a demo and a short retrospective.

## Sprint overview
| Sprint | Goal | Stories | SP committed | SP done |
|---|---|---|---|---|
| 0 — Inception | Architecture approved; repo and data foundations | Architecture & framework diagrams, E5-S1, E5-S4 | 10 | 10 |
| 1 — Data plane | Employee data served over MCP; all five stores loaded | E2-S1…S5, E5-S2 | 19 | 19 |
| 2 — Agents | End-to-end agentic run to human review | E1-S1…S8, E3-S2, E3-S3, E3-S4, E3-S6 | 63 | 63 |
| 3 — Experience | Persona UIs, live graphs, copilot, governance, docs | E4-S1…S6, E3-S1, E3-S5, E5-S3 | 37 | 37 |
| **Total** | | **37 stories** | **129** | **129** |

### Burn-up (story points done, cumulative)
| Checkpoint | Planned | Actual |
|---|---|---|
| End of Sprint 0 | 10 | 10 |
| End of Sprint 1 | 29 | 29 |
| End of Sprint 2 | 92 | 92 |
| End of Sprint 3 | 129 | 129 |

## Sprint 2 review — what we learned (excerpt)
- **Gemini free tier allows 5 requests per minute per model.** Parallel CrewAI agents burst past it.
  → Per-model rate windows; agents spread across different models; fallback runs the same tools deterministically.
- **The four-fifths rule is noisy on a 10-person shortlist** (one person changes the ratio by about 0.2).
  → Added a practical-significance test (a group must be at least 1.5 people short) before rebalancing.
- **Gemini 3 "thinking" tokens use up the output budget**, which truncated the JSON explanations.
  → Raised the output budget for the explainer; JSON repair stays on as a safety net.
- **Pending reviews lived in memory.** → Switched to a SQLite LangGraph checkpointer and reconcile runs on startup.

## Ceremonies
| Ceremony | When | Output |
|---|---|---|
| Sprint planning | Start of each sprint | Sprint goal, committed stories, task breakdown |
| Daily stand-up (async) | Every 2–3 hours | Blockers raised in the team channel |
| Backlog refinement | Mid-sprint | Acceptance criteria, estimates, Definition of Ready check |
| Sprint review / demo | End of sprint | Working increment shown in the UI, plus stakeholder feedback |
| Retrospective | End of sprint | One "keep" and one "change" action item |

## Definition of Ready
- The user story has a persona, a goal and a benefit, and testable acceptance criteria.
- Dependencies are known (MCP tool, store, UI page).
- Estimated by the team; fits in one sprint.

## Definition of Done
- Code is merged; type checks and lint pass (`tsc -b`, `oxlint`); backend tests pass (`pytest`).
- Acceptance criteria are shown in the running app (UI or API).
- Guardrails, RBAC and audit logging are applied to new endpoints and tools.
- No secrets in code (`.env` is git-ignored); errors are surfaced to the user.
- Docs updated (README, architecture, backlog status).

## Team roles (hackathon)
| Role | Responsibilities |
|---|---|
| Product Owner | Vision, backlog priority, demo narrative |
| Chief Solution Architect | Architecture, agent design, MCP contracts, governance |
| AI/ML Engineer | Agents, prompts, embeddings, outcome model |
| Full-stack Engineer | FastAPI, React UI, live charts |
| Data Engineer | Synthetic data, stores, bootstrap pipeline |
