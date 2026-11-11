import { useCallback, useEffect, useRef, useState } from 'react'

export type Priority = 'P1' | 'P2' | 'P3'

export interface Ticket {
  id: string
  title: string
  area: string
  landmark: string | null
  lat: number | null
  lng: number | null
  kind: string
  priority: Priority
  priority_score: number
  reasons: string[]
  status: string
  people: number | null
  vulnerable: string[]
  medical: string | null
  water_level: string | null
  danger: string[]
  battery: number | null
  verify_reason: string | null
  safe_camp: string | null
  safe_at: string | null
  team_id: string | null
  created_at: string
  updated_at: string
  notes: string[]
  report_count: number
  reporter_count: number
}

export interface Route {
  id: number
  coords: [number, number][]
  roads: string[]
  eta_min: number
  length_m: number
  status: string
  progress: number
  ticket_id: string | null
}

export interface Team {
  id: string
  name: string
  kind: string
  skills: string[]
  status: string
  lat: number
  lng: number
  hours_on_duty: number
  ticket_id: string | null
  note: string | null
  route: Route | null
}

export interface Approval {
  id: number
  kind: string
  ticket_id: string | null
  team_id: string | null
  title: string
  reasons: string[]
  payload: {
    route?: { coords: [number, number][]; summary: string; eta_min: number; length_m: number }
    why_team?: string
    alternatives?: { team_id: string; name: string; eta_min: number }[]
    text?: string
    into?: string
    why?: string
  }
  created_by: string
  created_at: string
}

export interface AuditEntry {
  id: number
  at: string
  agent: string
  tool: string | null
  kind: string
  summary: string
  input: string | null
  result: string | null
  ticket_id: string | null
  approved_by: string | null
}

export interface Camp {
  id: string
  name: string
  lat: number
  lng: number
  capacity: number
  occupancy: number
  needs: string[]
}

export interface LlmStatus {
  mode: string
  effective: string
  fallback: boolean
  model: string | null
  embeddings: string | null
  fallbacks: number
  last_error: string | null
}

export interface ReplayStatus {
  state: string
  speed: number
  sent: number
  total: number
  next_at?: string | null
}

export interface State {
  incident: { name: string; level: string; status: string; note: string }
  ward: { name: string; center: { lat: number; lng: number }; river: [number, number][]; incident_name: string; helplines: Record<string, string> }
  clock: string
  clock_speed: number
  automation: boolean
  auto_field: boolean
  llm: LlmStatus
  planner?: { scope: 'off' | 'judgment' | 'all'; provider: string | null; model: string | null; max_steps: number }
  replay: ReplayStatus
  tickets: Ticket[]
  teams: Team[]
  approvals: Approval[]
  camps: Camp[]
  blocked_roads: { road: string; segments: [number, number][][] }[]
  watch_zones: { name: string; polygon: [number, number][] }[]
  bulletins: { id: number; text: string; language: string; status: string }[]
  metrics: { reports_in: number; tickets: number; open_p1: number; waiting_approvals: number; wasted_trips: number; safe: number; verify: number }
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status = 0) {
    super(message)
    this.status = status
  }
}

// Officer and volunteer pages call this when the server says nobody is signed in.
export function goToLogin() {
  if (window.location.pathname === '/login') return
  const next = window.location.pathname + window.location.search
  window.location.assign(`/login?next=${encodeURIComponent(next)}`)
}

export interface User {
  username: string
  name: string
  role: 'officer' | 'volunteer'
  team_id: string | null
}

// Who is signed in. Sends the browser to the sign-in page if nobody is.
export function useMe() {
  const [user, setUser] = useState<User | null>(null)
  useEffect(() => {
    api<{ user: User }>('/api/auth/me').then((r) => setUser(r.user)).catch(() => { /* api() already redirected */ })
  }, [])
  return user
}

export async function logout() {
  try { await api('/api/auth/logout', {}) } finally { window.location.assign('/login') }
}

export async function api<T = unknown>(path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, body === undefined ? undefined : {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the Pukaar server. Is it running?')
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const data = await res.json()
      if (data.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* keep the generic message */ }
    if (res.status === 401 && !path.startsWith('/api/auth/login')) goToLogin()
    throw new ApiError(detail, res.status)
  }
  return res.json() as Promise<T>
}

export interface StreamEvent {
  kind: string
  data: Record<string, unknown>
}

// Opens the live event stream and calls onEvent for each event.
// The browser reconnects on its own if the connection drops.
export function useStream(query: string, onEvent: (e: StreamEvent) => void) {
  const handler = useRef(onEvent)
  handler.current = onEvent
  const [connected, setConnected] = useState(false)
  useEffect(() => {
    const source = new EventSource(`/api/stream${query}`)
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.onmessage = (msg) => {
      try {
        handler.current(JSON.parse(msg.data))
      } catch { /* ignore malformed events */ }
    }
    return () => source.close()
  }, [query])
  return connected
}

// The dashboard's view of the world: one state fetch, refreshed when the
// server says something changed, plus a live activity feed.
export function useLiveState() {
  const [state, setState] = useState<State | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activity, setActivity] = useState<AuditEntry[]>([])
  const timer = useRef<number | undefined>(undefined)

  const refresh = useCallback(async () => {
    try {
      setState(await api<State>('/api/state'))
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  const refreshSoon = useCallback(() => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(refresh, 250)
  }, [refresh])

  useEffect(() => {
    refresh()
    api<AuditEntry[]>('/api/activity?limit=120').then(setActivity).catch(() => {})
    // A slow heartbeat keeps the clock and moving teams fresh even when quiet.
    const id = window.setInterval(refresh, 3000)
    return () => window.clearInterval(id)
  }, [refresh])

  const connected = useStream('', (e) => {
    if (e.kind === 'activity') {
      const entry = e.data as unknown as AuditEntry
      if (entry.kind !== 'tool') setActivity((a) => [entry, ...a].slice(0, 300))
      refreshSoon()
    } else if (e.kind === 'changed') {
      if ((e.data as { what?: string }).what === 'all') setActivity([])
      refreshSoon()
    }
  })

  return { state, error, activity, connected, refresh }
}

export function clock(iso: string | null | undefined) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
}

export function minutesBetween(a: string, b: string) {
  return Math.max(0, Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000))
}
