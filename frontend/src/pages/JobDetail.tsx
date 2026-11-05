import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, CalendarDays, Download, MapPin, Play, Scale, Send, ShieldCheck, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import AgentTheater from '../components/AgentTheater'
import MatchCard, { type Draft } from '../components/MatchCard'
import { Badge, Card, Empty, ErrorNote, JobStatus, PageHeader, Spinner, StatusPill } from '../components/ui'
import { api, withToken } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDate } from '../lib/format'
import { useRunEvents } from '../lib/hooks'
import type { Job, RunDetail } from '../lib/types'

export default function JobDetail() {
  const { jobId } = useParams()
  const [params, setParams] = useSearchParams()
  const { user } = useAuth()
  const qc = useQueryClient()
  const canRun = user?.role === 'hiring_manager' || user?.role === 'hr_admin'
  const job = useQuery({ queryKey: ['job', jobId], queryFn: () => api<Job>(`/jobs/${jobId}`) })
  const runs = useQuery({ queryKey: ['runs', jobId], queryFn: () => api<{ run_id: string; status: string; started_at: string }[]>(`/runs?job_id=${jobId}`) })
  const runId = params.get('run') ?? runs.data?.[0]?.run_id ?? null
  const { events, connected } = useRunEvents(runId)
  const lastType = events[events.length - 1]?.type
  const run = useQuery({
    queryKey: ['run', runId], enabled: !!runId, queryFn: () => api<RunDetail>(`/runs/${runId}`),
    refetchInterval: (q) => (q.state.data && ['completed', 'failed', 'blocked'].includes(q.state.data.status) ? false : 4000),
  })
  useEffect(() => { if (['interrupt', 'done', 'result'].includes(lastType ?? '')) qc.invalidateQueries({ queryKey: ['run', runId] }) }, [events.length, lastType, qc, runId])

  const start = useMutation({
    mutationFn: () => api<{ run_id: string }>('/runs', { method: 'POST', json: { job_id: jobId } }),
    onSuccess: (r) => { setParams({ run: r.run_id }); qc.invalidateQueries({ queryKey: ['runs', jobId] }) },
  })
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const review = useMutation({
    mutationFn: () => api('/runs/' + runId + '/review', {
      method: 'POST', json: { decisions: Object.entries(drafts).filter(([, d]) => d.decision).map(([employee_id, d]) => ({ employee_id, decision: d.decision, reason: d.reason })) },
    }),
    onSuccess: () => { setDrafts({}); qc.invalidateQueries({ queryKey: ['run', runId] }) },
  })
  const pendingDecisions = Object.values(drafts).filter((d) => d.decision)
  const missingReason = pendingDecisions.some((d) => d.decision === 'rejected' && !d.reason.trim())
  const r = run.data
  const awaiting = r?.status === 'awaiting_review'
  const live = r?.live ?? r?.summary ?? {}
  const fairness = live?.fairness ?? r?.summary?.fairness
  const guard = live?.guardrail ?? r?.summary?.guardrail
  const brief = r?.summary?.sourcing_brief ?? live?.crew?.brief

  const reqs = live?.requirements?.required_skills ?? job.data?.required_skills ?? []

  if (job.isLoading) return <Spinner />
  if (job.error) return <ErrorNote error={job.error} />
  const j = job.data!

  return (
    <>
      <PageHeader eyebrow={`${j.job_id} · ${j.department}`} title={j.title}
        subtitle={<span className="flex flex-wrap items-center gap-3"><span className="inline-flex items-center gap-1"><MapPin size={14} />{j.location.city}, {j.location.country} · {j.work_mode}</span>
          <span className="inline-flex items-center gap-1"><CalendarDays size={14} />Start {fmtDate(j.start_date)}</span><JobStatus s={j.status} /><Badge tone="gold">{j.priority}</Badge></span>}
        actions={canRun && <button className="btn btn-gold" onClick={() => start.mutate()} disabled={start.isPending || run.data?.status === 'running'}>
          <Play size={16} />{runId ? 'Re-run agents' : 'Find internal talent'}</button>} />

      <div className="mb-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card title="Job description" subtitle="Unstructured text → structured requirements by the JD Parser agent">
          <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-ink-2">{j.description}</pre>
        </Card>
        <Card title="Structured requirements" subtitle={live?.requirements?.source ? `Extracted via ${live.requirements.source}` : 'From posting'}>
          <div className="space-y-1.5">
            {reqs.map((s: { name: string; min_proficiency: number; source?: string }) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <span className="font-medium text-navy-900">{s.name} {s.source && <Badge tone="gold" className="ml-1">AI-added</Badge>}</span>
                <span className="flex gap-0.5" aria-label={`min proficiency ${s.min_proficiency}`}>{[1, 2, 3, 4, 5].map((n) => <span key={n} className={`h-2 w-4 rounded-sm ${n <= s.min_proficiency ? 'bg-steel-600' : 'bg-slate-200'}`} />)}</span>
              </div>
            ))}
          </div>
          {!!j.nice_to_have_skills.length && <div className="mt-3 flex flex-wrap gap-1">{j.nice_to_have_skills.map((n) => <Badge key={n}>{n}</Badge>)}</div>}
          {live?.requirements?.summary && <p className="mt-3 border-t border-line pt-3 text-[13px] italic text-ink-2">{live.requirements.summary}</p>}
        </Card>
      </div>

      {!runId ? (
        <Empty><Bot className="mx-auto mb-2 text-steel-600" />No agent run yet. {canRun ? 'Click “Find internal talent” to launch the agent team.' : ''}</Empty>
      ) : (
        <>
          <AgentTheater events={events} connected={connected} />

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <Card title={<span className="flex items-center gap-2"><Sparkles size={16} className="text-gold-500" />Sourcing brief</span>} subtitle={`CrewAI · ${live?.crew?.mode ?? '…'} mode`}>
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-2">{brief ?? 'The crew is working…'}</p>
            </Card>
            <Card title={<span className="flex items-center gap-2"><ShieldCheck size={16} className="text-steel-600" />Guardrails</span>} subtitle="Input screening">
              {guard ? (
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-ink-2">Decision</span><StatusPill status={guard.decision === 'pass' ? 'good' : guard.decision === 'block' ? 'critical' : 'warning'} /></div>
                  <div className="flex justify-between"><span className="text-ink-2">Inclusivity</span><b>{guard.inclusivity_score}/100</b></div>
                  <div className="flex justify-between"><span className="text-ink-2">Injection risk</span><b>{guard.injection_score}</b></div>
                  {guard.findings?.map((f: { phrase: string; suggestion: string }) => <div key={f.phrase} className="rounded bg-amber-50 p-1.5 text-xs text-amber-900">“{f.phrase}” — {f.suggestion}</div>)}
                </div>
              ) : <Spinner />}
            </Card>
            <Card title={<span className="flex items-center gap-2"><Scale size={16} className="text-steel-600" />Fairness audit</span>} subtitle="Four-fifths rule + practical significance">
              {fairness ? (
                <div className="space-y-2 text-sm">
                  {Object.entries(fairness.attributes ?? {}).map(([a, v]) => {
                    const x = v as { impact_ratio: number; pass: boolean; note: string | null }
                    return (<div key={a}><div className="flex items-center justify-between"><span className="capitalize text-ink-2">{a.replace('_', ' ')}</span>
                      <span className="flex items-center gap-2"><b className="tabular-nums">{x.impact_ratio.toFixed(2)}</b><StatusPill status={x.pass ? 'good' : 'warning'} /></span></div>
                      {x.note && <div className="text-[11px] text-ink-3">{x.note}</div>}</div>)
                  })}
                  {fairness.rebalanced && <Badge tone="gold">Shortlist re-balanced</Badge>}
                  <div className="text-[11px] text-ink-3">Protected attributes are fetched only under the auditor role and never used for scoring or sent to the LLM.</div>
                </div>
              ) : <Spinner label="Audit pending…" />}
            </Card>
          </div>

          <div className="mt-6">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-serif text-2xl text-navy-900">Explainable shortlist</h2>
                <p className="text-sm text-ink-2">{awaiting ? 'Human-in-the-loop: approve or reject each candidate (a reason is required for rejections). Your decisions retrain the outcome model.' : r?.status === 'completed' ? 'Review complete — report generated.' : 'Agents are still working…'}</p>
              </div>
              <div className="flex gap-2">
                {r?.status === 'completed' && <a className="btn btn-ghost" href={withToken(`/runs/${runId}/report`)} target="_blank" rel="noreferrer"><Download size={16} />PDF report</a>}
                {awaiting && canRun && <button className="btn btn-primary" disabled={!pendingDecisions.length || missingReason || review.isPending} onClick={() => review.mutate()}>
                  <Send size={16} />Submit {pendingDecisions.length || ''} decision{pendingDecisions.length === 1 ? '' : 's'}</button>}
              </div>
            </div>
            {review.error && <ErrorNote error={review.error} />}
            {r?.status === 'blocked' && <ErrorNote error="Run blocked by the input guardrail." />}
            {!r?.results.length ? <Empty>Match cards appear here once the Explainer agent finishes.</Empty> : (
              <div className="grid gap-3 2xl:grid-cols-2">
                {r.results.map((c) => <MatchCard key={c.employee_id} c={c} reviewable={awaiting && canRun} draft={drafts[c.employee_id]}
                  onDraft={(d) => setDrafts({ ...drafts, [c.employee_id]: d })} />)}
              </div>
            )}
            {r?.summary?.model_update && <div className="mt-4 rounded-lg bg-steel-100 px-4 py-2 text-sm text-steel-600">Outcome model retrained on your feedback → AUC {r.summary.model_update.auc} ({r.summary.model_update.rows} labelled moves).</div>}
          </div>
        </>
      )}
    </>
  )
}
