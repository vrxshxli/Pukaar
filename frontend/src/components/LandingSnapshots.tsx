import { useEffect, useRef, type ReactNode } from 'react'
import type { Approval } from '../api'
import ApprovalCard from './ApprovalCard'
import { AgentTag, Chip, COLORS, Icon, Logo } from './ui'

/*
  Snapshots for the landing page, drawn with the app's own components and the
  output of a real pipeline run: Kamla Devi's three demo messages, processed by
  the orchestrator in rules mode. Only clock times are illustrative.
*/

const MESSAGES = [
  { who: 'Voice note · Hindi', text: 'पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे' },
  { who: 'Daughter · English', text: 'Please help my mother Kamla Devi, Lane 4 behind Hanuman temple, Shanti Nagar. Water rising!!' },
  { who: 'Neighbour · Hinglish', text: 'shantinagar gali 4 mandir ke peeche budhi amma aur bachcha phase hai' },
]
const TICKET = {
  id: 'P-0401', title: 'Kamla Devi household', area: 'Lane 4, Shanti Nagar', people: 2,
  reasons: ['Water at knee height', 'Water rising', 'Elder, 68', 'Child', 'Child with fever', '3 separate reporters'],
}
const APPROVAL: Approval = {
  id: 0, kind: 'dispatch', ticket_id: 'P-0401', team_id: 'boat1', title: 'Send Boat 1 to Kamla Devi household?',
  reasons: ['Medic on board', '0.8 km, about 11 min', '3 h on duty'],
  payload: { route: { coords: [], summary: '0.8 km via Station Road, Lane 4', eta_min: 11, length_m: 800 } },
  created_by: 'Dispatch', created_at: '',
}
const REPLIES = [
  { t: '9:40 PM', text: 'आपका संदेश मिल गया है। टिकट P-0401 खुला है। घर में कितने लोग हैं?' },
  { t: '9:44 PM', text: 'इस परिवार के बारे में 3 संदेश अब टिकट P-0401 से जुड़ गए हैं। सबको एक जैसी जानकारी मिलेगी।' },
  { t: '9:47 PM', text: 'Boat 1 आपकी ओर आ रही है, लगभग 11 मिनट। फ़ोन चालू रखें, ऊँची जगह पर रहें।' },
  { t: '9:47 PM', text: 'टीम पहुँचने पर यह OTP बताएँ: 9055' },
]
const noop = () => {}

// A picture of the app, not a working copy: nothing inside can be clicked or focused.
function Still({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { ref.current?.setAttribute('inert', '') }, [])
  return <div ref={ref} aria-hidden="true" className={`pointer-events-none select-none ${className}`}>{children}</div>
}

function Frame({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-line bg-surface">
      <div className="flex items-center gap-1.5 border-b border-line bg-panel px-2.5 py-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-[#d4705f]" />
        <span className="h-1.5 w-1.5 rounded-full bg-[#c68a2e]" />
        <span className="h-1.5 w-1.5 rounded-full bg-[#4f8a4c]" />
        <span className="ml-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{caption}</span>
      </div>
      <Still className="h-[236px] overflow-hidden p-3">{children}</Still>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-surface to-transparent" />
    </div>
  )
}

function InBubble({ children, voice }: { children: ReactNode; voice?: boolean }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[92%] rounded-xl rounded-tr-sm bg-[#d5e6e0] px-2.5 py-1.5 text-[12px] text-ink shadow-sm">
        {voice && <span className="mb-0.5 block text-[9.5px] font-bold text-safe">🎤 Voice note (transcribed)</span>}
        {children}
      </div>
    </div>
  )
}

function OutBubble({ children, time }: { children: ReactNode; time?: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-xl rounded-tl-sm bg-card px-2.5 py-1.5 text-[12px] shadow-sm">
        {children}
        {time && <span className="mt-0.5 block text-right text-[9.5px] text-muted">{time}</span>}
      </div>
    </div>
  )
}

function QueueRow() {
  return (
    <div className="flex gap-2.5 rounded-xl bg-accent-soft p-2 ring-1 ring-accent/50">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full" style={{ background: `${COLORS.urgent}26`, color: COLORS.urgent }}>
        <Icon name="heart" size={16} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[12.5px] font-semibold leading-tight">{TICKET.title}</span>
        <span className="mt-0.5 block truncate text-[10.5px] text-muted">
          <b style={{ color: COLORS.urgent }}>P1</b> · {TICKET.area} · {TICKET.people} people · Team proposed
        </span>
        <span className="mt-1 flex flex-wrap gap-1">
          <Chip tone="teal">3 reports merged</Chip>
          {TICKET.reasons.slice(0, 3).map((r) => <Chip key={r}>{r}</Chip>)}
        </span>
      </span>
      <span className="shrink-0 text-[10px] font-semibold text-muted">{TICKET.id}</span>
    </div>
  )
}

export function SnapListen() {
  const fields: [string, string][] = [['Language', 'Hindi'], ['Water', 'knee height'], ['Vulnerable', 'child, elderly'], ['Medical', 'fever'], ['Landmark', 'Hanuman temple'], ['Lane', 'Lane 4']]
  return (
    <Frame caption="Citizen chat → Listen">
      <InBubble voice>{MESSAGES[0].text}</InBubble>
      <div className="my-2 flex items-center gap-1.5 text-[10px] font-semibold text-muted">
        <span className="h-px flex-1 bg-line" /><AgentTag agent="Listen" /> read<span className="h-px flex-1 bg-line" />
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {fields.map(([k, v]) => (
          <div key={k} className="rounded-lg border border-line bg-card px-2 py-1">
            <div className="text-[9.5px] text-muted">{k}</div>
            <div className="text-[11.5px] font-semibold">{v}</div>
          </div>
        ))}
      </div>
    </Frame>
  )
}

export function SnapTriage() {
  return (
    <Frame caption="Ticket queue">
      <div className="space-y-1">
        {MESSAGES.map((m) => (
          <div key={m.who} className="flex items-center gap-2 rounded-md bg-card px-2 py-1 text-[10.5px]">
            <span className="shrink-0 font-semibold text-muted">{m.who}</span>
            <span className="truncate">{m.text}</span>
          </div>
        ))}
      </div>
      <div className="my-1.5 flex justify-center text-muted"><Icon name="layers" size={15} /></div>
      <QueueRow />
    </Frame>
  )
}

export function SnapApprove() {
  return (
    <Frame caption="Waiting for your approval">
      <div className="origin-top-left scale-[0.92]" style={{ width: '108.7%' }}>
        <ApprovalCard approval={APPROVAL} teams={[]} busy={false} onDecide={noop} onPreview={noop} />
      </div>
    </Frame>
  )
}

export function SnapLoop() {
  return (
    <Frame caption="Family chat + crew desk">
      <div className="space-y-1.5">
        <OutBubble time={REPLIES[2].t}>{REPLIES[2].text}</OutBubble>
        <OutBubble time={REPLIES[3].t}>{REPLIES[3].text}</OutBubble>
      </div>
      <div className="mt-2 rounded-lg border border-line bg-card p-2">
        <div className="flex items-center gap-1.5 text-[10.5px] font-bold"><Icon name="boat" size={13} /> Boat 1 · at the family</div>
        <div className="mt-1.5 flex gap-1.5">
          <span className="flex-1 rounded-lg border border-line bg-surface px-2 py-1 font-serif text-[13px] tracking-[0.3em]">9055</span>
          <span className="rounded-lg bg-safe px-2.5 py-1 text-[11px] font-bold text-white">Confirm safe</span>
        </div>
      </div>
    </Frame>
  )
}

/* The chat section: a phone with the citizen chat, over a faded control room. */

function StatusBar() {
  return (
    <div className="flex items-center justify-between px-6 pb-1 pt-3 text-[11px] font-semibold text-white">
      <span>9:47</span>
      <span className="absolute left-1/2 top-2.5 h-[22px] w-[88px] -translate-x-1/2 rounded-full bg-black" />
      <span className="flex items-center gap-1">
        <svg width="16" height="10" viewBox="0 0 16 10" fill="currentColor"><rect x="0" y="7" width="3" height="3" rx=".5" /><rect x="4.3" y="5" width="3" height="5" rx=".5" /><rect x="8.6" y="2.5" width="3" height="7.5" rx=".5" /><rect x="12.9" y="0" width="3" height="10" rx=".5" /></svg>
        <svg width="22" height="11" viewBox="0 0 22 11" fill="none" stroke="currentColor"><rect x=".5" y=".5" width="18" height="10" rx="2.5" /><rect x="2" y="2" width="11" height="7" rx="1" fill="currentColor" /><path d="M20.5 4v3" strokeLinecap="round" /></svg>
      </span>
    </div>
  )
}

export function PhoneChat() {
  return (
    <Still className="relative w-[292px] rounded-[46px] bg-[#16302c] p-[9px] shadow-[0_30px_60px_rgba(29,51,48,.35),0_0_0_1px_rgba(255,255,255,.08)_inset]">
      <div className="relative flex h-[590px] flex-col overflow-hidden rounded-[38px] bg-soft">
        <div className="relative bg-ink">
          <StatusBar />
          <div className="flex items-center gap-2 px-3 pb-2.5 pt-1 text-white">
            <Logo size={30} />
            <div className="min-w-0 flex-1 leading-tight">
              <b className="block font-serif text-[13px] font-semibold">Pukaar Ward 12 Helpline</b>
              <span className="block truncate text-[10.5px] opacity-75">Ticket P-0401 · Lane 4</span>
            </div>
          </div>
        </div>
        <div className="flex-1 space-y-2 overflow-hidden px-3 py-3">
          <InBubble voice>{MESSAGES[0].text}<span className="mt-0.5 block text-right text-[9.5px] text-muted">9:40 PM</span></InBubble>
          {REPLIES.map((r, i) => <OutBubble key={i} time={r.t}>{r.text}</OutBubble>)}
        </div>
        <div className="flex items-center gap-2 border-t border-line bg-card p-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm text-white">🎤</span>
          <span className="flex-1 rounded-2xl border border-line bg-surface px-3 py-2 text-[12px] text-muted">Message</span>
          <span className="rounded-full bg-safe px-3 py-2 text-[12px] font-bold text-white">Send</span>
        </div>
        <div className="mx-auto mb-1.5 mt-1 h-1 w-24 rounded-full bg-ink/40" />
      </div>
    </Still>
  )
}

// The officer's dashboard in miniature, for the background behind the phone.
export function DashboardGhost() {
  const pins = [
    { x: 150, y: 120, c: COLORS.urgent }, { x: 300, y: 90, c: COLORS.urgent }, { x: 240, y: 200, c: COLORS.marigold },
    { x: 360, y: 230, c: COLORS.teal }, { x: 110, y: 250, c: COLORS.safe }, { x: 410, y: 130, c: COLORS.grey },
  ]
  return (
    <Still className="flex h-[600px] w-[1000px] overflow-hidden rounded-[18px] border border-line bg-panel">
      <div className="flex w-[60px] flex-col items-center gap-3 border-r border-line py-4">
        <Logo size={28} />
        {['compass', 'chat', 'boat', 'family'].map((i, n) => (
          <span key={i} className={`flex h-9 w-9 items-center justify-center rounded-lg ${n === 0 ? 'bg-accent-soft text-accent' : 'text-muted'}`}><Icon name={i} size={17} /></span>
        ))}
      </div>
      <div className="w-[270px] space-y-3 border-r border-line p-4">
        <div className="font-serif text-[20px] font-semibold">Control room</div>
        <div className="grid grid-cols-3 gap-1.5">
          {[[2, 'open P1', COLORS.urgent], [5, 'waiting', COLORS.marigold], [1, 'safe', COLORS.safe]].map(([v, l, c]) => (
            <div key={l as string} className="rounded-lg border border-line bg-card p-2" style={{ borderTop: `3px solid ${c}` }}>
              <div className="font-serif text-[20px] font-semibold leading-none">{v}</div>
              <div className="mt-1 text-[10px] text-muted">{l}</div>
            </div>
          ))}
        </div>
        <QueueRow />
        <div className="flex gap-2.5 rounded-xl p-2">
          <span className="h-9 w-9 rounded-full" style={{ background: `${COLORS.marigold}26` }} />
          <span className="flex-1 space-y-1.5 pt-1"><span className="block h-2.5 w-3/4 rounded bg-line" /><span className="block h-2 w-1/2 rounded bg-line" /></span>
        </div>
        <div className="flex gap-2.5 rounded-xl p-2">
          <span className="h-9 w-9 rounded-full" style={{ background: `${COLORS.grey}26` }} />
          <span className="flex-1 space-y-1.5 pt-1"><span className="block h-2.5 w-2/3 rounded bg-line" /><span className="block h-2 w-1/3 rounded bg-line" /></span>
        </div>
      </div>
      <div className="relative flex-1 bg-[#dfe8e3]">
        <svg viewBox="0 0 520 600" className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid slice">
          <path d="M-10 470 C 100 430, 180 500, 300 450 S 470 400, 540 420 L 540 620 L -10 620 Z" fill="#e4a596" opacity="0.45" />
          {[70, 150, 230, 310, 390, 470].map((x) => <line key={x} x1={x} y1="0" x2={x - 40} y2="600" stroke="#fff" strokeWidth="7" />)}
          {[90, 190, 300, 380].map((y) => <line key={y} x1="0" y1={y} x2="520" y2={y + 16} stroke="#fff" strokeWidth="7" />)}
          <path d="M60 330 L 150 300 L 152 122" stroke={COLORS.accent} strokeWidth="3.5" fill="none" strokeDasharray="8 7" />
          {pins.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="8" fill={p.c} stroke="#fff" strokeWidth="2.5" />)}
        </svg>
        <div className="absolute right-3 top-3 w-[300px] space-y-2 rounded-xl border border-line bg-card p-3 shadow-[var(--shadow)]">
          <div className="font-serif text-[14px] font-semibold">Waiting for your approval</div>
          <ApprovalCard approval={APPROVAL} teams={[]} busy={false} onDecide={noop} onPreview={noop} />
          {[['Listen', 'Read a voice note in Hindi'], ['Triage', 'Merged 3 reports into P-0401'], ['Dispatch', 'Proposed Boat 1 (medic)']].map(([a, s]) => (
            <div key={s} className="flex items-center gap-2 text-[11px]"><AgentTag agent={a} /><span className="truncate">{s}</span></div>
          ))}
        </div>
      </div>
    </Still>
  )
}
