import type { Article, Day, Manifest, Methods, SearchShard, Status } from './types'

const BASE = `${import.meta.env.BASE_URL}data`

export class NotFoundError extends Error {
  constructor(path: string) {
    super(`Not found: ${path}`)
    this.name = 'NotFoundError'
  }
}

export async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BASE}/${path}`, { signal })
  if (response.status === 404) throw new NotFoundError(path)
  if (!response.ok) throw new Error(`Request failed with status ${response.status}`)
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) throw new NotFoundError(path)
  return (await response.json()) as T
}

export function getManifest(signal?: AbortSignal): Promise<Manifest> {
  return fetchJson<Manifest>('manifest.json', signal)
}

export function getDay(day: string, signal?: AbortSignal): Promise<Day> {
  return fetchJson<Day>(`days/${day}.json`, signal)
}

export function getArticle(slug: string, signal?: AbortSignal): Promise<Article> {
  return fetchJson<Article>(`articles/${slug.slice(0, 2)}/${slug}.json`, signal)
}

export function getSearchShard(prefix: string, signal?: AbortSignal): Promise<SearchShard> {
  return fetchJson<SearchShard>(`search/${prefix}.json`, signal)
}

export function getMethods(signal?: AbortSignal): Promise<Methods> {
  return fetchJson<Methods>('methods.json', signal)
}

export function getStatus(signal?: AbortSignal): Promise<Status> {
  return fetchJson<Status>('status.json', signal)
}
