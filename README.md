# TalentFlow AI — Agentic Internal Talent Marketplace

TalentFlow AI matches employees to internal roles by **skills, applications, location and availability**.
When a hiring manager posts a role, a team of 17 agents goes to work:

- **LangGraph** controls the overall workflow.
- A **CrewAI** crew builds the candidate pool.
- A **Swarm** of matching specialists hands work to each other (langgraph-swarm).
- Employee data is read and written **only through MCP servers**.

The output is a fair, explainable shortlist that a human approves or rejects. Every decision retrains the outcome model.

![stack](https://img.shields.io/badge/LangGraph-supervisor-2a78d6) ![](https://img.shields.io/badge/CrewAI-sourcing%20crew-c98500)
![](https://img.shields.io/badge/Swarm-matchers-1baf7a) ![](https://img.shields.io/badge/MCP-3%20servers-6250d6) ![](https://img.shields.io/badge/Gemini-3.5%20Flash-e34948)

| | |
|---|---|
| Architecture & framework diagrams | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · browser version: [docs/architecture.html](docs/architecture.html) |
| Agile delivery docs | [docs/agile/](docs/agile/) |
| Presentation | [docs/presentation.md](docs/presentation.md) (speaker version of the deck) |

---

## Quick start (Windows; no Docker needed)

Requirements: Python 3.12 and Node 20 or later.

```powershell
# 1) Python environment + data (≈5 min: generates 3,000 employees and embeds 3,000 résumés locally)
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
copy .env.example .env            # then set GEMINI_API_KEY
.venv\Scripts\python data\generate_seed.py
.venv\Scripts\python backend\scripts\bootstrap.py

# 2) Run all three MCP servers (employee :8101, jobs :8102, knowledge :8103)
.venv\Scripts\python backend\scripts\run_mcp_servers.py

# 3) API (new terminal)
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --port 8000

# 4) UI (new terminal)
cd frontend; npm install; npm run dev       # http://localhost:5173
```

Or run `start.ps1`, which opens the MCP servers, the API and the UI in three windows.

### Demo personas (password `Demo@123`)

| Username | Persona | What to show |
|---|---|---|
| `hiring.manager` | Hiring Manager | Post a role, then watch the **Live Agent Theater**, then approve or reject the explainable shortlist and download the PDF |
| `hr.admin` | HR Admin | Command Center with live pulse, the employee directory (MCP CRUD), and the **AI Governance** console |
| `employee` | Employee | **Career Hub**: roles ranked for me, skill-gap learning plan, apply |
| `leader` | Leadership | Mobility trends, scarcest and hottest skills, cost avoided, retention risk |

The **TalentFlow Copilot** button appears in every persona. It detects the intent of a question and routes it: policy questions go to search over policy documents (RAG), and there are also job search, talent search and insight answers. A semantic cache returns stored answers for near-identical questions, and guardrails screen every message.

---

## What runs where

| Layer | Implementation |
|---|---|
| UI | React 19, TypeScript, Vite, Tailwind 4, Recharts, React Query; JWT login with role-based access for 4 personas; live updates over SSE |
| API | FastAPI + Pydantic v2: REST endpoints, SSE streams for agent events and live telemetry, audit log |
| Orchestration | LangGraph `StateGraph` with a **SQLite checkpointer**. Human review uses `interrupt()`, so runs waiting for review survive restarts. A fairness check can send the shortlist back to the ranker |
| Agents | CrewAI crew (4 agents running in parallel) and a langgraph-swarm with 3 specialists that hand off to each other |
| LLM | Gemini (3.5 Flash for reasoning, 3.5 Flash-Lite for intent and agents). Includes a model fallback chain, per-model rate limits for the free tier (5 requests/minute per model), and exact and semantic caching |
| MCP | `employee-mcp` (search and CRUD, with role checks; protected attributes go only to the auditor role), `jobs-mcp`, `knowledge-mcp` (RAG, skills graph, Google Search) |
| Storage | Relational: SQLite (swap to Postgres). NoSQL: TinyDB (swap to MongoDB). Vector: ChromaDB. Graph: NetworkX (swap to Neo4j). Files: résumés, policies and PDF reports |
| ML | Local MiniLM-L6 embeddings (ONNX) and a gradient-boosted outcome model, AUC ≈ 0.76, retrained on reviewer feedback |

### Resilience

Gemini's free tier returns 503 and 429 errors under load. Every agent stage that uses the LLM therefore has a grounded fallback that does the same work deterministically:

- The crew tools still run.
- The swarm specialists run in their default order.
- Explanations come from templates.

The Theater shows these steps as `fallback`, and a run always completes. Every number in a shortlist comes from MCP data, not from LLM text.

### Google Search
`knowledge-mcp.market_intel` calls Google Programmable Search when `GOOGLE_CSE_KEY` and `GOOGLE_CSE_ID` are set. Otherwise it uses cached sample results from `data/seed/market_intel.json`, labelled as such in the UI.

---

## Data (synthetic, deterministic, about 14,000 records)

`data/generate_seed.py` (seed 20261105) produces:

- 3,000 employees across 12 sites and 32 role families, with skill proficiency, verification, availability windows, career interests, projects, certifications and performance
- 180 jobs with free-text job descriptions (5 deliberately contain biased wording, to demonstrate the guardrails)
- About 4,400 applications with cover notes
- 3,200 historical moves with 12-month outcomes, used to train the ML model
- 107 skills with market growth and an adjacency graph
- 3,000 unstructured résumés and 5 policy documents

All people and organisations are fictional.

## Tests

```powershell
cd backend; ..\.venv\Scripts\python -m pytest -q     # guardrails, scoring, intent, ML, API auth/RBAC/policy
cd frontend; npm run lint; npm run build
```

## Repository layout

```
backend/app/agents/      graph.py (LangGraph) · crew.py (CrewAI) · swarm.py (Swarm) · nodes/ · scoring.py · events.py
backend/app/core/        config, Gemini gateway (fallback, rate limits, cache, PII redaction)
backend/app/guardrails/  PII, prompt injection, inclusive language, grounding
backend/app/storage/     relational · document · vector · graph · files · cache
backend/app/ml/          embeddings · outcome model
backend/app/services/    career (reverse matching) · assistant (Copilot) · insights
backend/mcp_servers/     employee_server.py · jobs_server.py · knowledge_server.py
data/                    taxonomy + generator, seed JSON, résumés, policies
frontend/src/            pages (one workspace per persona) · components (AgentTheater, MatchCard, charts, Copilot)
docs/                    architecture, agile, presentation
```
