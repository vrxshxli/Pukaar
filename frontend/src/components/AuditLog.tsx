import { useEffect, useState } from 'react'
import type { AuditEntry } from '../api'
import { api, clock } from '../api'
import { AgentTag, Button, ErrorNote, Spinner } from './ui'

export default function AuditLog() {
  const [rows, setRows] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const load = () => api<AuditEntry[]>('/api/audit?limit=500').then((r) => { setRows(r); setError(null) })
    .catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  if (error) return <ErrorNote>{error}</ErrorNote>
  if (!rows) return <Spinner label="Loading the audit log" />
  const q = query.toLowerCase()
  const shown = q ? rows.filter((r) => `${r.agent} ${r.tool} ${r.summary} ${r.ticket_id} ${r.input}`.toLowerCase().includes(q)) : rows
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex gap-2">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter by agent, tool or ticket"
          className="w-full rounded-xl border border-line bg-soft px-2.5 py-1.5 text-xs outline-none focus:border-accent" aria-label="Filter the audit log" />
        <Button small onClick={load}>Refresh</Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-line">
        <table className="w-full text-left text-[11px]">
          <thead className="sticky top-0 bg-soft text-muted">
            <tr>
              <th className="px-2 py-1">Time</th><th className="px-2 py-1">Agent</th><th className="px-2 py-1">Tool</th>
              <th className="px-2 py-1">What happened</th><th className="px-2 py-1">Input</th>
              <th className="px-2 py-1">Result</th><th className="px-2 py-1">Approved by</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id} className="border-t border-line align-top">
                <td className="whitespace-nowrap px-2 py-1 text-muted">{clock(r.at)}</td>
                <td className="px-2 py-1"><AgentTag agent={r.agent} /></td>
                <td className="px-2 py-1 font-mono">{r.tool ?? r.kind}</td>
                <td className="px-2 py-1">{r.summary}</td>
                <td className="max-w-[180px] truncate px-2 py-1 font-mono text-muted" title={r.input ?? ''}>{r.input}</td>
                <td className="max-w-[180px] truncate px-2 py-1 font-mono text-muted" title={r.result ?? ''}>{r.result}</td>
                <td className="px-2 py-1 font-semibold">{r.approved_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
