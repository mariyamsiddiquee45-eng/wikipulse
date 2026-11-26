import { useState } from 'react'
import { applyTheme, resolveTheme, storedTheme, toggleTheme, type Theme } from '../lib/theme'
import { MoonIcon, SunIcon } from './icons'

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => storedTheme())
  const resolved = resolveTheme(theme)
  const next = resolved === 'dark' ? 'light' : 'dark'

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        const changed = toggleTheme(theme)
        applyTheme(changed)
        setTheme(changed)
      }}
    >
      {resolved === 'dark' ? <SunIcon /> : <MoonIcon />}
    </button>
  )
}
