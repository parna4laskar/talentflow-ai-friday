import { useEffect, useRef, useState } from 'react'
import { withToken } from './api'
import type { AgentEvent } from './types'

/** Subscribe to a run's agent event stream (SSE). Replays history, then streams live. */
export function useRunEvents(runId: string | null | undefined) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [connected, setConnected] = useState(false)
  const seen = useRef(new Set<number>())

  useEffect(() => {
    if (!runId) return
    seen.current = new Set()
    setEvents([])
    const es = new EventSource(withToken(`/runs/${runId}/events`))
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    es.addEventListener('agent', (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as AgentEvent
      if (seen.current.has(ev.seq)) return
      seen.current.add(ev.seq)
      setEvents((prev) => [...prev, ev])
    })
    return () => es.close()
  }, [runId])

  return { events, connected }
}

export interface LiveTick {
  ts: number
  telemetry: { llm_calls: number; llm_cache_hits: number; llm_fallbacks: number; mcp_calls: number; cache_hit_ratio: number; avg_mcp_ms: number }
  activity: { simulated: boolean; applications_per_min: number; profile_updates_per_min: number; event: string }
}

/** Live platform telemetry stream; keeps a rolling window of ticks. */
export function useLiveTicks(windowSize = 40) {
  const [ticks, setTicks] = useState<LiveTick[]>([])
  useEffect(() => {
    const es = new EventSource(withToken('/insights/live'))
    es.addEventListener('tick', (e) => {
      const t = JSON.parse((e as MessageEvent).data) as LiveTick
      setTicks((prev) => [...prev.slice(-(windowSize - 1)), t])
    })
    return () => es.close()
  }, [windowSize])
  return ticks
}
