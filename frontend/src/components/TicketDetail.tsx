import { useEffect, useState } from 'react'
import type { AuditEntry, Ticket } from '../api'
import { api, clock } from '../api'
import { AgentTag, Button, Chip, ErrorNote, Icon, Spinner, ticketColor, ticketLabel } from './ui'

interface Detail extends Ticket {
  reports: { reason: string; confidence: number; created_at: string; text: string; channel: string; language: string; phone: string }[]
  history: AuditEntry[]
}

const LANG: Record<string, string> = { hi: 'Hindi', mr: 'Marathi', hinglish: 'Hinglish', en: 'English' }

function Row({ icon, children }: { icon: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 text-xs">
      <Icon name={icon} size={14} className="mt-px shrink-0 text-muted" />
      <span className="min-w-0">{children}</span>
    </div>
  )
}

// The selected ticket, drawn as a card floating over the map.
export default function TicketDetail({ ticketId, officer, version, onClose }: {
  ticketId: string
  officer: string
  version: string
  onClose: () => void
}) {
  const [t, setT] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'details' | 'reports' | 'timeline'>('details')

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

  const color = t ? ticketColor(t) : '#8A9A93'
  const tabs = [
    { id: 'details', label: 'Details' },
    { id: 'reports', label: `Reports${t ? ` ${t.reports.length}` : ''}` },
    { id: 'timeline', label: 'Timeline' },
  ] as const
  return (
    <aside className="glass pointer-events-auto flex max-h-full min-h-0 w-full flex-col overflow-hidden" aria-label={`Ticket ${ticketId}`}>
      <div className="flex gap-3 p-3">
        <div className="flex h-[92px] w-[92px] shrink-0 flex-col items-center justify-center rounded-xl text-white"
          style={{ background: `linear-gradient(145deg, ${color}, ${color}99)` }}>
          <span className="text-2xl font-extrabold leading-none">{t ? ticketLabel(t) : '…'}</span>
          {t?.people ? <span className="mt-1 flex items-center gap-1 text-[11px] font-semibold opacity-90"><Icon name="people" size={12} />{t.people}</span> : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <h2 className="min-w-0 flex-1 text-[15px] font-semibold leading-snug">{t ? t.title : ticketId}</h2>
            <button onClick={onClose} aria-label="Close ticket details"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-soft text-muted hover:text-fg">
              <Icon name="close" size={14} />
            </button>
          </div>
          <div className="mt-1.5 space-y-1">
            <Row icon="pin">{ticketId} · {t?.area ?? '…'}</Row>
            <Row icon="clock">{t ? `${t.status.replace('_', ' ')}${t.safe_at ? ` at ${clock(t.safe_at)}` : ''}` : '…'}</Row>
          </div>
        </div>
      </div>
      <div className="flex gap-1 border-y border-line px-3 py-1.5" role="tablist">
        {tabs.map((x) => (
          <button key={x.id} role="tab" aria-selected={tab === x.id} onClick={() => setTab(x.id)}
            className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${tab === x.id ? 'bg-accent-soft text-accent' : 'text-muted hover:text-fg'}`}>
            {x.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {error && <ErrorNote>{error}</ErrorNote>}
        {!t && !error && <Spinner />}
        {t && tab === 'details' && (
          <>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <Row icon="people">{t.people ?? 'not known yet'} people</Row>
              <Row icon="water">Water: {t.water_level ?? 'not stated'}</Row>
              <Row icon="shield">Vulnerable: {t.vulnerable.join(', ') || 'none stated'}</Row>
              <Row icon="heart">Medical: {t.medical ?? 'none stated'}</Row>
            </div>
            {t.danger.length > 0 && <Row icon="alert"><b className="text-urgent">Danger: {t.danger.join(', ')}</b></Row>}
            {t.reasons.length > 0 && (
              <div>
                <h3 className="mb-1 text-[11px] font-bold uppercase tracking-wide text-muted">Why this priority</h3>
                <div className="flex flex-wrap gap-1">{t.reasons.map((r) => <Chip key={r}>{r}</Chip>)}</div>
              </div>
            )}
            {t.notes.length > 0 && <ul className="list-disc pl-4 text-xs text-muted">{t.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          </>
        )}
        {t && tab === 'reports' && (
          <ul className="space-y-1.5">
            <li className="text-[11px] text-muted">Raw messages beside the extraction.</li>
            {t.reports.map((r, i) => (
              <li key={i} className="rounded-xl bg-soft p-2 text-xs">
                <div className="mb-0.5 flex flex-wrap gap-1 text-[11px] text-muted">
                  <b className="text-fg">{r.channel}</b> · {LANG[r.language] ?? r.language} · {clock(r.created_at)} · {r.phone}
                </div>
                <p>{r.text}</p>
                <p className="mt-0.5 text-[11px] text-accent">Linked: {r.reason}{r.confidence < 1 ? ` (score ${r.confidence.toFixed(2)})` : ''}</p>
              </li>
            ))}
          </ul>
        )}
        {t && tab === 'timeline' && (
          <ol className="space-y-1.5">
            {t.history.map((h) => (
              <li key={h.id} className="flex gap-2 text-[11px]">
                <span className="w-14 shrink-0 text-muted">{clock(h.at)}</span>
                <span className="shrink-0"><AgentTag agent={h.agent} /></span><span>{h.summary}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
      {t && t.priority === 'P1' && !['safe', 'closed'].includes(t.status) && (
        <div className="flex items-center gap-2 border-t border-line px-3 py-2 text-[11px] text-muted">
          <span className="flex-1">Agents can raise a P1 but never lower it.</span>
          <Button small onClick={downgrade}>Downgrade to P2</Button>
        </div>
      )}
      {t && t.status === 'safe' && (
        <div className="flex items-center gap-2 border-t border-line px-3 py-2 text-[11px] text-muted">
          <span className="flex-1">Waiting for the family to confirm.</span>
          <Button small tone="primary" onClick={close}>Close as officer</Button>
        </div>
      )}
    </aside>
  )
}
