import { Link, useNavigate } from 'react-router-dom'
import { dayPath, formatDate } from '../lib/format'

export function DateScrubber({ days, current }: { days: string[]; current?: string }) {
  const navigate = useNavigate()
  if (days.length === 0) return null
  const index = current ? days.indexOf(current) : days.length - 1
  const safeIndex = index >= 0 ? index : days.length - 1

  return (
    <div className="scrubber">
      <label htmlFor="day-scrubber">
        Browse the archive ({days.length} {days.length === 1 ? 'day' : 'days'})
      </label>
      <div className="scrubber-row">
        {safeIndex > 0 ? (
          <Link className="button" to={dayPath(days[safeIndex - 1])} aria-label="Previous day">
            Previous
          </Link>
        ) : (
          <span className="button muted" aria-disabled="true">
            Previous
          </span>
        )}
        <input
          id="day-scrubber"
          type="range"
          min={0}
          max={days.length - 1}
          step={1}
          value={safeIndex}
          onChange={(event) => {
            const day = days[Number(event.target.value)]
            if (day) navigate(dayPath(day))
          }}
          aria-valuetext={formatDate(days[safeIndex])}
        />
        {safeIndex < days.length - 1 ? (
          <Link className="button" to={dayPath(days[safeIndex + 1])} aria-label="Next day">
            Next
          </Link>
        ) : (
          <span className="button muted" aria-disabled="true">
            Next
          </span>
        )}
      </div>
    </div>
  )
}
