import { Link } from 'react-router-dom'
import { BubblePack } from '../components/BubblePack'
import { DateScrubber } from '../components/DateScrubber'
import { HeroArt } from '../components/HeroArt'
import { RankedList } from '../components/RankedList'
import { EmptyState, ErrorState, LoadingBlock } from '../components/States'
import { useDay, useManifest } from '../data/hooks'
import type { Day, Manifest } from '../data/types'
import { dayPath, formatDate } from '../lib/format'
import { usePageMeta } from '../lib/usePageMeta'

function LatestDay({ manifest }: { manifest: Manifest }) {
  const day = useDay(manifest.last_day ?? '')
  if (!manifest.last_day) {
    return (
      <EmptyState title="No complete day is available">
        <p>The export does not contain a complete day yet.</p>
      </EmptyState>
    )
  }
  if (day.status === 'loading') return <LoadingBlock lines={8} />
  if (day.status === 'error' && day.notFound) {
    return (
      <EmptyState title="No events for the latest day">
        <p>The manifest points at {formatDate(manifest.last_day)} but its day file is missing.</p>
        <Link className="button" to={dayPath(manifest.last_day)}>
          Open the day page
        </Link>
      </EmptyState>
    )
  }
  if (day.status === 'error') return <ErrorState message={day.error} retry={day.retry} />
  return <DayContent day={day.data} manifest={manifest} />
}

function DayContent({ day, manifest }: { day: Day; manifest: Manifest }) {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="small muted">
            Data through {formatDate(manifest.data_through ?? day.day)} · English Wikipedia
          </p>
          <h1>The day's biggest pageview jumps on Wikipedia.</h1>
          <p>
            Daily pageviews on English Wikipedia, grouped into the events behind them. Each event
            collects the articles that rose together.
          </p>
          <div className="hero-actions">
            <a className="button primary" href="#events">
              See the events
            </a>
            <Link className="button" to="/methods">
              How this works
            </Link>
          </div>
        </div>
        <HeroArt />
      </section>

      <div className="home-grid" id="events">
        <section className="card" aria-labelledby="events-heading">
          <h2 id="events-heading">Events on {formatDate(day.day)}</h2>
          <p className="muted small">
            {day.events.length} {day.events.length === 1 ? 'event' : 'events'}, ranked by spike
            score.
          </p>
          {day.events.length ? (
            <RankedList events={day.events} limit={15} />
          ) : (
            <EmptyState title="No spike events on this day">
              <p>No candidate crossed the detection threshold.</p>
            </EmptyState>
          )}
        </section>

        <aside className="card bubble-panel" aria-labelledby="bubbles-heading">
          <h2 id="bubbles-heading">Events by score</h2>
          <p className="muted small">Circle size is spike score. Color is spike type.</p>
          {day.events.length ? (
            <BubblePack events={day.events} />
          ) : (
            <p className="muted">Nothing to draw for this day.</p>
          )}
          <DateScrubber days={manifest.days} current={day.day} />
        </aside>
      </div>
    </>
  )
}

export function HomePage() {
  usePageMeta({
    title: 'WikiPulse - what people looked up on Wikipedia today',
    description:
      'Daily pageview jumps in English Wikipedia, grouped into events. Updated once a day.',
  })
  const manifest = useManifest()
  if (manifest.status === 'loading') return <LoadingBlock lines={8} />
  if (manifest.status === 'error') {
    return <ErrorState message={manifest.error} retry={manifest.retry} />
  }
  return <LatestDay manifest={manifest.data} />
}
