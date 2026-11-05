export type Role = 'hr_admin' | 'hiring_manager' | 'employee' | 'leadership'

export interface User {
  username: string
  display_name: string
  role: Role
  employee_id: string | null
  title: string
}

export interface ReqSkill { name: string; min_proficiency: number; weight: number }

export interface Job {
  job_id: string
  title: string
  role_family: string
  level: string
  department: string
  hiring_manager_id: string
  hiring_manager_name: string
  location: { city: string; country: string; region: string }
  work_mode: string
  relocation_supported: boolean
  posted_on: string
  start_date: string
  status: string
  priority: string
  openings: number
  min_years_experience: number
  required_skills: ReqSkill[]
  nice_to_have_skills: string[]
  description?: string
  applications?: number
}

export interface EmpSkill { name: string; proficiency: number; years: number; verified: boolean; last_used: number }

export interface Employee {
  employee_id: string
  name: string
  title: string
  role_family: string
  level: string
  department: string
  years_experience: number
  months_in_role: number
  city: string
  country: string
  region: string
  work_mode_preference: string
  willing_to_relocate: boolean
  relocation_preferences: string[]
  availability: { status: string; allocation_pct: number; available_from: string; project_end: string; notice_weeks: number }
  eligible_for_move: boolean
  open_to_move: boolean
  target_roles: string[]
  last_rating: number
  skills: EmpSkill[]
  certifications: string[]
  projects?: { name: string; client: string; description: string; start: string; end: string | null }[]
  aspiration?: string
  resume_summary?: string
  languages?: string[]
  education?: string
}

export interface AgentEvent {
  run_id: string
  seq: number
  ts: number
  agent: string
  agent_name: string
  framework: string
  type: 'status' | 'thought' | 'tool_call' | 'handoff' | 'metric' | 'result' | 'warning' | 'error' | 'interrupt' | 'done' | 'fallback'
  message: string
  data: any // eslint-disable-line @typescript-eslint/no-explicit-any
}

export interface MatchCardData {
  employee_id: string
  rank: number
  score: number
  explanation: string
  decision: string
  decision_reason: string | null
  components: Record<'skill' | 'adjacency' | 'availability' | 'location' | 'interest' | 'success', number>
  reasons: { strengths: string[]; gaps: string[]; bridges: string[]; availability: string; location: string; interest: string; experience: string; nice_to_have: string[] }
  hidden_fit: boolean
  headline: string
  applied: boolean
  sources: string[]
  name: string
  title: string
  city: string
  level: string
  department: string
}

export interface RunDetail {
  run_id: string
  job_id: string
  status: string
  started_at: string
  summary: any // eslint-disable-line @typescript-eslint/no-explicit-any
  results: MatchCardData[]
  live: any // eslint-disable-line @typescript-eslint/no-explicit-any
}
