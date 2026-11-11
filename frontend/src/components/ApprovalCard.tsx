import { useState } from 'react'
import type { Approval, Team } from '../api'
import { Button, Chip } from './ui'

const KIND_LABEL: Record<string, string> = {
  dispatch: 'Dispatch', preposition: 'Pre-position', bulletin: 'Ward bulletin', merge: 'Possible duplicate',
  downgrade: 'Downgrade', close: 'Close ticket',
}

export default function ApprovalCard({ approval, teams, busy, onDecide, onPreview }: {
  approval: Approval
  teams: Team[]
  busy: boolean
  onDecide: (decision: 'approve' | 'reject', teamId?: string) => void
  onPreview: (coords: [number, number][] | null) => void
}) {
  const [changing, setChanging] = useState(false)
  const route = approval.payload.route
  const freeTeams = teams.filter((t) => t.status === 'free' && t.id !== approval.team_id &&
    (approval.kind !== 'dispatch' || (route ? true : false)))
  const alternatives = approval.payload.alternatives ?? []
  return (
    <article className="rounded-lg border border-marigold/60 bg-card p-3 shadow-sm"
      onMouseEnter={() => route && onPreview(route.coords)} onMouseLeave={() => onPreview(null)}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-extrabold uppercase tracking-wide text-[#a06d00] dark:text-marigold">
          {KIND_LABEL[approval.kind] ?? approval.kind} · waiting for you
        </span>
        <span className="text-[11px] text-muted">by {approval.created_by}</span>
      </div>
      <h3 className="mt-1 text-sm font-bold leading-snug">{approval.title}</h3>
      {approval.reasons.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {approval.reasons.map((r) => <Chip key={r} tone="teal">{r}</Chip>)}
        </div>
      )}
      {route && (
        <p className="mt-1.5 rounded-md bg-soft px-2 py-1 text-xs"><b className="text-teal">Route:</b> {route.summary}</p>
      )}
      {approval.payload.text && (
        <p className="mt-1.5 rounded-md bg-soft px-2 py-1 text-xs leading-relaxed">{approval.payload.text}</p>
      )}
      {changing ? (
        <div className="mt-2 space-y-1">
          <p className="text-xs font-semibold text-muted">Send a different team:</p>
          {freeTeams.length === 0 && <p className="text-xs text-muted">No other team is free right now.</p>}
          {freeTeams.map((t) => {
            const alt = alternatives.find((a) => a.team_id === t.id)
            return (
              <button key={t.id} disabled={busy} onClick={() => onDecide('approve', t.id)}
                className="block w-full rounded-md border border-line px-2 py-1 text-left text-xs hover:border-teal">
                <b>{t.name}</b> {t.skills.includes('medic') ? '· medic' : ''} · {t.hours_on_duty} h on duty
                {alt ? ` · about ${alt.eta_min} min` : ''}
              </button>
            )
          })}
          <Button small onClick={() => setChanging(false)}>Cancel</Button>
        </div>
      ) : (
        <div className="mt-2 flex gap-1.5">
          <Button tone="safe" small disabled={busy} onClick={() => onDecide('approve')}>Approve</Button>
          {approval.kind === 'dispatch' && <Button small disabled={busy} onClick={() => setChanging(true)}>Change team</Button>}
          <Button tone="danger" small disabled={busy} onClick={() => onDecide('reject')}>Reject</Button>
        </div>
      )}
    </article>
  )
}
