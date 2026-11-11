import { useEffect, useState } from 'react'
import type { AuditEntry, Ticket } from '../api'
import { api, clock } from '../api'
import { AgentTag, Button, Chip, ErrorNote, PriorityBadge, Spinner } from './ui'

interface Detail extends Ticket {
  reports: { reason: string; confidence: number; created_at: string; text: string; channel: string; language: string; phone: string }[]
  history: AuditEntry[]
}

const LANG: Record<string, string> = { hi: 'Hindi', mr: 'Marathi', hinglish: 'Hinglish', en: 'English' }

export default function TicketDetail({ ticketId, officer, version, onClose }: {
  ticketId: string
  officer: string
  version: string
  onClose: () => void
}) {
  const [t, setT] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Detail>(`/api/tickets/${ticketId}`).then((d) => { setT(d); setError(null) }).catch((e) => setError(e.message))
  }, [ticketId, version])

  async function downgrade() {
    try {
      await api(`/api/tickets/${ticketId}/downgrade`, { officer, priority: 'P2' })
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function close() {
    try {
      await api(`/api/tickets/${ticketId}/close`, { officer })
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <aside className="flex h-full min-h-0 flex-col rounded-lg border border-line bg-card" aria-label={`Ticket ${ticketId}`}>
      <div className="flex items-center gap-2 border-b border-line p-3">
        {t && <PriorityBadge ticket={t} />}
        <h2 className="text-sm font-bold">{ticketId}{t ? `: ${t.title}` : ''}</h2>
        <button onClick={onClose} className="ml-auto rounded px-2 text-lg leading-none text-muted hover:text-fg" aria-label="Close ticket details">×</button>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {error && <ErrorNote>{error}</ErrorNote>}
        {!t && !error && <Spinner />}
        {t && (
          <>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
              <span className="text-muted">Area</span><span>{t.area}</span>
              <span className="text-muted">People</span><span>{t.people ?? 'not known yet'}</span>
              <span className="text-muted">Water</span><span>{t.water_level ?? 'not stated'}</span>
              <span className="text-muted">Vulnerable</span><span>{t.vulnerable.join(', ') || 'none stated'}</span>
              <span className="text-muted">Medical</span><span>{t.medical ?? 'none stated'}</span>
              <span className="text-muted">Status</span><span>{t.status.replace('_', ' ')}{t.safe_at ? ` at ${clock(t.safe_at)}` : ''}</span>
            </div>
            {t.reasons.length > 0 && (
              <div>
                <h3 className="mb-1 text-xs font-bold text-muted">Why this priority</h3>
                <div className="flex flex-wrap gap-1">{t.reasons.map((r) => <Chip key={r}>{r}</Chip>)}</div>
              </div>
            )}
            {t.notes.length > 0 && <ul className="list-disc pl-4 text-xs">{t.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
            <div>
              <h3 className="mb-1 text-xs font-bold text-muted">{t.reports.length} report{t.reports.length === 1 ? '' : 's'} (raw messages beside the extraction)</h3>
              <ul className="space-y-1.5">
                {t.reports.map((r, i) => (
                  <li key={i} className="rounded-md border border-line p-2 text-xs">
                    <div className="mb-0.5 flex flex-wrap gap-1 text-[11px] text-muted">
                      <b className="text-fg">{r.channel}</b> · {LANG[r.language] ?? r.language} · {clock(r.created_at)} · {r.phone}
                    </div>
                    <p>{r.text}</p>
                    <p className="mt-0.5 text-[11px] text-teal">Linked: {r.reason}{r.confidence < 1 ? ` (score ${r.confidence.toFixed(2)})` : ''}</p>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-bold text-muted">Timeline</h3>
              <ol className="space-y-1">
                {t.history.map((h) => (
                  <li key={h.id} className="flex gap-2 text-[11px]">
                    <span className="w-14 shrink-0 text-muted">{clock(h.at)}</span>
                    <AgentTag agent={h.agent} /><span>{h.summary}</span>
                  </li>
                ))}
              </ol>
            </div>
            {t.priority === 'P1' && !['safe', 'closed'].includes(t.status) && (
              <div className="rounded-md bg-soft p-2 text-xs">
                Agents can raise a P1 but never lower it.
                <div className="mt-1"><Button small onClick={downgrade}>Downgrade to P2 as officer</Button></div>
              </div>
            )}
            {t.status === 'safe' && (
              <div className="rounded-md bg-soft p-2 text-xs">
                Waiting for the family to confirm. You can close it without their reply:
                <div className="mt-1"><Button small tone="primary" onClick={close}>Close ticket as officer</Button></div>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
