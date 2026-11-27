import { Link } from 'react-router-dom'
import type { Event } from '../data/types'
import { eventPath, formatNumber } from '../lib/format'
import { typeClass } from './typeClass'

export function RankedList({ events, limit }: { events: Event[]; limit?: number }) {
  const visible = limit ? events.slice(0, limit) : events
  const maximum = Math.max(1, ...visible.map((event) => event.score))

  return (
    <ol className="event-list">
      {visible.map((event, index) => {
        const members = event.members.map((member) => member.title)
        const extra = members.length - 3
        return (
          <li key={event.id} className="event-item event-enter">
            <span className="event-rank" aria-hidden="true">
              {index + 1}
            </span>
            <div>
              <h3 className="event-title">
                <Link to={eventPath(event.id)}>{event.label}</Link>
              </h3>
              <div className="event-meta">
                <span className={`badge ${typeClass(event.type)}`}>{event.type}</span>
                <span>
                  {event.members.length} {event.members.length === 1 ? 'article' : 'articles'}
                </span>
                <span>{formatNumber(event.members[0].views)} views on the top article</span>
              </div>
              <p className="event-members">
                {members.slice(0, 3).join(', ')}
                {extra > 0 ? ` and ${extra} more` : ''}
              </p>
            </div>
            <div className="event-score">
              <span>{formatNumber(Math.round(event.score))}</span>
              <progress className="score-progress" max={maximum} value={event.score}>
                {Math.round(event.score)}
              </progress>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
