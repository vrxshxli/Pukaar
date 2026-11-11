import { useState } from 'react'
import type { Ticket } from '../api'
import { minutesBetween } from '../api'
import { Chip, Empty, PriorityBadge } from './ui'

const FILTERS = [
  { id: 'active', label: 'Active' },
  { id: 'verify', label: 'Verify' },
  { id: 'safe', label: 'Safe' },
  { id: 'all', label: 'All' },
] as const

const STATUS_TEXT: Record<string, string> = {
  open: 'Open', proposed: 'Team proposed', assigned: 'Team assigned', en_route: 'Team on the way',
  safe: 'Safe', closed: 'Closed', verify: 'Checking claim', info: 'Field report',
}

function matches(t: Ticket, filter: string) {
  if (filter === 'all') return true
  if (filter === 'verify') return t.status === 'verify'
  if (filter === 'safe') return t.status === 'safe' || t.status === 'closed'
  return !['safe', 'closed', 'verify', 'info'].includes(t.status)
}

export default function TicketQueue({ tickets, clock, selected, onSelect }: {
  tickets: Ticket[]
  clock: string
  selected: string | null
  onSelect: (id: string) => void
}) {
  const [filter, setFilter] = useState<string>('active')
  const shown = tickets.filter((t) => matches(t, filter))
  const counts = Object.fromEntries(FILTERS.map((f) => [f.id, tickets.filter((t) => matches(t, f.id)).length]))
  return (
    <section className="flex min-h-0 flex-col" aria-label="Ticket queue">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-bold">Ticket queue</h2>
        <span className="text-xs text-muted">ranked by priority</span>
      </div>
      <div className="mb-2 flex gap-1" role="tablist">
        {FILTERS.map((f) => (
          <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}
            className={`rounded-md px-2 py-1 text-xs font-semibold ${filter === f.id ? 'bg-teal text-white' : 'bg-soft text-muted hover:text-fg'}`}>
            {f.label} <span className="opacity-75">{counts[f.id]}</span>
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {shown.length === 0 && (
          <Empty>{filter === 'active' ? 'No open tickets. Messages will appear here as they are triaged.' : 'Nothing here yet.'}</Empty>
        )}
        {shown.map((t) => (
          <button key={t.id} onClick={() => onSelect(t.id)}
            className={`block w-full rounded-lg border p-2.5 text-left transition hover:border-teal ${selected === t.id ? 'border-teal bg-teal/5 ring-1 ring-teal' : 'border-line bg-card'}`}>
            <div className="flex items-center gap-2">
              <PriorityBadge ticket={t} />
              <span className="text-[11px] font-semibold text-muted">{t.id}</span>
              {t.report_count > 1 && <Chip tone="teal">{t.report_count} reports merged</Chip>}
              <span className="ml-auto text-[11px] text-muted">{minutesBetween(t.created_at, clock)} min</span>
            </div>
            <div className="mt-1 text-sm font-bold leading-tight">{t.title}</div>
            <div className="text-xs text-muted">
              {t.area}{t.people ? ` · ${t.people} people` : ''} · {STATUS_TEXT[t.status] ?? t.status}
            </div>
            {t.verify_reason && <div className="mt-1 text-xs text-muted">{t.verify_reason}</div>}
            {t.reasons.length > 0 && t.status !== 'verify' && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {t.reasons.slice(0, 5).map((r) => <Chip key={r} tone={t.priority === 'P1' ? 'urgent' : 'marigold'}>{r}</Chip>)}
              </div>
            )}
            {t.danger.length > 0 && <div className="mt-1 text-xs font-bold text-urgent">Danger: {t.danger.join(', ')}</div>}
          </button>
        ))}
      </div>
    </section>
  )
}
