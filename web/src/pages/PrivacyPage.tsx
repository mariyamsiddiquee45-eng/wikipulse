import { Link } from 'react-router-dom'
import { usePageMeta } from '../lib/usePageMeta'

export function PrivacyPage() {
  usePageMeta({
    title: 'Privacy - WikiPulse',
    description: 'WikiPulse has no cookies, tracking, accounts, or stored user data.',
  })
  return (
    <article className="prose stack">
      <h1>Privacy</h1>
      <p>WikiPulse is a static site. It does not run a server of its own.</p>
      <ul>
        <li>No cookies.</li>
        <li>No analytics or tracking scripts.</li>
        <li>No accounts and no stored user input.</li>
        <li>
          The theme preference is stored in your browser's local storage only, on your device.
          Clearing site data removes it.
        </li>
        <li>No third-party requests are made by the site.</li>
      </ul>
      <p>
        The site is served from Cloudflare Pages. Cloudflare processes standard request logs as the
        hosting provider; WikiPulse does not add identifying data to them.
      </p>
      <p className="small muted">
        <Link to="/about">About the data and attribution</Link>
      </p>
    </article>
  )
}
