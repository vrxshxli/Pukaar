import { useState } from 'react'
import type { ReplayStatus } from '../api'
import { api } from '../api'

const SPEEDS = [1, 5, 10]

export default function ReplayControls({ replay, onError }: { replay: ReplayStatus; onError: (msg: string) => void }) {
  const [speed, setSpeed] = useState(replay.speed || 10)
  const [busy, setBusy] = useState(false)

  async function send(action: string, s = speed) {
    if (action === 'start' && replay.state !== 'idle' && !window.confirm('Restart the flood night? This resets every ticket.')) return
    if (action === 'reset' && !window.confirm('Reset the ward to the start of the night?')) return
    setBusy(true)
    try {
      await api('/api/replay', { action, speed: s })
    } catch (e) {
      onError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const playing = replay.state === 'playing'
  return (
    <div className="flex items-center gap-1.5 rounded-lg bg-white/10 px-2 py-1 text-xs" aria-label="Replay controls">
      <span className="font-semibold opacity-80">Replay</span>
      {SPEEDS.map((s) => (
        <button key={s} disabled={busy} onClick={() => { setSpeed(s); if (replay.state !== 'idle') send('speed', s) }}
          aria-pressed={speed === s}
          className={`rounded px-1.5 py-0.5 font-bold ${speed === s ? 'bg-marigold text-ink' : 'bg-white/10'}`}>{s}×</button>
      ))}
      {replay.state === 'idle' || replay.state === 'finished' ? (
        <button disabled={busy} onClick={() => send('start')} className="rounded bg-safe px-2 py-0.5 font-bold">▶ Start</button>
      ) : playing ? (
        <button disabled={busy} onClick={() => send('pause')} className="rounded bg-white/20 px-2 py-0.5 font-bold">❚❚ Pause</button>
      ) : (
        <button disabled={busy} onClick={() => send('resume')} className="rounded bg-safe px-2 py-0.5 font-bold">▶ Resume</button>
      )}
      <button disabled={busy} onClick={() => send('reset')} className="rounded bg-white/10 px-2 py-0.5">Reset</button>
      {replay.total > 0 && (
        <span className="tabular-nums opacity-80">{replay.sent}/{replay.total}{replay.state === 'finished' ? ' done' : ''}</span>
      )}
    </div>
  )
}
