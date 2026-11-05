import { useQuery } from '@tanstack/react-query'
import { Brain, CheckCircle2, Database, HardDrive, Network, Scale, ShieldCheck, Zap } from 'lucide-react'
import { ChartCard, HBars } from '../components/charts'
import { Badge, Card, ErrorNote, KpiTile, PageHeader, Spinner, StatusPill } from '../components/ui'
import { api } from '../lib/api'
import { fmtNum, fmtPct, SERIES } from '../lib/format'

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Governance() {
  const q = useQuery({ queryKey: ['gov'], queryFn: () => api<any>('/governance'), refetchInterval: 10000 })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorNote error={q.error} />
  const g = q.data
  const fi = (g.model_card.feature_importance ?? []).map((f: any) => ({ ...f, pct: Math.round(f.importance * 1000) / 10 }))
  const st = g.storage
  const stores = [
    { kind: 'Relational', icon: Database, tech: 'SQLite → PostgreSQL', detail: 'employees, skills, jobs, applications, placements, runs, audit' },
    { kind: 'NoSQL', icon: HardDrive, tech: 'TinyDB → MongoDB', detail: Object.entries(st.nosql).map(([k, v]) => `${k} ${fmtNum(v as number)}`).join(' · ') },
    { kind: 'Vector', icon: Brain, tech: 'ChromaDB · MiniLM-384', detail: Object.entries(st.vector).map(([k, v]) => `${k} ${fmtNum(v as number)}`).join(' · ') },
    { kind: 'Graph', icon: Network, tech: 'NetworkX → Neo4j', detail: `${fmtNum(st.graph.nodes)} nodes · ${fmtNum(st.graph.edges)} edges` },
    { kind: 'File', icon: HardDrive, tech: 'Local FS → S3/MinIO', detail: `${st.files.resumes} résumés · ${st.files.policies} policies · ${st.files.reports} reports` },
  ]
  return (
    <>
      <PageHeader eyebrow="Intelligence & Governance" title="AI Governance Console" subtitle="Guardrails, fairness, caching, MCP health, model card, storage coverage and a full audit trail." />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <KpiTile accent label="LLM calls" value={fmtNum(g.llm.calls)} icon={Brain} hint={`avg ${g.llm.avg_latency_ms} ms`} />
        <KpiTile label="LLM cache hits" value={fmtNum(g.llm.cache_hits)} icon={Zap} hint={`${g.llm.fallbacks} model fallbacks`} />
        <KpiTile label="Cache hit ratio" value={fmtPct(g.cache.hit_ratio)} hint={`${fmtNum(g.cache.semantic_hits)} semantic hits`} />
        <KpiTile label="MCP calls" value={fmtNum(g.mcp.calls)} icon={Network} hint={`${g.mcp.errors} errors`} />
        <KpiTile label="PII redactions" value={fmtNum(g.llm.pii_redactions)} icon={ShieldCheck} />
        <KpiTile label="Guardrail warnings" value={fmtNum(g.guardrails.warnings)} hint={`${g.guardrails.blocked} blocked · ${g.guardrails.fallbacks} fallbacks`} />
      </div>
      <div className="mb-6 grid gap-6 xl:grid-cols-3">
        <Card title="MCP servers" subtitle="Model Context Protocol · streamable HTTP">
          <div className="space-y-2">{Object.entries(g.mcp.servers).map(([k, v]: any) => (
            <div key={k} className="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-sm"><span className="font-semibold text-navy-900">{k}-mcp</span>
              <span className="flex items-center gap-2 text-ink-2">{v.ok ? `${v.tools} tools` : v.error}<StatusPill status={v.ok ? 'good' : 'critical'} /></span></div>))}</div>
          <div className="mt-3 text-xs text-ink-3">Models: {g.llm.models.primary.join(' → ')} (with deterministic fallback)</div>
        </Card>
        <ChartCard title="Outcome-model feature importance" subtitle={`${g.model_card.model} · AUC ${g.model_card.auc} · acc ${g.model_card.accuracy} · n=${fmtNum(g.model_card.n_train)}`}
          rows={fi} height={260} columns={[{ key: 'feature', label: 'Feature' }, { key: 'pct', label: 'Importance (×100)' }]}>
          <HBars data={fi} cat="feature" val="pct" name="Permutation importance" width={150} color={SERIES[3]} />
        </ChartCard>
        <Card title={<span className="flex items-center gap-2"><Scale size={16} className="text-steel-600" />Fairness — recent runs</span>} subtitle="Four-fifths rule with practical significance">
          <div className="max-h-[270px] space-y-2 overflow-y-auto">
            {!g.fairness_runs.length && <div className="text-sm text-ink-3">No completed runs yet.</div>}
            {g.fairness_runs.map((r: any) => (
              <div key={r.run_id} className="rounded-lg border border-line px-3 py-2 text-[13px]">
                <div className="flex justify-between"><b className="text-navy-900">{r.job_id}</b>{r.fairness.rebalanced && <Badge tone="gold">re-balanced</Badge>}</div>
                <div className="mt-1 flex flex-wrap gap-2">{Object.entries(r.fairness.attributes ?? {}).map(([a, v]: any) => (
                  <span key={a} className="inline-flex items-center gap-1 text-ink-2">{a.replace('_', ' ')} {v.impact_ratio.toFixed(2)} <StatusPill status={v.pass ? 'good' : 'warning'} /></span>))}</div>
              </div>))}
          </div>
        </Card>
      </div>
      <Card title="Storage coverage" subtitle="Polyglot persistence — every store in use by the platform" className="mb-6">
        <div className="grid gap-3 md:grid-cols-5">{stores.map((s) => (
          <div key={s.kind} className="rounded-xl border border-line p-3"><div className="flex items-center gap-2"><s.icon size={16} className="text-steel-600" /><b className="text-navy-900">{s.kind}</b><CheckCircle2 size={14} className="ml-auto text-green-700" /></div>
            <div className="mt-1 text-xs font-semibold text-gold-500">{s.tech}</div><div className="mt-1 text-xs text-ink-2">{s.detail}</div></div>))}</div>
      </Card>
      <Card title="Audit trail" subtitle="Logins, MCP write tools, agent runs and human review decisions">
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-[13px]"><thead className="sticky top-0 bg-white"><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-3"><th className="py-2">Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Details</th></tr></thead>
            <tbody>{g.audit.map((a: any, i: number) => (
              <tr key={i} className="border-b border-line/50"><td className="py-1.5 tabular-nums text-ink-3">{new Date(a.ts).toLocaleString()}</td><td className="font-medium text-navy-900">{a.actor}</td>
                <td><Badge tone={a.action.startsWith('mcp') ? 'steel' : a.action.includes('review') ? 'gold' : 'gray'}>{a.action}</Badge></td><td className="max-w-[220px] truncate text-ink-2">{a.target}</td>
                <td className="max-w-[260px] truncate text-xs text-ink-3">{JSON.stringify(a.details)}</td></tr>))}</tbody></table>
        </div>
      </Card>
    </>
  )
}
