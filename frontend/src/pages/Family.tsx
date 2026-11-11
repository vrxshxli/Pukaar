import { useState } from 'react'
import { api, clock } from '../api'
import { Button, ErrorNote, Logo } from '../components/ui'

interface Result {
  ticket_id: string
  title: string
  status: string
  safe_at: string | null
  camp: string | null
  updated_at: string
}

function describe(r: Result) {
  if (r.status === 'safe' || r.status === 'closed') {
    return { tone: 'safe', text: `Rescued at ${clock(r.safe_at)}, now at ${r.camp?.split(' (')[0] ?? 'a relief camp'}.` }
  }
  if (r.status === 'en_route') return { tone: 'teal', text: 'A rescue team is on the way.' }
  if (r.status === 'assigned') return { tone: 'teal', text: 'A rescue team has been assigned.' }
  return { tone: 'marigold', text: 'The request has reached the control room and is in the queue.' }
}

const TONES: Record<string, string> = {
  safe: 'border-safe bg-safe/10',
  teal: 'border-teal bg-teal/10',
  marigold: 'border-marigold bg-marigold/10',
}

export default function Family() {
  const [ticket, setTicket] = useState('')
  const [name, setName] = useState('')
  const [area, setArea] = useState('')
  const [results, setResults] = useState<Result[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function search(e: React.FormEvent) {
    e.preventDefault()
    if (!ticket.trim() && !name.trim()) {
      setError('Enter a ticket number, or a name.')
      return
    }
    setBusy(true)
    setError(null)
    const q = new URLSearchParams(ticket.trim() ? { ticket: ticket.trim() } : { name: name.trim(), area: area.trim() })
    try {
      setResults((await api<{ results: Result[] }>(`/api/family?${q}`)).results)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md p-4">
      <div className="mb-1 flex items-center gap-2"><Logo /><h1 className="text-xl font-extrabold">Is my family safe?</h1></div>
      <p className="mb-4 text-sm text-muted">
        Check a rescue request in Ward 12. We only show the status and the relief camp, never an address or phone number.
      </p>
      <form onSubmit={search} className="space-y-3 rounded-xl border border-line bg-card p-4">
        <label className="block text-sm font-semibold">
          Ticket number
          <input value={ticket} onChange={(e) => setTicket(e.target.value)} placeholder="for example P-0401"
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 font-normal" />
        </label>
        <div className="text-center text-xs font-semibold text-muted">or</div>
        <label className="block text-sm font-semibold">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="for example Kamla"
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 font-normal" />
        </label>
        <label className="block text-sm font-semibold">
          Area
          <input value={area} onChange={(e) => setArea(e.target.value)} placeholder="for example Lane 4"
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 font-normal" />
        </label>
        <Button type="submit" tone="primary" disabled={busy}>{busy ? 'Searching…' : 'Search'}</Button>
      </form>
      <div className="mt-4 space-y-2" aria-live="polite">
        {error && <ErrorNote>{error}</ErrorNote>}
        {results && results.length === 0 && (
          <p className="rounded-lg border border-line bg-card p-3 text-sm">
            No matching request found. Check the spelling, or message the helpline to report your family.
          </p>
        )}
        {results?.map((r) => {
          const d = describe(r)
          return (
            <div key={r.ticket_id} className={`rounded-xl border-l-4 p-3 ${TONES[d.tone]}`}>
              <div className="text-xs font-semibold text-muted">{r.ticket_id}</div>
              <div className="font-bold">{r.title}</div>
              <div className="text-sm">{d.text}</div>
              <div className="mt-1 text-[11px] text-muted">Last updated {clock(r.updated_at)}. Please don't forward old requests.</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
