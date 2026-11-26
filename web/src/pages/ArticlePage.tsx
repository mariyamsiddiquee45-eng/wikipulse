import { Link, useParams } from 'react-router-dom'
import { ArticleChart } from '../components/ArticleChart'
import { EmptyState, ErrorState, LoadingBlock } from '../components/States'
import { typeClass } from '../components/typeClass'
import { useArticle } from '../data/hooks'
import { dayPath, formatDate, formatNumber, searchPath } from '../lib/format'
import { usePageMeta } from '../lib/usePageMeta'

export function ArticlePage() {
  const { slug = '' } = useParams()
  const resource = useArticle(slug)
  const article = resource.status === 'ready' ? resource.data : null
  usePageMeta({
    title: article ? `${article.title} - WikiPulse` : 'Article not found - WikiPulse',
    description: article
      ? `${article.title}: Wikipedia pageview history and spikes.`
      : 'This article page does not exist.',
  })

  if (resource.status === 'loading') return <LoadingBlock lines={8} />
  if (resource.status === 'error' && resource.notFound) {
    return (
      <EmptyState title="This article is not in the export">
        <p>
          Article pages exist only for articles that spiked. The slug may be wrong, or the article
          has not spiked in the exported period.
        </p>
        <Link className="button" to={searchPath(slug.replace(/-/g, ' '))}>
          Search for this article
        </Link>
      </EmptyState>
    )
  }
  if (resource.status === 'error') {
    return <ErrorState message={resource.error} retry={resource.retry} />
  }
  if (!article) return null

  return (
    <article className="stack">
      <header>
        <p className="small muted">Article history</p>
        <h1>{article.title}</h1>
        {article.description ? <p className="muted">{article.description}</p> : null}
        <p className="small muted">
          {formatDate(article.first_day)} to {formatDate(article.last_day)} ·{' '}
          {article.spikes.length} {article.spikes.length === 1 ? 'spike' : 'spikes'}
        </p>
      </header>

      <section className="card">
        <ArticleChart article={article} />
        <p className="attribution">
          Daily views from Wikimedia pageview data (CC0). Spike markers show days detected by
          WikiPulse.
        </p>
      </section>

      {article.extract ? (
        <section className="card">
          <h2>From the article</h2>
          <p>{article.extract}</p>
          <p className="attribution">
            Text from{' '}
            <a href={article.url} target="_blank" rel="noreferrer noopener">
              {article.title} on Wikipedia
            </a>{' '}
            · CC BY-SA 4.0
          </p>
        </section>
      ) : null}

      <section className="card" aria-labelledby="spikes-heading">
        <h2 id="spikes-heading">Spike days</h2>
        {article.spikes.length ? (
          <ul className="spike-list">
            {article.spikes.map((spike) => (
              <li key={spike.day}>
                <Link to={dayPath(spike.day)}>{formatDate(spike.day)}</Link> ·{' '}
                <span className={`badge ${typeClass(spike.type)}`}>{spike.type}</span> · z{' '}
                {spike.z_score === null ? 'unknown' : spike.z_score.toFixed(1)} · score{' '}
                {formatNumber(Math.round(spike.score))}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No spikes were detected for this article.</p>
        )}
      </section>

      <p className="small muted">
        <Link to="/">Latest day</Link> ·{' '}
        <a href={article.url} target="_blank" rel="noreferrer noopener">
          Read the article on Wikipedia
        </a>
      </p>
    </article>
  )
}
