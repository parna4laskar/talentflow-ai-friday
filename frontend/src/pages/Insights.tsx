import { AlertTriangle, CheckCircle2, Clock3, DollarSign, Gem, OctagonAlert, Repeat, TrendingUp, Users } from 'lucide-react'
import { ChartCard, HBars, LivePulse, TrendLine } from '../components/charts'
import { ErrorNote, KpiTile, PageHeader, Spinner } from '../components/ui'
import { toRows, useOverview } from '../lib/insights'
import { fmtNum, fmtPct, fmtUsd, SERIES, STATUS } from '../lib/format'

const monthFmt = (m: string) => new Date(`${m}-01`).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })

export default function Insights() {
  const q = useOverview()
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorNote error={q.error} />
  const d = q.data!
  const k = d.kpis
  const coverage = d.supply_demand.map((s) => ({ ...s, per_role: Math.round(s.employees / Math.max(1, s.open_roles)) })).sort((a, b) => a.per_role - b.per_role).slice(0, 12)
  const hot = d.hot_skills.map((h) => ({ ...h, yoy: Math.round((h.growth - 1) * 100) }))
  const flows = d.flows.slice(0, 10).map((f) => ({ ...f, path: `${short(f.from)} → ${short(f.to)}` }))
  const risk = ['Low', 'Medium', 'High'].map((r) => ({ level: r, employees: d.by_retention_risk[r] ?? 0 }))

  return (
    <>
      <PageHeader eyebrow="Leadership" title="Talent Mobility Insights" subtitle="Business impact of internal mobility: speed, cost avoided, skills supply vs demand and retention signals." />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <KpiTile accent label="Cost avoided (36 m)" value={fmtUsd(k.cost_avoided_usd ?? 0)} icon={DollarSign} hint="vs external hiring" />
        <KpiTile label="Internal fill rate" value={fmtPct(k.internal_fill_rate)} icon={Repeat} hint="filled ÷ (filled + closed)" />
        <KpiTile label="Avg time to fill" value={`${k.avg_time_to_fill_days} d`} icon={Clock3} hint="internal moves" />
        <KpiTile label="Move success rate" value={fmtPct(k.move_success_rate)} icon={TrendingUp} hint="retained & performing at 12 m" />
        <KpiTile label="Eligible to move" value={fmtNum(k.eligible_for_move)} icon={Users} hint={`of ${fmtNum(k.headcount)} employees`} />
        <KpiTile label="Hidden fits surfaced" value={fmtNum(k.hidden_fits_surfaced)} icon={Gem} hint={`${fmtNum(k.matching_runs)} agent runs`} />
      </div>

      <div className="mb-6"><LivePulse /></div>

      <div className="mb-6 grid gap-6 xl:grid-cols-2">
        <ChartCard title="Internal moves per month" subtitle="Historical placements with known 12-month outcomes" rows={d.trend} height={240}
          columns={[{ key: 'month', label: 'Month' }, { key: 'internal_moves', label: 'Moves' }]}>
          <TrendLine data={d.trend} x="month" y="internal_moves" name="Internal moves" area xFmt={monthFmt} />
        </ChartCard>
        <ChartCard title="Average time to fill (days)" subtitle="Lower is better" rows={d.trend} height={240}
          columns={[{ key: 'month', label: 'Month' }, { key: 'avg_time_to_fill_days', label: 'Days' }]}>
          <TrendLine data={d.trend} x="month" y="avg_time_to_fill_days" name="Avg time to fill" unit=" d" color={SERIES[1]} xFmt={monthFmt} />
        </ChartCard>
      </div>

      <div className="mb-6 grid gap-6 xl:grid-cols-3">
        <ChartCard title="Scarcest skills" subtitle="Employees holding the skill per open role requiring it (lower = scarcer)" rows={coverage} height={330}
          columns={[{ key: 'skill', label: 'Skill' }, { key: 'open_roles', label: 'Open roles' }, { key: 'employees', label: 'Employees' }, { key: 'per_role', label: 'Per role' }]}>
          <HBars data={coverage} cat="skill" val="per_role" name="Employees per open role" width={150} />
        </ChartCard>
        <ChartCard title="Hottest skills in the market" subtitle="Year-over-year demand growth (Google Search market intel)" rows={hot} height={330}
          columns={[{ key: 'skill', label: 'Skill' }, { key: 'yoy', label: 'YoY %' }, { key: 'employees', label: 'Internal supply' }]}>
          <HBars data={hot} cat="skill" val="yoy" name="YoY growth" unit="%" color={SERIES[1]} width={150} fmt={(v) => `+${v}%`} />
        </ChartCard>
        <ChartCard title="Top cross-department moves" subtitle="Where internal talent flows" rows={flows} height={330}
          columns={[{ key: 'from', label: 'From' }, { key: 'to', label: 'To' }, { key: 'moves', label: 'Moves' }]}>
          <HBars data={flows} cat="path" val="moves" name="Moves" color={SERIES[2]} width={170} />
        </ChartCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <ChartCard title="Open roles by department" rows={toRows(d.open_by_department, 'department', 'roles')} height={280}
          columns={[{ key: 'department', label: 'Department' }, { key: 'roles', label: 'Open roles' }]}>
          <HBars data={toRows(d.open_by_department, 'department', 'roles')} cat="department" val="roles" name="Open roles" width={160} />
        </ChartCard>
        <ChartCard title="Workforce availability" rows={toRows(d.by_availability, 'status', 'employees')} height={280}
          columns={[{ key: 'status', label: 'Status' }, { key: 'employees', label: 'Employees' }]}>
          <HBars data={toRows(d.by_availability, 'status', 'employees')} cat="status" val="employees" name="Employees" color={SERIES[3]} width={130} />
        </ChartCard>
        <ChartCard title="Retention risk" subtitle="Model-scored flight risk — act on High first" rows={risk} height={280}
          columns={[{ key: 'level', label: 'Risk' }, { key: 'employees', label: 'Employees' }]}>
          <div className="flex h-full flex-col justify-center gap-4">
            {risk.map((r) => {
              const Icon = r.level === 'Low' ? CheckCircle2 : r.level === 'Medium' ? AlertTriangle : OctagonAlert
              const color = r.level === 'Low' ? STATUS.good : r.level === 'Medium' ? STATUS.warning : STATUS.critical
              const total = risk.reduce((a, b) => a + b.employees, 0)
              return (
                <div key={r.level}>
                  <div className="mb-1 flex items-center justify-between text-sm"><span className="inline-flex items-center gap-1.5 font-medium text-navy-900"><Icon size={15} style={{ color }} />{r.level} risk</span>
                    <span className="tabular-nums text-ink-2">{fmtNum(r.employees)} · {fmtPct(r.employees / total)}</span></div>
                  <div className="h-2.5 rounded-full bg-slate-100"><div className="h-2.5 rounded-full" style={{ width: `${(r.employees / total) * 100}%`, background: color }} /></div>
                </div>
              )
            })}
          </div>
        </ChartCard>
      </div>
    </>
  )
}

const short = (s: string) => s.replace('& Infrastructure', '& Infra').replace('AI Center of Excellence', 'AI CoE').replace('Enterprise Applications', 'Ent. Apps').replace('Delivery Excellence', 'Delivery').replace('Business Consulting', 'Consulting')
