import MiniSearch from 'minisearch'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingBlock } from '../components/States'
import { useSearchShard } from '../data/hooks'
import type { SearchShard } from '../data/types'
import { articlePath, formatDate, searchPath } from '../lib/format'
import { searchPrefix } from '../lib/search'
import { usePageMeta } from '../lib/usePageMeta'

type Entry = SearchShard['articles'][number]

function SearchResults({ query, prefix }: { query: string; prefix: string }) {
  const resource = useSearchShard(prefix)
  const articles = resource.status === 'ready' ? resource.data.articles : null
  const index = useMemo(() => {
    if (!articles) return null
    const mini = new MiniSearch<Entry>({
      fields: ['title', 'description'],
      storeFields: ['slug', 'title', 'description', 'url', 'last_day'],
      idField: 'slug',
    })
    mini.addAll(articles)
    return mini
  }, [articles])

  if (resource.status === 'loading') return <LoadingBlock lines={5} />
  if (resource.status === 'error' && resource.notFound) {
    return (
      <EmptyState title="No articles start with that prefix">
        <p>Try a different spelling or a longer name.</p>
      </EmptyState>
    )
  }
  if (resource.status === 'error') {
    return <ErrorState message={resource.error} retry={resource.retry} />
  }
  if (!index) return null
  const results = index
    .search(query, { prefix: true, fuzzy: 0.2, boost: { title: 2 } })
    .slice(0, 50) as unknown as Entry[]

  if (results.length === 0) {
    return (
      <EmptyState title="No matches in this prefix">
        <p>Only articles that ever spiked are in the search index.</p>
      </EmptyState>
    )
  }
  return (
    <ul className="search-results">
      {results.map((result) => (
        <li key={result.slug}>
          <Link to={articlePath(result.slug)}>{result.title}</Link>
          {result.description ? <p className="muted small">{result.description}</p> : null}
          <p className="small muted">Last active {formatDate(result.last_day)}</p>
        </li>
      ))}
    </ul>
  )
}

function SearchForm({ initial }: { initial: string }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState(initial)
  function submit(event: FormEvent) {
    event.preventDefault()
    if (query.trim()) navigate(searchPath(query.trim()))
  }
  return (
    <form className="search-form" role="search" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="search-page-input">
        Search articles
      </label>
      <input
        id="search-page-input"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Article title"
      />
      <button className="button primary" type="submit">
        Search
      </button>
    </form>
  )
}

export function SearchPage() {
  const [params] = useSearchParams()
  const query = (params.get('q') ?? '').trim()
  const prefix = searchPrefix(query)
  usePageMeta({
    title: query ? `Search: ${query} - WikiPulse` : 'Search - WikiPulse',
    description: 'Search Wikipedia articles that spiked, by title.',
  })

  return (
    <div className="stack">
      <header>
        <h1>Search articles</h1>
        <p className="muted">
          The index covers articles with a pageview jump in the available days. Enter at least two
          characters.
        </p>
      </header>
      <SearchForm initial={query} />
      {query.length === 0 ? (
        <EmptyState title="Start with a title">
          <p>Search for an article name, not a full question.</p>
        </EmptyState>
      ) : prefix === null ? (
        <EmptyState title="Keep typing">
          <p>At least two letters are needed to choose a search shard.</p>
        </EmptyState>
      ) : (
        <SearchResults query={query} prefix={prefix} />
      )}
    </div>
  )
}
