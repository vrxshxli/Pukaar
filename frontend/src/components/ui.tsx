import type { ReactNode } from 'react'
import type { Ticket } from '../api'

export const COLORS = {
  teal: '#5B7FA6',
  marigold: '#C68A2E',
  urgent: '#C8443C',
  safe: '#4F8A4C',
  ink: '#1F3D39',
  grey: '#8C9A95',
  accent: '#2F5D58',
}

// Map pin and badge colour: red P1, gold P2, teal P3, grey verify, green safe.
export function ticketColor(t: Pick<Ticket, 'priority' | 'status' | 'kind'>) {
  if (t.status === 'safe' || t.status === 'closed') return COLORS.safe
  if (t.status === 'verify' || t.kind === 'verify') return COLORS.grey
  if (t.kind === 'info') return '#8A96A8'
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

export function Chip({ children, tone = 'urgent' }: { children: ReactNode; tone?: 'urgent' | 'teal' | 'muted' | 'safe' | 'marigold' | 'accent' }) {
  const styles: Record<string, string> = {
    urgent: 'bg-urgent/10 text-[#a8352e] dark:bg-urgent/20 dark:text-[#f0a39b]',
    teal: 'bg-[#5B7FA6]/12 text-[#3f6283] dark:bg-[#5B7FA6]/22 dark:text-[#a9c3e0]',
    muted: 'bg-soft text-muted',
    safe: 'bg-safe/12 text-[#3c6e3a] dark:bg-safe/20 dark:text-[#a8d4a2]',
    marigold: 'bg-marigold/14 text-[#8a5f12] dark:bg-marigold/22 dark:text-[#e8c07a]',
    accent: 'bg-accent-soft text-accent',
  }
  return <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${styles[tone]}`}>{children}</span>
}

export function Button({ children, onClick, tone = 'plain', disabled, small, title, type = 'button', className = '' }: {
  children: ReactNode
  onClick?: () => void
  tone?: 'plain' | 'primary' | 'safe' | 'danger'
  disabled?: boolean
  small?: boolean
  title?: string
  type?: 'button' | 'submit'
  className?: string
}) {
  const tones: Record<string, string> = {
    plain: 'bg-card text-fg border border-line hover:bg-soft',
    primary: 'bg-accent text-accent-fg border border-accent hover:opacity-90',
    safe: 'bg-safe text-white border border-safe hover:opacity-90',
    danger: 'bg-transparent text-urgent border border-urgent/50 hover:bg-urgent/10',
  }
  return (
    <button type={type} title={title} disabled={disabled} onClick={onClick}
      className={`${tones[tone]} ${small ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-2 text-sm'} inline-flex items-center justify-center gap-1.5 rounded-xl font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-accent ${className}`}>
      {children}
    </button>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-line p-4 text-center text-sm text-muted">{children}</div>
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      {label}
    </div>
  )
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div role="alert" className="rounded-xl border border-urgent/40 bg-urgent/10 px-3 py-2 text-sm text-urgent">{children}</div>
}

export const AGENT_COLORS: Record<string, string> = {
  Planner: '#7A8AA6',
  Listen: '#5B7FA6',
  Triage: COLORS.urgent,
  Dispatch: '#C4703F',
  Loop: '#4F8A4C',
  Saathi: '#8A6BA8',
  Watch: '#2F5D58',
  Officer: '#A8805C',
}

export function AgentTag({ agent }: { agent: string }) {
  return (
    <span className="inline-flex min-w-[66px] items-center gap-1.5 text-[11.5px] font-semibold text-fg">
      <i className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: AGENT_COLORS[agent] ?? COLORS.grey }} />
      {agent}
    </span>
  )
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="12" fill={COLORS.accent} />
      <path d="M13 15a9 9 0 0 1 14 0" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" />
      <path d="M16.5 18.5a4.5 4.5 0 0 1 7 0" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" />
      <circle cx="20" cy="22" r="1.9" fill="#fff" />
      <path d="M8 28c3-2.4 5-2.4 8 0s5 2.4 8 0 5-2.4 8 0" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinecap="round" />
    </svg>
  )
}

// Line icons drawn on a 24px grid, stroked in the current text colour.
const ICONS: Record<string, ReactNode> = {
  compass: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2 5-5 2 2-5z" /></>,
  chat: <path d="M4 5h16v11H9l-5 4z" />,
  boat: <><path d="M3 15h18l-2.5 4h-13z" /><path d="M12 4v11M12 5l5 7h-5" /></>,
  family: <><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9.5" r="2.2" /><path d="M3.5 19c.6-3.3 2.8-5 5.5-5s4.9 1.7 5.5 5M14.5 14.4c2.6-.3 4.7 1.2 5.3 4.1" /></>,
  bell: <><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" /><path d="M10 20.5a2 2 0 0 0 4 0" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />,
  pin: <><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z" /><circle cx="12" cy="10" r="2.3" /></>,
  rain: <><path d="M7 15a4 4 0 0 1 .5-8 5.5 5.5 0 0 1 10.4 1.6A3.5 3.5 0 0 1 17.5 15z" /><path d="M8 18l-1 2.5M12 18l-1 2.5M16 18l-1 2.5" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  target: <><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 13 9 5 9-5" /></>,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  people: <><circle cx="12" cy="8" r="3.5" /><path d="M5 20c.8-4 3.6-6 7-6s6.2 2 7 6" /></>,
  water: <path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z" />,
  alert: <><path d="M12 3 2.5 20h19z" /><path d="M12 10v4M12 17.2v.3" /></>,
  heart: <path d="M12 20s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.4-7.5 10-7.5 10z" />,
  list: <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  shield: <path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.2 7.5 9.5 4.3-1.3 7.5-4.9 7.5-9.5V6z" />,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  play: <path d="M8 5.5v13l10.5-6.5z" />,
  pause: <path d="M8 5v14M16 5v14" />,
  reset: <><path d="M4 12a8 8 0 1 0 2.4-5.7" /><path d="M4 4v4.5h4.5" /></>,
  qr: <><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z" /><path d="M14 14h2v2h-2zM18 18h2v2h-2zM14 18h2M18 14h2" /></>,
  logout: <><path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" /><path d="M10 16l-4-4 4-4M6 12h10" /></>,
  route: <><circle cx="6" cy="18" r="2" /><circle cx="18" cy="6" r="2" /><path d="M8 18h6.5a3.5 3.5 0 0 0 0-7h-5a3.5 3.5 0 0 1 0-7H16" /></>,
}

export function Icon({ name, size = 18, className = '', strokeWidth = 1.8 }: { name: keyof typeof ICONS | string; size?: number; className?: string; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      {ICONS[name]}
    </svg>
  )
}
