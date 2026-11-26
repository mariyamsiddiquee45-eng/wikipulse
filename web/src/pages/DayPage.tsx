import { Link, useParams } from 'react-router-dom'
import { DateScrubber } from '../components/DateScrubber'
import { RankedList } from '../components/RankedList'
import { EmptyState, ErrorState, LoadingBlock } from '../components/States'
import { useDay, useManifest } from '../data/hooks'
import { dayPath, formatDate } from '../lib/format'
import { usePageMeta } from '../lib/usePageMeta'
import { NotFoundPage } from './NotFoundPage'

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function validDate(value: string): boolean {
  if (!DATE_PATTERN.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().startsWith(value)
}

export function DayPage() {
  const { date = '' } = useParams()
  const valid = validDate(date)
  const manifest = useManifest()
  const day = useDay(valid ? date : 'invalid')
  usePageMeta({
    title: valid ? `${formatDate(date)} - WikiPulse` : 'Day not found - WikiPulse',
    description: valid
      ? `Wikipedia spike events on ${formatDate(date)}.`
      : 'This day page does not exist.',
  })

  if (!valid) return <NotFoundPage />
  if (day.status === 'loading') return <LoadingBlock lines={8} />
  if (day.status === 'error' && day.notFound) {
    return (
      <div className="stack">
        <EmptyState title={`No data file for ${formatDate(date)}`}>
          <p>
            This day was not exported. It may be missing from the source data or outside the
            published range.
          </p>
          <Link className="button" to="/">
            Go to the latest day
          </Link>
        </EmptyState>
        {manifest.status === 'ready' ? (
          <DateScrubber days={manifest.data.days} current={date} />
        ) : null}
      </div>
    )
  }
  if (day.status === 'error') return <ErrorState message={day.error} retry={day.retry} />

  return (
    <div className="stack">
      <header className="day-header">
        <div>
          <p className="small muted">
            <Link to="/">Latest</Link> · Day page
          </p>
          <h1>{formatDate(day.data.day)}</h1>
        </div>
        <p className="muted">
          {day.data.events.length} {day.data.events.length === 1 ? 'event' : 'events'}
        </p>
      </header>
      <section className="card" aria-label={`Events on ${formatDate(day.data.day)}`}>
        {day.data.events.length ? (
          <RankedList events={day.data.events} />
        ) : (
          <EmptyState title="No spike events on this day">
            <p>No candidate crossed the detection threshold.</p>
          </EmptyState>
        )}
      </section>
      {manifest.status === 'ready' ? (
        <section className="card">
          <DateScrubber days={manifest.data.days} current={day.data.day} />
        </section>
      ) : null}
      <p className="small muted">
        <Link to={dayPath(day.data.day)}>Permalink for this day</Link>
      </p>
    </div>
  )
}
