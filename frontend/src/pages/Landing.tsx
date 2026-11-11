import { useEffect, useState, type ReactNode } from 'react'
import { clock } from '../api'
import LandingMap, { type Overview } from '../components/LandingMap'
import { DashboardGhost, PhoneChat, SnapApprove, SnapListen, SnapLoop, SnapTriage } from '../components/LandingSnapshots'
import { Icon, Logo } from '../components/ui'

// Small uppercase labels, in the same sans as the rest of the app.
const CAPS = 'uppercase tracking-[0.14em] font-semibold'

const NAV = [
  { href: '#how', label: 'How it works' },
  { href: '#people', label: 'Who it serves' },
  { href: '#results', label: 'Results' },
  { href: '#safety', label: 'Safety' },
]

// Real numbers from docs/eval-report.md (rules mode, synthetic 311-message flood night).
const RESULTS = [
  { label: 'Median time to assign a boat to a P1 family', unit: 'min', before: 463, after: 20 },
  { label: 'Wasted trips: already rescued, rumour or duplicate', unit: '', before: 131, after: 15 },
  { label: 'Boat and van trips for the night', unit: '', before: 210, after: 56 },
  { label: 'Rumours caught before a boat went out (of 15)', unit: '', before: 0, after: 15 },
]

const STEPS = [
  { code: '01', agent: 'Listen', title: 'Every message is read', text: 'Texts and voice notes in Hindi, Marathi, English or a mix. People, water level, the elderly, medical needs and the nearest landmark come out of each one.' },
  { code: '02', agent: 'Triage', title: 'Repeats become one ticket', text: 'A daughter, a neighbour and the family itself calling about one house become a single ticket, ranked by need, with the reasons written out.' },
  { code: '03', agent: 'Officer', title: 'A person approves every boat', text: 'Dispatch proposes the nearest suitable crew and a route around blocked roads. Nothing moves until the duty officer taps Approve.' },
  { code: '04', agent: 'Loop', title: 'Families hear back', text: 'Updates go out in the language the family wrote in, with an OTP so the crew knows they reached the right door.' },
]

const SAFETY = [
  { title: 'No boat without an officer', text: 'Agents only propose. Dispatch, bulletins and uncertain merges wait for a human tap.' },
  { title: 'P1 can go up, never down', text: 'Agents may raise a family to P1. Only a signed-in officer can lower it, and that is logged.' },
  { title: 'One switch stops everything', text: 'Automation off: agents keep logging, but no message is sent and nothing new is proposed.' },
  { title: 'Lookups reveal no address', text: 'The family lookup returns status and camp only, never a phone number or a house.' },
  { title: 'Every action on record', text: 'Each tool call, approval and message is in the audit log, with who approved it.' },
  { title: 'Runs on one laptop', text: 'Works with no AI model at all, or a local one through Ollama. Messages never go to a cloud AI.' },
]

function useOverview() {
  const [data, setData] = useState<Overview | null>(null)
  useEffect(() => {
    let alive = true
    const load = () => fetch('/api/public/overview').then((r) => (r.ok ? r.json() : null)).then((d) => { if (alive && d) setData(d) }).catch(() => {})
    load()
    const id = window.setInterval(load, 15000)
    return () => { alive = false; window.clearInterval(id) }
  }, [])
  return data
}

function useWide() {
  const [wide, setWide] = useState(() => window.innerWidth >= 1024)
  useEffect(() => {
    const on = () => setWide(window.innerWidth >= 1024)
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return wide
}

function Label({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`${CAPS} text-[10.5px] text-[#677c77] ${className}`}>{children}</span>
}

function EmergencyStrip() {
  const numbers = [['112', 'Emergency'], ['108', 'Ambulance'], ['101', 'Fire'], ['1906', 'Gas leak']]
  return (
    <div className="relative z-30 flex h-[30px] items-center overflow-x-auto whitespace-nowrap border-b border-[#c8443c]/20 bg-[#f6e3de] px-4 sm:px-8">
      <div className="mx-auto flex w-full max-w-7xl items-center gap-x-5">
        <span className={`${CAPS} flex items-center gap-1.5 text-[10.5px] text-[#a8352e]`}>
          <Icon name="alert" size={13} /> In danger right now? Call first
        </span>
        {numbers.map(([n, l]) => (
          <a key={n} href={`tel:${n}`} className={`${CAPS} text-[10.5px] text-[#5b3a35] hover:text-[#a8352e]`}>
            <b className="font-serif text-[12px] tracking-normal text-[#a8352e]">{n}</b> {l}
          </a>
        ))}
      </div>
    </div>
  )
}

function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 40)
    on()
    window.addEventListener('scroll', on, { passive: true })
    return () => window.removeEventListener('scroll', on)
  }, [])
  return (
    <header className={`fixed inset-x-0 top-[30px] z-[1000] transition ${scrolled ? 'top-0 border-b border-[var(--hud-line)] bg-[#e3eae6]/90 backdrop-blur-md' : ''}`}>
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-8 px-4 sm:px-8">
        <a href="/" className="flex items-center gap-2.5" aria-label="Pukaar home">
          <Logo size={30} />
          <span className="font-serif text-[18px] font-semibold">Pukaar<span className="text-[var(--coral)]">·</span> <span className="font-normal text-[#677c77]">पुकार</span></span>
        </a>
        <nav className="hidden items-center gap-7 md:flex" aria-label="Sections">
          {NAV.map((n) => <a key={n.href} href={n.href} className={`${CAPS} text-[11px] text-[#4f6560] hover:text-[var(--ink)]`}>{n.label}</a>)}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <a href="/login" className={`${CAPS} hidden px-3 py-2 text-[11px] hover:text-[var(--coral)] sm:block`}>Sign in</a>
          <a href="/chat" className={`${CAPS} border border-[var(--ink)] bg-[var(--ink)] px-3.5 py-2 text-[11px] text-white hover:bg-transparent hover:text-[var(--ink)]`}>Get help</a>
          <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Menu" className="flex h-9 w-9 items-center justify-center md:hidden">
            <Icon name={open ? 'close' : 'list'} size={18} />
          </button>
        </div>
      </div>
      {open && (
        <nav className="hud-panel mx-4 mb-2 p-2 md:hidden" aria-label="Sections">
          {[...NAV, { href: '/login', label: 'Sign in' }].map((n) => (
            <a key={n.href} href={n.href} onClick={() => setOpen(false)} className={`${CAPS} block px-2 py-2.5 text-[11px]`}>{n.label}</a>
          ))}
        </nav>
      )}
    </header>
  )
}

function LiveHud({ data }: { data: Overview | null }) {
  const t = data?.totals
  const level = data?.incident.level
  const stats = [
    { v: t?.reports_in, l: 'Reports in' },
    { v: t?.families_safe, l: 'Families safe' },
    { v: t ? `${t.boats_out}/${t.boats}` : undefined, l: 'Boats on water' },
    { v: t?.people_in_camps, l: 'People in camps' },
  ]
  return (
    <div className="hud-panel w-full p-4 sm:w-[340px]">
      <div className="flex items-center justify-between">
        <Label className="flex items-center gap-2 !text-[var(--ink)]">
          <span className="relative flex h-2 w-2"><span className="absolute inset-0 animate-ping rounded-full bg-[var(--coral)] opacity-60" /><span className="relative h-2 w-2 rounded-full bg-[var(--coral)]" /></span>
          Tonight · live
        </Label>
        <span className="font-serif text-[15px] font-semibold tabular-nums">{data ? clock(data.clock) : '--:--'}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-px overflow-hidden border border-[var(--hud-line)] bg-[var(--hud-line)]">
        {stats.map((s) => (
          <div key={s.l} className="bg-[#f6f9f7] px-3 py-3">
            <div className="font-serif text-[28px] font-semibold leading-none tabular-nums">{s.v ?? '—'}</div>
            <Label className="mt-1.5 block !text-[9.5px]">{s.l}</Label>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Label className="!text-[9.5px]">{data?.ward.incident_name ?? 'Ward 12'}</Label>
        <span className={`${CAPS} px-1.5 py-0.5 text-[9.5px] ${level && level !== 'none' ? 'bg-[#c8443c]/12 text-[#a8352e]' : 'bg-[var(--hud-line)] text-[var(--ink)]'}`}>
          {level && level !== 'none' ? `${level} alert` : 'No alert'}
        </span>
      </div>
    </div>
  )
}

function Hero({ data }: { data: Overview | null }) {
  const wide = useWide()
  const c = data?.ward.center ?? { lat: 19.077, lng: 72.877 }
  return (
    <section className="relative min-h-[100svh] overflow-hidden lg:h-[100svh] lg:min-h-[720px]">
      <div className="absolute inset-0" aria-hidden="true">
        <LandingMap data={data} offsetLng={wide ? -0.0065 : 0} />
      </div>
      {/* Mist and legibility washes, then the HUD frame. */}
      <div className="pointer-events-none absolute inset-0 z-[500] bg-[#e3eae6] opacity-30" />
      <div className="pointer-events-none absolute inset-0 z-[500] bg-gradient-to-r from-[#e3eae6] via-[#e3eae6]/70 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[500] h-40 bg-gradient-to-b from-[#e3eae6] to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[500] h-48 bg-gradient-to-t from-[#e3eae6] to-transparent" />
      <div className="hud-scan pointer-events-none absolute inset-x-0 top-0 z-[500] h-px bg-gradient-to-r from-transparent via-[var(--coral)] to-transparent opacity-50" />
      <div className="pointer-events-none absolute inset-4 z-[500] hidden border border-[var(--hud-line)] sm:block" />

      <div className="relative z-[600] mx-auto flex min-h-[100svh] max-w-7xl flex-col justify-end gap-8 px-4 pb-10 pt-32 sm:px-8 lg:h-full lg:min-h-0 lg:flex-row lg:items-end lg:justify-between lg:pb-14">
        <div className="max-w-[600px] rise-in">
          <Label className="flex items-center gap-2 !text-[var(--hud)]">
            <span className="inline-block h-px w-8 bg-[var(--coral)]" /> {data ? `${data.ward.name} · ${data.ward.city}` : 'Ward flood response'}
          </Label>
          <h1 className="mt-5 font-serif text-[44px] font-normal leading-[1.04] tracking-tight sm:text-[64px]">
            Every call heard.<br /><span className="font-semibold text-[var(--coral)]">Every family reached.</span>
          </h1>
          <p className="mt-6 max-w-[520px] text-[16px] leading-relaxed text-[#4f6560]">
            On a flood night a ward gets hundreds of messages: the same family three times, rumours, voice notes in three
            languages. Pukaar turns them into one ranked list, proposes the right boat, and lets the duty officer decide.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="/login" className={`${CAPS} inline-flex items-center gap-2 border border-[var(--ink)] bg-[var(--ink)] px-5 py-3.5 text-[12px] text-white hover:bg-transparent hover:text-[var(--ink)]`}>
              <Icon name="compass" size={16} /> Open the control room
            </a>
            <a href="/chat" className={`${CAPS} inline-flex items-center gap-2 border border-[var(--ink)]/40 bg-[#f6f9f7]/60 px-5 py-3.5 text-[12px] hover:border-[var(--ink)]`}>
              <Icon name="chat" size={16} /> I need help
            </a>
          </div>
          <a href="/family" className="mt-5 inline-flex items-center gap-2 text-sm text-[#4f6560] hover:text-[var(--ink)]">
            <Icon name="family" size={16} /> Looking for your family? Check if they are safe →
          </a>
        </div>
        <LiveHud data={data} />
      </div>

      <div className="pointer-events-none absolute bottom-6 left-1/2 z-[600] hidden -translate-x-1/2 items-center gap-4 lg:flex">
        <Label className="!text-[9.5px]">{c.lat.toFixed(4)}° N · {c.lng.toFixed(4)}° E</Label>
        <span className="flex items-end gap-1"><span className="h-1.5 w-[88px] border-x border-b border-[#677c77]" /><Label className="!text-[9.5px]">200 m</Label></span>
        <Label className="!text-[9.5px]">Sat · Esri</Label>
      </div>
    </section>
  )
}

function Ticker({ data }: { data: Overview | null }) {
  const items = [
    '311 messages in five hours on the test night',
    'Hindi · Marathi · English · Hinglish',
    '15 rumours, 0 boats sent for them',
    data ? `${data.camps.length} relief camps on the map` : '3 boats for the whole ward',
    'Every boat approved by a person',
  ]
  return (
    <div className="border-y border-[var(--hud-line)] bg-[#edf2ef] px-4 py-4 sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-wrap gap-x-8 gap-y-2">
        {items.map((t, i) => (
          <Label key={t} className="!text-[#4f6560]">
            <span className="mr-2 font-serif text-[12px] tracking-normal text-[var(--coral)]">{String(i + 1).padStart(2, '0')}</span>{t}
          </Label>
        ))}
      </div>
    </div>
  )
}

function Section({ id, code, title, intro, children }: { id: string; code: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className="hud-grid scroll-mt-16 px-4 py-20 sm:px-8 sm:py-28">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <Label className="!text-[var(--coral)]">{code}</Label>
          <div>
            <h2 className="max-w-3xl font-serif text-[32px] font-normal leading-[1.12] tracking-tight sm:text-[44px]">{title}</h2>
            {intro && <p className="mt-4 max-w-2xl text-[15.5px] leading-relaxed text-[#4f6560]">{intro}</p>}
          </div>
        </div>
        <div className="mt-14">{children}</div>
      </div>
    </section>
  )
}

const SNAPSHOTS = [SnapListen, SnapTriage, SnapApprove, SnapLoop]

function How() {
  return (
    <Section id="how" code="01 / How it works" title="Agents do the sorting. People make the decisions."
      intro="Seven small agents each do one job. None of them can send a boat or a public message on its own.">
      <ol className="grid gap-px overflow-hidden border border-[var(--hud-line)] bg-[var(--hud-line)] md:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s, i) => {
          const Snap = SNAPSHOTS[i]
          return (
            <li key={s.code} className="group flex flex-col bg-[#f6f9f7] p-5">
              <Label className="!text-[var(--coral)]">{s.code} / {s.agent}</Label>
              <div className="mt-4 transition duration-300 group-hover:-translate-y-1 group-hover:shadow-[0_14px_30px_rgba(29,51,48,.12)]">
                <Snap />
              </div>
              <h3 className="mt-5 font-serif text-[19px] font-semibold">{s.title}</h3>
              <p className="mt-2 text-[14px] leading-relaxed text-[#4f6560]">{s.text}</p>
            </li>
          )
        })}
      </ol>
      <p className="mt-6 max-w-4xl text-[14px] leading-relaxed text-[#4f6560]">
        Each snapshot is the real app showing Kamla Devi’s three demo messages after one pass through the pipeline.
        Also on duty: <b className="text-[var(--ink)]">Saathi</b> answers questions from vetted playbooks (a gas leak reply always starts with 1906),
        <b className="text-[var(--ink)]"> Watch</b> reads weather alerts and suggests where to pre-position boats, and
        <b className="text-[var(--ink)]"> Planner</b> decides which agents handle each event and logs every step.
      </p>
    </Section>
  )
}

function Lens({ icon }: { icon: string }) {
  return (
    <span className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full border border-[var(--hud)]/50 bg-[#f6f9f7] text-[var(--hud)]">
      <span className="absolute inset-1.5 rounded-full border border-dashed border-[var(--coral)]/50" />
      <Icon name={icon} size={22} strokeWidth={1.5} />
    </span>
  )
}

function People() {
  const rows = [
    { icon: 'chat', who: 'Families', text: 'Message the helpline like any chat app, or send a voice note. No account, no form. Replies come in their own language.', href: '/chat', cta: 'Open the helpline chat' },
    { icon: 'compass', who: 'Duty officers', text: 'A live map, a ranked queue with the reasons spelled out, and approval cards for every boat, bulletin and uncertain merge.', href: '/login', cta: 'Sign in to the control room' },
    { icon: 'boat', who: 'Boat and van crews', text: 'The next task, who is waiting and what they need, the route, and one tap to report a blocked road. No reporter phone numbers.', href: '/login?next=%2Fvolunteer', cta: 'Crew sign-in' },
  ]
  return (
    <Section id="people" code="02 / Who it serves" title="One system, three very different screens.">
      <div className="grid gap-10 lg:grid-cols-[1fr_1.2fr]">
        <figure className="relative h-[660px] overflow-hidden rounded-[18px] border border-[var(--hud-line)] bg-[#edf2ef]">
          <div className="absolute left-[-140px] top-8 origin-top-left scale-[0.84] opacity-[0.32] blur-[0.4px]">
            <DashboardGhost />
          </div>
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(closest-side,rgba(237,242,239,.75),transparent)]" />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <PhoneChat />
          </div>
          <figcaption className="absolute bottom-3 left-4 right-4 flex flex-wrap items-center justify-between gap-2">
            <Label className="!text-[9.5px]">The helpline on a family’s phone</Label>
            <Label className="!text-[9.5px]">Behind it: the officer’s control room</Label>
          </figcaption>
        </figure>
        <ul className="divide-y divide-[var(--hud-line)] border-y border-[var(--hud-line)]">
          {rows.map((r) => (
            <li key={r.who} className="flex gap-5 py-6">
              <Lens icon={r.icon} />
              <div>
                <h3 className="font-serif text-[20px] font-semibold">{r.who}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-[#4f6560]">{r.text}</p>
                <a href={r.href} className={`${CAPS} mt-3 inline-block text-[11px] text-[var(--hud)] hover:text-[var(--coral)]`}>{r.cta} →</a>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  )
}

function Results() {
  return (
    <Section id="results" code="03 / Results" title="Tested on a full flood night, against first come, first served."
      intro="We replayed a 311-message night through Pukaar and through the usual approach, where three boats take requests in the order they arrive.">
      <div className="hud-panel">
        <div className={`${CAPS} hidden grid-cols-[1.3fr_1fr_110px_110px] gap-6 border-b border-[var(--hud-line)] px-6 py-3 text-[10px] text-[#677c77] md:grid`}>
          <span>Measure</span><span>Comparison</span><span className="text-right">First come</span><span className="text-right">Pukaar</span>
        </div>
        {RESULTS.map((r) => {
          const max = Math.max(r.before, r.after, 1)
          return (
            <div key={r.label} className="grid gap-3 border-b border-[var(--hud-line)] px-6 py-5 last:border-b-0 md:grid-cols-[1.3fr_1fr_110px_110px] md:items-center md:gap-6">
              <span className="text-[15px]">{r.label}</span>
              <span className="space-y-1.5" aria-hidden="true">
                <span className="block h-1.5 bg-[#b8c5c0]" style={{ width: `${Math.max((r.before / max) * 100, 1.5)}%` }} />
                <span className="block h-1.5 bg-[var(--coral)]" style={{ width: `${Math.max((r.after / max) * 100, 1.5)}%` }} />
              </span>
              <span className="flex justify-between font-serif text-[16px] tabular-nums text-[#677c77] md:block md:text-right">
                <span className="font-sans text-[13px] md:hidden">First come</span>{r.before}{r.unit && ` ${r.unit}`}
              </span>
              <span className="flex justify-between font-serif text-[24px] font-semibold tabular-nums md:block md:text-right">
                <span className="font-sans text-[13px] font-normal text-[#677c77] md:hidden">Pukaar</span>{r.after}{r.unit && <span className="text-[13px] font-normal"> {r.unit}</span>}
              </span>
            </div>
          )
        })}
      </div>
      <p className="mt-5 max-w-4xl text-[13px] leading-relaxed text-[#677c77]">
        These come from a simulated night with known answers, in rules mode, not from a live deployment. Pukaar reached 25 of the 28 most
        urgent families within the night; the first-come approach reaches all 28 only because it keeps going about 21 hours longer.
        Field accuracy on generated messages is an upper bound, since real messages are messier.
      </p>
    </Section>
  )
}

function Safety() {
  return (
    <Section id="safety" code="04 / Safety" title="Built so a tired officer at 2 AM cannot be overruled by software.">
      <div className="grid gap-px overflow-hidden border border-[var(--hud-line)] bg-[var(--hud-line)] sm:grid-cols-2 lg:grid-cols-3">
        {SAFETY.map((s, i) => (
          <div key={s.title} className="bg-[#f6f9f7] p-6">
            <span className="font-serif text-[20px] font-semibold text-[var(--coral)]">S-{String(i + 1).padStart(2, '0')}</span>
            <h3 className="mt-3 font-serif text-[17px] font-semibold">{s.title}</h3>
            <p className="mt-2 text-[14px] leading-relaxed text-[#4f6560]">{s.text}</p>
          </div>
        ))}
      </div>
    </Section>
  )
}

function FinalCta() {
  return (
    <section className="px-4 pb-24 sm:px-8">
      <div className="hud-panel mx-auto flex max-w-7xl flex-col items-start gap-8 overflow-hidden px-6 py-12 sm:px-12 md:flex-row md:items-center">
        <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.18]" aria-hidden="true">
          <defs>
            <pattern id="cta-contours" width="220" height="120" patternUnits="userSpaceOnUse">
              <path d="M0 60c50-40 110 40 220 0M0 25c50-40 110 40 220 0M0 95c50-40 110 40 220 0" stroke="#2f5d58" fill="none" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#cta-contours)" />
        </svg>
        <div className="relative flex-1">
          <Label className="!text-[var(--coral)]">For responders</Label>
          <h2 className="mt-3 font-serif text-[32px] font-normal leading-tight sm:text-[40px]">On duty tonight?</h2>
          <p className="mt-2 max-w-xl text-[15px] text-[#4f6560]">Sign in to see the ward, the queue and what is waiting for your approval.</p>
        </div>
        <div className="relative flex flex-wrap gap-3">
          <a href="/login" className={`${CAPS} border border-[var(--ink)] bg-[var(--ink)] px-5 py-3.5 text-[12px] text-white hover:bg-transparent hover:text-[var(--ink)]`}>Sign in</a>
          <a href="/chat" className={`${CAPS} border border-[var(--ink)]/40 px-5 py-3.5 text-[12px] hover:border-[var(--ink)]`}>Message the helpline</a>
        </div>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-[var(--hud-line)] px-4 py-12 sm:px-8">
      <div className="mx-auto grid max-w-7xl gap-10 sm:grid-cols-[1.6fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5"><Logo size={26} /><b className="font-serif text-[17px] font-semibold">Pukaar</b></div>
          <p className="mt-4 max-w-sm text-[14px] leading-relaxed text-[#4f6560]">
            Pukaar means “a call for help”. It helps one ward control room answer every one of them during a flood.
          </p>
        </div>
        <div>
          <Label>Get help</Label>
          <ul className="mt-4 space-y-2.5 text-[14px]">
            <li><a href="/chat" className="hover:text-[var(--coral)]">Helpline chat</a></li>
            <li><a href="/family" className="hover:text-[var(--coral)]">Is my family safe?</a></li>
            <li><a href="tel:112" className="hover:text-[var(--coral)]">Call 112</a></li>
          </ul>
        </div>
        <div>
          <Label>For responders</Label>
          <ul className="mt-4 space-y-2.5 text-[14px]">
            <li><a href="/login" className="hover:text-[var(--coral)]">Control room sign-in</a></li>
            <li><a href="/login?next=%2Fvolunteer" className="hover:text-[var(--coral)]">Crew sign-in</a></li>
            <li><a href="#safety" className="hover:text-[var(--coral)]">Safety rules</a></li>
          </ul>
        </div>
      </div>
      <div className="mx-auto mt-12 flex max-w-7xl flex-wrap justify-between gap-2">
        <Label className="!text-[9.5px]">© {new Date().getFullYear()} Pukaar</Label>
        <Label className="!text-[9.5px]">Shanti Nagar is a fictional ward; every household and name is invented · Imagery © Esri, Maxar, Earthstar Geographics</Label>
      </div>
    </footer>
  )
}

export default function Landing() {
  const data = useOverview()
  useEffect(() => {
    document.title = 'Pukaar · Flood response for ward control rooms'
    // The landing page is always drawn in the light palette, even if the app is in dark mode.
    const root = document.documentElement
    const wasDark = root.classList.contains('dark')
    root.classList.remove('dark')
    return () => { if (wasDark) root.classList.add('dark') }
  }, [])
  return (
    <div className="landing min-h-full">
      <a href="#how" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <EmergencyStrip />
      <Nav />
      <main>
        <Hero data={data} />
        <Ticker data={data} />
        <How />
        <People />
        <Results />
        <Safety />
        <FinalCta />
      </main>
      <Footer />
    </div>
  )
}
