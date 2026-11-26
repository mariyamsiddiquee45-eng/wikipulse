import { useState, type FormEvent } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useManifest } from '../data/hooks'
import { formatDate, isStale, searchPath } from '../lib/format'
import { LogoMark, SearchIcon } from './icons'
import { ThemeToggle } from './ThemeToggle'

function StaleBanner() {
  const manifest = useManifest()
  if (manifest.status !== 'ready') return null
  if (!isStale(manifest.data.data_through)) return null
  return (
    <div className="container">
      <p className="notice" role="status">
        Data is current through {formatDate(manifest.data.data_through ?? '')}. The newest complete
        day is more than 48 hours old.
      </p>
    </div>
  )
}

export function Layout() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (trimmed) navigate(searchPath(trimmed))
  }

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container header-inner">
          <Link className="brand" to="/">
            <LogoMark className="brand-mark" />
            WikiPulse
          </Link>
          <nav className="site-nav" aria-label="Main">
            <NavLink to="/" end>
              Today
            </NavLink>
            <NavLink to="/methods">Methods</NavLink>
            <NavLink to="/about">About</NavLink>
          </nav>
          <form className="header-search" role="search" onSubmit={submit}>
            <label className="visually-hidden" htmlFor="site-search">
              Search articles
            </label>
            <input
              id="site-search"
              name="q"
              type="search"
              placeholder="Search articles"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <button className="theme-toggle" type="submit" aria-label="Search">
              <SearchIcon />
            </button>
          </form>
          <ThemeToggle />
        </div>
      </header>
      <StaleBanner />
      <main id="main-content" className="page-main">
        <div className="container">
          <Outlet />
        </div>
      </main>
      <footer className="footer">
        <div className="container footer-grid">
          <div>
            <p>WikiPulse shows what people suddenly became curious about on English Wikipedia.</p>
            <p>
              Pageview and edit data from Wikimedia (CC0). Article text CC BY-SA 4.0, linked to its
              source.
            </p>
          </div>
          <div>
            <p>
              <Link to="/methods">Methods</Link> · <Link to="/about">About</Link> ·{' '}
              <Link to="/privacy">Privacy</Link>
            </p>
            <p>Not affiliated with Wikipedia or the Wikimedia Foundation.</p>
          </div>
        </div>
      </footer>
    </>
  )
}
