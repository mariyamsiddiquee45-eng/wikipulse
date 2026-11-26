export type Theme = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_KEY = 'wikipulse-theme'

export function storedTheme(): Theme {
  try {
    const value = localStorage.getItem(THEME_KEY)
    if (value === 'light' || value === 'dark') return value
  } catch {
    // Private mode can deny storage; the system preference still works.
  }
  return 'system'
}

export function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme !== 'system') return theme
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'system') {
    root.removeAttribute('data-theme')
    try {
      localStorage.removeItem(THEME_KEY)
    } catch {
      // Nothing to do; the in-memory theme still applies for this page.
    }
    return
  }
  root.dataset.theme = theme
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    // Storage is optional; the attribute still applies.
  }
}

export function toggleTheme(current: Theme): Theme {
  return resolveTheme(current) === 'dark' ? 'light' : 'dark'
}
