import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BadgeCheck, ChevronLeft, ChevronRight, Database, MapPin, Search, UserX, X } from 'lucide-react'
import { useState } from 'react'
import { Badge, Card, ErrorNote, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Employee } from '../lib/types'

const AVAIL_TONE: Record<string, 'good' | 'gold' | 'steel' | 'gray'> = { Available: 'good', 'Rolling off': 'gold', 'Partially available': 'steel', Allocated: 'gray' }
const DEPTS = ['', 'Engineering', 'Cloud & Infrastructure', 'Data & Analytics', 'AI Center of Excellence', 'Cyber Security', 'Quality Engineering', 'Product', 'Design',
  'Business Consulting', 'Delivery Excellence', 'Finance', 'Enterprise Applications', 'Human Resources', 'Marketing', 'Sales', 'Risk & Compliance']

export default function Employees() {
  const [q, setQ] = useState('')
  const [term, setTerm] = useState('')
  const [dept, setDept] = useState('')
  const [avail, setAvail] = useState('')
  const [page, setPage] = useState(1)
  const [sel, setSel] = useState<string | null>(null)
  const list = useQuery({
    queryKey: ['employees', term, dept, avail, page], placeholderData: keepPreviousData,
    queryFn: () => api<{ total: number; employees: Employee[] }>(`/employees?q=${encodeURIComponent(term)}&page=${page}&page_size=20${dept ? `&department=${encodeURIComponent(dept)}` : ''}${avail ? `&availability=${encodeURIComponent(avail)}` : ''}`),
  })
  const pages = Math.max(1, Math.ceil((list.data?.total ?? 0) / 20))
  return (
    <>
      <PageHeader eyebrow="HR Admin" title="Employee Directory" subtitle={<span className="inline-flex items-center gap-1.5"><Database size={14} />Served by <b>employee-mcp</b> — every read and write is an MCP tool call, role-checked and audit-logged.</span>} />
      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card title={`${list.data?.total ?? '…'} employees`} action={
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setTerm(q); setPage(1) }}>
            <div className="relative"><Search size={14} className="absolute left-2.5 top-2.5 text-ink-3" /><input className="input w-56 py-1.5 pl-8" placeholder="Name, title, skill, ID…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <select className="input w-44 py-1.5" aria-label="Department" value={dept} onChange={(e) => { setDept(e.target.value); setPage(1) }}>{DEPTS.map((d) => <option key={d} value={d}>{d || 'All departments'}</option>)}</select>
            <select className="input w-40 py-1.5" aria-label="Availability" value={avail} onChange={(e) => { setAvail(e.target.value); setPage(1) }}>{['', 'Available', 'Rolling off', 'Partially available', 'Allocated'].map((d) => <option key={d} value={d}>{d || 'Any availability'}</option>)}</select>
          </form>}>
          {list.isLoading ? <Spinner /> : list.error ? <ErrorNote error={list.error} /> : (
            <>
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-3"><th className="py-2">Employee</th><th>Location</th><th>Top skills</th><th>Availability</th></tr></thead>
                <tbody>{list.data!.employees.map((e) => (
                  <tr key={e.employee_id} onClick={() => setSel(e.employee_id)} className={`cursor-pointer border-b border-line/60 hover:bg-slate-50 ${sel === e.employee_id ? 'bg-steel-100' : ''}`}>
                    <td className="py-2"><div className="font-semibold text-navy-900">{e.name}</div><div className="text-xs text-ink-3">{e.employee_id} · {e.title}</div></td>
                    <td className="text-ink-2">{e.city}<div className="text-xs text-ink-3">{e.region}</div></td>
                    <td><div className="flex max-w-xs flex-wrap gap-1">{[...e.skills].sort((a, b) => b.proficiency - a.proficiency).slice(0, 3).map((s) => <Badge key={s.name} tone="steel">{s.name} {s.proficiency}</Badge>)}</div></td>
                    <td><Badge tone={AVAIL_TONE[e.availability.status]}>{e.availability.status}</Badge><div className="text-[11px] text-ink-3">from {e.availability.available_from}</div></td>
                  </tr>))}</tbody>
              </table>
              <div className="mt-3 flex items-center justify-end gap-2 text-sm text-ink-2">
                <button className="btn btn-ghost py-1" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft size={15} /></button>
                Page {page} / {pages}
                <button className="btn btn-ghost py-1" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight size={15} /></button>
              </div>
            </>
          )}
        </Card>
        {sel ? <EmployeePanel id={sel} onClose={() => setSel(null)} /> : <Card><div className="py-16 text-center text-sm text-ink-3">Select an employee to view the full profile and manage skills / availability via MCP.</div></Card>}
      </div>
    </>
  )
}

function EmployeePanel({ id, onClose }: { id: string; onClose: () => void }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const isHR = user?.role === 'hr_admin'
  const emp = useQuery({ queryKey: ['employee', id], queryFn: () => api<Employee>(`/employees/${id}`) })
  const [skill, setSkill] = useState({ skill: '', proficiency: 3, verified: true })
  const [av, setAv] = useState(() => ({ status: 'Available', available_from: new Date().toISOString().slice(0, 10), allocation_pct: 0 }))
  const refresh = () => { qc.invalidateQueries({ queryKey: ['employee', id] }); qc.invalidateQueries({ queryKey: ['employees'] }) }
  const upSkill = useMutation({ mutationFn: () => api(`/employees/${id}/skills`, { method: 'PUT', json: skill }), onSuccess: refresh })
  const upAv = useMutation({ mutationFn: () => api(`/employees/${id}/availability`, { method: 'PUT', json: av }), onSuccess: refresh })
  const deact = useMutation({ mutationFn: () => api(`/employees/${id}`, { method: 'DELETE' }), onSuccess: () => { refresh(); onClose() } })
  if (emp.isLoading) return <Card><Spinner /></Card>
  if (emp.error) return <Card><ErrorNote error={emp.error} /></Card>
  const e = emp.data!
  return (
    <Card title={e.name} subtitle={`${e.employee_id} · ${e.title} · ${e.department}`} action={<button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-slate-100"><X size={16} /></button>}>
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap gap-2"><Badge tone="steel"><MapPin size={11} />{e.city}, {e.country}</Badge><Badge>{e.level} · {e.years_experience} yrs</Badge>
          <Badge tone={AVAIL_TONE[e.availability.status]}>{e.availability.status}</Badge>{e.open_to_move && <Badge tone="gold">Open to move</Badge>}{e.willing_to_relocate && <Badge>Relocation: {e.relocation_preferences.join(', ')}</Badge>}</div>
        <p className="text-[13px] leading-relaxed text-ink-2">{e.resume_summary}</p>
        <div><div className="label mb-1.5">Skills</div><div className="flex flex-wrap gap-1.5">{[...e.skills].sort((a, b) => b.proficiency - a.proficiency).map((s) => (
          <span key={s.name} className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-0.5 text-xs">{s.name}<b className="text-steel-600">{s.proficiency}</b>{s.verified && <BadgeCheck size={12} className="text-green-700" />}</span>))}</div></div>
        {e.projects && <div><div className="label mb-1.5">Recent projects</div>{e.projects.slice(0, 2).map((p) => <div key={p.name} className="mb-1.5 text-[13px]"><b className="text-navy-900">{p.name}</b><div className="text-ink-2">{p.description}</div></div>)}</div>}
        <div className="text-[13px] text-ink-2"><b>Target roles:</b> {e.target_roles.join(', ')} · <b>Aspiration:</b> {e.aspiration}</div>
        {isHR && (
          <div className="space-y-3 rounded-xl border border-line bg-slate-50 p-3">
            <div className="label">MCP write tools (hr_admin)</div>
            <div className="flex gap-2">
              <input className="input py-1.5" placeholder="Skill (e.g. Agentic AI)" value={skill.skill} onChange={(x) => setSkill({ ...skill, skill: x.target.value })} />
              <select className="input w-16 py-1.5" aria-label="Proficiency" value={skill.proficiency} onChange={(x) => setSkill({ ...skill, proficiency: Number(x.target.value) })}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select>
              <button className="btn btn-primary py-1.5" disabled={!skill.skill || upSkill.isPending} onClick={() => upSkill.mutate()}>Save skill</button>
            </div>
            <div className="flex gap-2">
              <select className="input py-1.5" aria-label="Status" value={av.status} onChange={(x) => setAv({ ...av, status: x.target.value })}>{['Available', 'Rolling off', 'Partially available', 'Allocated'].map((s) => <option key={s}>{s}</option>)}</select>
              <input type="date" className="input py-1.5" aria-label="Available from" value={av.available_from} onChange={(x) => setAv({ ...av, available_from: x.target.value })} />
              <button className="btn btn-primary py-1.5" disabled={upAv.isPending} onClick={() => upAv.mutate()}>Update</button>
            </div>
            <button className="btn btn-ghost py-1.5 text-red-700" onClick={() => confirm(`Deactivate ${e.name} from the marketplace?`) && deact.mutate()}><UserX size={15} />Deactivate</button>
            {[upSkill, upAv, deact].map((m, i) => m.error ? <ErrorNote key={i} error={m.error} /> : null)}
            {(upSkill.isSuccess || upAv.isSuccess) && <div className="text-xs text-green-800">Saved via employee-mcp · audit-logged.</div>}
          </div>
        )}
      </div>
    </Card>
  )
}
