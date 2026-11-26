import { useEffect } from 'react'

type Meta = { title: string; description: string }

function upsert(selector: string, attributes: Record<string, string>): void {
  let element = document.head.querySelector<HTMLMetaElement>(selector)
  if (!element) {
    element = document.createElement('meta')
    document.head.append(element)
  }
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value)
}

export function usePageMeta({ title, description }: Meta): void {
  useEffect(() => {
    document.title = title
    upsert('meta[name="description"]', { name: 'description', content: description })
    upsert('meta[property="og:title"]', { property: 'og:title', content: title })
    upsert('meta[property="og:description"]', {
      property: 'og:description',
      content: description,
    })
    upsert('meta[property="og:type"]', { property: 'og:type', content: 'website' })
  }, [title, description])
}
