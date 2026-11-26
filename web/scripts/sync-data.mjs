import { cpSync, existsSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'

const exportSource = resolve(import.meta.dirname, '../../data/export')
const fixtureSource = resolve(import.meta.dirname, '../test-fixtures')
const target = resolve(import.meta.dirname, '../public/data')

const source = existsSync(exportSource) ? exportSource : fixtureSource
rmSync(target, { recursive: true, force: true })
cpSync(source, target, { recursive: true })
if (source === fixtureSource) {
  console.warn('No data/export found; using committed test fixtures.')
} else {
  console.log(`Copied export data to ${target}`)
}
