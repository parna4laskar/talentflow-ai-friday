import clsx from 'clsx'
import { Check, ChevronDown, Gem, MapPin, Send, X } from 'lucide-react'
import { useState } from 'react'
import { COMPONENT_LABEL, COMPONENT_WEIGHT } from '../lib/format'
import type { MatchCardData } from '../lib/types'
import { Badge, MiniBar, ScoreRing } from './ui'

export type Draft = { decision: 'approved' | 'rejected' | null; reason: string }

export default function MatchCard({ c, reviewable, draft, onDraft }: {
  c: MatchCardData; reviewable: boolean; draft?: Draft; onDraft?: (d: Draft) => void
}) {
  const [open, setOpen] = useState(c.rank <= 2)
  const decided = c.decision !== 'pending' ? c.decision : draft?.decision
  return (
    <article className={clsx('card slide-in overflow-hidden transition-shadow',
      decided === 'approved' && 'ring-2 ring-green-600/40', decided === 'rejected' && 'opacity-75')}>
      <div className="flex items-start gap-4 p-4">
        <div className="flex flex-col items-center gap-1">
          <ScoreRing score={c.score} />
          <span className="text-[10px] font-semibold text-ink-3">#{c.rank}</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-[15px] font-semibold text-navy-900">{c.name}</h4>
            <span className="text-xs text-ink-3">{c.employee_id}</span>
            {c.hidden_fit && <Badge tone="gold"><Gem size={11} />Hidden fit</Badge>}
            {c.applied && <Badge tone="steel"><Send size={10} />Applied</Badge>}
            {c.decision !== 'pending' && <Badge tone={c.decision === 'approved' ? 'good' : 'bad'}>{c.decision}</Badge>}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-ink-2">
            <span>{c.title} · {c.department}</span>
            <span className="inline-flex items-center gap-1"><MapPin size={11} />{c.city}</span>
          </div>
          <p className="mt-2 text-sm font-medium text-navy-900">{c.headline}</p>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{c.explanation}</p>
        </div>
        <button onClick={() => setOpen(!open)} aria-label="Toggle details" className="rounded p-1 text-ink-3 hover:bg-slate-100">
          <ChevronDown size={18} className={clsx('transition-transform', open && 'rotate-180')} />
        </button>
      </div>
      {open && (
        <div className="grid gap-5 border-t border-line bg-slate-50/60 px-4 py-4 md:grid-cols-[1fr_1.3fr]">
          <div className="space-y-2">
            <div className="label">Score breakdown</div>
            {Object.entries(c.components).map(([k, v]) => <MiniBar key={k} label={`${COMPONENT_LABEL[k]} (${COMPONENT_WEIGHT[k] * 100}%)`} value={v} weight={COMPONENT_WEIGHT[k]} />)}
          </div>
          <div className="grid gap-3 text-[13px] sm:grid-cols-2">
            <Reason title="Strengths" items={c.reasons.strengths} tone="text-green-800" />
            <Reason title="Gaps" items={c.reasons.gaps} tone="text-red-700" empty="No critical gaps" />
            <Reason title="Skill bridges (graph)" items={c.reasons.bridges} tone="text-[#8a6a00]" empty="—" />
            <div>
              <div className="label mb-1">Mobility</div>
              <div className="text-ink-2">{c.reasons.availability}</div>
              <div className="text-ink-2">{c.reasons.location}</div>
              <div className="text-ink-2">{c.reasons.interest}</div>
              <div className="text-ink-3">{c.reasons.experience}</div>
            </div>
          </div>
        </div>
      )}
      {reviewable && c.decision === 'pending' && onDraft && (
        <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
          <button onClick={() => onDraft({ decision: 'approved', reason: draft?.reason ?? '' })}
            className={clsx('btn py-1.5', draft?.decision === 'approved' ? 'bg-green-700 text-white' : 'btn-ghost')}><Check size={15} />Approve</button>
          <button onClick={() => onDraft({ decision: 'rejected', reason: draft?.reason ?? '' })}
            className={clsx('btn py-1.5', draft?.decision === 'rejected' ? 'bg-red-700 text-white' : 'btn-ghost')}><X size={15} />Reject</button>
          {draft?.decision && (
            <input className="input max-w-md flex-1 py-1.5" placeholder={draft.decision === 'rejected' ? 'Reason (required)' : 'Note (optional)'}
              value={draft.reason} onChange={(e) => onDraft({ ...draft, reason: e.target.value })} />
          )}
        </div>
      )}
    </article>
  )
}

function Reason({ title, items, tone, empty = '—' }: { title: string; items: string[]; tone: string; empty?: string }) {
  return (
    <div>
      <div className="label mb-1">{title}</div>
      {items.length ? <ul className="space-y-0.5">{items.map((s) => <li key={s} className={tone}>• {s}</li>)}</ul> : <div className="text-ink-3">{empty}</div>}
    </div>
  )
}
