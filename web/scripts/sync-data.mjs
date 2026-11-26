import { cpSync, existsSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'

const source = resolve(import.meta.dirname, '../../data/export')
const target = resolve(import.meta.dirname, '../public/data')

if (!existsSync(source)) {
  console.warn('No data/export found; the site will build without data.')
  process.exit(0)
}
rmSync(target, { recursive: true, force: true })
cpSync(source, target, { recursive: true })
console.log(`Copied export data to ${target}`)
