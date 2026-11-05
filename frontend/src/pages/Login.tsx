import { ArrowRight, BarChart3, BriefcaseBusiness, Compass, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { HOME, useAuth } from '../lib/auth'

const PERSONAS = [
  { username: 'hiring.manager', label: 'Hiring Manager', desc: 'Post roles, watch agents match talent live, approve shortlists', icon: BriefcaseBusiness },
  { username: 'hr.admin', label: 'HR Admin', desc: 'Workforce command center, MCP employee CRUD, AI governance', icon: ShieldCheck },
  { username: 'employee', label: 'Employee', desc: 'Career Hub: matched roles, skill-gap plans, apply in one click', icon: Compass },
  { username: 'leader', label: 'Leadership', desc: 'Mobility trends, skills supply vs demand, business impact', icon: BarChart3 },
]

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [username, setUsername] = useState('hiring.manager')
  const [password, setPassword] = useState('Demo@123')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(u = username, p = password) {
    setBusy(true)
    setErr('')
    try {
      const user = await login(u, p)
      nav(HOME[user.role])
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden bg-navy-900 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-steel-600/30 blur-3xl" />
        <div className="absolute -bottom-40 -left-20 h-96 w-96 rounded-full bg-gold-500/20 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-gold-500 font-serif text-2xl font-bold text-navy-950">T</div>
          <div className="font-serif text-2xl">TalentFlow<span className="text-gold-400"> AI</span></div>
        </div>
        <div className="relative max-w-xl">
          <div className="eyebrow mb-3">Internal Talent Marketplace</div>
          <h1 className="font-serif text-5xl leading-[1.1]">Your next hire already works here.</h1>
          <p className="mt-5 text-lg text-slate-300">
            A team of AI agents — LangGraph, CrewAI and a matching Swarm — reads every role, searches employee data through MCP,
            and delivers a fair, explainable shortlist in minutes.
          </p>
          <div className="mt-10 grid grid-cols-3 gap-6 border-t border-white/10 pt-6">
            {[['3,000', 'employee profiles'], ['17', 'specialised agents'], ['5', 'storage engines']].map(([n, l]) => (
              <div key={l}><div className="font-serif text-3xl text-gold-400">{n}</div><div className="text-xs uppercase tracking-wider text-slate-400">{l}</div></div>
            ))}
          </div>
        </div>
        <div className="relative text-xs text-slate-500">AI Friday Hackathon · Responsible AI by design · Human-in-the-loop decisions</div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <h2 className="font-serif text-3xl text-navy-900">Sign in</h2>
          <p className="mt-1 text-sm text-ink-2">Choose a persona — each sees a different workspace. Demo password: <code className="rounded bg-slate-100 px-1">Demo@123</code></p>
          <div className="mt-6 grid gap-2">
            {PERSONAS.map((p) => (
              <button key={p.username} onClick={() => { setUsername(p.username); submit(p.username, 'Demo@123') }} disabled={busy}
                className="group flex items-center gap-3 rounded-xl border border-line bg-white px-4 py-3 text-left transition hover:border-gold-500 hover:shadow-md">
                <div className="grid h-10 w-10 place-items-center rounded-lg bg-steel-100 text-steel-600 group-hover:bg-navy-900 group-hover:text-gold-400"><p.icon size={19} /></div>
                <div className="flex-1"><div className="font-semibold text-navy-900">{p.label}</div><div className="text-xs text-ink-3">{p.desc}</div></div>
                <ArrowRight size={16} className="text-ink-3 group-hover:text-gold-500" />
              </button>
            ))}
          </div>
          <div className="my-6 flex items-center gap-3 text-xs text-ink-3"><div className="h-px flex-1 bg-line" />or sign in with credentials<div className="h-px flex-1 bg-line" /></div>
          <form onSubmit={(e) => { e.preventDefault(); submit() }} className="space-y-3">
            <div><label className="label" htmlFor="u">Username</label><input id="u" className="input mt-1" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" /></div>
            <div><label className="label" htmlFor="p">Password</label><input id="p" type="password" className="input mt-1" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></div>
            {err && <div className="text-sm text-red-700">{err}</div>}
            <button className="btn btn-primary w-full justify-center py-2.5" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
        </div>
      </div>
    </div>
  )
}
