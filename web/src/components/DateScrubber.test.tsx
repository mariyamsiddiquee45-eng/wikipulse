import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { DateScrubber } from './DateScrubber'

function Location() {
  const location = useLocation()
  return <p data-testid="location">{location.pathname}</p>
}

describe('DateScrubber', () => {
  it('navigates to the chosen day', () => {
    render(
      <MemoryRouter initialEntries={['/d/2026-11-25']}>
        <DateScrubber days={['2026-11-23', '2026-11-24', '2026-11-25']} current="2026-11-25" />
        <Location />
      </MemoryRouter>,
    )
    const slider = screen.getByLabelText(/Browse the archive/)
    fireEvent.change(slider, { target: { value: '0' } })
    expect(screen.getByTestId('location')).toHaveTextContent('/d/2026-11-23')
    expect(screen.getByRole('link', { name: 'Previous day' })).toHaveAttribute(
      'href',
      '/d/2026-11-24',
    )
  })

  it('renders nothing without days', () => {
    const { container } = render(
      <MemoryRouter>
        <DateScrubber days={[]} />
      </MemoryRouter>,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
