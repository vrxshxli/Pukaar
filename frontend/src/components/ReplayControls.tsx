import { useState } from 'react'
import type { ReplayStatus } from '../api'
import { api } from '../api'
import { Icon } from './ui'

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
  const startable = replay.state === 'idle' || replay.state === 'finished'
  const progress = replay.total > 0 ? Math.round((replay.sent / replay.total) * 100) : 0
  return (
    <div className="flex items-center gap-1.5 text-xs" aria-label="Replay controls">
      <div className="flex min-w-[120px] flex-col px-1">
        <span className="font-semibold text-muted">
          Flood-night replay{replay.total > 0 ? ` · ${replay.sent}/${replay.total}` : ''}{replay.state === 'finished' ? ' done' : ''}
        </span>
        <span className="mt-1 h-1 overflow-hidden rounded-full bg-soft">
          <span className="block h-full rounded-full bg-accent transition-all" style={{ width: `${progress}%` }} />
        </span>
      </div>
      <div className="flex rounded-xl bg-soft p-0.5">
        {SPEEDS.map((s) => (
          <button key={s} disabled={busy} onClick={() => { setSpeed(s); if (replay.state !== 'idle') send('speed', s) }}
            aria-pressed={speed === s}
            className={`rounded-lg px-2 py-1 font-bold transition ${speed === s ? 'bg-card text-accent shadow-sm' : 'text-muted hover:text-fg'}`}>{s}×</button>
        ))}
      </div>
      <button disabled={busy} onClick={() => send('reset')} title="Reset the ward" aria-label="Reset the ward"
        className="flex h-8 w-8 items-center justify-center rounded-xl bg-soft text-muted hover:text-fg">
        <Icon name="reset" size={16} />
      </button>
      <button disabled={busy}
        onClick={() => send(startable ? 'start' : playing ? 'pause' : 'resume')}
        aria-label={startable ? 'Start the replay' : playing ? 'Pause the replay' : 'Resume the replay'}
        title={startable ? 'Start' : playing ? 'Pause' : 'Resume'}
        className="flex h-8 items-center gap-1 rounded-xl bg-accent px-2.5 font-bold text-accent-fg hover:brightness-110">
        <Icon name={playing ? 'pause' : 'play'} size={15} strokeWidth={2.4} />
        {startable ? 'Start' : playing ? 'Pause' : 'Resume'}
      </button>
    </div>
  )
}
