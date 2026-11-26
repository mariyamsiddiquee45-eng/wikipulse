import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../src/assets/svg')
const failures = []
const limit = 30 * 1024

function walk(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      walk(path)
      continue
    }
    if (!entry.name.endsWith('.svg')) continue
    const text = readFileSync(path, 'utf8')
    const size = statSync(path).size
    if (size > limit) failures.push(`${path}: ${size} bytes exceeds 30 KB`)
    if (/<script\b/i.test(text)) failures.push(`${path}: script element`)
    if (/\son[a-z]+\s*=/i.test(text)) failures.push(`${path}: event handler attribute`)
    if (/\b(?:xlink:)?href\s*=\s*["'](?:https?:)?\/\//i.test(text)) {
      failures.push(`${path}: external reference`)
    }
  }
}

walk(root)
if (failures.length) {
  console.error(failures.join('\n'))
  process.exit(1)
}
console.log('SVG assets passed the safety checks.')
