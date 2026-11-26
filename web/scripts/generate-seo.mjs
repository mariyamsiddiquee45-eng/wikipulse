import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const siteUrl = (process.env.WIKIPULSE_SITE_URL || '').replace(/\/$/, '')
if (!siteUrl) {
  console.log('WIKIPULSE_SITE_URL is empty; skipping sitemap and robots.')
  process.exit(0)
}
const exportDir = resolve(import.meta.dirname, '../../data/export')
const manifestPath = resolve(exportDir, 'manifest.json')
if (!existsSync(manifestPath)) {
  console.warn('No manifest found; skipping sitemap and robots.')
  process.exit(0)
}
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
const urls = ['/', '/methods', '/about', '/privacy']
for (const day of manifest.days) {
  urls.push(`/d/${day}`)
  const dayFile = JSON.parse(readFileSync(resolve(exportDir, 'days', `${day}.json`), 'utf8'))
  for (const event of dayFile.events) urls.push(`/e/${event.id}`)
}
const sitemap = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...urls.map((path) => `  <url><loc>${siteUrl}${path}</loc></url>`),
  '</urlset>',
  '',
].join('\n')
writeFileSync(resolve(import.meta.dirname, '../public/sitemap.xml'), sitemap, 'utf8')
writeFileSync(
  resolve(import.meta.dirname, '../public/robots.txt'),
  `User-agent: *\nAllow: /\nSitemap: ${siteUrl}/sitemap.xml\n`,
  'utf8',
)
console.log(`Wrote sitemap with ${urls.length} URLs.`)
