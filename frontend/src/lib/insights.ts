import { useQuery } from '@tanstack/react-query'
import { api } from './api'

/* eslint-disable @typescript-eslint/no-explicit-any */
export interface Overview {
  kpis: Record<string, number | null>
  trend: { month: string; internal_moves: number; avg_time_to_fill_days: number; success_rate: number; cost_avoided_usd: number }[]
  flows: { from: string; to: string; moves: number }[]
  supply_demand: { skill: string; open_roles: number; employees: number; avg_proficiency: number; growth: number }[]
  hot_skills: { skill: string; growth: number; employees: number }[]
  by_department: Record<string, number>
  by_region: Record<string, number>
  by_availability: Record<string, number>
  by_level: Record<string, number>
  by_retention_risk: Record<string, number>
  open_by_department: Record<string, number>
  applications_by_status: Record<string, number>
}

export function useOverview() {
  return useQuery({ queryKey: ['overview'], queryFn: () => api<Overview>('/insights/overview'), refetchInterval: 30000 })
}

export const toRows = (o: Record<string, number>, k: string, v: string) =>
  Object.entries(o).map(([a, b]) => ({ [k]: a, [v]: b } as any)).sort((x: any, y: any) => y[v] - x[v])
