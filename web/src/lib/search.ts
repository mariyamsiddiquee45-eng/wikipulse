export function slugify(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
}

export function searchPrefix(query: string): string | null {
  const slug = slugify(query.trim())
  if (slug.length < 2) return null
  return slug.slice(0, 2)
}
