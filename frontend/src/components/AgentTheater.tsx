import clsx from 'clsx'
import {
  AlertTriangle, ArrowRightLeft, Brain, CheckCircle2, CircleDot, Cpu, FileText, Flag, Gauge, Hand, Wrench, Zap,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { FRAMEWORK_COLOR, SEQ } from '../lib/format'
import type { AgentEvent } from '../lib/types'
import { axisProps, ChartTip } from './ui'

const STAGES = [
  { id: 'guardrail', label: 'Guardrail', fw: 'LangGraph', agents: ['guardrail'] },
  { id: 'intent', label: 'Intent', fw: 'LangGraph', agents: ['intent'] },
  { id: 'jd', label: 'JD Parser', fw: 'LangGraph', agents: ['jd_parser'] },
  { id: 'crew', label: 'Sourcing Crew', fw: 'CrewAI', agents: ['crew_manager', 'skills_analyst', 'availability_analyst', 'applications_screener', 'market_intel'] },
  { id: 'swarm', label: 'Matching Swarm', fw: 'Swarm', agents: ['skill_matcher', 'hidden_fit_finder', 'mobility_matcher'] },
  { id: 'rank', label: 'Ranker', fw: 'LangGraph', agents: ['ranker'] },
  { id: 'fair', label: 'Fairness', fw: 'Responsible AI', agents: ['fairness_auditor'] },
  { id: 'explain', label: 'Explainer', fw: 'LangGraph', agents: ['explainer'] },
  { id: 'hitl', label: 'Human Review', fw: 'LangGraph', agents: ['hitl'] },
  { id: 'learn', label: 'Feedback ML', fw: 'ML', agents: ['feedback_learner'] },
  { id: 'report', label: 'Report', fw: 'LangGraph', agents: ['report'] },
]
const STAGE_OF = Object.fromEntries(STAGES.flatMap((s, i) => s.agents.map((a) => [a, i])))

const TYPE_ICON: Record<string, typeof Brain> = {
  status: CircleDot, thought: Brain, tool_call: Wrench, handoff: ArrowRightLeft, metric: Gauge, result: CheckCircle2,
  warning: AlertTriangle, error: AlertTriangle, interrupt: Hand, done: Flag, fallback: Zap,
}

export default function AgentTheater({ events, connected }: { events: AgentEvent[]; connected: boolean }) {
  const feedRef = useRef<HTMLDivElement>(null)
  const [follow, setFollow] = useState(true)
  useEffect(() => { if (follow) feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' }) }, [events.length, follow])

  const derived = useMemo(() => {
    let current = -1
    const fallbackStages = new Set<number>()
    let done = false, awaiting = false, failed = false
    for (const e of events) {
      const st = STAGE_OF[e.agent]
      if (st !== undefined && st > current) current = st
      if (e.type === 'fallback' && st !== undefined) fallbackStages.add(st)
      if (e.type === 'done') done = true
      if (e.type === 'error') failed = true
      if (e.type === 'interrupt') awaiting = true
      if (st !== undefined && st > 8) awaiting = false
    }
    const tools = events.filter((e) => e.type === 'tool_call')
    const latency = tools.map((e, i) => ({ i: i + 1, ms: e.data?.ms ?? 0, tool: e.data?.tool }))
    const metric = [...events].reverse().find((e) => e.type === 'metric' && e.agent === 'ranker')?.data
    const byAgent = new Map<string, { agent: string; framework: string; events: number }>()
    for (const e of events) {
      if (!e.framework) continue
      const k = e.agent_name
      byAgent.set(k, { agent: k, framework: e.framework, events: (byAgent.get(k)?.events ?? 0) + 1 })
    }
    const t0 = events[0]?.ts
    const tN = events[events.length - 1]?.ts
    return {
      current, fallbackStages, done, awaiting, failed, latency, metric,
      byAgent: [...byAgent.values()],
      counters: {
        tools: tools.length, handoffs: events.filter((e) => e.type === 'handoff').length,
        fallbacks: events.filter((e) => e.type === 'fallback').length, elapsed: t0 && tN ? Math.round(tN - t0) : 0,
      },
    }
  }, [events])

  const funnel = derived.metric?.funnel ? Object.entries(derived.metric.funnel as Record<string, number>).map(([k, v]) => ({ stage: k, count: v })) : []
  const hist = derived.metric?.histogram ?? []

  return (
    <div className="space-y-4">
      {/* pipeline stepper */}
      <div className="card overflow-x-auto px-5 py-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold text-navy-900"><Cpu size={16} className="text-steel-600" /> Live Agent Theater</div>
          <div className="flex items-center gap-4 text-xs text-ink-3">
            <span className="tabular-nums">{derived.counters.elapsed}s</span>
            <span className="tabular-nums">{derived.counters.tools} MCP calls</span>
            <span className="tabular-nums">{derived.counters.handoffs} handoffs</span>
            {derived.counters.fallbacks > 0 && <span className="tabular-nums text-amber-700">{derived.counters.fallbacks} fallbacks</span>}
            <span className={clsx('inline-flex items-center gap-1', connected ? 'text-green-700' : 'text-ink-3')}>
              <span className={clsx('h-2 w-2 rounded-full', connected ? 'bg-green-600' : 'bg-slate-300')} />{connected ? 'streaming' : 'offline'}
            </span>
          </div>
        </div>
        <ol className="flex min-w-[980px] items-center">
          {STAGES.map((s, i) => {
            const state = derived.failed && i === derived.current ? 'failed'
              : derived.done || i < derived.current ? 'done'
              : i === derived.current ? (s.id === 'hitl' && derived.awaiting ? 'awaiting' : 'active') : 'pending'
            return (
              <li key={s.id} className="flex flex-1 items-center">
                <div className="flex flex-col items-center gap-1.5">
                  <div className={clsx('grid h-9 w-9 place-items-center rounded-full border-2 text-xs font-bold transition-all',
                    state === 'done' && 'border-navy-900 bg-navy-900 text-white',
                    state === 'active' && 'pulse border-gold-500 bg-gold-100 text-navy-900',
                    state === 'awaiting' && 'pulse border-gold-500 bg-gold-500 text-navy-950',
                    state === 'failed' && 'border-red-600 bg-red-50 text-red-700',
                    state === 'pending' && 'border-line bg-white text-ink-3')}>
                    {state === 'done' ? <CheckCircle2 size={16} /> : state === 'awaiting' ? <Hand size={15} /> : i + 1}
                  </div>
                  <div className="text-center leading-tight">
                    <div className={clsx('text-[11px] font-semibold', state === 'pending' ? 'text-ink-3' : 'text-navy-900')}>{s.label}</div>
                    <div className="text-[10px] text-ink-3">{s.fw}{derived.fallbackStages.has(i) ? ' · fallback' : ''}</div>
                  </div>
                </div>
                {i < STAGES.length - 1 && <div className={clsx('mx-1 mb-7 h-0.5 flex-1 rounded', i < derived.current || derived.done ? 'bg-navy-900' : 'bg-line')} />}
              </li>
            )
          })}
        </ol>
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        {/* event feed */}
        <div className="card xl:col-span-3">
          <div className="flex items-center justify-between px-5 pt-4">
            <h3 className="text-[15px] font-semibold text-navy-900">Agent activity stream</h3>
            <label className="flex items-center gap-1.5 text-xs text-ink-3"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> auto-scroll</label>
          </div>
          <div ref={feedRef} className="mt-3 h-[420px] space-y-1.5 overflow-y-auto px-5 pb-5">
            {events.length === 0 && <div className="py-16 text-center text-sm text-ink-3">Waiting for agents…</div>}
            {events.map((e) => {
              const Icon = TYPE_ICON[e.type] ?? CircleDot
              const color = FRAMEWORK_COLOR[e.framework] ?? '#64748b'
              return (
                <div key={e.seq} className={clsx('slide-in flex gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px]',
                  e.type === 'warning' || e.type === 'fallback' ? 'bg-amber-50' : e.type === 'error' ? 'bg-red-50' : e.type === 'handoff' ? 'bg-steel-100' : e.type === 'interrupt' ? 'bg-gold-100' : 'hover:bg-slate-50')}>
                  <Icon size={14} className="mt-0.5 shrink-0 text-ink-3" />
                  <span className="mt-[3px] h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: color }} title={e.framework} />
                  <div className="min-w-0 flex-1">
                    <span className="font-semibold text-navy-900">{e.agent_name}</span>
                    <span className="ml-1.5 text-[11px] uppercase tracking-wide text-ink-3">{e.type.replace('_', ' ')}</span>
                    <div className={clsx('break-words text-ink-2', e.type === 'thought' && 'italic')}>{e.message}</div>
                  </div>
                  <span className="shrink-0 text-[10px] tabular-nums text-ink-3">{new Date(e.ts * 1000).toLocaleTimeString()}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* live charts */}
        <div className="viz-root space-y-4 xl:col-span-2">
          <div className="card px-5 py-4">
            <h3 className="text-[13px] font-semibold text-navy-900">Candidate funnel</h3>
            <div className="h-[150px]">
              {funnel.length ? (
                <ResponsiveContainer>
                  <BarChart data={funnel} layout="vertical" margin={{ left: 8, right: 36, top: 4, bottom: 0 }} barCategoryGap={4}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="stage" width={104} {...axisProps} />
                    <Tooltip content={<ChartTip />} cursor={{ fill: '#f1f5f9' }} />
                    <Bar dataKey="count" name="Candidates" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, fill: '#475569' }}>
                      {funnel.map((_, i) => <Cell key={i} fill={SEQ[Math.min(SEQ.length - 1, 2 + i * 2)]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : <Placeholder text="Appears when the Ranker finishes" />}
            </div>
          </div>
          <div className="card px-5 py-4">
            <h3 className="text-[13px] font-semibold text-navy-900">Match-score distribution</h3>
            <div className="h-[130px]">
              {hist.length ? (
                <ResponsiveContainer>
                  <BarChart data={hist} margin={{ left: -18, right: 4, top: 6, bottom: 0 }} barCategoryGap={2}>
                    <CartesianGrid vertical={false} stroke="#eef1f5" />
                    <XAxis dataKey="bucket" {...axisProps} interval={1} />
                    <YAxis {...axisProps} allowDecimals={false} />
                    <Tooltip content={<ChartTip />} cursor={{ fill: '#f1f5f9' }} />
                    <Bar dataKey="count" name="Candidates" fill="#2a78d6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <Placeholder text="Appears when scoring completes" />}
            </div>
          </div>
          <div className="card px-5 py-4">
            <h3 className="text-[13px] font-semibold text-navy-900">MCP tool-call latency (ms)</h3>
            <div className="h-[110px]">
              {derived.latency.length ? (
                <ResponsiveContainer>
                  <LineChart data={derived.latency} margin={{ left: -18, right: 6, top: 6, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#eef1f5" />
                    <XAxis dataKey="i" {...axisProps} />
                    <YAxis {...axisProps} />
                    <Tooltip content={<ChartTip unit=" ms" labelFmt={(l: number) => `Call #${l} · ${derived.latency[l - 1]?.tool ?? ''}`} />} />
                    <Line dataKey="ms" name="Latency" stroke="#c98500" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : <Placeholder text="Streams as agents call MCP tools" />}
            </div>
          </div>
          <div className="card px-5 py-4">
            <h3 className="text-[13px] font-semibold text-navy-900">Events by agent</h3>
            <div className="mb-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-2">
              {Object.entries(FRAMEWORK_COLOR).map(([k, c]) => <span key={k} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: c }} />{k}</span>)}
            </div>
            <div className="h-[170px]">
              {derived.byAgent.length ? (
                <ResponsiveContainer>
                  <BarChart data={derived.byAgent} layout="vertical" margin={{ left: 8, right: 24, top: 2, bottom: 0 }} barCategoryGap={2}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="agent" width={150} {...axisProps} fontSize={10} />
                    <Tooltip content={<ChartTip />} cursor={{ fill: '#f1f5f9' }} />
                    <Bar dataKey="events" name="Events" radius={[0, 4, 4, 0]}>
                      {derived.byAgent.map((d) => <Cell key={d.agent} fill={FRAMEWORK_COLOR[d.framework] ?? '#94a3b8'} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : <Placeholder text="—" />}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const Placeholder = ({ text }: { text: string }) => (
  <div className="grid h-full place-items-center rounded-lg bg-slate-50 text-xs text-ink-3"><span className="flex items-center gap-1.5"><FileText size={13} />{text}</span></div>
)
