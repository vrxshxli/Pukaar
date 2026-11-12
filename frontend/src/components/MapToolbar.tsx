import { QRCodeSVG } from 'qrcode.react'
import { useState } from 'react'
import type { State } from '../api'
import { Icon } from './ui'

// The floating bar across the top of the map: replay, LLM mode, the kill switch and the chat QR code.
export default function MapToolbar({ state, onToggleAutomation, onLlmMode, children }: {
  state: State
  onToggleAutomation: () => void
  onLlmMode: (mode: 'rules' | 'ollama' | 'groq') => void
  children?: React.ReactNode
}) {
  const [showQr, setShowQr] = useState(false)
  const chatUrl = `${window.location.origin}/chat`
  const llm = state.llm
  const llmText = llm.mode === 'rules' ? 'rules'
    : llm.effective === llm.mode ? (llm.model ?? llm.mode) : 'unavailable · rules'
  return (
    <div className="glass pointer-events-auto flex flex-wrap items-center gap-2 px-2 py-1.5">
      {children}
      <span className="hidden h-6 w-px bg-line sm:block" />
      <label className="flex items-center gap-1.5 rounded-xl bg-soft px-2 py-1 text-xs" title={llm.last_error ?? 'Which engine reads messages'}>
        <span className="font-semibold text-muted">LLM</span>
        <select value={llm.mode} onChange={(e) => onLlmMode(e.target.value as 'rules' | 'ollama' | 'groq')}
          className="rounded-md bg-transparent text-xs font-semibold text-fg outline-none" aria-label="LLM mode">
          <option value="rules" className="bg-card text-fg">Rules</option>
          <option value="ollama" className="bg-card text-fg">Ollama</option>
          <option value="groq" className="bg-card text-fg">Groq</option>
        </select>
        <span className={`rounded-full px-1.5 py-0.5 text-[10.5px] font-semibold ${llm.fallback ? 'bg-marigold text-ink' : 'bg-card text-muted'}`}>{llmText}</span>
      </label>
      {state.planner && (
        <span title="Which events the LLM Planner handles, and with which model"
          className={`rounded-xl px-2 py-1 text-[11px] font-semibold ${state.planner.provider && state.planner.scope !== 'off' ? 'bg-accent-soft text-accent' : 'bg-soft text-muted'}`}>
          Planner {state.planner.provider && state.planner.scope !== 'off' ? `${state.planner.scope} · ${state.planner.model}` : 'off · rules'}
        </span>
      )}
      <button onClick={onToggleAutomation} role="switch" aria-checked={state.automation}
        className={`flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-xs font-bold ${state.automation ? 'bg-safe/15 text-[#3c6e3a] dark:text-[#a8d4a2]' : 'bg-urgent text-white'}`}
        title="When off, agents only log and propose nothing; no message leaves the control room">
        <span className={`relative h-4 w-7 rounded-full transition ${state.automation ? 'bg-safe' : 'bg-white/40'}`}>
          <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${state.automation ? 'left-3.5' : 'left-0.5'}`} />
        </span>
        Automation {state.automation ? 'on' : 'off'}
      </button>
      <div className="relative">
        <button onClick={() => setShowQr((s) => !s)} aria-label="Show QR code for the citizen chat" title="QR code for the citizen chat"
          className="flex h-8 w-8 items-center justify-center rounded-xl bg-soft text-fg hover:text-accent">
          <Icon name="qr" size={17} />
        </button>
        {showQr && (
          <div className="glass absolute right-0 top-11 z-[2000] w-60 p-3 text-center">
            <div className="rounded-xl bg-white p-2"><QRCodeSVG value={chatUrl} size={196} className="mx-auto" /></div>
            <p className="mt-2 text-xs font-semibold">Scan to message the control room</p>
            <p className="break-all text-[10px] text-muted">{chatUrl}</p>
          </div>
        )}
      </div>
    </div>
  )
}
