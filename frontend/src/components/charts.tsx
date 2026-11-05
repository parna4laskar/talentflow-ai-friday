import { Activity, Table2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useLiveTicks } from '../lib/hooks'
import { SERIES } from '../lib/format'
import { axisProps, Card, ChartTip } from './ui'

/** Card wrapper with a chart/table toggle (accessibility: every chart has a table view). */
export function ChartCard({ title, subtitle, rows, columns, children, height = 260, action }: {
  title: string; subtitle?: string; rows: Record<string, unknown>[]; columns: { key: string; label: string; fmt?: (v: unknown) => string }[]
  children: ReactNode; height?: number; action?: ReactNode
}) {
  const [table, setTable] = useState(false)
  return (
    <Card title={title} subtitle={subtitle} action={
      <div className="flex items-center gap-2">{action}
        <button onClick={() => setTable(!table)} className="rounded-md p-1.5 text-ink-3 hover:bg-slate-100" aria-label={table ? 'Show chart' : 'Show table'} title={table ? 'Show chart' : 'Show table'}>
          {table ? <Activity size={15} /> : <Table2 size={15} />}
        </button></div>}>
      <div className="viz-root" style={{ height }}>
        {table ? (
          <div className="h-full overflow-y-auto">
            <table className="w-full text-[13px]"><thead><tr className="border-b border-line text-left text-xs text-ink-3">{columns.map((c) => <th key={c.key} className="py-1.5 pr-2">{c.label}</th>)}</tr></thead>
              <tbody>{rows.map((r, i) => <tr key={i} className="border-b border-line/50">{columns.map((c) => <td key={c.key} className="py-1 pr-2 tabular-nums text-ink-2">{c.fmt ? c.fmt(r[c.key]) : String(r[c.key])}</td>)}</tr>)}</tbody></table>
          </div>
        ) : children}
      </div>
    </Card>
  )
}

export function TrendLine({ data, x, y, name, color = SERIES[0], unit = '', area = false, xFmt }: {
  data: Record<string, unknown>[]; x: string; y: string; name: string; color?: string; unit?: string; area?: boolean; xFmt?: (v: string) => string
}) {
  const common = { data, margin: { left: -8, right: 12, top: 8, bottom: 0 } }
  return (
    <ResponsiveContainer>
      {area ? (
        <AreaChart {...common}>
          <defs><linearGradient id={`g-${y}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.25} /><stop offset="100%" stopColor={color} stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid vertical={false} stroke="#eef1f5" />
          <XAxis dataKey={x} {...axisProps} tickFormatter={xFmt} minTickGap={24} />
          <YAxis {...axisProps} width={48} />
          <Tooltip content={<ChartTip unit={unit} labelFmt={xFmt} />} cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }} />
          <Area dataKey={y} name={name} stroke={color} strokeWidth={2} fill={`url(#g-${y})`} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }} isAnimationActive={false} />
        </AreaChart>
      ) : (
        <LineChart {...common}>
          <CartesianGrid vertical={false} stroke="#eef1f5" />
          <XAxis dataKey={x} {...axisProps} tickFormatter={xFmt} minTickGap={24} />
          <YAxis {...axisProps} width={48} />
          <Tooltip content={<ChartTip unit={unit} labelFmt={xFmt} />} cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }} />
          <Line dataKey={y} name={name} stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }} />
        </LineChart>
      )}
    </ResponsiveContainer>
  )
}

export function HBars({ data, cat, val, name, color = SERIES[0], colors, unit = '', width = 140, fmt }: {
  data: Record<string, unknown>[]; cat: string; val: string; name: string; color?: string; colors?: string[]; unit?: string; width?: number; fmt?: (v: number) => string
}) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} layout="vertical" margin={{ left: 4, right: 44, top: 0, bottom: 0 }} barCategoryGap={3}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey={cat} width={width} {...axisProps} interval={0} />
        <Tooltip content={<ChartTip unit={unit} />} cursor={{ fill: '#f1f5f9' }} />
        <Bar dataKey={val} name={name} radius={[0, 4, 4, 0]} fill={color}
          label={{ position: 'right', fontSize: 11, fill: '#475569', formatter: (v: unknown) => (fmt ? fmt(Number(v)) : String(v)) }}>
          {colors && data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function VBars({ data, cat, val, name, color = SERIES[0], unit = '' }: { data: Record<string, unknown>[]; cat: string; val: string; name: string; color?: string; unit?: string }) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} margin={{ left: -8, right: 8, top: 8, bottom: 0 }} barCategoryGap={6}>
        <CartesianGrid vertical={false} stroke="#eef1f5" />
        <XAxis dataKey={cat} {...axisProps} interval={0} fontSize={10} />
        <YAxis {...axisProps} width={44} />
        <Tooltip content={<ChartTip unit={unit} />} cursor={{ fill: '#f1f5f9' }} />
        <Bar dataKey={val} name={name} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Live marketplace pulse: real platform telemetry + simulated activity feed (clearly labelled). */
export function LivePulse() {
  const ticks = useLiveTicks(45)
  const last = ticks[ticks.length - 1]
  const data = ticks.map((t) => ({ t: new Date(t.ts * 1000).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' }), apps: t.activity.applications_per_min, updates: t.activity.profile_updates_per_min }))
  return (
    <Card title="Live marketplace pulse" subtitle="Streams every 2 s over SSE · activity feed is simulated for demo; telemetry counters are real"
      action={<span className="inline-flex items-center gap-1.5 text-xs font-semibold text-green-700"><span className="pulse h-2 w-2 rounded-full bg-green-600" />LIVE</span>}>
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <div className="viz-root">
          <div className="mb-1 flex gap-4 text-[11px] text-ink-2">
            <span className="inline-flex items-center gap-1"><span className="h-0.5 w-3 bg-[#2a78d6]" />Applications / min</span>
            <span className="inline-flex items-center gap-1"><span className="h-0.5 w-3 bg-[#c98500]" />Profile updates / min</span>
          </div>
          <div className="h-[170px]">
            <ResponsiveContainer>
              <LineChart data={data} margin={{ left: -18, right: 8, top: 4, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#eef1f5" />
                <XAxis dataKey="t" {...axisProps} minTickGap={40} />
                <YAxis {...axisProps} />
                <Tooltip content={<ChartTip />} />
                <Line dataKey="apps" name="Applications / min" stroke={SERIES[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="updates" name="Profile updates / min" stroke={SERIES[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {[['LLM calls', last?.telemetry.llm_calls], ['LLM cache hits', last?.telemetry.llm_cache_hits], ['MCP calls', last?.telemetry.mcp_calls],
              ['Avg MCP latency', last ? `${last.telemetry.avg_mcp_ms} ms` : '—']].map(([k, v]) => (
              <div key={k as string} className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-[11px] text-ink-3">{k}</div><div className="text-lg font-semibold tabular-nums text-navy-900">{v ?? '—'}</div></div>
            ))}
          </div>
          <div className="h-[72px] overflow-hidden rounded-lg border border-line px-3 py-2 text-[12px] text-ink-2">
            {ticks.slice(-3).reverse().map((t) => <div key={t.ts} className="slide-in truncate">• {t.activity.event}</div>)}
          </div>
        </div>
      </div>
    </Card>
  )
}
