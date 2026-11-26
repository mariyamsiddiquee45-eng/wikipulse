import { Link } from 'react-router-dom'
import { usePageMeta } from '../lib/usePageMeta'

export function AboutPage() {
  usePageMeta({
    title: 'About - WikiPulse',
    description: 'What WikiPulse is, where its data comes from, and its independence.',
  })
  return (
    <article className="prose stack">
      <h1>About WikiPulse</h1>
      <p>
        WikiPulse shows what people suddenly became curious about on English Wikipedia. Once a day,
        the pipeline finds unusual pageview jumps, groups the articles that belong to the same
        event, and publishes the result as static files.
      </p>

      <h2>Data</h2>
      <ul>
        <li>
          Pageview and edit analytics:{' '}
          <a href="https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/">
            Wikimedia Analytics API
          </a>
          , CC0.
        </li>
        <li>
          Article summaries: <a href="https://en.wikipedia.org/">English Wikipedia</a>, CC BY-SA
          4.0, attributed and linked on every event and article page.
        </li>
        <li>No Wikipedia logos, marks or article images are used.</li>
      </ul>

      <h2>How it works</h2>
      <p>
        A Python pipeline ingests daily top-1000 pageviews, fetches history for candidate articles,
        computes features, applies a rule-based detector, and groups spikes into events with
        sentence embeddings and HDBSCAN. A React app reads the exported JSON from the same origin.
        There is no runtime server and no account system.
      </p>

      <h2>Independence</h2>
      <p>
        WikiPulse is not affiliated with Wikipedia or the Wikimedia Foundation. It is an independent
        project built on public data.
      </p>

      <p className="small muted">
        <Link to="/methods">Read the methods and limitations</Link>
      </p>
    </article>
  )
}
