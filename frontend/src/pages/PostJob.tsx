import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Rocket, ShieldCheck, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, ErrorNote, PageHeader } from '../components/ui'
import { api } from '../lib/api'

const SITES: [string, string, string][] = [['Pune', 'India', 'APAC'], ['Bengaluru', 'India', 'APAC'], ['Hyderabad', 'India', 'APAC'], ['Chennai', 'India', 'APAC'],
  ['Gurugram', 'India', 'APAC'], ['London', 'United Kingdom', 'EMEA'], ['Kraków', 'Poland', 'EMEA'], ['Dublin', 'Ireland', 'EMEA'],
  ['New York', 'United States', 'AMER'], ['Austin', 'United States', 'AMER'], ['Toronto', 'Canada', 'AMER'], ['Singapore', 'Singapore', 'APAC']]
const DEPTS = ['Engineering', 'Cloud & Infrastructure', 'Data & Analytics', 'AI Center of Excellence', 'Cyber Security', 'Quality Engineering', 'Product',
  'Design', 'Business Consulting', 'Delivery Excellence', 'Finance', 'Enterprise Applications', 'Human Resources', 'Marketing', 'Sales', 'Risk & Compliance']

const SAMPLE = `We are launching an internal GenAI platform squad and need an AI Engineer to build agentic assistants for our claims operations.

What you will do:
- Design and ship retrieval-augmented generation (RAG) and multi-agent workflows with LangGraph.
- Integrate enterprise data through MCP servers and secure APIs.
- Evaluate LLM quality, latency and cost; harden guardrails for production.
- Partner with product and operations stakeholders to measure business impact.

Must have: Python, LLM Engineering, Generative AI, REST API design. Experience with vector databases is a strong plus.
Location: Pune (Hybrid). Start in January; 12-month assignment with extension.`

interface Precheck { decision: string; inclusive_language: { inclusivity_score: number; findings: { phrase: string; category: string; suggestion: string }[] }; injection: { score: number; blocked: boolean } }

export default function PostJob() {
  const nav = useNavigate()
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: () => api<{ name: string; category: string; trend: string }[]>('/catalog/skills') })
  const [f, setF] = useState(() => ({
    title: 'AI Engineer – Agentic Claims Assistant', role_family: 'AI Engineer', level: 'L3', department: 'AI Center of Excellence',
    site: 'Pune', work_mode: 'Hybrid', start_date: new Date(Date.now() + 45 * 864e5).toISOString().slice(0, 10), min_years_experience: 4,
    priority: 'High', relocation_supported: true, description: SAMPLE,
  }))
  const [skills, setSkills] = useState([{ name: 'Python', min_proficiency: 4 }, { name: 'LLM Engineering', min_proficiency: 3 },
    { name: 'Generative AI', min_proficiency: 3 }, { name: 'REST API Design', min_proficiency: 3 }])
  const [nice, setNice] = useState<string[]>(['Vector Databases', 'Agentic AI'])
  const [pre, setPre] = useState<Precheck | null>(null)

  // live inclusive-language + injection lint (debounced)
  useEffect(() => {
    const t = setTimeout(() => {
      api<Precheck>('/jobs/precheck', { method: 'POST', json: { title: f.title, description: f.description } }).then(setPre).catch(() => setPre(null))
    }, 500)
    return () => clearTimeout(t)
  }, [f.title, f.description])

  const create = useMutation({
    mutationFn: () => {
      const [city, country, region] = SITES.find((s) => s[0] === f.site)!
      return api<{ job_id: string; run_id: string }>('/jobs', {
        method: 'POST', json: {
          title: f.title, description: f.description, role_family: f.role_family, level: f.level, department: f.department, city, country, region,
          work_mode: f.work_mode, start_date: f.start_date, min_years_experience: Number(f.min_years_experience), priority: f.priority,
          relocation_supported: f.relocation_supported, required_skills: skills.map((s) => ({ ...s, weight: 1 })), nice_to_have_skills: nice, auto_match: true,
        },
      })
    },
    onSuccess: (r) => nav(`/jobs/${r.job_id}?run=${r.run_id}`),
  })

  const names = useMemo(() => (catalog.data ?? []).map((c) => c.name).sort(), [catalog.data])
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })

  return (
    <>
      <PageHeader eyebrow="Hiring Manager" title="Post an internal role" subtitle="Publishing starts the agent team immediately: guardrails → intent → JD parsing → CrewAI sourcing → Swarm matching → fair, explainable shortlist." />
      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card title="Role details">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Title" full><input className="input" value={f.title} onChange={set('title')} /></Field>
            <Field label="Role family"><input className="input" value={f.role_family} onChange={set('role_family')} /></Field>
            <Field label="Level"><select className="input" value={f.level} onChange={set('level')}>{['L1', 'L2', 'L3', 'L4', 'L5'].map((l) => <option key={l}>{l}</option>)}</select></Field>
            <Field label="Department"><select className="input" value={f.department} onChange={set('department')}>{DEPTS.map((d) => <option key={d}>{d}</option>)}</select></Field>
            <Field label="Location"><select className="input" value={f.site} onChange={set('site')}>{SITES.map((s) => <option key={s[0]}>{s[0]}</option>)}</select></Field>
            <Field label="Work mode"><select className="input" value={f.work_mode} onChange={set('work_mode')}>{['Onsite', 'Hybrid', 'Remote'].map((m) => <option key={m}>{m}</option>)}</select></Field>
            <Field label="Start date"><input type="date" className="input" value={f.start_date} onChange={set('start_date')} /></Field>
            <Field label="Min. years experience"><input type="number" min={0} className="input" value={f.min_years_experience} onChange={set('min_years_experience')} /></Field>
            <Field label="Priority"><select className="input" value={f.priority} onChange={set('priority')}>{['Critical', 'High', 'Medium', 'Low'].map((m) => <option key={m}>{m}</option>)}</select></Field>
            <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink-2"><input type="checkbox" checked={f.relocation_supported} onChange={(e) => setF({ ...f, relocation_supported: e.target.checked })} /> Relocation supported</label>
            <Field label="Job description (unstructured — parsed by the JD agent)" full>
              <textarea className="input min-h-[220px] font-mono text-[13px] leading-relaxed" value={f.description} onChange={set('description')} />
            </Field>
          </div>
        </Card>
        <div className="space-y-6">
          <Card title="Required skills" subtitle="Minimum proficiency 1 (beginner) – 5 (expert)">
            <div className="space-y-2">
              {skills.map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <select className="input py-1.5" value={s.name} onChange={(e) => setSkills(skills.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}>{names.map((n) => <option key={n}>{n}</option>)}</select>
                  <select className="input w-20 py-1.5" aria-label="Minimum proficiency" value={s.min_proficiency} onChange={(e) => setSkills(skills.map((x, j) => j === i ? { ...x, min_proficiency: Number(e.target.value) } : x))}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select>
                  <button aria-label="Remove skill" className="rounded p-1.5 text-ink-3 hover:bg-red-50 hover:text-red-700" onClick={() => setSkills(skills.filter((_, j) => j !== i))}><Trash2 size={15} /></button>
                </div>
              ))}
              <button className="btn btn-ghost w-full justify-center py-1.5" onClick={() => setSkills([...skills, { name: names[0] ?? 'Python', min_proficiency: 3 }])}>+ Add skill</button>
            </div>
            <div className="label mt-4">Nice to have</div>
            <select multiple className="input mt-1 h-28 py-1 text-[13px]" value={nice} onChange={(e) => setNice([...e.target.selectedOptions].map((o) => o.value))}>{names.map((n) => <option key={n}>{n}</option>)}</select>
          </Card>
          <Card title={<span className="flex items-center gap-2"><ShieldCheck size={16} className="text-steel-600" />Responsible-AI pre-check</span>} subtitle="Live inclusive-language & prompt-injection screening">
            {!pre ? <div className="text-sm text-ink-3">Checking…</div> : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-ink-2">Inclusivity score</span>
                  <span className="text-2xl font-semibold tabular-nums text-navy-900">{pre.inclusive_language.inclusivity_score}<span className="text-sm text-ink-3">/100</span></span>
                </div>
                {pre.injection.blocked && <div className="flex gap-2 rounded-lg bg-red-50 p-2 text-sm text-red-700"><AlertTriangle size={16} />Instruction-override / discriminatory filter detected — posting will be blocked.</div>}
                {pre.inclusive_language.findings.length === 0 && !pre.injection.blocked && <div className="flex items-center gap-2 text-sm text-green-800"><CheckCircle2 size={16} />No exclusionary language found.</div>}
                {pre.inclusive_language.findings.map((x, i) => (
                  <div key={i} className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-[13px]">
                    <div className="flex items-center gap-1.5 font-semibold text-amber-900"><AlertTriangle size={13} />“{x.phrase}” · {x.category}</div>
                    <div className="text-amber-900/80">{x.suggestion}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
          {create.error && <ErrorNote error={create.error} />}
          <button className="btn btn-gold w-full justify-center py-3 text-base" disabled={create.isPending || skills.length === 0 || pre?.injection.blocked}
            onClick={() => create.mutate()}><Rocket size={18} />{create.isPending ? 'Publishing…' : 'Publish & launch agents'}</button>
        </div>
      </div>
    </>
  )
}

const Field = ({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) => (
  <div className={full ? 'md:col-span-2' : ''}><div className="label mb-1">{label}</div>{children}</div>
)
