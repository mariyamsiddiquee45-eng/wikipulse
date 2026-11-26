import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ThemeToggle } from './ThemeToggle'

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('switches to the opposite explicit theme', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button', { name: /Switch to dark theme/ })
    fireEvent.click(button)
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('wikipulse-theme')).toBe('dark')
  })
})
