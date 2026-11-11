import { QRCodeSVG } from 'qrcode.react'
import { useState } from 'react'
import type { State } from '../api'
import { clock } from '../api'
import { ThemeToggle } from '../theme'
import { COLORS, Logo } from './ui'

const LEVEL_COLOR: Record<string, string> = { Red: COLORS.urgent, Orange: '#D9530B', Yellow: COLORS.marigold, none: COLORS.grey }

export default function Header({ state, connected, officer, setOfficer, onToggleAutomation, onLlmMode, children }: {
  state: State
  connected: boolean
  officer: string
  setOfficer: (name: string) => void
  onToggleAutomation: () => void
  onLlmMode: (mode: 'rules' | 'ollama') => void
  children?: React.ReactNode
}) {
  const [showQr, setShowQr] = useState(false)
  const chatUrl = `${window.location.origin}/chat`
  const llm = state.llm
  const llmText = llm.mode === 'ollama'
    ? (llm.effective === 'ollama' ? `Ollama · ${llm.model}` : 'Ollama unavailable · using rules')
    : 'Rules mode'
  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 bg-ink px-4 py-2 text-white">
      <div className="flex items-center gap-2">
        <Logo />
        <div className="leading-tight">
          <div className="text-base font-extrabold">Pukaar <span className="font-normal opacity-70">पुकार</span></div>
          <div className="text-[11px] opacity-75">{state.ward.name} control room</div>
        </div>
      </div>
      <div className="leading-tight">
        <div className="text-sm font-bold">{state.ward.incident_name}</div>
        <div className="flex items-center gap-1.5 text-[11px]">
          <span className="rounded px-1.5 font-bold" style={{ background: LEVEL_COLOR[state.incident.level] ?? COLORS.grey }}>
            {state.incident.level === 'none' ? 'No alert' : `${state.incident.level} alert`}
          </span>
          <span className="opacity-75">{state.incident.status}</span>
        </div>
      </div>
      <div className="text-center leading-tight" title="Game clock for the flood night">
        <div className="font-mono text-xl font-bold tabular-nums">{clock(state.clock)}</div>
        <div className="text-[10px] opacity-70">{state.clock_speed > 1 ? `${state.clock_speed}× speed` : state.clock_speed === 0 ? 'paused' : 'live'}</div>
      </div>
      {children}
      <div className="ml-auto flex flex-wrap items-center gap-3">
        <nav className="flex gap-2 text-xs opacity-90" aria-label="Other apps">
          <a href="/chat" target="_blank" rel="noreferrer" className="hover:underline">Citizen chat</a>
          <a href="/volunteer" target="_blank" rel="noreferrer" className="hover:underline">Volunteer</a>
          <a href="/family" target="_blank" rel="noreferrer" className="hover:underline">Family lookup</a>
        </nav>
        <ThemeToggle className="bg-white/10 text-white" />
        <label className="flex items-center gap-1.5 text-xs">
          <span className="opacity-75">LLM</span>
          <select value={llm.mode} onChange={(e) => onLlmMode(e.target.value as 'rules' | 'ollama')}
            className="rounded bg-white/10 px-1 py-0.5 text-xs" aria-label="LLM mode">
            <option value="rules" className="text-ink">Rules</option>
            <option value="ollama" className="text-ink">Ollama</option>
          </select>
          <span className={`rounded px-1.5 py-0.5 font-semibold ${llm.fallback ? 'bg-marigold text-ink' : 'bg-white/15'}`}
            title={llm.last_error ?? ''}>{llmText}</span>
        </label>
        <button onClick={onToggleAutomation} role="switch" aria-checked={state.automation}
          className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold ${state.automation ? 'bg-safe' : 'bg-urgent'}`}
          title="When off, agents only log and propose nothing; no message leaves the control room">
          <span className={`h-3 w-3 rounded-full bg-white ${state.automation ? '' : 'opacity-60'}`} />
          Automation {state.automation ? 'on' : 'off'}
        </button>
        <label className="flex items-center gap-1 text-xs">
          <span className="opacity-75">Officer</span>
          <input value={officer} onChange={(e) => setOfficer(e.target.value)}
            className="w-28 rounded bg-white/10 px-1.5 py-0.5 text-xs" aria-label="Officer name" />
        </label>
        <span className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-[#7ee08a]' : 'bg-urgent'}`} title={connected ? 'Live' : 'Reconnecting'} />
        <div className="relative">
          <button onClick={() => setShowQr((s) => !s)} className="rounded bg-white p-0.5" aria-label="Show QR code for the citizen chat">
            <QRCodeSVG value={chatUrl} size={34} />
          </button>
          {showQr && (
            <div className="absolute right-0 top-11 z-[2000] w-60 rounded-lg bg-white p-3 text-center text-ink shadow-xl">
              <QRCodeSVG value={chatUrl} size={200} className="mx-auto" />
              <p className="mt-2 text-xs font-semibold">Scan to message the control room</p>
              <p className="break-all text-[10px] text-muted">{chatUrl}</p>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
