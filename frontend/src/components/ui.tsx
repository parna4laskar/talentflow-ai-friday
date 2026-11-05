import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, Loader2, OctagonAlert, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function Card({ title, subtitle, action, children, className, bodyClass }: {
  title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; bodyClass?: string
}) {
  return (
    <section className={clsx('card', className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 px-5 pt-4">
          <div>
            {title && <h3 className="text-[15px] font-semibold text-navy-900">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={clsx('px-5 pb-5', title ? 'pt-3' : 'pt-5', bodyClass)}>{children}</div>
    </section>
  )
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h1 className="font-serif text-[28px] leading-tight text-navy-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  )
}

export function KpiTile({ label, value, hint, icon: Icon, accent = false }: { label: string; value: ReactNode; hint?: ReactNode; icon?: LucideIcon; accent?: boolean }) {
  return (
    <div className={clsx('card relative overflow-hidden px-5 py-4', accent && 'bg-navy-900 text-white')}>
      <div className="flex items-center justify-between">
        <span className={clsx('text-xs font-semibold uppercase tracking-wider', accent ? 'text-gold-400' : 'text-ink-3')}>{label}</span>
        {Icon && <Icon size={18} className={accent ? 'text-gold-400' : 'text-steel-600'} />}
      </div>
      <div className={clsx('mt-2 text-[28px] font-semibold tabular-nums leading-none', accent ? 'text-white' : 'text-navy-900')}>{value}</div>
      {hint && <div className={clsx('mt-1.5 text-xs', accent ? 'text-slate-300' : 'text-ink-3')}>{hint}</div>}
    </div>
  )
}

const BADGE: Record<string, string> = {
  navy: 'bg-navy-900 text-white',
  steel: 'bg-steel-100 text-steel-600',
  gold: 'bg-gold-100 text-[#8a6a00]',
  gray: 'bg-slate-100 text-slate-600',
  good: 'bg-green-50 text-green-800',
  warn: 'bg-amber-50 text-amber-800',
  bad: 'bg-red-50 text-red-700',
}

export function Badge({ children, tone = 'gray', className }: { children: ReactNode; tone?: keyof typeof BADGE; className?: string }) {
  return <span className={clsx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold', BADGE[tone], className)}>{children}</span>
}

/** Status pill: icon + label + color (never color alone). */
export function StatusPill({ status }: { status: 'good' | 'warning' | 'critical'; children?: ReactNode }) {
  const map = {
    good: { Icon: CheckCircle2, cls: 'text-green-800 bg-green-50', label: 'Pass' },
    warning: { Icon: AlertTriangle, cls: 'text-amber-800 bg-amber-50', label: 'Review' },
    critical: { Icon: OctagonAlert, cls: 'text-red-700 bg-red-50', label: 'Blocked' },
  }[status]
  return (
    <span className={clsx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold', map.cls)}>
      <map.Icon size={12} /> {map.label}
    </span>
  )
}

const JOB_STATUS_TONE: Record<string, keyof typeof BADGE> = { Open: 'good', 'In Review': 'gold', Filled: 'steel', Closed: 'gray' }
export const JobStatus = ({ s }: { s: string }) => <Badge tone={JOB_STATUS_TONE[s] ?? 'gray'}>{s}</Badge>

export function ScoreRing({ score, size = 56 }: { score: number; size?: number }) {
  const r = (size - 8) / 2
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, score)) / 100
  return (
    <svg width={size} height={size} className="shrink-0" role="img" aria-label={`Match score ${score.toFixed(0)} of 100`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#e8eef5" strokeWidth={6} fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#c9a227" strokeWidth={6} fill="none" strokeLinecap="round"
        strokeDasharray={`${c * pct} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="52%" dominantBaseline="middle" textAnchor="middle" className="fill-navy-900 text-[15px] font-bold">{score.toFixed(0)}</text>
    </svg>
  )
}

export function MiniBar({ value, label, weight }: { value: number; label: string; weight?: number }) {
  return (
    <div className="group" title={`${label}: ${(value * 100).toFixed(0)}%${weight ? ` · weight ${(weight * 100).toFixed(0)}%` : ''}`}>
      <div className="flex justify-between text-[11px] text-ink-3">
        <span>{label}</span>
        <span className="tabular-nums text-ink-2">{(value * 100).toFixed(0)}</span>
      </div>
      <div className="mt-0.5 h-1.5 rounded-full bg-slate-100">
        <div className="h-1.5 rounded-full bg-steel-600 transition-all" style={{ width: `${Math.max(2, value * 100)}%` }} />
      </div>
    </div>
  )
}

export const Spinner = ({ label }: { label?: string }) => (
  <div className="flex items-center gap-2 text-sm text-ink-3"><Loader2 size={16} className="animate-spin" /> {label ?? 'Loading…'}</div>
)

export const Empty = ({ children }: { children: ReactNode }) => (
  <div className="rounded-xl border border-dashed border-line px-4 py-10 text-center text-sm text-ink-3">{children}</div>
)

export const ErrorNote = ({ error }: { error: unknown }) => (
  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error instanceof Error ? error.message : String(error)}</div>
)

/** Shared chart tooltip: text wears ink tokens; a swatch carries identity. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function ChartTip({ active, payload, label, unit = '', labelFmt }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-semibold text-ink">{labelFmt ? labelFmt(label) : label}</div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-ink-2">
          <span className="inline-block h-2 w-2 rounded-sm" style={{ background: p.color ?? p.fill }} />
          <span>{p.name}</span>
          <span className="ml-auto pl-3 font-semibold tabular-nums text-ink">{typeof p.value === 'number' ? p.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : p.value}{unit}</span>
        </div>
      ))}
    </div>
  )
}

export const axisProps = { stroke: '#94a3b8', fontSize: 11, tickLine: false, axisLine: false } as const
