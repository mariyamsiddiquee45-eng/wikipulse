import type { ReactNode } from 'react'

export function LoadingBlock({ lines = 5 }: { lines?: number }) {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="visually-hidden">Loading</span>
      <div className="skeleton skeleton-title" />
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton skeleton-line" aria-hidden="true" />
      ))}
    </div>
  )
}

export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className="error-box" role="alert">
      <h2>Could not load this page</h2>
      <p>{message}</p>
      <button type="button" className="button" onClick={retry}>
        Try again
      </button>
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty-box">
      <h2>{title}</h2>
      {children}
    </div>
  )
}
