import { describe, expect, it } from 'vitest'
import {
  articlePath,
  clamp,
  dayPath,
  eventPath,
  formatDate,
  formatNumber,
  hoursSince,
  isStale,
  searchPath,
  truncate,
} from './format'

describe('format helpers', () => {
  it('formats numbers with grouping', () => {
    expect(formatNumber(1234567)).toBe('1,234,567')
  })

  it('formats ISO days in UTC', () => {
    expect(formatDate('2026-11-25')).toBe('25 November 2026')
  })

  it('measures hours since a day', () => {
    const now = new Date('2026-11-27T12:00:00Z')
    expect(hoursSince('2026-11-26', now)).toBe(36)
    expect(hoursSince(null, now)).toBeNull()
    expect(hoursSince('not-a-date', now)).toBeNull()
  })

  it('marks data older than 48 hours stale', () => {
    const now = new Date('2026-11-28T12:00:00Z')
    expect(isStale('2026-11-26', now)).toBe(true)
    expect(isStale('2026-11-27', now)).toBe(false)
    expect(isStale(null, now)).toBe(true)
  })

  it('truncates long text with an ellipsis', () => {
    expect(truncate('abcdef', 5)).toBe('abcd…')
    expect(truncate('abc', 5)).toBe('abc')
  })

  it('builds routes', () => {
    expect(dayPath('2026-11-25')).toBe('/d/2026-11-25')
    expect(eventPath('20261125-abcd')).toBe('/e/20261125-abcd')
    expect(articlePath('albert-einstein')).toBe('/a/albert-einstein')
    expect(searchPath('star trek')).toBe('/search?q=star%20trek')
  })

  it('clamps values', () => {
    expect(clamp(5, 0, 3)).toBe(3)
    expect(clamp(-1, 0, 3)).toBe(0)
  })
})
