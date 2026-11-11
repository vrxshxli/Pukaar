import { useEffect, useState } from 'react'
import { api, useLiveState } from '../api'
import ActivityFeed from '../components/ActivityFeed'
import ApprovalCard from '../components/ApprovalCard'
import AuditLog from '../components/AuditLog'
import Header from '../components/Header'
import ReplayControls from '../components/ReplayControls'
import TicketDetail from '../components/TicketDetail'
import TicketQueue from '../components/TicketQueue'
import WardMap from '../components/WardMap'
import { Empty, ErrorNote, Spinner } from '../components/ui'

function useOfficer() {
  const [officer, setOfficer] = useState(() => {
    try { return localStorage.getItem('pukaar-officer') || 'Officer Rao' } catch { return 'Officer Rao' }
  })
  useEffect(() => {
    try { localStorage.setItem('pukaar-officer', officer) } catch { /* private mode */ }
  }, [officer])
  return [officer, setOfficer] as const
}

function Metric({ value, label, tone }: { value: number; label: string; tone?: string }) {
  return (
    <div className="flex-1 border-r border-line px-3 py-1.5 last:border-r-0">
      <div className="text-xl font-extrabold tabular-nums" style={tone ? { color: tone } : undefined}>{value}</div>
      <div className="text-[11px] text-muted">{label}</div>
    </div>
  )
}

export default function Dashboard() {
  const { state, error, activity, connected, refresh } = useLiveState()
  const [officer, setOfficer] = useOfficer()
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

  if (!state) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        {error ? <ErrorNote>{error}</ErrorNote> : <Spinner label="Connecting to the control room" />}
      </div>
    )
  }

  const m = state.metrics
  return (
    <div className="flex h-full flex-col">
      <Header state={state} connected={connected} officer={officer} setOfficer={setOfficer}
        onToggleAutomation={() => act(() => api('/api/settings', { automation: !state.automation }))}
        onLlmMode={(mode) => act(() => api('/api/settings', { llm_mode: mode }))}>
        <ReplayControls replay={state.replay} onError={setActionError} />
      </Header>
      {!state.automation && (
        <div className="bg-urgent px-4 py-1 text-center text-xs font-bold text-white">
          Automation is off: agents keep logging, but no message is sent and no new proposal is made.
        </div>
      )}
      <div className="flex border-b border-line bg-card">
        <Metric value={m.reports_in} label="reports in" />
        <Metric value={m.tickets} label="tickets after merging" />
        <Metric value={m.open_p1} label="open P1 tickets" tone="#B3284F" />
        <Metric value={m.waiting_approvals} label="waiting for your approval" tone="#a06d00" />
        <Metric value={m.safe} label="families safe" tone="#5A8A23" />
        <Metric value={m.verify} label="claims in Verify" />
        <Metric value={m.wasted_trips} label="wasted trips" />
      </div>
      {(error || actionError) && <div className="px-4 pt-2"><ErrorNote>{actionError ?? error}</ErrorNote></div>}
      <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[340px_1fr_360px]">
        <div className="flex min-h-[300px] flex-col lg:min-h-0">
          <TicketQueue tickets={state.tickets} clock={state.clock} selected={selected} onSelect={setSelected} />
        </div>
        <div className="relative min-h-[360px] overflow-hidden rounded-lg border border-line lg:min-h-0">
          <WardMap center={state.ward.center} river={state.ward.river} tickets={state.tickets} teams={state.teams}
            camps={state.camps} blocked={state.blocked_roads} zones={state.watch_zones} preview={preview}
            selectedTicket={selected} onSelectTicket={setSelected} />
          <div className="pointer-events-none absolute bottom-2 left-2 z-[1000] flex flex-wrap gap-2 rounded-md bg-card/90 px-2 py-1 text-[10px] font-semibold shadow">
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-urgent" />P1</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-marigold" />P2</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-teal" />P3</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-[#7A8B8C]" />Verify</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-safe" />Safe</span>
            <span><i className="mr-1 inline-block h-1 w-3 bg-urgent align-middle" />Blocked road</span>
          </div>
        </div>
        <div className="flex min-h-0 flex-col gap-3">
          {selected ? (
            <div className="min-h-[300px] flex-1 lg:min-h-0">
              <TicketDetail ticketId={selected} officer={officer} version={state.clock} onClose={() => setSelected(null)} />
            </div>
          ) : (
            <>
              <section aria-label="Waiting for approval" className="max-h-[45%] min-h-0 overflow-y-auto">
                <h2 className="mb-2 text-sm font-bold">Waiting for your approval ({state.approvals.length})</h2>
                <div className="space-y-2">
                  {state.approvals.length === 0 && <Empty>Nothing to approve. Dispatches, bulletins and uncertain merges will appear here.</Empty>}
                  {state.approvals.map((a) => (
                    <ApprovalCard key={a.id} approval={a} teams={state.teams} busy={busy} onPreview={setPreview}
                      onDecide={(decision, teamId) => act(() => api(`/api/approvals/${a.id}`, { decision, officer, team_id: teamId }))} />
                  ))}
                </div>
              </section>
              <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-line bg-card p-2">
                <div className="mb-2 flex gap-1" role="tablist">
                  {(['activity', 'audit'] as const).map((id) => (
                    <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                      className={`rounded-md px-2 py-1 text-xs font-semibold ${tab === id ? 'bg-teal text-white' : 'bg-soft text-muted'}`}>
                      {id === 'activity' ? 'Agent activity' : 'Audit log'}
                    </button>
                  ))}
                </div>
                <div className="min-h-[200px] flex-1 overflow-y-auto lg:min-h-0">
                  {tab === 'activity' ? <ActivityFeed entries={activity} onSelectTicket={setSelected} /> : <AuditLog />}
                </div>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
