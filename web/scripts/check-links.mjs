import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const exportDir = resolve(import.meta.dirname, '../../data/export')
const publicDir = resolve(import.meta.dirname, '../public/data')
const dataDir = existsSync(join(publicDir, 'manifest.json')) ? publicDir : exportDir
const manifestPath = join(dataDir, 'manifest.json')
if (!existsSync(manifestPath)) {
  console.warn('No export data; run wikipulse export first.')
  process.exit(0)
}
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
const failures = []
const articleFiles = new Set()

for (const record of manifest.files) {
  if (!existsSync(join(dataDir, record.path))) {
    failures.push(`manifest entry missing: ${record.path}`)
  }
}

for (const day of manifest.days) {
  const dayPath = join(dataDir, 'days', `${day}.json`)
  if (!existsSync(dayPath)) {
    failures.push(`day file missing: ${day}`)
    continue
  }
  const document = JSON.parse(readFileSync(dayPath, 'utf8'))
  for (const event of document.events) {
    for (const member of event.members) {
      const articlePath = join(dataDir, 'articles', member.slug.slice(0, 2), `${member.slug}.json`)
      articleFiles.add(articlePath)
      if (!existsSync(articlePath)) {
        failures.push(`${day} event ${event.id} points at missing article ${member.slug}`)
      }
    }
  }
}

for (const articlePath of articleFiles) {
  const article = JSON.parse(readFileSync(articlePath, 'utf8'))
  if (!article.url.startsWith('https://en.wikipedia.org/wiki/')) {
    failures.push(`${article.slug} has an unexpected source URL: ${article.url}`)
  }
}

if (failures.length) {
  console.error(failures.join('\n'))
  process.exit(1)
}
console.log(`Checked ${manifest.days.length} days and ${articleFiles.size} article links.`)
