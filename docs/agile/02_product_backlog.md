# Product Backlog

Story points use a Fibonacci scale. Priority uses MoSCoW. ✅ means done in the hackathon build.

## Epic E1 — Agentic matching engine (Must)
| ID | User story | Acceptance criteria | SP | Status |
|---|---|---|---|---|
| E1-S1 | As a hiring manager, when I post a role I want internal candidates matched automatically, so that I don't have to search manually. | Posting starts a run; the run reaches human review with up to 10 ranked candidates; the time is shown | 8 | ✅ |
| E1-S2 | As a hiring manager, I want the JD parsed into structured requirements, so that free-text posts work. | The LLM extracts skills, proficiency and years; skills are mapped to the taxonomy through `normalize_skills`; skills the AI added are flagged in the UI | 5 | ✅ |
| E1-S3 | As the platform, I want a CrewAI crew to source candidates in parallel, so that skills, applications, market and availability are all covered. | 4 agents with MCP tools; a sourcing brief is produced; any tool the agents skipped is run anyway | 8 | ✅ |
| E1-S4 | As the platform, I want swarm specialists to hand off to each other, so that matching adapts to the pool. | langgraph-swarm with 3 agents and handoff tools; handoffs appear in the Theater; all three specialists always run | 8 | ✅ |
| E1-S5 | As a hiring manager, I want hidden-fit candidates, so that I see people that title search misses. | Graph adjacency bridges each gap; a hidden fit is a candidate from a different role family with coverage ≥ 0.6 and adjacency ≥ 0.6, shown with a badge | 5 | ✅ |
| E1-S6 | As a hiring manager, I want a hybrid, explainable score. | Score = 35% skills, 15% adjacency, 15% availability, 10% location, 10% interest, 15% predicted success; the breakdown is shown on every card | 5 | ✅ |
| E1-S7 | As a hiring manager, I want to approve or reject each candidate with a reason. | LangGraph `interrupt()` pauses the run; a rejection without a reason returns 422; a run waiting for review survives an API restart | 5 | ✅ |
| E1-S8 | As the platform, I want the system to keep working when the LLM is unavailable. | Model fallback chain; per-model rate limits; deterministic fallback per stage, shown as `fallback` events | 5 | ✅ |

## Epic E2 — MCP data plane (Must)
| ID | User story | Acceptance criteria | SP | Status |
|---|---|---|---|---|
| E2-S1 | As an architect, I want employee data available only through an MCP server. | `employee-mcp` with 12 tools and an `employee://{id}` resource; agents and API use MCP clients only | 5 | ✅ |
| E2-S2 | As HR, I want CRUD on employees through MCP with role checks. | Create, update skill, update availability and deactivate are limited to HR; employees can update only their own skills (marked unverified); writes are audit-logged | 5 | ✅ |
| E2-S3 | As a fairness auditor, I need protected attributes, but no one else should see them. | `get_demographics_for_audit` returns 403-equivalent errors to any role other than auditor or HR | 3 | ✅ |
| E2-S4 | As an agent, I want knowledge tools. | `knowledge-mcp`: semantic résumé search, skill normalisation, graph neighbours and paths, policy RAG, market intel (Google Search) | 5 | ✅ |
| E2-S5 | As a desktop user, I want the same MCP servers usable from Claude Desktop or an IDE. | A `--stdio` flag on every server | 1 | ✅ |

## Epic E3 — Responsible AI & governance (Must)
| ID | User story | Acceptance criteria | SP | Status |
|---|---|---|---|---|
| E3-S1 | As HR, I want job descriptions screened for exclusionary language as they are typed. | Live precheck in the UI; findings come with suggested rewrites; an inclusivity score is shown | 3 | ✅ |
| E3-S2 | As security, I want prompt-injection and discriminatory instructions blocked. | Pattern-based scoring; blocks both job posts and Copilot messages | 3 | ✅ |
| E3-S3 | As the DPO, I want PII redacted from every LLM prompt. | Emails, phone numbers, national IDs and card numbers replaced; the count is shown on the governance dashboard | 2 | ✅ |
| E3-S4 | As HR, I want every shortlist audited for disparate impact. | Four-fifths rule on gender and age band (plus region for remote roles) with a practical-significance test; rebalance with equally qualified swaps and loop back to the ranker | 8 | ✅ |
| E3-S5 | As an auditor, I want a full trace and audit log. | Agent traces in the NoSQL store; an audit log of logins, MCP writes, runs and reviews; a governance console | 3 | ✅ |
| E3-S6 | As a hiring manager, I want explanations without bias. | The LLM sees anonymised candidate codes only, and a grounding check rejects invented candidates | 3 | ✅ |

## Epic E4 — Experience & insights (Must/Should)
| ID | User story | Acceptance criteria | SP | Status |
|---|---|---|---|---|
| E4-S1 | As any user, I want to sign in to my persona's workspace. | JWT; 4 roles; route guards plus API role checks | 3 | ✅ |
| E4-S2 | As a hiring manager, I want to watch the agents work live. | SSE stream; pipeline stepper; event feed; live funnel, score histogram, MCP latency and agent-activity charts | 8 | ✅ |
| E4-S3 | As an employee, I want roles ranked for me plus a gap plan. | Reverse matching; skill radar; learning path through the skills graph; one-click apply (policy: max 3 active applications) | 5 | ✅ |
| E4-S4 | As leadership, I want mobility trends and skill gaps. | KPIs, monthly moves and time-to-fill trends, scarcest and hottest skills, flows, retention risk; table view for every chart | 5 | ✅ |
| E4-S5 | As any user, I want a copilot. | Intent routing to policy RAG with citations, job search, talent search or insights; semantic cache; guardrails | 5 | ✅ |
| E4-S6 | As a hiring manager, I want a PDF shortlist report. | ReportLab PDF with brief, funnel, fairness, shortlist, decisions and explanations | 2 | ✅ |

## Epic E5 — ML & data (Should)
| ID | User story | Acceptance criteria | SP | Status |
|---|---|---|---|---|
| E5-S1 | As a data scientist, I want a realistic dataset. | 3,000 employees, 180 jobs, about 4,400 applications, 3,200 placements, 3,000 résumés, 107 skills; deterministic seed | 5 | ✅ |
| E5-S2 | As the platform, I want an outcome model learned from past moves. | Gradient-boosted classifier, AUC ≥ 0.75, model card, feature importance; protected attributes excluded | 3 | ✅ |
| E5-S3 | As the platform, I want the model to learn from reviewers. | Each approve or reject becomes a labelled row; retraining runs in the background | 3 | ✅ |
| E5-S4 | As an engineer, I want local embeddings with no API quota. | MiniLM ONNX, 384 dimensions, 3,000+ documents indexed in about 4 minutes | 2 | ✅ |

## Next release (Could / Won't-now)
| ID | Story | Priority | SP |
|---|---|---|---|
| N-1 | Workday / SAP SuccessFactors MCP adapters replacing the seed data | Could | 13 |
| N-2 | Postgres, MongoDB and Neo4j via Docker Compose (code already isolated behind storage modules) | Could | 5 |
| N-3 | Teams/Slack notification when a matched role opens | Could | 3 |
| N-4 | Use a validation set to choose whether the LLM narrative or the template reads better | Could | 3 |
| N-5 | SSO (Entra ID / Okta) | Won't (MVP) | 5 |
