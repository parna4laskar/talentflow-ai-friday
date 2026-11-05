import { useQuery } from '@tanstack/react-query'
import { Boxes, Database, Network, ShieldCheck, Workflow } from 'lucide-react'
import { Card, ErrorNote, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { FRAMEWORK_COLOR } from '../lib/format'

interface Arch { agents: { id: string; name: string; framework: string }[]; mcp_tools: Record<string, { name: string; description: string }[]> }

const LAYERS = [
  { icon: Boxes, name: 'Experience', items: ['React 19 + TypeScript + Tailwind', '4 personas · JWT RBAC', 'Live Agent Theater (SSE)', 'Recharts live dashboards', 'Copilot (intent-routed RAG)'] },
  { icon: ShieldCheck, name: 'API & Governance', items: ['FastAPI · Pydantic v2', 'Guardrails: PII, injection, inclusive language', 'Semantic + exact LLM cache', 'Audit log · model card', 'Fairness auditor (4/5 rule)'] },
  { icon: Workflow, name: 'Agentic Orchestration', items: ['LangGraph supervisor (checkpointed, HITL interrupt)', 'CrewAI Talent Sourcing Crew', 'langgraph-swarm matching specialists', 'Gemini 3.5 Flash with model fallback chain'] },
  { icon: Network, name: 'MCP Integration', items: ['employee-mcp (CRUD, RBAC)', 'jobs-mcp (postings, applications)', 'knowledge-mcp (RAG, skills graph, Google Search)'] },
  { icon: Database, name: 'Data & ML', items: ['SQLite/Postgres · TinyDB/Mongo', 'ChromaDB vectors (MiniLM)', 'Skills graph (NetworkX/Neo4j)', 'File store · GBDT outcome model'] },
]

export default function Architecture() {
  const q = useQuery({ queryKey: ['arch'], queryFn: () => api<Arch>('/system/architecture') })
  return (
    <>
      <PageHeader eyebrow="Under the hood" title="How TalentFlow AI works" subtitle="Seventeen agents across three agent frameworks. Every agent reads and writes employee data only through MCP servers." />
      <div className="mb-6 grid gap-3 lg:grid-cols-5">
        {LAYERS.map((l, i) => (
          <div key={l.name} className="card relative p-4">
            <div className="mb-2 flex items-center gap-2"><div className="grid h-8 w-8 place-items-center rounded-lg bg-navy-900 text-gold-400"><l.icon size={16} /></div><div><div className="text-[10px] font-bold uppercase tracking-widest text-ink-3">Layer {i + 1}</div><div className="font-semibold text-navy-900">{l.name}</div></div></div>
            <ul className="space-y-1 text-[13px] text-ink-2">{l.items.map((x) => <li key={x}>• {x}</li>)}</ul>
          </div>
        ))}
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorNote error={q.error} /> : (
        <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
          <Card title="Agent roster" subtitle="Colour = framework">
            <div className="grid gap-2 sm:grid-cols-2">{q.data!.agents.map((a) => (
              <div key={a.id} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: FRAMEWORK_COLOR[a.framework] }} />
                <span className="font-medium text-navy-900">{a.name}</span><span className="ml-auto text-[11px] text-ink-3">{a.framework}</span></div>))}</div>
          </Card>
          <Card title="Live MCP tool catalogue" subtitle="Discovered at runtime via MCP list_tools">
            <div className="grid gap-4 md:grid-cols-3">{Object.entries(q.data!.mcp_tools).map(([s, tools]) => (
              <div key={s}><div className="mb-2 font-semibold text-navy-900">{s}-mcp <span className="text-xs font-normal text-ink-3">({tools.length})</span></div>
                <ul className="space-y-1.5">{tools.map((t) => <li key={t.name} className="text-[12px]"><code className="rounded bg-steel-100 px-1 text-steel-600">{t.name}</code><div className="text-ink-3">{t.description}</div></li>)}</ul></div>))}</div>
          </Card>
        </div>
      )}
    </>
  )
}
