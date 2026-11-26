# Static data contract

`schema_version` is 1. The JSON Schemas in `schemas/` are the source of truth; exported files
are validated against them before the published directory is replaced.

## Files

```
manifest.json                   archive index and file hashes
status.json                      last run, health, warnings
methods.json                     detector, classifier and limitations
days/YYYY-MM-DD.json             one published day
articles/<shard>/<slug>.json     history for every exported article
search/<prefix>.json             search index shard
```

`<shard>` and `<prefix>` are the first two characters of the slug. Slugs are lowercase
ASCII with hyphens; collisions receive a short hash suffix.

### manifest.json

- `schema_version`: 1
- `generated_at`: deterministic timestamp derived from `data_through`
- `data_through`: last complete pageview day
- `first_day`, `last_day`: first and last day with a day file
- `days`: every published day, for the archive scrubber
- `counts`: days, events, articles, search shards, files
- `files`: path, SHA-256, byte size and gzip size for every published file except the
  manifest itself

### Day file

Each event has a stable `id` formatted `YYYYMMDD-` plus 12 hex characters, a human label,
score, spike type, member articles and a short attributed extract. Members carry views,
baseline, z-score, class probability and spike type. Day files must stay under 150 KB
gzipped; the export fails otherwise.

### Article file

Compact daily history (`d`, `v`, `s` where `s` marks a spike day), spike records, title,
description, plain-text extract, source URL and first/last day. Article files are capped at
12,000 by highest spike score to stay under the Cloudflare Pages free file limit.

### Search shard

Articles whose slug starts with the shard prefix: slug, title, description, source URL and
last active day. The client loads only the shard for the first two normalized characters of
the query.

### Methods

Detector thresholds, label counts and classes, the latest classifier metadata and metrics
when one exists, and the limitation list shown on the site.

## Determinism

JSON is serialized with sorted keys, compact separators and a final newline. Timestamps are
derived from the data, not the wall clock. Identical inputs produce identical bytes, and a
test exports twice and compares every file.

## Compatibility

A breaking change requires a `schema_version` bump, a migration note in this file and a
release note. Additive changes that old clients can ignore do not need a bump, but the
manifest hash list still changes.

## Caching

- Hashed assets: one year, immutable.
- JSON data: five minutes.
- `theme.js`: five minutes.
- The manifest is the cache-busting source of truth for the frontend.
