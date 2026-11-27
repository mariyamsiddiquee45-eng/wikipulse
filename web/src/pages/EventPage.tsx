import { motion, useReducedMotion } from 'framer-motion'
import { Link, useParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingBlock } from '../components/States'
import { typeClass } from '../components/typeClass'
import { useDay } from '../data/hooks'
import { articlePath, dayPath, formatDate, formatNumber } from '../lib/format'
import { usePageMeta } from '../lib/usePageMeta'

const ID_PATTERN = /^(\d{4})(\d{2})(\d{2})-/

export function EventPage() {
  const { id = '' } = useParams()
  const reduceMotion = useReducedMotion()
  const match = ID_PATTERN.exec(id)
  const day = match ? `${match[1]}-${match[2]}-${match[3]}` : 'invalid'
  const resource = useDay(day)
  const event =
    resource.status === 'ready' ? resource.data.events.find((item) => item.id === id) : undefined
  usePageMeta({
    title: event ? `${event.label} - WikiPulse` : 'Event not found - WikiPulse',
    description: event
      ? `${event.label}: ${event.members.length} Wikipedia articles spiked on ${formatDate(day)}.`
      : 'This event page does not exist.',
  })

  if (!match) {
    return (
      <EmptyState title="Event not found">
        <p>The event identifier is not valid.</p>
        <Link className="button" to="/">
          Go to the latest day
        </Link>
      </EmptyState>
    )
  }
  if (resource.status === 'loading') return <LoadingBlock lines={8} />
  if (resource.status === 'error' && resource.notFound) {
    return (
      <EmptyState title="Event not found">
        <p>No day file exists for this event.</p>
        <Link className="button" to={dayPath(day)}>
          Open {formatDate(day)}
        </Link>
      </EmptyState>
    )
  }
  if (resource.status === 'error') {
    return <ErrorState message={resource.error} retry={resource.retry} />
  }
  if (!event) {
    return (
      <EmptyState title="Event not found">
        <p>The event is not present in the {formatDate(day)} file.</p>
        <Link className="button" to={dayPath(day)}>
          See all events on {formatDate(day)}
        </Link>
      </EmptyState>
    )
  }

  return (
    <article className="stack">
      <header>
        <p className="small muted">
          <Link to={dayPath(day)}>{formatDate(day)}</Link> · Event
        </p>
        <h1>{event.label}</h1>
        <div className="row">
          <span className={`badge ${typeClass(event.type)}`}>{event.type}</span>
          <span className="muted small">
            Spike score {formatNumber(Math.round(event.score))} · {event.members.length}{' '}
            {event.members.length === 1 ? 'article' : 'articles'}
          </span>
        </div>
      </header>

      {event.extract.text ? (
        <section className="card">
          <blockquote className="extract">{event.extract.text}</blockquote>
          <p className="attribution">
            Text from{' '}
            <a href={event.extract.url} target="_blank" rel="noreferrer noopener">
              the source Wikipedia article
            </a>{' '}
            · {event.extract.license}
          </p>
        </section>
      ) : null}

      <section className="card" aria-labelledby="members-heading">
        <h2 id="members-heading">Articles in this event</h2>
        <ul className="member-list">
          {event.members.map((member, index) => (
            <motion.li
              className="member"
              key={member.slug}
              initial={reduceMotion ? false : { opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: reduceMotion ? 0 : index * 0.03, duration: 0.2 }}
            >
              <div>
                <div className="member-title">
                  <Link to={articlePath(member.slug)}>{member.title}</Link>
                </div>
                <div className="member-stats">
                  <span>{formatNumber(member.views)} views</span>
                  <span>
                    baseline{' '}
                    {member.baseline === null
                      ? 'unknown'
                      : formatNumber(Math.round(member.baseline))}
                  </span>
                  <span>
                    z-score {member.z_score === null ? 'unknown' : member.z_score.toFixed(1)}
                  </span>
                  <span className={`badge ${typeClass(member.type)}`}>{member.type}</span>
                  {member.class_probability === null ? null : (
                    <span>event likelihood {Math.round(member.class_probability * 100)}%</span>
                  )}
                </div>
              </div>
              <Link className="button" to={articlePath(member.slug)}>
                View history
              </Link>
            </motion.li>
          ))}
        </ul>
      </section>
      <p className="small muted">
        <Link to="/">Latest day</Link> · <Link to="/methods">How events are built</Link>
      </p>
    </article>
  )
}
