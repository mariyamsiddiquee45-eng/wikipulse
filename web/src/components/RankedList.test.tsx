import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Event } from '../data/types'
import { RankedList } from './RankedList'

const event: Event = {
  id: '20261125-abcdef123456',
  label: 'Space mission',
  score: 4200,
  type: 'Flash',
  members: [
    {
      article: 'Space_A',
      title: 'Space A',
      slug: 'space-a',
      views: 120000,
      baseline: 2000,
      z_score: 40.2,
      class_probability: null,
      type: 'Flash',
      score: 4200,
    },
  ],
  extract: { text: null, url: 'https://en.wikipedia.org/wiki/Space_A', license: 'CC BY-SA 4.0' },
}

describe('RankedList', () => {
  it('links each event and shows its type', () => {
    render(
      <MemoryRouter>
        <RankedList events={[event]} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Space mission' })).toHaveAttribute(
      'href',
      '/e/20261125-abcdef123456',
    )
    expect(screen.getByText('Flash')).toBeInTheDocument()
    expect(screen.getByText('1 article')).toBeInTheDocument()
    expect(screen.getByText(/120,000 views/)).toBeInTheDocument()
  })
})
