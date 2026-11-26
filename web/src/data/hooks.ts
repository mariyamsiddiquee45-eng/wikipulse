import { useCallback, useEffect, useState } from 'react'
import {
  getArticle,
  getDay,
  getManifest,
  getMethods,
  getSearchShard,
  getStatus,
  NotFoundError,
} from './client'
import type { Article, Day, Manifest, Methods, SearchShard, Status } from './types'

type Internal<T> =
  | { key: string; status: 'loading' }
  | { key: string; status: 'error'; error: string; notFound: boolean }
  | { key: string; status: 'ready'; data: T }

export type Resource<T> =
  | { status: 'loading'; retry: () => void }
  | { status: 'error'; error: string; notFound: boolean; retry: () => void }
  | { status: 'ready'; data: T; retry: () => void }

export function useResource<T>(
  key: string,
  load: (signal: AbortSignal) => Promise<T>,
): Resource<T> {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<Internal<T>>({ key, status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ key, status: 'ready', data })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({
          key,
          status: 'error',
          error: error instanceof Error ? error.message : 'Request failed',
          notFound: error instanceof NotFoundError,
        })
      })
    return () => controller.abort()
  }, [key, attempt, load])

  const retry = () => {
    setState({ key, status: 'loading' })
    setAttempt((value) => value + 1)
  }
  if (state.key !== key) return { status: 'loading', retry }
  if (state.status === 'loading') return { status: 'loading', retry }
  if (state.status === 'error') {
    return { status: 'error', error: state.error, notFound: state.notFound, retry }
  }
  return { status: 'ready', data: state.data, retry }
}

export function useManifest(): Resource<Manifest> {
  return useResource('manifest', getManifest)
}

export function useDay(day: string): Resource<Day> {
  const load = useCallback((signal: AbortSignal) => getDay(day, signal), [day])
  return useResource(`day:${day}`, load)
}

export function useArticle(slug: string): Resource<Article> {
  const load = useCallback((signal: AbortSignal) => getArticle(slug, signal), [slug])
  return useResource(`article:${slug}`, load)
}

export function useMethods(): Resource<Methods> {
  return useResource('methods', getMethods)
}

export function useStatus(): Resource<Status> {
  return useResource('status', getStatus)
}

export function useSearchShard(prefix: string): Resource<SearchShard> {
  const load = useCallback((signal: AbortSignal) => getSearchShard(prefix, signal), [prefix])
  return useResource(`search:${prefix}`, load)
}
