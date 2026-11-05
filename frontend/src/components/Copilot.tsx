import clsx from 'clsx'
import { Bot, Send, ShieldAlert, Sparkles, X, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

interface Reply {
  intent: string
  answer: string
  citations: { n: number; document: string; section: string }[]
  model?: string
  intent_detail?: { confidence: number; source: string }
  _cache?: { semantic_similarity: number; matched_query: string }
  data?: { matches?: { job_id: string; title: string; score: number }[]; people?: { employee_id: string; name: string; title: string }[] }
}
interface Msg { role: 'user' | 'bot'; text: string; reply?: Reply }

const SUGGESTIONS: Record<string, string[]> = {
  employee: ['Which open roles suit me best?', 'How long must I stay in my role before applying?', 'What relocation support do I get for an international move?', 'Will my manager know I applied?'],
  hiring_manager: ['Who knows Kafka and Spring Boot in Pune?', 'Is the AI making the final hiring decision?', 'What are the most in-demand skills right now?'],
  hr_admin: ['Find senior data engineers who are rolling off soon', 'How is fairness checked on shortlists?', 'How many employees are eligible to move?'],
  leadership: ['Which skills have the biggest supply gap?', 'How many employees are eligible to move?', 'How is fairness checked on shortlists?'],
}

const INTENT_LABEL: Record<string, string> = {
  policy_question: 'Policy (RAG)', job_search: 'Job search', career_guidance: 'Career guidance', search_talent: 'Talent search',
  insight_query: 'Insights', blocked: 'Blocked by guardrail', other: 'General',
}

export default function Copilot({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user } = useAuth()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  // Block body on purpose: newer browsers return a Promise from scrollIntoView, and an effect
  // must return nothing or a cleanup function (returning the Promise crashes on unmount).
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, busy])

  async function send(q: string) {
    if (!q.trim() || busy) return
    setMsgs((m) => [...m, { role: 'user', text: q }])
    setText('')
    setBusy(true)
    try {
      const r = await api<Reply>('/assistant/chat', { method: 'POST', json: { message: q } })
      setMsgs((m) => [...m, { role: 'bot', text: r.answer, reply: r }])
    } catch (e) {
      setMsgs((m) => [...m, { role: 'bot', text: `Sorry — ${(e as Error).message}` }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={clsx('fixed inset-0 z-50 transition', open ? 'pointer-events-auto' : 'pointer-events-none')} aria-hidden={!open}>
      <div className={clsx('absolute inset-0 bg-navy-950/30 transition-opacity', open ? 'opacity-100' : 'opacity-0')} onClick={onClose} />
      <aside className={clsx('absolute right-0 top-0 flex h-full w-[440px] max-w-full flex-col bg-white shadow-2xl transition-transform', open ? 'translate-x-0' : 'translate-x-full')}>
        <header className="flex items-center justify-between bg-navy-900 px-5 py-4 text-white">
          <div className="flex items-center gap-2"><Sparkles size={18} className="text-gold-400" /><div>
            <div className="font-semibold">TalentFlow Copilot</div>
            <div className="text-[11px] text-slate-300">Intent-routed · RAG · semantic cache · guardrails</div></div></div>
          <button onClick={onClose} aria-label="Close copilot" className="rounded p-1 hover:bg-white/10"><X size={18} /></button>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto bg-ivory px-4 py-4">
          {msgs.length === 0 && (
            <div className="space-y-2">
              <p className="text-sm text-ink-2">Ask about roles, skills, policies or talent. Try:</p>
              {(SUGGESTIONS[user?.role ?? 'employee'] ?? []).map((s) => (
                <button key={s} onClick={() => send(s)} className="block w-full rounded-lg border border-line bg-white px-3 py-2 text-left text-sm text-navy-900 hover:border-steel-500">{s}</button>
              ))}
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={clsx('slide-in flex gap-2', m.role === 'user' && 'justify-end')}>
              {m.role === 'bot' && <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-navy-900 text-gold-400"><Bot size={15} /></div>}
              <div className={clsx('max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm', m.role === 'user' ? 'bg-steel-600 text-white' : 'border border-line bg-white text-ink')}>
                {m.reply && (
                  <div className="mb-1.5 flex flex-wrap gap-1">
                    <span className={clsx('inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold', m.reply.intent === 'blocked' ? 'bg-red-50 text-red-700' : 'bg-steel-100 text-steel-600')}>
                      {m.reply.intent === 'blocked' && <ShieldAlert size={11} />}{INTENT_LABEL[m.reply.intent] ?? m.reply.intent}
                      {m.reply.intent_detail && ` · ${(m.reply.intent_detail.confidence * 100).toFixed(0)}%`}
                    </span>
                    {m.reply._cache && <span className="inline-flex items-center gap-1 rounded bg-gold-100 px-1.5 py-0.5 text-[10px] font-semibold text-[#8a6a00]"><Zap size={10} />semantic cache {m.reply._cache.semantic_similarity}</span>}
                  </div>
                )}
                <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
                {m.reply?.data?.matches && (
                  <ul className="mt-2 space-y-1">{m.reply.data.matches.map((j) => <li key={j.job_id} className="flex justify-between rounded bg-ivory px-2 py-1 text-xs"><span>{j.title} · {j.job_id}</span><b>{j.score.toFixed(0)}</b></li>)}</ul>
                )}
                {m.reply?.data?.people && (
                  <ul className="mt-2 space-y-1">{m.reply.data.people.map((p) => <li key={p.employee_id} className="rounded bg-ivory px-2 py-1 text-xs">{p.name} · {p.title}</li>)}</ul>
                )}
                {!!m.reply?.citations?.length && (
                  <div className="mt-2 border-t border-line pt-1.5 text-[11px] text-ink-3">
                    {m.reply.citations.map((c) => <div key={c.n}>[{c.n}] {c.document} — {c.section}</div>)}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && <div className="flex items-center gap-2 text-xs text-ink-3"><span className="h-2 w-2 animate-bounce rounded-full bg-gold-500" />Agents are thinking…</div>}
          <div ref={end} />
        </div>
        <form onSubmit={(e) => { e.preventDefault(); send(text) }} className="flex gap-2 border-t border-line p-3">
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask TalentFlow…" aria-label="Message" />
          <button className="btn btn-primary" disabled={busy || !text.trim()} aria-label="Send"><Send size={16} /></button>
        </form>
      </aside>
    </div>
  )
}
