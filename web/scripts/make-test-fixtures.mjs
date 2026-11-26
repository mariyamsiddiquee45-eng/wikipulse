import { createHash } from 'node:crypto'
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { gzipSync } from 'node:zlib'

const root = resolve(import.meta.dirname, '../test-fixtures')
rmSync(root, { recursive: true, force: true })
mkdirSync(root, { recursive: true })

const day = '2026-11-25'
const moonUrl = 'https://en.wikipedia.org/wiki/Moon'
const spacexUrl = 'https://en.wikipedia.org/wiki/SpaceX'
const license = 'CC BY-SA 4.0'

function history(values) {
  return values.map((value, index) => ({
    d: new Date(Date.UTC(2026, 9, 27 + index)).toISOString().slice(0, 10),
    v: value,
    s: index === values.length - 1,
  }))
}

function write(path, value) {
  const full = join(root, path)
  mkdirSync(resolve(full, '..'), { recursive: true })
  writeFileSync(full, `${JSON.stringify(value)}\n`, 'utf8')
}

const moonHistory = history([
  ...Array.from({ length: 29 }, (_, index) => 1000 + ((index * 37) % 40)),
  180000,
])
const spacexHistory = history([
  ...Array.from({ length: 29 }, (_, index) => 800 + ((index * 29) % 30)),
  42000,
])

write(`days/${day}.json`, {
  schema_version: 1,
  day,
  events: [
    {
      id: '20261125-aaaaaaaaaaaa',
      label: 'Moon',
      score: 1200,
      type: 'Flash',
      members: [
        {
          article: 'Moon',
          title: 'Moon',
          slug: 'moon',
          views: 180000,
          baseline: 1000,
          z_score: 30.2,
          class_probability: null,
          type: 'Flash',
          score: 1200,
        },
      ],
      extract: {
        text: "The Moon is Earth's only natural satellite.",
        url: moonUrl,
        license,
      },
    },
    {
      id: '20261125-bbbbbbbbbbbb',
      label: 'SpaceX',
      score: 800,
      type: 'Slow burn',
      members: [
        {
          article: 'SpaceX',
          title: 'SpaceX',
          slug: 'spacex',
          views: 42000,
          baseline: 800,
          z_score: 12.4,
          class_probability: null,
          type: 'Slow burn',
          score: 800,
        },
      ],
      extract: {
        text: 'SpaceX is an American aerospace manufacturer.',
        url: spacexUrl,
        license,
      },
    },
  ],
})

write('articles/mo/moon.json', {
  schema_version: 1,
  article: 'Moon',
  title: 'Moon',
  slug: 'moon',
  url: moonUrl,
  description: 'Natural satellite orbiting Earth',
  extract: "The Moon is Earth's only natural satellite.",
  first_day: moonHistory[0].d,
  last_day: day,
  history: moonHistory,
  spikes: [{ day, type: 'Flash', z_score: 30.2, score: 1200 }],
})

write('articles/sp/spacex.json', {
  schema_version: 1,
  article: 'SpaceX',
  title: 'SpaceX',
  slug: 'spacex',
  url: spacexUrl,
  description: 'American aerospace manufacturer',
  extract: 'SpaceX is an American aerospace manufacturer.',
  first_day: spacexHistory[0].d,
  last_day: day,
  history: spacexHistory,
  spikes: [{ day, type: 'Slow burn', z_score: 12.4, score: 800 }],
})

write('search/mo.json', {
  schema_version: 1,
  prefix: 'mo',
  articles: [
    {
      slug: 'moon',
      title: 'Moon',
      description: 'Natural satellite orbiting Earth',
      url: moonUrl,
      last_day: day,
    },
  ],
})

write('search/sp.json', {
  schema_version: 1,
  prefix: 'sp',
  articles: [
    {
      slug: 'spacex',
      title: 'SpaceX',
      description: 'American aerospace manufacturer',
      url: spacexUrl,
      last_day: day,
    },
  ],
})

write('methods.json', {
  schema_version: 1,
  generated_at: `${day}T00:00:00Z`,
  labels: 0,
  classes: [],
  detector: { z_threshold: 3.0, minimum_views: 1000 },
  classifier: null,
  limitations: [
    'Human labels: 0 of the 300 target.',
    'Edit-surge data publishes about two months late, so recent spikes lack it.',
  ],
})

write('status.json', {
  schema_version: 1,
  last_run: null,
  ok: true,
  warnings: ['Test fixture data.'],
  data_through: day,
})

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = join(directory, entry.name)
    return entry.isDirectory() ? walk(full) : [full]
  })
}

const files = walk(root)
  .map((full) => {
    const bytes = readFileSync(full)
    return {
      path: relative(root, full).replaceAll('\\', '/'),
      sha256: createHash('sha256').update(bytes).digest('hex'),
      bytes: bytes.length,
      gzip_bytes: gzipSync(bytes).length,
    }
  })
  .sort((left, right) => left.path.localeCompare(right.path))

write('manifest.json', {
  schema_version: 1,
  generated_at: `${day}T00:00:00Z`,
  data_through: day,
  first_day: day,
  last_day: day,
  days: [day],
  counts: {
    days: 1,
    events: 2,
    articles: 2,
    search_shards: 2,
    files: files.length,
  },
  files,
})

console.log(`Wrote ${files.length + 1} test fixture files to ${root}`)
