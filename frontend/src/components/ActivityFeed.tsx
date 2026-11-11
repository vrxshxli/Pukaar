import type { AuditEntry } from '../api'
import { clock } from '../api'
import { AgentTag, Empty } from './ui'

export default function ActivityFeed({ entries, onSelectTicket }: {
  entries: AuditEntry[]
  onSelectTicket: (id: string) => void
}) {
  const shown = entries.filter((e) => e.kind !== 'tool')
  if (shown.length === 0) {
    return <Empty>Agents are quiet. Start the replay or send a message from the citizen chat.</Empty>
  }
  return (
    <ol className="space-y-1.5" aria-live="polite">
      {shown.map((e) => (
        <li key={e.id} className={`flex gap-2 rounded-xl px-2 py-1.5 text-xs leading-snug ${e.kind === 'human' ? 'bg-marigold/10' : e.kind === 'held' ? 'bg-soft' : ''}`}>
          <span className="w-14 shrink-0 pt-0.5 text-[11px] text-muted">{clock(e.at)}</span>
          <span className="shrink-0"><AgentTag agent={e.agent} /></span>
          <span className="min-w-0">
            {e.summary}
            {e.ticket_id && !e.summary.includes(e.ticket_id) && (
              <button className="ml-1 font-semibold text-accent hover:underline" onClick={() => onSelectTicket(e.ticket_id!)}>
                {e.ticket_id}
              </button>
            )}
          </span>
        </li>
      ))}
    </ol>
  )
}
