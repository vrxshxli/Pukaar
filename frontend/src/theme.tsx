import { useEffect, useState } from 'react'
import { Icon } from './components/ui'

type Theme = 'light' | 'dark' | 'system'

function systemDark() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

function apply(theme: Theme) {
  const dark = theme === 'dark' || (theme === 'system' && systemDark())
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

function stored(): Theme {
  try {
    const t = localStorage.getItem('pukaar-theme')
    return t === 'light' || t === 'dark' ? t : 'light'
  } catch {
    return 'light'
  }
}

// Starts light (calm and readable in a lit control room) until the person picks dark.
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(stored)
  useEffect(() => {
    apply(theme)
    try {
      if (theme === 'system') localStorage.removeItem('pukaar-theme')
      else localStorage.setItem('pukaar-theme', theme)
    } catch { /* private mode */ }
    if (theme !== 'system') return
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    const onChange = () => apply('system')
    media?.addEventListener('change', onChange)
    return () => media?.removeEventListener('change', onChange)
  }, [theme])
  const isDark = theme === 'dark' || (theme === 'system' && systemDark())
  return { isDark, toggle: () => setTheme(isDark ? 'light' : 'dark') }
}

export function ThemeToggle({ className = '' }: { className?: string }) {
  const { isDark, toggle } = useTheme()
  return (
    <button onClick={toggle} aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={`inline-flex items-center justify-center rounded-xl p-1.5 text-sm ${className}`}>
      <Icon name={isDark ? 'sun' : 'moon'} size={18} />
    </button>
  )
}

// Set the theme before React draws, so there is no flash of the wrong colours.
apply(stored())
// Keep popups and other tabs on the same theme when it is switched.
window.addEventListener('storage', (e) => { if (e.key === 'pukaar-theme') apply(stored()) })
