const numberFormat = new Intl.NumberFormat('en-US')
const dateFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})

export function formatNumber(value: number): string {
  return numberFormat.format(value)
}

export function formatDate(iso: string): string {
  return dateFormat.format(new Date(`${iso}T00:00:00Z`))
}

export function hoursSince(iso: string | null, now: Date = new Date()): number | null {
  if (!iso) return null
  const then = Date.parse(iso.length === 10 ? `${iso}T00:00:00Z` : iso)
  if (Number.isNaN(then)) return null
  return (now.getTime() - then) / 3_600_000
}

export function isStale(dataThrough: string | null, now: Date = new Date()): boolean {
  const hours = hoursSince(dataThrough, now)
  return hours === null || hours > 48
}

export function truncate(value: string, length = 180): string {
  if (value.length <= length) return value
  return `${value.slice(0, length - 1).trimEnd()}…`
}

export function dayPath(day: string): string {
  return `/d/${day}`
}

export function eventPath(id: string): string {
  return `/e/${id}`
}

export function articlePath(slug: string): string {
  return `/a/${slug}`
}

export function searchPath(query: string): string {
  return `/search?q=${encodeURIComponent(query)}`
}

export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value))
}
