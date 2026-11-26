import { motion, useReducedMotion } from 'framer-motion'
import { hierarchy, pack, type HierarchyCircularNode } from 'd3-hierarchy'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Event } from '../data/types'
import { eventPath } from '../lib/format'
import { typeClass } from './typeClass'

type BubbleDatum = { event?: Event; children?: BubbleDatum[] }

const WIDTH = 600
const HEIGHT = 380

export function BubblePack({ events }: { events: Event[] }) {
  const navigate = useNavigate()
  const reduceMotion = useReducedMotion()
  const root = useMemo(() => {
    const data: BubbleDatum = { children: events.map((event) => ({ event })) }
    const layout = pack<BubbleDatum>().size([WIDTH, HEIGHT]).padding(3)
    return layout(hierarchy(data).sum((node) => node.event?.score ?? 0))
  }, [events])
  const leaves = root.leaves() as HierarchyCircularNode<BubbleDatum>[]

  return (
    <svg
      className="bubble-svg"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="group"
      aria-label={`${events.length} events sized by spike score`}
    >
      {leaves.map((leaf, index) => {
        const event = leaf.data.event
        if (!event) return null
        const label = event.label
        const short = label.length > Math.max(8, leaf.r / 3.4) ? `${label.slice(0, 14)}…` : label
        return (
          <motion.g
            key={event.id}
            role="link"
            tabIndex={0}
            aria-label={`${event.label}, ${event.type}, ${event.members.length} ${
              event.members.length === 1 ? 'article' : 'articles'
            }`}
            onClick={() => navigate(eventPath(event.id))}
            onKeyDown={(eventKey) => {
              if (eventKey.key === 'Enter' || eventKey.key === ' ') {
                eventKey.preventDefault()
                navigate(eventPath(event.id))
              }
            }}
            initial={reduceMotion ? false : { opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: reduceMotion ? 0 : index * 0.015, duration: 0.3 }}
            style={{ cursor: 'pointer' }}
          >
            <circle
              className={`bubble ${typeClass(event.type)}`}
              cx={leaf.x}
              cy={leaf.y}
              r={leaf.r}
            />
            {leaf.r > 26 ? (
              <text
                className="bubble-label"
                x={leaf.x}
                y={leaf.y + 4}
                textAnchor="middle"
                aria-hidden="true"
              >
                {short}
              </text>
            ) : null}
            <title>{`${event.label} (${event.type})`}</title>
          </motion.g>
        )
      })}
    </svg>
  )
}
