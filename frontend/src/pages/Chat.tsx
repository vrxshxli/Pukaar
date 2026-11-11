import { useEffect, useRef, useState } from 'react'
import { api, clock, useStream } from '../api'
import { ErrorNote, Logo } from '../components/ui'
import { ThemeToggle } from '../theme'

interface Message {
  id: number
  direction: 'in' | 'out'
  text: string
  kind: string
  created_at: string
  channel: string
}

interface Identity {
  name: string
  area: string
  phone: string
}

const PRESETS: Identity[] = [
  { name: 'Kamla Devi', area: 'Lane 4, Shanti Nagar', phone: '+91 90000 00412' },
  { name: 'Priya (Kamla\'s daughter, Pune)', area: 'Pune', phone: '+91 90000 05101' },
  { name: 'Neighbour on Lane 4', area: 'Lane 4, Shanti Nagar', phone: '+91 90000 05102' },
  { name: 'Thomas Joseph', area: 'Lane 9, Shanti Nagar', phone: '+91 90000 00909' },
  { name: 'Rukhsar Shaikh', area: 'Gali 7, Shanti Nagar', phone: '+91 90000 00707' },
]

const SAMPLES = [
  'पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे',
  'गली 7 मस्जिद के पास गैस की बदबू आ रही है और पानी अंदर है, क्या करें?',
  'We are 5 people on the roof at Lane 9, small child with us',
  'Where is the nearest relief camp?',
  'माझे वडील मोहन सेक्टर 3 मध्ये एकटे राहतात, फोन उचलत नाही',
]

const VOICE_LANGS = [
  { code: 'hi-IN', label: 'हिंदी' },
  { code: 'mr-IN', label: 'मराठी' },
  { code: 'en-IN', label: 'English' },
]

function newIdentity(): Identity {
  const n = Math.floor(6000 + Math.random() * 3999)
  return { name: 'Demo visitor', area: 'Shanti Nagar', phone: `+91 90000 0${n}` }
}

function loadIdentity(): Identity | null {
  try {
    const raw = localStorage.getItem('pukaar-identity')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveIdentity(id: Identity) {
  try { localStorage.setItem('pukaar-identity', JSON.stringify(id)) } catch { /* private mode */ }
}

// The browser's speech recognition, when it exists (Chrome, Edge, Safari).
type Recognition = {
  lang: string
  interimResults: boolean
  onresult: (e: { results: { 0: { transcript: string } }[] }) => void
  onerror: (e: { error: string }) => void
  onend: () => void
  start: () => void
  stop: () => void
}
function makeRecognizer(): Recognition | null {
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition }
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition
  return Ctor ? new Ctor() : null
}

function Picker({ onPick }: { onPick: (id: Identity) => void }) {
  return (
    <div className="mx-auto flex h-full max-w-md flex-col bg-surface">
      <div className="bg-ink px-4 py-4 text-white">
        <div className="flex items-center gap-2"><Logo /><b className="font-serif text-lg font-semibold">Pukaar Ward 12 Helpline</b></div>
        <p className="mt-1 text-xs opacity-80">Demo: messages go to the Pukaar control-room simulation. Use made-up details only.</p>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-4">
        <p className="text-sm font-semibold">Who are you in this demo?</p>
        {PRESETS.map((p) => (
          <button key={p.phone} onClick={() => onPick(p)}
            className="block w-full rounded-xl border border-line bg-card p-3 text-left hover:border-accent">
            <b>{p.name}</b>
            <div className="text-xs text-muted">{p.area} · {p.phone}</div>
          </button>
        ))}
        <button onClick={() => onPick(newIdentity())}
          className="block w-full rounded-xl border-2 border-dashed border-accent p-3 text-left font-semibold text-accent">
          I'm a new person (random demo number)
        </button>
      </div>
    </div>
  )
}

export default function Chat() {
  const [identity, setIdentity] = useState<Identity | null>(loadIdentity)
  const [messages, setMessages] = useState<Message[]>([])
  const [text, setText] = useState('')
  const [channel, setChannel] = useState<'chat' | 'voice'>('chat')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [listening, setListening] = useState(false)
  const [voiceLang, setVoiceLang] = useState('hi-IN')
  const recognizer = useRef<Recognition | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const voiceSupported = typeof window !== 'undefined' && makeRecognizer() !== null

  useEffect(() => {
    if (!identity) return
    api<Message[]>(`/api/chat/${encodeURIComponent(identity.phone)}`).then(setMessages)
      .catch((e) => setError(e.message))
  }, [identity])

  useStream(identity ? `?phone=${encodeURIComponent(identity.phone)}` : '?phone=none', (e) => {
    if (e.kind !== 'message') return
    const m = e.data as unknown as Message
    setMessages((list) => (list.some((x) => x.id === m.id) ? list : [...list, m]))
  })

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  if (!identity) {
    return <Picker onPick={(id) => { saveIdentity(id); setIdentity(id) }} />
  }

  async function send(body = text, ch = channel) {
    if (!body.trim() || !identity) return
    setSending(true)
    setError(null)
    try {
      await api('/api/messages', { phone: identity.phone, text: body.trim(), channel: ch, name: identity.name, area: identity.area })
      setText('')
      setChannel('chat')
      const fresh = await api<Message[]>(`/api/chat/${encodeURIComponent(identity.phone)}`)
      setMessages(fresh)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSending(false)
    }
  }

  function toggleVoice() {
    if (listening) {
      recognizer.current?.stop()
      return
    }
    const r = makeRecognizer()
    if (!r) {
      setError('Voice notes need Chrome, Edge or Safari. You can still type.')
      return
    }
    r.lang = voiceLang
    r.interimResults = false
    r.onresult = (e) => {
      setText(e.results[0][0].transcript)
      setChannel('voice')
    }
    r.onerror = (e) => setError(e.error === 'not-allowed' ? 'Microphone permission was denied.' : `Voice error: ${e.error}`)
    r.onend = () => setListening(false)
    recognizer.current = r
    setListening(true)
    r.start()
  }

  return (
    <div className="mx-auto flex h-full max-w-md flex-col bg-soft">
      <div className="flex items-center gap-2 bg-ink px-3 py-2 text-white">
        <Logo size={32} />
        <div className="min-w-0 flex-1 leading-tight">
          <b className="block font-serif text-sm font-semibold">Pukaar Ward 12 Helpline</b>
          <span className="block truncate text-[11px] opacity-75">You are {identity.name} · {identity.phone}</span>
        </div>
        <button onClick={() => { try { localStorage.removeItem('pukaar-identity') } catch { /* ignore */ } setIdentity(null); setMessages([]) }}
          className="rounded bg-white/15 px-2 py-1 text-[11px]">Switch</button>
        <ThemeToggle className="bg-white/10 text-white" />
      </div>
      <div className="bg-marigold/20 px-3 py-1 text-center text-[11px] font-semibold text-[#7a5410] dark:text-marigold">
        Demo: messages go to the Pukaar control-room simulation
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="rounded-lg bg-card p-3 text-center text-xs text-muted">
              Tell us what is happening and where you are. You can type, or hold the mic to speak in Hindi, Marathi or English.
            </p>
            <p className="text-center text-[11px] font-semibold text-muted">Or try a sample message:</p>
            {SAMPLES.map((s) => (
              <button key={s} onClick={() => setText(s)}
                className="block w-full rounded-lg border border-line bg-card px-3 py-2 text-left text-xs hover:border-accent">{s}</button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.direction === 'in' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] whitespace-pre-line rounded-xl px-3 py-2 text-sm shadow-sm ${m.direction === 'in'
              ? 'rounded-tr-sm bg-[#d5e6e0] text-ink dark:bg-[#24423d] dark:text-white'
              : m.kind === 'saathi' ? 'rounded-tl-sm border-l-4 border-urgent bg-card' : 'rounded-tl-sm bg-card'}`}>
              {m.direction === 'in' && m.channel === 'voice' && <span className="mb-0.5 block text-[10px] font-bold text-safe">🎤 Voice note (transcribed)</span>}
              {m.kind === 'saathi' && <span className="mb-0.5 block text-[10px] font-bold text-urgent">Saathi · safety steps</span>}
              {m.kind === 'bulletin' && <span className="mb-0.5 block text-[10px] font-bold text-accent">Ward bulletin</span>}
              {m.text}
              <span className="mt-0.5 block text-right text-[10px] text-muted">{clock(m.created_at)}</span>
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      {error && <div className="px-3 pb-1"><ErrorNote>{error}</ErrorNote></div>}
      <form className="flex items-end gap-2 border-t border-line bg-card p-2" onSubmit={(e) => { e.preventDefault(); send() }}>
        <div className="flex flex-col items-center gap-1">
          <button type="button" onClick={toggleVoice} disabled={!voiceSupported}
            title={voiceSupported ? 'Speak a voice note' : 'Voice notes need Chrome, Edge or Safari'}
            aria-label={listening ? 'Stop listening' : 'Record a voice note'}
            className={`h-11 w-11 rounded-full text-lg text-white ${listening ? 'animate-pulse bg-urgent' : 'bg-accent'} disabled:opacity-40`}>
            🎤
          </button>
          <select value={voiceLang} onChange={(e) => setVoiceLang(e.target.value)} aria-label="Voice language"
            className="rounded bg-soft text-[10px]">
            {VOICE_LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </div>
        <textarea value={text} onChange={(e) => { setText(e.target.value); if (!e.target.value) setChannel('chat') }}
          rows={2} placeholder={listening ? 'Listening…' : 'Message'} aria-label="Message"
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          className="min-h-11 flex-1 resize-none rounded-2xl border border-line bg-surface px-3 py-2 text-sm" />
        <button type="submit" disabled={sending || !text.trim()} aria-label="Send"
          className="h-11 rounded-full bg-safe px-4 text-sm font-bold text-white disabled:opacity-40">
          {sending ? '…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
