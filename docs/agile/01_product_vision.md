# Product Vision — TalentFlow AI

## Vision statement
**For** large enterprises that lose talent and money by hiring externally for roles their own people could fill,
**TalentFlow AI** is an agentic internal talent marketplace.
**It** turns every internal job post into a fair, explainable shortlist of employees within minutes, using skills, applications, location and availability.
**Unlike** keyword-based job boards and HR search tools, it finds *hidden-fit* employees through a skills graph, explains every score, checks every shortlist for bias, and keeps a human in charge of every decision.

## Problem
| Pain | Evidence in our data (synthetic, realistic) |
|---|---|
| Roles go external by default | Internal fill rate only 71%; 25 roles closed without an internal hire |
| Talent is invisible | 2,045 of 3,000 employees are eligible to move, but title and keyword search miss people whose skills transfer from another role family |
| Slow, manual shortlisting | Average time to fill is 23.5 days; a TA partner reviews résumés by hand |
| Bias and opacity risk | Job descriptions contain exclusionary language; shortlisting is not audited |
| Flight risk | Employees with long tenure in their current role and high ratings show "High" retention risk |

## Personas
| Persona | Goal | Top job-to-be-done |
|---|---|---|
| **Hiring Manager** (e.g. a Lead ML Engineer) | Staff a role fast with the right person | "Show me who internally can do this job, and why, today." |
| **HR Admin / Talent Partner** | Run a fair, compliant marketplace | "Keep employee data correct and prove that our AI is fair." |
| **Employee** (e.g. a Senior Backend Engineer) | Grow without leaving | "Which roles suit me, and what do I learn to get there?" |
| **Leadership** (e.g. a Chief People Officer) | Retain talent and cut hiring cost | "Is internal mobility working, and where are our skill gaps?" |

## Value hypotheses and KPIs
| Outcome | KPI | Baseline | Target (pilot) |
|---|---|---|---|
| Faster staffing | Time to shortlist | 5–10 working days | **< 5 minutes** (agent run) |
| More internal fills | Internal fill rate | 71% | 80% |
| Cost avoidance | External hiring cost avoided | — | USD 32K average per internal fill |
| Wider talent pool | Hidden-fit candidates per shortlist | 0 | ≥ 2 |
| Fairness | Shortlists passing the four-fifths rule | not measured | 100% audited; rebalanced when needed |
| Trust | Hiring-manager approval rate of AI matches | — | ≥ 60% |
| Retention | Annual attrition among high-risk employees | — | −10% |

## Scope (hackathon MVP)
**In scope:**
- Agentic matching pipeline (LangGraph, CrewAI, Swarm) over MCP
- Four persona workspaces
- Live Agent Theater and dashboards
- Copilot (RAG plus intent routing)
- Guardrails and fairness checks
- Feedback-driven ML model
- Storage across five store types

**Out of scope:** HRIS integration (Workday/SAP) and SSO, which the MCP adapters are designed to take over. Also out of scope: notifications, interview scheduling, and multi-tenant deployment.

## Principles
1. **Human decides, AI recommends.** Every shortlist pauses for a human, and a rejection needs a reason.
2. **Grounded numbers.** Scores come from MCP data and deterministic scoring; the LLM explains them and never invents them.
3. **Privacy and fairness by design.** Protected attributes are never used for matching or sent to an LLM; only the auditor role can see them.
4. **Always available.** The LLM is optional for correctness: every agent stage has a grounded fallback.
