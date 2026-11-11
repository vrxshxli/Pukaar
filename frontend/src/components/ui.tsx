import type { ReactNode } from 'react'
import type { Ticket } from '../api'

export const COLORS = {
  teal: '#0F7173',
  marigold: '#E0A21C',
  urgent: '#B3284F',
  safe: '#5A8A23',
  ink: '#0E2A2B',
  grey: '#7A8B8C',
}

// Map pin and badge colour: red P1, gold P2, teal P3, grey verify, green safe.
export function ticketColor(t: Pick<Ticket, 'priority' | 'status' | 'kind'>) {
  if (t.status === 'safe' || t.status === 'closed') return COLORS.safe
  if (t.status === 'verify' || t.kind === 'verify') return COLORS.grey
  if (t.kind === 'info') return '#4F7CAC'
  if (t.priority === 'P1') return COLORS.urgent
  if (t.priority === 'P2') return COLORS.marigold
  return COLORS.teal
}

export function ticketLabel(t: Pick<Ticket, 'priority' | 'status' | 'kind'>) {
  if (t.status === 'safe' || t.status === 'closed') return 'Safe'
  if (t.status === 'verify') return 'Verify'
  if (t.kind === 'info') return 'Info'
  return t.priority
}

export function PriorityBadge({ ticket }: { ticket: Pick<Ticket, 'priority' | 'status' | 'kind'> }) {
  const color = ticketColor(ticket)
  return (
    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-extrabold text-white"
      style={{ background: color }}>
      {ticketLabel(ticket)}
    </span>
  )
}

export function Chip({ children, tone = 'urgent' }: { children: ReactNode; tone?: 'urgent' | 'teal' | 'muted' | 'safe' | 'marigold' }) {
  const styles: Record<string, string> = {
    urgent: 'bg-urgent/10 text-urgent dark:bg-urgent/25 dark:text-[#ff9db7]',
    teal: 'bg-teal/10 text-teal dark:bg-teal/30 dark:text-[#8fe0e1]',
    muted: 'bg-soft text-muted',
    safe: 'bg-safe/10 text-safe dark:bg-safe/30 dark:text-[#b9e48a]',
    marigold: 'bg-marigold/15 text-[#8a5f00] dark:bg-marigold/25 dark:text-marigold',
  }
  return <span className={`inline-block rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${styles[tone]}`}>{children}</span>
}

export function Button({ children, onClick, tone = 'plain', disabled, small, title, type = 'button' }: {
  children: ReactNode
  onClick?: () => void
  tone?: 'plain' | 'primary' | 'safe' | 'danger'
  disabled?: boolean
  small?: boolean
  title?: string
  type?: 'button' | 'submit'
}) {
  const tones: Record<string, string> = {
    plain: 'bg-card text-fg border border-line hover:bg-soft',
    primary: 'bg-teal text-white hover:bg-[#0c5d5f] border border-teal',
    safe: 'bg-safe text-white hover:bg-[#4a731c] border border-safe',
    danger: 'bg-card text-urgent border border-urgent/40 hover:bg-urgent/10',
  }
  return (
    <button type={type} title={title} disabled={disabled} onClick={onClick}
      className={`${tones[tone]} ${small ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm'} rounded-lg font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-marigold`}>
      {children}
    </button>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-line p-4 text-center text-sm text-muted">{children}</div>
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-teal border-t-transparent" />
      {label}
    </div>
  )
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div role="alert" className="rounded-lg border border-urgent/40 bg-urgent/10 px-3 py-2 text-sm text-urgent">{children}</div>
}

export const AGENT_COLORS: Record<string, string> = {
  Planner: '#5B6C8F',
  Listen: '#4F7CAC',
  Triage: COLORS.urgent,
  Dispatch: '#D9530B',
  Loop: COLORS.safe,
  Saathi: '#8A4FB3',
  Watch: COLORS.teal,
  Officer: COLORS.ink,
}

export function AgentTag({ agent }: { agent: string }) {
  return (
    <span className="inline-block min-w-[62px] rounded px-1.5 py-0.5 text-center text-[11px] font-bold text-white"
      style={{ background: AGENT_COLORS[agent] ?? COLORS.grey }}>
      {agent}
    </span>
  )
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="19" fill={COLORS.teal} />
      <path d="M13 15a9 9 0 0 1 14 0" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" />
      <path d="M16.5 18.5a4.5 4.5 0 0 1 7 0" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" />
      <circle cx="20" cy="22" r="1.9" fill={COLORS.marigold} />
      <path d="M8 28c3-2.4 5-2.4 8 0s5 2.4 8 0 5-2.4 8 0" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinecap="round" />
    </svg>
  )
}
