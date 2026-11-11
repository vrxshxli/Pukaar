import { useEffect, useState, type FormEvent } from 'react'
import { api, type User } from '../api'
import { Icon, Logo } from '../components/ui'
import { ThemeToggle } from '../theme'

function destination(user: User) {
  const next = new URLSearchParams(window.location.search).get('next') ?? ''
  // Only same-site paths, so a crafted link cannot send someone elsewhere after sign-in.
  const safe = next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login') ? next : ''
  if (user.role === 'volunteer') return safe.startsWith('/volunteer') ? safe : '/volunteer'
  return safe && safe !== '/' ? safe : '/control'
}

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Already signed in: go straight on.
  useEffect(() => {
    api<{ user: User }>('/api/auth/me').then((r) => window.location.replace(destination(r.user))).catch(() => {})
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api<{ user: User }>('/api/auth/login', { username, password })
      window.location.replace(destination(r.user))
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center p-3 sm:p-6">
      <div className="grid w-full max-w-[960px] overflow-hidden rounded-[26px] border border-line bg-panel shadow-[var(--shadow)] md:grid-cols-[1.1fr_1fr]">
        <section className="relative hidden flex-col justify-between overflow-hidden p-8 text-[#eef4f1] md:flex"
          style={{ background: 'linear-gradient(160deg, #2f5d58, #1f3d39)' }}>
          <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.16]" aria-hidden="true">
            <defs>
              <pattern id="contours" width="160" height="160" patternUnits="userSpaceOnUse">
                <path d="M0 80c40-30 80 30 160 0M0 40c40-30 80 30 160 0M0 120c40-30 80 30 160 0" stroke="#cfe3dc" strokeWidth="1" fill="none" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#contours)" />
          </svg>
          <a href="/" className="relative flex items-center gap-3">
            <Logo size={42} />
            <div>
              <div className="text-xl font-extrabold">Pukaar <span className="font-normal opacity-70">पुकार</span></div>
              <div className="text-xs opacity-70">Flood control room</div>
            </div>
          </a>
          <div className="relative">
            <h1 className="text-[32px] leading-tight">Every call heard.<br />Every family reached.</h1>
            <ul className="mt-5 space-y-2.5 text-sm opacity-85">
              {[
                ['layers', 'Repeated calls merged into one ticket, ranked by need'],
                ['boat', 'Boats proposed by the agents, sent only on your approval'],
                ['chat', 'Updates to families in Hindi, Marathi and English'],
              ].map(([icon, text]) => (
                <li key={text} className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/10 text-[#f0b3a6]"><Icon name={icon} size={16} /></span>
                  {text}
                </li>
              ))}
            </ul>
          </div>
          <p className="relative text-[11px] opacity-60">Every approval is signed with your name in the audit log.</p>
        </section>

        <section className="flex flex-col p-6 sm:p-9">
          <div className="flex items-center justify-between">
            <a href="/" className="flex items-center gap-2 md:hidden"><Logo size={32} /><b className="font-serif text-lg font-semibold">Pukaar</b></a>
            <a href="/" className="hidden items-center gap-1 text-xs font-semibold text-muted hover:text-fg md:flex">← Back to home</a>
            <ThemeToggle className="ml-auto bg-soft text-muted hover:text-fg" />
          </div>
          <h2 className="mt-6 text-[26px]">Sign in</h2>
          <p className="mt-1 text-sm text-muted">For duty officers and boat or van teams.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-muted">Username</span>
              <span className="flex items-center gap-2 rounded-xl border border-line bg-card px-3 focus-within:border-accent">
                <Icon name="people" size={16} className="text-muted" />
                <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required
                  autoCapitalize="none" spellCheck={false} placeholder="e.g. rao or boat1"
                  className="w-full bg-transparent py-2.5 text-sm outline-none placeholder:text-muted/70" />
              </span>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-muted">Password</span>
              <span className="flex items-center gap-2 rounded-xl border border-line bg-card px-3 focus-within:border-accent">
                <Icon name="shield" size={16} className="text-muted" />
                <input value={password} onChange={(e) => setPassword(e.target.value)} type={show ? 'text' : 'password'}
                  autoComplete="current-password" required
                  className="w-full bg-transparent py-2.5 text-sm outline-none" />
                <button type="button" onClick={() => setShow((s) => !s)} className="text-xs font-semibold text-muted hover:text-fg">
                  {show ? 'Hide' : 'Show'}
                </button>
              </span>
            </label>
            {error && <div role="alert" className="rounded-xl border border-urgent/40 bg-urgent/10 px-3 py-2 text-sm text-urgent">{error}</div>}
            <button type="submit" disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-2.5 text-sm font-bold text-accent-fg transition hover:brightness-110 disabled:opacity-60">
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="mt-auto pt-8">
            <p className="mb-2 text-xs font-semibold text-muted">Not on duty? No account needed:</p>
            <div className="grid grid-cols-2 gap-2">
              <a href="/chat" className="flex items-center gap-2 rounded-xl border border-line bg-card px-3 py-2.5 text-xs font-semibold hover:border-accent">
                <Icon name="chat" size={16} className="text-accent" />Ask for help
              </a>
              <a href="/family" className="flex items-center gap-2 rounded-xl border border-line bg-card px-3 py-2.5 text-xs font-semibold hover:border-accent">
                <Icon name="family" size={16} className="text-accent" />Is my family safe?
              </a>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
