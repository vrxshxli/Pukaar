import { useState } from 'react'
import type { Ticket } from '../api'
import { minutesBetween } from '../api'
import { Chip, Empty, Icon, ticketColor, ticketLabel } from './ui'

const FILTERS = [
  { id: 'active', label: 'Active', icon: 'list' },
  { id: 'verify', label: 'Verify', icon: 'shield' },
  { id: 'safe', label: 'Safe', icon: 'check' },
  { id: 'all', label: 'All', icon: 'layers' },
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

function kindIcon(t: Ticket) {
  if (t.status === 'safe' || t.status === 'closed') return 'check'
  if (t.status === 'verify') return 'shield'
  if (t.medical) return 'heart'
  if (t.danger.length > 0) return 'alert'
  return 'people'
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
    <section className="flex min-h-0 flex-1 flex-col" aria-label="Ticket queue">
      <div className="mb-2 flex items-baseline justify-between px-1">
        <h2 className="text-[15px] font-semibold">Ticket queue</h2>
        <span className="text-[11px] text-muted">ranked by priority</span>
      </div>
      <div className="-mx-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto px-1 pb-2">
        {shown.length === 0 && (
          <Empty>{filter === 'active' ? 'No open tickets. Messages will appear here as they are triaged.' : 'Nothing here yet.'}</Empty>
        )}
        {shown.map((t) => {
          const color = ticketColor(t)
          const active = selected === t.id
          return (
            <button key={t.id} onClick={() => onSelect(t.id)}
              className={`group flex w-full gap-3 rounded-xl p-2 text-left transition ${active ? 'bg-accent-soft ring-1 ring-accent/60' : 'hover:bg-soft'}`}>
              <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                style={{ background: `${color}26`, color }}>
                <Icon name={kindIcon(t)} size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 block text-[13.5px] font-semibold leading-tight">{t.title}</span>
                <span className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-muted">
                  <b className="font-extrabold" style={{ color }}>{ticketLabel(t)}</b>
                  <span>·</span>
                  <span className="truncate">{t.area}{t.people ? ` · ${t.people} people` : ''} · {STATUS_TEXT[t.status] ?? t.status}</span>
                </span>
                {t.verify_reason && <span className="mt-1 block text-[11px] text-muted">{t.verify_reason}</span>}
                {(t.reasons.length > 0 && t.status !== 'verify') || t.report_count > 1 ? (
                  <span className="mt-1.5 flex flex-wrap gap-1">
                    {t.report_count > 1 && <Chip tone="teal">{t.report_count} reports merged</Chip>}
                    {t.status !== 'verify' && t.reasons.slice(0, 3).map((r) => <Chip key={r} tone={t.priority === 'P1' ? 'urgent' : 'marigold'}>{r}</Chip>)}
                  </span>
                ) : null}
                {t.danger.length > 0 && <span className="mt-1 block text-[11px] font-bold text-urgent">Danger: {t.danger.join(', ')}</span>}
              </span>
              <span className="flex shrink-0 flex-col items-end gap-1 pt-0.5">
                <span className="text-[10.5px] font-semibold text-muted">{t.id}</span>
                <span className="rounded-full bg-soft px-1.5 py-0.5 text-[10.5px] font-semibold tabular-nums text-muted">{minutesBetween(t.created_at, clock)}m</span>
              </span>
            </button>
          )
        })}
      </div>
      <nav className="mt-1 grid grid-cols-4 gap-1 rounded-xl border border-line bg-card p-1" role="tablist" aria-label="Filter tickets">
        {FILTERS.map((f) => (
          <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}
            className={`flex flex-col items-center gap-0.5 rounded-xl py-1.5 text-[10.5px] font-semibold transition ${filter === f.id ? 'bg-accent-soft text-accent' : 'text-muted hover:text-fg'}`}>
            <Icon name={f.icon} size={16} />
            <span>{f.label} <span className="tabular-nums opacity-75">{counts[f.id]}</span></span>
          </button>
        ))}
      </nav>
    </section>
  )
}
