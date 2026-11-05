// Validated categorical order (dataviz validator: all adjacent checks pass on white; first 3 pass all-pairs).
export const SERIES = ['#2a78d6', '#c98500', '#1baf7a', '#6250d6', '#e34948'] as const
// Sequential blue ramp (ordinal steps start at 250 to clear 2:1 on white)
export const SEQ = ['#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b']
export const STATUS = { good: '#0ca30c', warning: '#fab219', serious: '#ec835a', critical: '#d03b3b' } as const
export const INK = { primary: '#0f172a', secondary: '#475569', muted: '#64748b', grid: '#eef1f5' }

export const FRAMEWORK_COLOR: Record<string, string> = {
  LangGraph: '#2a78d6',
  CrewAI: '#c98500',
  Swarm: '#1baf7a',
  'Responsible AI': '#6250d6',
  ML: '#e34948',
}

export const fmtNum = (n: number | null | undefined, digits = 0) =>
  n == null ? '—' : n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })

export const fmtUsd = (n: number) =>
  n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${(n / 1e3).toFixed(0)}K` : `$${n}`

export const fmtPct = (n: number | null | undefined, digits = 0) => (n == null ? '—' : `${(n * 100).toFixed(digits)}%`)

export const fmtDate = (s: string) => new Date(s).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })

export const initials = (name: string) => name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()

export const COMPONENT_LABEL: Record<string, string> = {
  skill: 'Skill fit',
  adjacency: 'Adjacency',
  availability: 'Availability',
  location: 'Location',
  interest: 'Interest',
  success: 'P(success)',
}
export const COMPONENT_WEIGHT: Record<string, number> = { skill: 0.35, adjacency: 0.15, availability: 0.15, location: 0.1, interest: 0.1, success: 0.15 }
