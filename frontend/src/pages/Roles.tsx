import { useQuery } from '@tanstack/react-query'
import { MapPin, PlusCircle, Search, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Card, Empty, ErrorNote, JobStatus, KpiTile, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDate } from '../lib/format'
import type { Job } from '../lib/types'

const PRIORITY_TONE = { Critical: 'bad', High: 'warn', Medium: 'steel', Low: 'gray' } as const

export default function Roles({ mine }: { mine: boolean }) {
  const { user } = useAuth()
  const [status, setStatus] = useState<string>('Open')
  const [q, setQ] = useState('')
  const jobs = useQuery({
    queryKey: ['jobs', mine, status],
    queryFn: () => api<Job[]>(`/jobs?mine=${mine}${status ? `&status=${encodeURIComponent(status)}` : ''}`),
  })
  const rows = useMemo(() => (jobs.data ?? []).filter((j) =>
    !q || `${j.title} ${j.job_id} ${j.location.city} ${j.department} ${j.required_skills.map((s) => s.name).join(' ')}`.toLowerCase().includes(q.toLowerCase())), [jobs.data, q])
  const apps = rows.reduce((a, j) => a + (j.applications ?? 0), 0)

  return (
    <>
      <PageHeader eyebrow={mine ? 'Hiring Manager' : 'All internal roles'} title={mine ? `Welcome back, ${user?.display_name.split(' ')[0]}` : 'Internal Roles'}
        subtitle={mine ? 'Your internal roles. Open one to run the agent team and review an explainable shortlist.' : 'Every internal posting across the organisation.'}
        actions={mine && <Link to="/hm/post" className="btn btn-gold"><PlusCircle size={16} />Post a role</Link>} />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <KpiTile label={`${status || 'All'} roles`} value={rows.length} icon={Users} accent />
        <KpiTile label="Applications" value={apps} hint="across listed roles" />
        <KpiTile label="Critical / High priority" value={rows.filter((r) => r.priority === 'Critical' || r.priority === 'High').length} />
      </div>
      <Card title="Roles" action={
        <div className="flex gap-2">
          <div className="relative"><Search size={14} className="absolute left-2.5 top-2.5 text-ink-3" />
            <input className="input w-60 pl-8 py-1.5" placeholder="Search title, skill, city…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <select className="input w-36 py-1.5" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
            {['Open', 'In Review', 'Filled', 'Closed', ''].map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
          </select>
        </div>}>
        {jobs.isLoading ? <Spinner /> : jobs.error ? <ErrorNote error={jobs.error} /> : rows.length === 0 ? <Empty>No roles match.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-3">
                <th className="py-2 pr-3">Role</th><th className="pr-3">Location</th><th className="pr-3">Key skills</th><th className="pr-3">Start</th>
                <th className="pr-3">Priority</th><th className="pr-3">Apps</th><th>Status</th></tr></thead>
              <tbody>
                {rows.map((j) => (
                  <tr key={j.job_id} className="border-b border-line/60 hover:bg-slate-50">
                    <td className="py-2.5 pr-3"><Link to={`/jobs/${j.job_id}`} className="font-semibold text-navy-900 hover:text-steel-600">{j.title}</Link>
                      <div className="text-xs text-ink-3">{j.job_id} · {j.department}{!mine && ` · ${j.hiring_manager_name}`}</div></td>
                    <td className="pr-3 text-ink-2"><span className="inline-flex items-center gap-1"><MapPin size={12} />{j.location.city}</span><div className="text-xs text-ink-3">{j.work_mode}</div></td>
                    <td className="pr-3"><div className="flex max-w-xs flex-wrap gap-1">{j.required_skills.slice(0, 4).map((s) => <Badge key={s.name} tone="steel">{s.name}</Badge>)}</div></td>
                    <td className="pr-3 text-ink-2">{fmtDate(j.start_date)}</td>
                    <td className="pr-3"><Badge tone={PRIORITY_TONE[j.priority as keyof typeof PRIORITY_TONE] ?? 'gray'}>{j.priority}</Badge></td>
                    <td className="pr-3 tabular-nums text-ink-2">{j.applications ?? 0}</td>
                    <td><JobStatus s={j.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
