import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { compile } = require('json-schema-to-typescript')

const schemaDir = resolve(import.meta.dirname, '../../schemas')
const output = resolve(import.meta.dirname, '../src/types/generated.ts')
const names = {
  article: 'Article',
  day: 'Day',
  manifest: 'Manifest',
  methods: 'Methods',
  search: 'SearchShard',
  status: 'Status',
}

const blocks = ['/* Generated from schemas/ by scripts/generate-types.mjs. Do not edit. */', '']
for (const [file, name] of Object.entries(names)) {
  const schema = JSON.parse(readFileSync(join(schemaDir, `${file}.schema.json`), 'utf8'))
  const types = await compile(schema, name, {
    bannerComment: '',
    additionalProperties: false,
  })
  blocks.push(types.trim(), '')
}
mkdirSync(resolve(import.meta.dirname, '../src/types'), { recursive: true })
writeFileSync(output, blocks.join('\n'), 'utf8')
console.log(`Wrote ${output}`)
