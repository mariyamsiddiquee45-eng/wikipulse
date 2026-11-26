import { beforeEach, describe, expect, it, vi } from 'vitest'
import { applyTheme, resolveTheme, storedTheme, THEME_KEY, toggleTheme } from './theme'

function mockDark(dark: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: dark,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    mockDark(false)
  })

  it('defaults to the system preference', () => {
    expect(storedTheme()).toBe('system')
    expect(resolveTheme('system')).toBe('light')
    mockDark(true)
    expect(resolveTheme('system')).toBe('dark')
  })

  it('stores an explicit theme and applies it to the document', () => {
    applyTheme('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('removes the attribute when returning to system', () => {
    applyTheme('dark')
    applyTheme('system')
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('toggles away from the resolved theme', () => {
    mockDark(true)
    expect(toggleTheme('system')).toBe('light')
    expect(toggleTheme('light')).toBe('dark')
  })
})
