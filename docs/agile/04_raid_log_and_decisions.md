# RAID Log & Architecture Decision Records

## RAID log
| Type | Item | Impact | Mitigation / owner | Status |
|---|---|---|---|---|
| Risk | LLM capacity (Gemini 503s, 5 requests per minute per model on the free tier) | Slow or degraded agent runs | Model fallback chain, per-model rate windows, deterministic fallback per stage, caching — *Architect* | Mitigated |
| Risk | Biased shortlists | Legal and reputational | Protected attributes excluded from scoring and prompts; four-fifths audit plus rebalancing; human review — *AI Eng* | Mitigated |
| Risk | LLM inventing candidates or skills | Wrong decisions | Scores computed from MCP evidence only; grounding check on narratives; anonymised codes — *AI Eng* | Mitigated |
| Risk | Prompt injection through job posts or chat | Policy bypass | Injection scoring blocks posts and messages — *Architect* | Mitigated |
| Assumption | Synthetic data is representative of a 3,000-person IT services company | Demo validity | Realistic distributions; deterministic seed; documented generator | Accepted |
| Assumption | Docker is not available on the demo machine | Store choice | Embedded equivalents behind storage interfaces (SQLite, TinyDB, ChromaDB, NetworkX, file system) | Accepted |
| Issue | Embedding API quota too low for bulk indexing | Indexing blocked | Local MiniLM ONNX embeddings | Closed |
| Dependency | Google Programmable Search key | Live market intel | Cached sample results labelled in the UI until a key is configured | Open |

## ADR-001 — Three agent styles, each where it fits
**Context.** The rubric asks for a fully agentic system, and the problem has both fixed steps and exploratory steps.
**Decision.**
- **LangGraph** is the supervisor. It gives checkpoints, a human-review interrupt and conditional loops.
- **CrewAI** runs the role-based sourcing analysis in parallel.
- **langgraph-swarm** runs matching, where specialists choose the next step through handoffs.

**Consequences.** Each framework is used where it is strongest. Agents talk to each other through the run context and MCP, not through shared prompts.

## ADR-002 — MCP as the only data-access path
**Decision.** Employee, job and knowledge data are exposed through three FastMCP servers over streamable HTTP. Role checks travel in headers, and every write is audited.
**Consequences.** The data plane can be swapped for a real HR system without touching the agents. The same servers work in Claude Desktop or an IDE (`--stdio`).

## ADR-003 — Grounded scoring, LLM for language
**Decision.** Ranking is deterministic and explainable: the hybrid formula plus the ML probability. LLMs parse job descriptions, route intent, write briefs and narratives, and drive orchestration choices.
**Consequences.** The results can be reproduced and audited, and runs complete even without an LLM.

## ADR-004 — Embedded polyglot storage
**Decision.** Each storage role has its own module:
- Relational: SQLite (swap to PostgreSQL)
- NoSQL: TinyDB (swap to MongoDB)
- Vector: ChromaDB
- Graph: NetworkX, persisted, with Neo4j-compatible labels
- Files: local file system (swap to S3/MinIO)

**Consequences.** The project runs without Docker. Production stores can be swapped in per module.

## ADR-005 — Fairness: four-fifths rule plus practical significance
**Decision.** A shortlist is flagged only when a group's impact ratio is below 0.8 **and** the group is at least 1.5 people short of proportional representation. Rebalancing uses only swaps within 6 score points, and runs at most once.
**Consequences.** This avoids false alarms on small shortlists while still catching material under-selection. Remaining flags go to the human reviewer.

## ADR-006 — Durable human-in-the-loop
**Decision.** Use the LangGraph SQLite checkpointer. At startup, the API marks runs that cannot be resumed as `interrupted`.
**Consequences.** Reviews survive restarts and deployments.
