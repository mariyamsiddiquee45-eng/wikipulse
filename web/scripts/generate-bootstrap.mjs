import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dataDir = resolve(import.meta.dirname, '../public/data')
const output = resolve(import.meta.dirname, '../public/data/bootstrap.js')
const manifestPath = resolve(dataDir, 'manifest.json')

let payload = 'null'
if (existsSync(manifestPath)) {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
  let latestDay = null
  if (manifest.last_day) {
    const dayPath = resolve(dataDir, 'days', `${manifest.last_day}.json`)
    if (existsSync(dayPath)) latestDay = JSON.parse(readFileSync(dayPath, 'utf8'))
  }
  payload = JSON.stringify({ manifest, latestDay })
}
mkdirSync(dataDir, { recursive: true })
writeFileSync(output, `window.__WIKIPULSE_BOOTSTRAP__ = ${payload};\n`, 'utf8')
console.log('Wrote the synchronous bootstrap for the latest day.')
