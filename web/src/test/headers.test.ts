import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const headers = readFileSync(resolve(process.cwd(), 'public/_headers'), 'utf8')

describe('Cloudflare Pages headers', () => {
  it('sets the required security directives', () => {
    for (const directive of [
      'Content-Security-Policy',
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self'",
      "img-src 'self' data:",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "object-src 'none'",
      'X-Content-Type-Options: nosniff',
      'Referrer-Policy',
      'Permissions-Policy',
      'Cross-Origin-Opener-Policy: same-origin',
    ]) {
      expect(headers).toContain(directive)
    }
    expect(headers).not.toContain('unsafe-inline')
    expect(headers).not.toContain('Access-Control-Allow-Origin')
  })

  it('caches hashed assets for a year and data for five minutes', () => {
    expect(headers).toContain('max-age=31536000, immutable')
    expect(headers).toContain('max-age=300')
  })
})
