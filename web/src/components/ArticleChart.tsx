import { scaleLinear } from 'd3-scale'
import { area, curveMonotoneX, line } from 'd3-shape'
import type { Article } from '../data/types'
import { formatDate, formatNumber } from '../lib/format'

type Point = Article['history'][number]

const WIDTH = 760
const HEIGHT = 260
const MARGIN = { top: 16, right: 18, bottom: 34, left: 58 }

export function ArticleChart({ article }: { article: Article }) {
  const points = article.history
  if (points.length < 2) return null
  const x = scaleLinear()
    .domain([0, points.length - 1])
    .range([MARGIN.left, WIDTH - MARGIN.right])
  const maximum = Math.max(...points.map((point) => point.v), 1)
  const y = scaleLinear()
    .domain([0, maximum])
    .nice()
    .range([HEIGHT - MARGIN.bottom, MARGIN.top])
  const linePath = line<Point>()
    .x((_, index) => x(index))
    .y((point) => y(point.v))
    .curve(curveMonotoneX)(points)
  const areaPath = area<Point>()
    .x((_, index) => x(index))
    .y0(y(0))
    .y1((point) => y(point.v))
    .curve(curveMonotoneX)(points)
  const spikes = points.map((point, index) => ({ point, index })).filter((entry) => entry.point.s)

  return (
    <figure className="chart-card">
      <svg
        className="chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Daily views from ${formatDate(points[0].d)} to ${formatDate(
          points[points.length - 1].d,
        )}. Peak ${formatNumber(maximum)} views.`}
      >
        {[0, 0.5, 1].map((fraction) => {
          const value = Math.round(maximum * fraction)
          return (
            <g key={fraction}>
              <line
                className="chart-axis"
                x1={MARGIN.left}
                x2={WIDTH - MARGIN.right}
                y1={y(value)}
                y2={y(value)}
              />
              <text className="chart-label" x={MARGIN.left - 8} y={y(value) + 3} textAnchor="end">
                {formatNumber(value)}
              </text>
            </g>
          )
        })}
        {areaPath ? <path className="chart-area" d={areaPath} /> : null}
        {linePath ? <path className="chart-line" d={linePath} /> : null}
        {spikes.map((entry) => (
          <circle
            key={entry.point.d}
            className="chart-spike"
            cx={x(entry.index)}
            cy={y(entry.point.v)}
            r={4}
          >
            <title>{`Spike on ${formatDate(entry.point.d)}`}</title>
          </circle>
        ))}
        <text className="chart-label" x={MARGIN.left} y={HEIGHT - 10}>
          {formatDate(points[0].d)}
        </text>
        <text className="chart-label" x={WIDTH - MARGIN.right} y={HEIGHT - 10} textAnchor="end">
          {formatDate(points[points.length - 1].d)}
        </text>
      </svg>
      <figcaption className="visually-hidden">
        Daily pageviews for {article.title} with spike markers.
      </figcaption>
    </figure>
  )
}
