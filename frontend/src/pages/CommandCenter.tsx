import { useQuery } from '@tanstack/react-query'
import { Bot, BriefcaseBusiness, Gem, Timer, UserCheck, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { ChartCard, HBars, LivePulse } from '../components/charts'
import { Badge, Card, Empty, ErrorNote, KpiTile, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { fmtNum, fmtPct, SERIES } from '../lib/format'
import { toRows, useOverview } from '../lib/insights'

interface RunRow { run_id: string; job_id: string; status: string; started_by: string; started_at: string; summary: { funnel?: Record<string, number>; approved?: string[]; time_to_shortlist_s?: number; hidden_fits?: number } }

const RUN_TONE: Record<string, 'good' | 'gold' | 'steel' | 'bad' | 'gray'> = { completed: 'good', awaiting_review: 'gold', running: 'steel', finalizing: 'steel', failed: 'bad', blocked: 'bad' }

export default function CommandCenter() {
  const ov = useOverview()
  const runs = useQuery({ queryKey: ['runs-all'], queryFn: () => api<RunRow[]>('/runs'), refetchInterval: 8000 })
  if (ov.isLoading) return <Spinner />
  if (ov.error) return <ErrorNote error={ov.error} />
  const d = ov.data!
  const levels = ['L1', 'L2', 'L3', 'L4', 'L5'].map((l) => ({ level: l, employees: d.by_level[l] ?? 0 }))
  const apps = toRows(d.applications_by_status, 'status', 'count')
  return (
    <>
      <PageHeader eyebrow="HR Admin" title="Talent Command Center" subtitle="Workforce supply, marketplace demand and every agent run in one place." />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <KpiTile accent label="Headcount" value={fmtNum(d.kpis.headcount)} icon={Users} />
        <KpiTile label="Eligible to move" value={fmtNum(d.kpis.eligible_for_move)} icon={UserCheck} hint={fmtPct((d.kpis.eligible_for_move ?? 0) / (d.kpis.headcount ?? 1))} />
        <KpiTile label="Open roles" value={fmtNum(d.kpis.open_roles)} icon={BriefcaseBusiness} />
        <KpiTile label="Agent runs" value={fmtNum(d.kpis.matching_runs)} icon={Bot} />
        <KpiTile label="Hidden fits" value={fmtNum(d.kpis.hidden_fits_surfaced)} icon={Gem} />
        <KpiTile label="HM approval rate" value={fmtPct(d.kpis.approval_rate)} icon={Timer} hint="of reviewed AI matches" />
      </div>
      <div className="mb-6"><LivePulse /></div>
      <div className="mb-6 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card title="Recent agent runs" subtitle="Click a run to open its Live Agent Theater">
          {runs.isLoading ? <Spinner /> : !runs.data?.length ? <Empty>No runs yet.</Empty> : (
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-3"><th className="py-2">Run</th><th>Role</th><th>Funnel</th><th>Time</th><th>Status</th></tr></thead>
              <tbody>{runs.data.slice(0, 10).map((r) => (
                <tr key={r.run_id} className="border-b border-line/60 hover:bg-slate-50">
                  <td className="py-2"><Link className="font-medium text-steel-600 hover:underline" to={`/jobs/${r.job_id}?run=${r.run_id}`}>{r.run_id.slice(4, 19)}</Link><div className="text-xs text-ink-3">by {r.started_by}</div></td>
                  <td className="text-ink-2">{r.job_id}</td>
                  <td className="text-xs tabular-nums text-ink-2">{r.summary?.funnel ? `${r.summary.funnel.pooled} → ${r.summary.funnel['qualified(>=50)']} → ${r.summary.funnel.shortlisted}` : '—'}</td>
                  <td className="tabular-nums text-ink-2">{r.summary?.time_to_shortlist_s ? `${Math.round(r.summary.time_to_shortlist_s / 60)} min` : '—'}</td>
                  <td><Badge tone={RUN_TONE[r.status] ?? 'gray'}>{r.status.replace('_', ' ')}</Badge></td>
                </tr>))}</tbody>
            </table>
          )}
        </Card>
        <ChartCard title="Application pipeline" rows={apps} height={300} columns={[{ key: 'status', label: 'Status' }, { key: 'count', label: 'Applications' }]}>
          <HBars data={apps} cat="status" val="count" name="Applications" width={100} />
        </ChartCard>
      </div>
      <div className="grid gap-6 xl:grid-cols-3">
        <ChartCard title="Headcount by department" rows={toRows(d.by_department, 'department', 'employees')} height={340} columns={[{ key: 'department', label: 'Department' }, { key: 'employees', label: 'Employees' }]}>
          <HBars data={toRows(d.by_department, 'department', 'employees')} cat="department" val="employees" name="Employees" width={160} />
        </ChartCard>
        <ChartCard title="Headcount by region" rows={toRows(d.by_region, 'region', 'employees')} height={340} columns={[{ key: 'region', label: 'Region' }, { key: 'employees', label: 'Employees' }]}>
          <HBars data={toRows(d.by_region, 'region', 'employees')} cat="region" val="employees" name="Employees" color={SERIES[1]} width={60} />
        </ChartCard>
        <ChartCard title="Headcount by level" rows={levels} height={340} columns={[{ key: 'level', label: 'Level' }, { key: 'employees', label: 'Employees' }]}>
          <HBars data={levels} cat="level" val="employees" name="Employees" color={SERIES[2]} width={40} />
        </ChartCard>
      </div>
    </>
  )
}
