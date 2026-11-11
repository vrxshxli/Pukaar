import type L from 'leaflet'
import { useEffect, useState } from 'react'
import type { State } from '../api'
import { api, clock, logout, useLiveState, useMe } from '../api'
import ActivityFeed from '../components/ActivityFeed'
import ApprovalCard from '../components/ApprovalCard'
import AuditLog from '../components/AuditLog'
import MapToolbar from '../components/MapToolbar'
import ReplayControls from '../components/ReplayControls'
import TicketDetail from '../components/TicketDetail'
import TicketQueue from '../components/TicketQueue'
import WardMap, { type Basemap } from '../components/WardMap'
import { COLORS, Empty, ErrorNote, Icon, Logo, Spinner } from '../components/ui'
import { ThemeToggle } from '../theme'

const LEVEL_COLOR: Record<string, string> = { Red: COLORS.urgent, Orange: '#D9733B', Yellow: COLORS.marigold, none: COLORS.grey }

function useStored<T extends string>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => {
    try { return (localStorage.getItem(key) as T) || fallback } catch { return fallback }
  })
  useEffect(() => {
    try { localStorage.setItem(key, value) } catch { /* private mode */ }
  }, [key, value])
  return [value, setValue] as const
}

const APPS = [
  { href: '/chat', icon: 'chat', label: 'Chat', title: 'Citizen chat', hint: 'What a family sees on the helpline', width: 420 },
  { href: '/volunteer', icon: 'boat', label: 'Volunteer', title: 'Volunteer desk', hint: 'A boat or van crew phone', width: 440 },
  { href: '/family', icon: 'family', label: 'Family', title: 'Is my family safe?', hint: 'Public lookup: status and camp only', width: 520 },
] as const
type App = (typeof APPS)[number]

function Rail({ connected, open, onOpen }: { connected: boolean; open: App | null; onOpen: (a: App | null) => void }) {
  const item = 'flex w-[58px] flex-col items-center gap-1 rounded-xl py-2 text-[10.5px] font-semibold transition'
  return (
    <nav aria-label="Pukaar apps" className="hidden w-[76px] shrink-0 flex-col items-center border-r border-line bg-panel py-4 lg:flex">
      <Logo size={34} />
      <div className="mt-6 flex flex-col gap-1">
        <button onClick={() => onOpen(null)} aria-current={!open ? 'page' : undefined}
          className={`${item} ${!open ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-soft hover:text-fg'}`}>
          <Icon name="compass" size={20} />Control
        </button>
        {APPS.map((a) => (
          <button key={a.href} onClick={() => onOpen(open?.href === a.href ? null : a)} aria-pressed={open?.href === a.href}
            className={`${item} ${open?.href === a.href ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-soft hover:text-fg'}`}>
            <Icon name={a.icon} size={20} />{a.label}
          </button>
        ))}
      </div>
      <div className="mt-auto flex flex-col items-center gap-3">
        <ThemeToggle className="bg-soft text-muted hover:text-fg" />
        <button onClick={logout} title="Sign out" aria-label="Sign out"
          className="flex h-8 w-8 items-center justify-center rounded-xl bg-soft text-muted hover:text-urgent">
          <Icon name="logout" size={17} />
        </button>
        <span className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-safe' : 'bg-urgent'}`} title={connected ? 'Live' : 'Reconnecting'} />
      </div>
    </nav>
  )
}

function MobileBar({ connected, open, onOpen }: { connected: boolean; open: App | null; onOpen: (a: App | null) => void }) {
  return (
    <div className="flex items-center gap-2 border-b border-line bg-panel px-4 py-2.5 lg:hidden">
      <Logo size={30} />
      <b className="font-serif text-base font-semibold">Pukaar</b>
      <span className={`h-2 w-2 rounded-full ${connected ? 'bg-safe' : 'bg-urgent'}`} />
      <nav className="ml-auto flex gap-1" aria-label="Pukaar apps">
        {APPS.map((a) => (
          <button key={a.href} onClick={() => onOpen(open?.href === a.href ? null : a)} aria-label={a.title}
            className={`flex h-8 w-8 items-center justify-center rounded-xl ${open?.href === a.href ? 'bg-accent-soft text-accent' : 'bg-soft text-muted'}`}>
            <Icon name={a.icon} size={17} />
          </button>
        ))}
      </nav>
      <ThemeToggle className="bg-soft text-muted" />
      <button onClick={logout} aria-label="Sign out" className="flex h-8 w-8 items-center justify-center rounded-xl bg-soft text-muted">
        <Icon name="logout" size={17} />
      </button>
    </div>
  )
}

// Chat, volunteer desk and family lookup open in a card over the map, so the
// officer never leaves the control room and the dashboard keeps updating behind it.
function AppPopup({ app, onClose }: { app: App; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div role="dialog" aria-label={app.title}
      className="glass fixed inset-2 z-[3000] flex flex-col overflow-hidden lg:inset-auto lg:bottom-4 lg:left-[88px] lg:top-4 lg:w-[var(--popup-w)]"
      style={{ '--popup-w': `${app.width}px` } as React.CSSProperties}>
      <div className="flex items-center gap-2.5 border-b border-line px-3 py-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-soft text-accent"><Icon name={app.icon} size={17} /></span>
        <div className="min-w-0 flex-1 leading-tight">
          <div className="text-sm font-bold">{app.title}</div>
          <div className="truncate text-[11px] text-muted">{app.hint}</div>
        </div>
        <button onClick={onClose} aria-label={`Close ${app.title}`} title="Close (Esc)"
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-soft text-muted hover:text-fg">
          <Icon name="close" size={15} />
        </button>
      </div>
      <iframe key={app.href} src={app.href} title={app.title} className="min-h-0 w-full flex-1 border-0 bg-surface" />
    </div>
  )
}

// Number colours readable on both the light and the dark panel.
const TONE_TEXT: Record<string, string> = {
  urgent: 'text-[#a8352e] dark:text-[#f0a39b]',
  marigold: 'text-[#8a5f12] dark:text-[#e8c07a]',
  safe: 'text-[#3c6e3a] dark:text-[#a8d4a2]',
}

// The three counts an officer acts on: a coloured edge and number, nothing else competing.
function KeyMetric({ value, label, tone, toneName, icon }: { value: number; label: string; tone: string; toneName: string; icon: string }) {
  return (
    <div className="flex flex-col rounded-xl border border-line bg-card p-2.5" style={{ borderTop: `3px solid ${tone}` }}>
      <span className="flex items-center justify-between">
        <span className={`font-serif text-[30px] font-semibold leading-none tabular-nums ${TONE_TEXT[toneName]}`}>{value}</span>
        <span style={{ color: tone }}><Icon name={icon} size={16} /></span>
      </span>
      <span className="mt-1.5 text-[12px] font-semibold leading-tight text-fg">{label}</span>
    </div>
  )
}

// Context counts: smaller, but still on solid cards.
function MinorMetric({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-xl border border-line bg-card px-2 py-2">
      <div className="font-serif text-[20px] font-semibold leading-none tabular-nums text-fg">{value}</div>
      <div className="mt-1 text-[11px] font-semibold leading-tight text-muted">{label}</div>
    </div>
  )
}

function IncidentCards({ state }: { state: State }) {
  const level = state.incident.level
  return (
    <div className="grid grid-cols-2 gap-2">
      <div className="rounded-xl border border-line bg-card p-3">
        <div className="flex items-center gap-1.5 text-[11px] text-muted"><Icon name="pin" size={13} />Current incident</div>
        <div className="mt-1 line-clamp-2 text-[13px] font-bold leading-snug">{state.ward.incident_name}</div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[10.5px]">
          <span className="rounded-full px-2 py-0.5 font-bold text-white" style={{ background: LEVEL_COLOR[level] ?? COLORS.grey }}>
            {level === 'none' ? 'No alert' : `${level} alert`}
          </span>
          <span className="text-muted">{state.incident.status}</span>
        </div>
      </div>
      <div className="relative overflow-hidden rounded-xl border border-line bg-card p-3" title="Game clock for the flood night">
        <div className="flex items-center gap-1.5 text-[11px] text-muted"><Icon name="clock" size={13} />Game clock</div>
        <div className="mt-1 font-serif text-[26px] font-semibold leading-none tabular-nums">{clock(state.clock)}</div>
        <div className="mt-1.5 text-[11px] text-muted">
          {state.clock_speed > 1 ? `${state.clock_speed}× speed` : state.clock_speed === 0 ? 'Paused' : 'Live'}
        </div>
      </div>
    </div>
  )
}

function MapControls({ map, center, basemap, setBasemap }: {
  map: L.Map | null
  center: { lat: number; lng: number }
  basemap: Basemap
  setBasemap: (b: Basemap) => void
}) {
  const btn = 'flex h-9 w-9 items-center justify-center text-fg hover:text-accent'
  return (
    <div className="pointer-events-auto flex flex-col items-end gap-2">
      <div className="glass flex flex-col divide-y divide-line overflow-hidden !rounded-xl">
        <button className={btn} onClick={() => map?.zoomIn()} aria-label="Zoom in"><Icon name="plus" size={17} /></button>
        <button className={btn} onClick={() => map?.zoomOut()} aria-label="Zoom out"><Icon name="minus" size={17} /></button>
        <button className={btn} onClick={() => map?.setView([center.lat, center.lng], 16)} aria-label="Back to the ward" title="Back to the ward">
          <Icon name="target" size={17} />
        </button>
      </div>
      <div className="glass flex gap-0.5 !rounded-xl p-1" role="radiogroup" aria-label="Map style">
        {(['streets', 'terrain', 'satellite'] as const).map((b) => (
          <button key={b} role="radio" aria-checked={basemap === b} onClick={() => setBasemap(b)}
            className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold capitalize transition ${basemap === b ? 'bg-accent-soft text-accent' : 'text-muted hover:text-fg'}`}>
            {b}
          </button>
        ))}
      </div>
    </div>
  )
}

function Legend() {
  const dot = (color: string, label: string) => (
    <span className="flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />{label}</span>
  )
  return (
    <div className="glass pointer-events-auto flex flex-wrap gap-x-2.5 gap-y-1 self-start !rounded-xl px-2.5 py-1.5 text-[10.5px] font-semibold">
      {dot(COLORS.urgent, 'P1')}{dot(COLORS.marigold, 'P2')}{dot(COLORS.teal, 'P3')}{dot(COLORS.grey, 'Verify')}{dot(COLORS.safe, 'Safe')}
      <span className="flex items-center gap-1"><i className="inline-block h-1 w-3 rounded" style={{ background: COLORS.urgent }} />Blocked</span>
      <span className="flex items-center gap-1"><i className="inline-block h-0.5 w-3 border-t-2 border-dashed" style={{ borderColor: COLORS.accent }} />Boat route</span>
    </div>
  )
}

export default function Dashboard() {
  const { state, error, activity, connected, refresh } = useLiveState()
  const me = useMe()
  const officer = me?.name ?? ''
  // New key so browsers that saved the old Terrain default start on Streets.
  const [basemap, setBasemap] = useStored<Basemap>('pukaar-map-style', 'streets')
  const [map, setMap] = useState<L.Map | null>(null)
  const [openApp, setOpenApp] = useState<App | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [preview, setPreview] = useState<[number, number][] | null>(null)
  const [tab, setTab] = useState<'activity' | 'audit'>('activity')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
      await refresh()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    // Volunteer accounts have their own desk.
    if (me?.role === 'volunteer') window.location.replace('/volunteer')
  }, [me])

  if (!state || !me || me.role !== 'officer') {
    return (
      <div className="flex h-full items-center justify-center p-6">
        {error ? <ErrorNote>{error}</ErrorNote> : <Spinner label="Connecting to the control room" />}
      </div>
    )
  }

  const m = state.metrics
  // P1 dispatches first, then other dispatches, then everything else.
  const scoreOf = Object.fromEntries(state.tickets.map((t) => [t.id, t.priority_score]))
  const approvalsSorted = [...state.approvals].sort((a, b) => {
    const rank = (x: typeof a) => (x.kind === 'dispatch' ? 0 : x.kind === 'merge' ? 1 : 2)
    return rank(a) - rank(b) || (scoreOf[b.ticket_id ?? ''] ?? 0) - (scoreOf[a.ticket_id ?? ''] ?? 0) || a.id - b.id
  })
  const initials = officer.split(/\s+/).filter(Boolean).slice(-2).map((w) => w[0]?.toUpperCase()).join('') || 'O'
  return (
    <div className="h-full lg:p-3">
      <div className="flex h-full flex-col overflow-y-auto bg-panel lg:flex-row lg:overflow-hidden lg:rounded-[18px] lg:border lg:border-line lg:shadow-[var(--shadow)]">
        <MobileBar connected={connected} open={openApp} onOpen={setOpenApp} />
        <Rail connected={connected} open={openApp} onOpen={setOpenApp} />
        {openApp && <AppPopup app={openApp} onClose={() => setOpenApp(null)} />}

        <aside className="flex max-h-[88vh] shrink-0 flex-col gap-4 border-line p-4 lg:max-h-none lg:min-h-0 lg:w-[316px] lg:border-r xl:w-[344px]">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h1 className="text-[24px] leading-tight">Control room</h1>
              <p className="text-xs text-muted">{state.ward.name} · पुकार</p>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-line bg-card py-1 pl-1 pr-2.5" title="Signed in. Your name goes on every approval.">
              <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-accent text-[11px] font-extrabold text-accent-fg">
                {initials}
                <span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-card ${connected ? 'bg-safe' : 'bg-urgent'}`} />
              </span>
              <span className="leading-tight">
                <span className="block text-xs font-bold">{officer}</span>
                <span className="block text-[10px] text-muted">Duty officer · {connected ? 'live' : 'reconnecting'}</span>
              </span>
            </div>
          </div>

          <section aria-label="Tonight at a glance">
            <h2 className="mb-2 px-1 text-[15px] font-semibold">Tonight at a glance</h2>
            <div className="grid grid-cols-3 gap-2">
              <KeyMetric value={m.open_p1} label="open P1 tickets" tone={COLORS.urgent} toneName="urgent" icon="alert" />
              <KeyMetric value={m.waiting_approvals} label="waiting for you" tone={COLORS.marigold} toneName="marigold" icon="bell" />
              <KeyMetric value={m.safe} label="families safe" tone={COLORS.safe} toneName="safe" icon="check" />
            </div>
            <div className="mt-2 grid grid-cols-4 gap-2">
              <MinorMetric value={m.reports_in} label="reports in" />
              <MinorMetric value={m.tickets} label="tickets after merge" />
              <MinorMetric value={m.verify} label="in Verify" />
              <MinorMetric value={m.wasted_trips} label="wasted trips" />
            </div>
          </section>

          <IncidentCards state={state} />

          <TicketQueue tickets={state.tickets} clock={state.clock} selected={selected} onSelect={setSelected} />
        </aside>

        <main className="relative flex min-w-0 flex-1 flex-col lg:overflow-y-auto xl:block xl:overflow-hidden">
          <div className="relative h-[72vh] min-h-[440px] shrink-0 xl:absolute xl:inset-0 xl:h-auto">
            <WardMap center={state.ward.center} river={state.ward.river} tickets={state.tickets} teams={state.teams}
              camps={state.camps} blocked={state.blocked_roads} zones={state.watch_zones} preview={preview}
              selectedTicket={selected} onSelectTicket={setSelected} basemap={basemap} onMap={setMap} />

            <div className="pointer-events-none absolute inset-3 z-[1000] flex flex-col gap-2 xl:right-[396px]">
              <div className="flex flex-col items-end gap-2">
                <MapToolbar state={state}
                  onToggleAutomation={() => act(() => api('/api/settings', { automation: !state.automation }))}
                  onLlmMode={(mode) => act(() => api('/api/settings', { llm_mode: mode }))}>
                  <ReplayControls replay={state.replay} onError={setActionError} />
                </MapToolbar>
                {!state.automation && (
                  <div className="pointer-events-auto rounded-xl bg-urgent px-3 py-1.5 text-xs font-bold text-white shadow-lg">
                    Automation is off: agents keep logging, but no message is sent and no new proposal is made.
                  </div>
                )}
                {(error || actionError) && <div className="pointer-events-auto"><ErrorNote>{actionError ?? error}</ErrorNote></div>}
              </div>
              <Legend />
              <div className="flex-1" />
              <div className="flex max-h-[62%] min-h-0 items-end gap-3">
                {selected && (
                  <div className="flex max-h-full min-h-0 w-full max-w-[500px]">
                    <TicketDetail ticketId={selected} officer={officer} version={state.clock} onClose={() => setSelected(null)} />
                  </div>
                )}
                <div className="ml-auto">
                  <MapControls map={map} center={state.ward.center} basemap={basemap} setBasemap={setBasemap} />
                </div>
              </div>
            </div>
          </div>

          <section className="m-3 flex h-[80vh] min-h-0 flex-col gap-3 rounded-xl border border-line bg-panel p-3 xl:glass xl:absolute xl:bottom-3 xl:right-3 xl:top-3 xl:z-[1000] xl:m-0 xl:h-auto xl:w-[372px]">
            <div className="flex items-center justify-between px-1">
              <h2 className="text-[15px] font-semibold">Waiting for your approval</h2>
              <span className={`rounded-full px-2 py-0.5 text-xs font-extrabold tabular-nums ${state.approvals.length ? 'bg-accent text-accent-fg' : 'bg-soft text-muted'}`}>
                {state.approvals.length}
              </span>
            </div>
            <div className="max-h-[52%] min-h-0 shrink-0 space-y-2 overflow-y-auto" aria-label="Waiting for approval">
              {state.approvals.length === 0 && <Empty>Nothing to approve. Dispatches, bulletins and uncertain merges will appear here.</Empty>}
              {approvalsSorted.map((a) => (
                <ApprovalCard key={a.id} approval={a} teams={state.teams} busy={busy} onPreview={setPreview}
                  onDecide={(decision, teamId) => act(() => api(`/api/approvals/${a.id}`, { decision, officer, team_id: teamId }))} />
              ))}
            </div>
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="mb-2 flex rounded-xl bg-soft p-1" role="tablist">
                {(['activity', 'audit'] as const).map((id) => (
                  <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                    className={`flex-1 rounded-lg px-2 py-1.5 text-xs font-semibold transition ${tab === id ? 'bg-card text-accent shadow-sm' : 'text-muted hover:text-fg'}`}>
                    {id === 'activity' ? 'Agent activity' : 'Audit log'}
                  </button>
                ))}
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                {tab === 'activity' ? <ActivityFeed entries={activity} onSelectTicket={setSelected} /> : <AuditLog />}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}
