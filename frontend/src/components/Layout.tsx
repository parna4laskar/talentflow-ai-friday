import clsx from 'clsx'
import {
  BarChart3, BriefcaseBusiness, Compass, Gauge, LayoutDashboard, LogOut, Network, PlusCircle, ShieldCheck, Sparkles, Users,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ROLE_LABEL, useAuth } from '../lib/auth'
import { initials } from '../lib/format'
import type { Role } from '../lib/types'
import Copilot from './Copilot'

const NAV: Record<Role, { to: string; label: string; icon: typeof Gauge }[]> = {
  hiring_manager: [
    { to: '/hm', label: 'My Roles', icon: BriefcaseBusiness },
    { to: '/hm/post', label: 'Post a Role', icon: PlusCircle },
    { to: '/insights', label: 'Talent Insights', icon: BarChart3 },
    { to: '/architecture', label: 'How it Works', icon: Network },
  ],
  hr_admin: [
    { to: '/hr', label: 'Command Center', icon: LayoutDashboard },
    { to: '/hr/jobs', label: 'All Roles', icon: BriefcaseBusiness },
    { to: '/hr/employees', label: 'Employee Directory', icon: Users },
    { to: '/hr/governance', label: 'AI Governance', icon: ShieldCheck },
    { to: '/architecture', label: 'How it Works', icon: Network },
  ],
  employee: [
    { to: '/me', label: 'Career Hub', icon: Compass },
    { to: '/architecture', label: 'How it Works', icon: Network },
  ],
  leadership: [
    { to: '/insights', label: 'Talent Insights', icon: BarChart3 },
    { to: '/hr/governance', label: 'AI Governance', icon: ShieldCheck },
    { to: '/architecture', label: 'How it Works', icon: Network },
  ],
}

export default function Layout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const [copilot, setCopilot] = useState(false)
  if (!user) return null
  return (
    <div className="flex h-full">
      <aside className="flex w-64 shrink-0 flex-col bg-navy-900 text-slate-200">
        <div className="flex items-center gap-3 px-6 py-6">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-gold-500 font-serif text-lg font-bold text-navy-950">T</div>
          <div>
            <div className="font-serif text-lg leading-none text-white">TalentFlow<span className="text-gold-400"> AI</span></div>
            <div className="mt-1 text-[10px] uppercase tracking-[.18em] text-slate-400">Internal Talent Marketplace</div>
          </div>
        </div>
        <div className="mx-4 mb-4 rounded-lg bg-navy-800 px-3 py-2 text-[11px] uppercase tracking-wider text-gold-400">{ROLE_LABEL[user.role]} workspace</div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV[user.role].map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to.split('/').length === 2}
              className={({ isActive }) => clsx('flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors',
                isActive ? 'bg-white/10 font-semibold text-white shadow-[inset_3px_0_0_#c9a227]' : 'text-slate-300 hover:bg-white/5 hover:text-white')}>
              <Icon size={18} /> {label}
            </NavLink>
          ))}
        </nav>
        <button onClick={() => setCopilot(true)} className="mx-4 mb-4 flex items-center justify-center gap-2 rounded-lg border border-gold-500/40 bg-gold-500/10 px-3 py-2.5 text-sm font-semibold text-gold-400 hover:bg-gold-500/20">
          <Sparkles size={16} /> Ask TalentFlow Copilot
        </button>
        <div className="flex items-center gap-3 border-t border-white/10 px-5 py-4">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-steel-600 text-xs font-bold text-white">{initials(user.display_name)}</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-white">{user.display_name}</div>
            <div className="truncate text-[11px] text-slate-400">{user.title}</div>
          </div>
          <button aria-label="Sign out" title="Sign out" onClick={() => { logout(); nav('/login') }} className="rounded-md p-1.5 text-slate-400 hover:bg-white/10 hover:text-white">
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1400px] px-8 py-8">
          <Outlet />
        </div>
      </main>
      <Copilot open={copilot} onClose={() => setCopilot(false)} />
    </div>
  )
}
