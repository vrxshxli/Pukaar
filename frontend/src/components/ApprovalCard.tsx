import { useState } from 'react'
import type { Approval, Team } from '../api'
import { Button, Chip, Icon } from './ui'

const KIND_LABEL: Record<string, string> = {
  dispatch: 'Dispatch', preposition: 'Pre-position', bulletin: 'Ward bulletin', merge: 'Possible duplicate',
  downgrade: 'Downgrade', close: 'Close ticket',
}

const KIND_ICON: Record<string, string> = {
  dispatch: 'boat', preposition: 'route', bulletin: 'bell', merge: 'layers', downgrade: 'shield', close: 'check',
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
    <article className="rounded-xl border border-line bg-card p-3 transition hover:border-accent/50"
      onMouseEnter={() => route && onPreview(route.coords)} onMouseLeave={() => onPreview(null)}>
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-soft text-accent">
          <Icon name={KIND_ICON[approval.kind] ?? 'bell'} size={15} />
        </span>
        <span className="text-[11px] font-extrabold uppercase tracking-wide text-accent">
          {KIND_LABEL[approval.kind] ?? approval.kind}
        </span>
        <span className="ml-auto text-[10.5px] text-muted">by {approval.created_by}</span>
      </div>
      <h3 className="mt-1.5 text-[13.5px] font-bold leading-snug">{approval.title}</h3>
      {approval.reasons.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {approval.reasons.map((r) => <Chip key={r} tone="teal">{r}</Chip>)}
        </div>
      )}
      {route && (
        <p className="mt-1.5 flex gap-1.5 rounded-xl bg-soft px-2 py-1.5 text-xs">
          <Icon name="route" size={14} className="mt-px shrink-0 text-accent" /><span>{route.summary}</span>
        </p>
      )}
      {approval.payload.text && (
        <p className="mt-1.5 rounded-xl bg-soft px-2 py-1.5 text-xs leading-relaxed">{approval.payload.text}</p>
      )}
      {changing ? (
        <div className="mt-2 space-y-1">
          <p className="text-xs font-semibold text-muted">Send a different team:</p>
          {freeTeams.length === 0 && <p className="text-xs text-muted">No other team is free right now.</p>}
          {freeTeams.map((t) => {
            const alt = alternatives.find((a) => a.team_id === t.id)
            return (
              <button key={t.id} disabled={busy} onClick={() => onDecide('approve', t.id)}
                className="block w-full rounded-xl border border-line px-2 py-1.5 text-left text-xs hover:border-accent">
                <b>{t.name}</b> {t.skills.includes('medic') ? '· medic' : ''} · {t.hours_on_duty} h on duty
                {alt ? ` · about ${alt.eta_min} min` : ''}
              </button>
            )
          })}
          <Button small onClick={() => setChanging(false)}>Cancel</Button>
        </div>
      ) : (
        <div className="mt-2.5 flex gap-1.5">
          <Button tone="safe" small disabled={busy} onClick={() => onDecide('approve')} className="flex-1">
            <Icon name="check" size={14} strokeWidth={2.4} />Approve
          </Button>
          {approval.kind === 'dispatch' && <Button small disabled={busy} onClick={() => setChanging(true)}>Change team</Button>}
          <Button tone="danger" small disabled={busy} onClick={() => onDecide('reject')}>Reject</Button>
        </div>
      )}
    </article>
  )
}
