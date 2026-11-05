import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, BadgeCheck, CalendarDays, Compass, GraduationCap, MapPin, Rocket, Send, X } from 'lucide-react'
import { useState } from 'react'
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import { Badge, Card, ChartTip, ErrorNote, KpiTile, MiniBar, PageHeader, ScoreRing, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { COMPONENT_LABEL, COMPONENT_WEIGHT, fmtDate, SERIES } from '../lib/format'
import type { Employee, Job } from '../lib/types'

interface Match { job: Job; score: number; components: Record<string, number>; gaps: { skill: string; have: number; need: number }[]; strengths: { skill: string }[]; bridges: { missing: string; via: string }[]; location: string; availability: { status: string; gap_days: number }; level_ok: boolean }
interface Plan { job: Job; coverage: number; plan: { skill: string; have: number; need: number; via: string | null; transfer_weight: number; path: string[]; estimated_weeks: number }[]; market_signal: string | null }

export default function CareerHub() {
  const q = useQuery({ queryKey: ['my-matches'], queryFn: () => api<{ employee: Employee; matches: Match[] }>('/me/matches') })
  const [planFor, setPlanFor] = useState<string | null>(null)
  if (q.isLoading) return <Spinner label="Agents are matching open roles to your profile…" />
  if (q.error) return <ErrorNote error={q.error} />
  const { employee: me, matches } = q.data!
  const radar = [...me.skills].sort((a, b) => b.proficiency - a.proficiency).slice(0, 8).map((s) => ({ skill: s.name, proficiency: s.proficiency }))
  return (
    <>
      <PageHeader eyebrow="Career Hub" title={`Hi ${me.name.split(' ')[0]}, here's where you could grow next`} subtitle="Roles ranked for you by the same explainable engine hiring managers use — with a learning plan for every gap." />
      <div className="mb-6 grid gap-4 sm:grid-cols-4">
        <KpiTile accent label="Strong matches" value={matches.filter((m) => m.score >= 70).length} icon={Rocket} hint="score ≥ 70" />
        <KpiTile label="Availability" value={<span className="text-xl">{me.availability.status}</span>} icon={CalendarDays} hint={`from ${fmtDate(me.availability.available_from)}`} />
        <KpiTile label="Verified skills" value={me.skills.filter((s) => s.verified).length} icon={BadgeCheck} hint={`of ${me.skills.length}`} />
        <KpiTile label="Move eligibility" value={<span className="text-xl">{me.eligible_for_move ? 'Eligible' : 'Not yet'}</span>} icon={Compass} hint={`${me.months_in_role} months in role`} />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1fr_2fr]">
        <div className="space-y-6">
          <Card title="Your skill profile" subtitle="Top skills by proficiency (1–5)">
            <div className="viz-root h-[280px]">
              <ResponsiveContainer>
                <RadarChart data={radar} outerRadius="72%">
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="skill" tick={{ fontSize: 10, fill: '#475569' }} />
                  <Tooltip content={<ChartTip />} />
                  <Radar dataKey="proficiency" name="Proficiency" stroke={SERIES[0]} fill={SERIES[0]} fillOpacity={0.18} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Profile">
            <div className="space-y-2 text-sm text-ink-2">
              <div><b className="text-navy-900">{me.title}</b> · {me.department}</div>
              <div className="flex items-center gap-1"><MapPin size={13} />{me.city}, {me.country} · prefers {me.work_mode_preference}</div>
              <div>Target roles: {me.target_roles.join(', ')}</div>
              {me.aspiration && <div className="italic">“{me.aspiration}”</div>}
              <div className="flex flex-wrap gap-1 pt-1">{me.certifications.map((c) => <Badge key={c} tone="gold">{c}</Badge>)}</div>
            </div>
          </Card>
        </div>
        <div className="space-y-3">
          {matches.map((m) => <RoleMatch key={m.job.job_id} m={m} onPlan={() => setPlanFor(m.job.job_id)} />)}
        </div>
      </div>
      {planFor && <PlanModal jobId={planFor} onClose={() => setPlanFor(null)} />}
    </>
  )
}

function RoleMatch({ m, onPlan }: { m: Match; onPlan: () => void }) {
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const [open, setOpen] = useState(false)
  const apply = useMutation({ mutationFn: () => api('/me/apply', { method: 'POST', json: { job_id: m.job.job_id, cover_note: note } }), onSuccess: () => qc.invalidateQueries({ queryKey: ['my-matches'] }) })
  return (
    <article className="card slide-in p-4">
      <div className="flex items-start gap-4">
        <ScoreRing score={m.score} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-navy-900">{m.job.title}</h3><span className="text-xs text-ink-3">{m.job.job_id}</span>
            {!m.level_ok && <Badge tone="warn">Level stretch</Badge>}{m.bridges.length > 0 && <Badge tone="gold">Bridgeable gaps</Badge>}</div>
          <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-ink-2"><span>{m.job.department}</span><span className="inline-flex items-center gap-1"><MapPin size={11} />{m.job.location.city} · {m.job.work_mode}</span><span>Start {fmtDate(m.job.start_date)}</span></div>
          <div className="mt-2 flex flex-wrap gap-1">
            {m.strengths.map((s) => <Badge key={s.skill} tone="good">✓ {s.skill}</Badge>)}
            {m.gaps.map((g) => <Badge key={g.skill} tone="bad">{g.skill} {g.have}/{g.need}</Badge>)}
          </div>
          <div className="mt-3 grid grid-cols-3 gap-x-4 gap-y-1.5">{Object.entries(m.components).map(([k, v]) => <MiniBar key={k} label={COMPONENT_LABEL[k]} value={v} weight={COMPONENT_WEIGHT[k]} />)}</div>
        </div>
        <div className="flex flex-col gap-2">
          <button className="btn btn-primary py-1.5" onClick={() => setOpen(!open)}><Send size={14} />Apply</button>
          <button className="btn btn-ghost py-1.5" onClick={onPlan}><GraduationCap size={14} />Gap plan</button>
        </div>
      </div>
      {open && (
        <div className="mt-3 flex gap-2 border-t border-line pt-3">
          <input className="input" placeholder="Short note to the hiring manager (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <button className="btn btn-gold" disabled={apply.isPending || apply.isSuccess} onClick={() => apply.mutate()}>{apply.isSuccess ? 'Applied ✓' : 'Submit'}</button>
        </div>
      )}
      {apply.error && <div className="mt-2"><ErrorNote error={apply.error} /></div>}
    </article>
  )
}

function PlanModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ['plan', jobId], queryFn: () => api<Plan>(`/me/skill-gap/${jobId}`) })
  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-navy-950/40 p-4" onClick={onClose}>
      <div className="card w-full max-w-2xl p-6" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="mb-4 flex items-start justify-between"><div><div className="eyebrow">Personal learning plan</div><h3 className="font-serif text-2xl text-navy-900">{q.data?.job.title ?? '…'}</h3></div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-slate-100"><X size={18} /></button></div>
        {q.isLoading ? <Spinner label="Walking the skills graph…" /> : q.error ? <ErrorNote error={q.error} /> : (
          <div className="space-y-3">
            <div className="text-sm text-ink-2">Current coverage of required skills: <b className="text-navy-900">{Math.round(q.data!.coverage * 100)}%</b></div>
            {!q.data!.plan.length && <div className="rounded-lg bg-green-50 p-3 text-sm text-green-800">You already meet every required skill — apply now!</div>}
            {q.data!.plan.map((p) => (
              <div key={p.skill} className="rounded-xl border border-line p-3">
                <div className="flex items-center justify-between"><b className="text-navy-900">{p.skill}</b><Badge tone="steel">~{p.estimated_weeks} weeks</Badge></div>
                <div className="mt-1 text-[13px] text-ink-2">Level {p.have} → {p.need}{p.via ? <> · leverage your <b>{p.via}</b> (transfer {Math.round(p.transfer_weight * 100)}%)</> : ' · new skill area'}</div>
                {p.path.length > 1 && <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">{p.path.map((s, i) => <span key={s} className="inline-flex items-center gap-1"><Badge tone={i === 0 ? 'good' : i === p.path.length - 1 ? 'gold' : 'gray'}>{s}</Badge>{i < p.path.length - 1 && <ArrowRight size={12} className="text-ink-3" />}</span>)}</div>}
              </div>
            ))}
            {q.data!.market_signal && <div className="rounded-lg bg-steel-100 p-3 text-[13px] text-steel-600"><b>Market signal:</b> {q.data!.market_signal}</div>}
          </div>
        )}
      </div>
    </div>
  )
}
