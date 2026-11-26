import { Link } from 'react-router-dom'
import { usePageMeta } from '../lib/usePageMeta'

export function NotFoundPage() {
  usePageMeta({
    title: 'Page not found - WikiPulse',
    description: 'This page does not exist.',
  })
  return (
    <div className="centered stack">
      <p className="muted">404</p>
      <h1>Page not found</h1>
      <p>The page you asked for does not exist or is not part of this site.</p>
      <p>
        <Link className="button primary" to="/">
          Go to the latest day
        </Link>
      </p>
    </div>
  )
}
