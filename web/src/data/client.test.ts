import { afterEach, describe, expect, it, vi } from 'vitest'
import { getArticle, getDay, NotFoundError } from './client'

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('data client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests the sharded day path', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ day: '2026-11-25' }))
    vi.stubGlobal('fetch', fetchMock)
    const day = await getDay('2026-11-25')
    expect(day.day).toBe('2026-11-25')
    expect(fetchMock).toHaveBeenCalledWith('/data/days/2026-11-25.json', {
      signal: undefined,
    })
  })

  it('uses the first two characters of the slug for articles', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ slug: 'albert-einstein' }))
    vi.stubGlobal('fetch', fetchMock)
    await getArticle('albert-einstein')
    expect(fetchMock).toHaveBeenCalledWith('/data/articles/al/albert-einstein.json', {
      signal: undefined,
    })
  })

  it('throws NotFoundError for 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond({}, 404)))
    await expect(getDay('2026-01-01')).rejects.toBeInstanceOf(NotFoundError)
  })

  it('throws for other failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond({}, 500)))
    await expect(getDay('2026-01-01')).rejects.toThrow('500')
  })
})
