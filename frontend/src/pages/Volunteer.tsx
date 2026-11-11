import { useCallback, useEffect, useState } from 'react'
import { api, clock, useStream, type Route, type Team } from '../api'
import WardMap from '../components/WardMap'
import { Button, Chip, Empty, ErrorNote, Logo, PriorityBadge, Spinner } from '../components/ui'

interface Task {
  id: string
  title: string
  area: string
  priority: 'P1' | 'P2' | 'P3'
  reasons: string[]
  people: number | null
  vulnerable: string[]
  medical: string | null
  danger: string[]
  water_level: string | null
  status: string
  lat: number | null
  lng: number | null
  notes: string[]
}

interface View {
  team: Team
  task: Task | null
  route: Route | null
  messages: { id: number; text: string; created_at: string }[]
  blocked_roads: { road: string; segments: [number, number][][] }[]
}

const TEAMS = [
  { id: 'boat1', label: 'Boat 1 (medic)' },
  { id: 'boat2', label: 'Boat 2' },
  { id: 'boat3', label: 'Boat 3' },
  { id: 'van1', label: 'Supplies van' },
]
const ROADS = ['Lane 1', 'Lane 2', 'Lane 3', 'Lane 4', 'Lane 5', 'Lane 6', 'Lane 7', 'Lane 8', 'Lane 9',
  'Station Road', 'Market Road', 'River Road']
const STATUS: Record<string, string> = {
  free: 'Free, waiting for a task', assigned: 'New task: accept it to start', en_route: 'On the way',
  on_scene: 'At the family', returning: 'Taking the family to camp', repositioning: 'Moving to pre-position',
}

function useTeam() {
  const [team, setTeam] = useState(() => {
    try { return localStorage.getItem('pukaar-team') || '' } catch { return '' }
  })
  const pick = (id: string) => {
    setTeam(id)
    try { localStorage.setItem('pukaar-team', id) } catch { /* private mode */ }
  }
  return [team, pick] as const
}

export default function Volunteer() {
  const [teamId, setTeamId] = useTeam()
  const [view, setView] = useState<View | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [mode, setMode] = useState<'none' | 'blocked' | 'otp'>('none')
  const [otp, setOtp] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!teamId) return
    try {
      setView(await api<View>(`/api/volunteer/${teamId}`))
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [teamId])

  useEffect(() => {
    load()
    const id = window.setInterval(load, 3000)
    return () => window.clearInterval(id)
  }, [load])

  useStream(teamId ? `?team=${teamId}&phone=volunteer` : '?phone=none', (e) => {
    if (e.kind === 'team_message' || e.kind === 'changed') load()
  })

  async function act(action: string, extra: Record<string, string> = {}) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const r = await api<{ ok: boolean; error?: string }>(`/api/volunteer/${teamId}`, { action, ...extra })
      if (r.ok === false) setError(r.error ?? 'That did not work')
      else {
        setMode('none')
        setOtp('')
        if (action === 'otp') setNotice('Family confirmed safe. Take them to the camp shown on the map.')
      }
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!teamId) {
    return (
      <div className="mx-auto max-w-md p-4">
        <div className="mb-4 flex items-center gap-2"><Logo /><h1 className="text-lg font-extrabold">Pukaar volunteer desk</h1></div>
        <p className="mb-2 text-sm">Pick your team:</p>
        <div className="grid grid-cols-2 gap-2">
          {TEAMS.map((t) => (
            <button key={t.id} onClick={() => setTeamId(t.id)}
              className="rounded-xl border border-line bg-card p-4 text-left font-bold hover:border-teal">{t.label}</button>
          ))}
        </div>
      </div>
    )
  }

  const team = view?.team
  const task = view?.task
  return (
    <div className="mx-auto flex min-h-full max-w-md flex-col bg-surface">
      <div className="flex items-center gap-2 bg-ink px-3 py-2 text-white">
        <Logo size={30} />
        <div className="flex-1 leading-tight">
          <b className="block text-sm">Volunteer desk · {team?.name ?? teamId}</b>
          <span className="text-[11px] opacity-75">{team ? STATUS[team.status] ?? team.status : 'Loading'}</span>
        </div>
        <button onClick={() => setTeamId('')} className="rounded bg-white/15 px-2 py-1 text-[11px]">Switch team</button>
      </div>
      <div className="flex-1 space-y-3 p-3">
        {error && <ErrorNote>{error}</ErrorNote>}
        {notice && <div className="rounded-lg bg-safe/15 px-3 py-2 text-sm font-semibold text-safe">{notice}</div>}
        {!view && !error && <Spinner />}
        {view && !task && team?.status !== 'returning' && team?.status !== 'repositioning' && (
          <Empty>No task right now. Stay ready; new tasks appear here as soon as the officer approves them.</Empty>
        )}
        {task && (
          <section className="rounded-xl border border-line bg-card p-3">
            <div className="flex items-center gap-2">
              <PriorityBadge ticket={{ priority: task.priority, status: task.status, kind: 'rescue' }} />
              <span className="text-xs font-semibold text-muted">{task.id}</span>
            </div>
            <h2 className="mt-1 text-base font-extrabold">{task.title}</h2>
            <p className="text-sm text-muted">{task.area}{task.people ? ` · ${task.people} people` : ''}{task.water_level ? ` · water ${task.water_level}` : ''}</p>
            <div className="mt-1.5 flex flex-wrap gap-1">{task.reasons.map((r) => <Chip key={r}>{r}</Chip>)}</div>
            {task.danger.length > 0 && <p className="mt-1.5 rounded bg-urgent px-2 py-1 text-sm font-bold text-white">Danger: {task.danger.join(', ')}</p>}
            {task.notes.filter((n) => n.startsWith('Danger')).map((n) => <p key={n} className="mt-1 text-xs font-semibold text-urgent">{n}</p>)}
          </section>
        )}
        {view && (view.route || task) && (
          <div className="h-56 overflow-hidden rounded-xl border border-line">
            <WardMap center={task?.lat ? { lat: task.lat, lng: task.lng as number } : { lat: team!.lat, lng: team!.lng }}
              zoom={16} teams={team ? [{ ...team, route: view.route }] : []} blocked={view.blocked_roads}
              tickets={task && task.lat ? [{ ...task, kind: 'rescue', landmark: null, priority_score: 0, battery: null, verify_reason: null, safe_camp: null, safe_at: null, team_id: null, created_at: '', updated_at: '', report_count: 1, reporter_count: 1 }] : []} />
          </div>
        )}
        {view?.route && (
          <p className="text-xs text-muted">Route: {view.route.roads.join(', ')} · {(view.route.length_m / 1000).toFixed(1)} km · about {view.route.eta_min} min</p>
        )}
        {team && (
          <div className="grid grid-cols-2 gap-2">
            <Button tone="safe" disabled={busy || team.status !== 'assigned'} onClick={() => act('accept')}>Accept</Button>
            <Button tone="danger" disabled={busy} onClick={() => setMode(mode === 'blocked' ? 'none' : 'blocked')}>Lane blocked</Button>
            <Button disabled={busy || team.status !== 'en_route'} onClick={() => act('reached')}>Reached</Button>
            <Button tone="primary" disabled={busy || !['en_route', 'on_scene'].includes(team.status)} onClick={() => setMode(mode === 'otp' ? 'none' : 'otp')}>Enter family OTP</Button>
            <Button disabled={busy || !task} onClick={() => act('need_medic')}>Need medic</Button>
          </div>
        )}
        {mode === 'blocked' && (
          <div className="rounded-xl border border-urgent/40 bg-card p-3">
            <p className="mb-2 text-sm font-semibold">Which road is blocked?</p>
            <div className="grid grid-cols-3 gap-1.5">
              {ROADS.map((r) => (
                <button key={r} disabled={busy} onClick={() => act('blocked', { road: r })}
                  className="rounded-md border border-line px-2 py-2 text-xs font-semibold hover:border-urgent">{r}</button>
              ))}
            </div>
          </div>
        )}
        {mode === 'otp' && (
          <form className="flex gap-2 rounded-xl border border-teal/40 bg-card p-3" onSubmit={(e) => { e.preventDefault(); act('otp', { otp }) }}>
            <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 4))} inputMode="numeric"
              placeholder="4-digit OTP" aria-label="Family OTP" autoFocus
              className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-lg tracking-widest" />
            <Button type="submit" tone="primary" disabled={busy || otp.length !== 4}>Confirm</Button>
          </form>
        )}
        <section>
          <h3 className="mb-1 text-xs font-bold text-muted">Messages from the control room</h3>
          {view && view.messages.length === 0 && <p className="text-xs text-muted">None yet.</p>}
          <ul className="space-y-1.5">
            {view?.messages.slice().reverse().map((m) => (
              <li key={m.id} className="rounded-lg bg-card px-3 py-2 text-sm shadow-sm">
                {m.text}<span className="block text-right text-[10px] text-muted">{clock(m.created_at)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
