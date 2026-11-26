import { describe, expect, it } from 'vitest'
import { searchPrefix, slugify } from './search'

describe('search helpers', () => {
  it('slugifies titles with accents and punctuation', () => {
    expect(slugify('Beyoncé')).toBe('beyonce')
    expect(slugify('Star Trek: Discovery')).toBe('star-trek-discovery')
    expect(slugify('  AC/DC  ')).toBe('ac-dc')
  })

  it('requires two characters before choosing a shard', () => {
    expect(searchPrefix('a')).toBeNull()
    expect(searchPrefix('  ')).toBeNull()
    expect(searchPrefix('Beyoncé')).toBe('be')
    expect(searchPrefix('Star Trek')).toBe('st')
  })
})
