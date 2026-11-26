# Architecture

WikiPulse has two halves: a Python batch pipeline and a static React site. There is no
runtime server of our own.

```
Wikimedia APIs
      |
      v
pipeline ingest -> cache + DuckDB -> candidates -> history
      |                                  |
      v                                  v
   features -> rule detector -> spikes -> classifier -> events
                                              |            |
                                              v            v
                                          schemas -> JSON export -> Cloudflare Pages
                                                                     |
                                                                     v
                                                                 React app
```

## Pipeline

- `client.py` is the only network boundary. It sends `WikiPulse/<version> (<contact>)`,
  caches every response by request key, waits between requests, and backs off on 429 and
  5xx with a hard retry cap. Completed past days are immutable.
- `ingest.py` writes top pageviews and daily edit analytics. A day is complete only when
  both sources are present. Edit analytics publish about two months late, so recent days
  stay retryable instead of being marked complete with zero edits.
- `candidates.py` selects new entrants to the top 1000, large rank movers and the recent
  spike watch list. History is fetched only for those articles.
- `features.py` computes the robust baseline, z-score, STL residual, year-over-year ratio,
  spike shape and rank features. Missing days are excluded, never imputed.
- `classifier.py` trains and evaluates logistic regression and LightGBM with expanding
  time windows. Without enough human labels, export uses the rule-based score.
- `embeddings.py` caches one all-MiniLM-L6-v2 vector per article (title plus summary).
- `events.py` clusters a day's spikes with HDBSCAN, keeps singletons as single-article
  events, and names each event after its highest-scoring member.
- `export.py` builds a staging directory, validates every document against `schemas/`,
  enforces the day-file gzip budget, hashes every file, and only then replaces the
  published export.

## Storage

DuckDB holds the working set; Parquet snapshots are written beside it.

| Table | Key | Purpose |
| --- | --- | --- |
| `top_daily` | day, article | top 1000 pageviews |
| `article_daily` | day, article | per-article user views |
| `edits` | day, article | daily top-100 edited pages |
| `article_meta` | article | title, description, extract, URL |
| `days` | day | completeness and failure note |
| `spikes` | spike_id | detected features and scores |
| `events` | event_id | clustered events and members |
| `runs` | run_id | start, finish, counts, failures |

Raw responses live under `data/cache/`; DuckDB, Parquet, embeddings, models, reports and
exports all stay under `data/`. Nothing under `data/` is committed.

## Frontend

Vite builds a React app with route-level chunks. The first paint of the home page is
bootstrapped from `data/bootstrap.js`, a generated synchronous copy of the manifest and the
latest day, so the ranked list does not appear after a layout shift. Every other route
fetches its JSON on demand.

Data files live under `/data/` on the same origin. The manifest drives cache busting and
the archive scrubber. Search is sharded by the first two characters of the slug and indexed
with MiniSearch in the browser.

The theme is a token set in `web/src/styles/tokens.css`. `public/theme.js` applies a stored
choice before React starts, so there is no flash. No inline scripts or styles are used.

## Hosting and security

- Cloudflare Pages, direct upload of `web/dist`.
- `web/public/_headers` sets CSP without `unsafe-inline`, clickjacking protection, a
  restrictive permissions policy, immutable hashed assets and short JSON caching.
- No CORS headers are added; all data is same-origin.
- The site makes no third-party requests. Fonts are system or self-hosted.

## Budget

- Target host: about 8 GB RAM, dual-core i3, no GPU.
- Peak pipeline RAM stays below 4 GB; PyTorch is CPU-only in the container.
- Incremental daily compute target: under 15 minutes excluding rate-limit waits.
- Initial JavaScript is about 154 KB transfer on the home page.
- Lighthouse on the desktop profile: performance 1.0, accessibility 1.0, LCP about 250 ms,
  CLS 0.

## Repository map

```
pipeline/  Python package, tests and fixtures
web/       React app, unit, browser and visual tests, test data
schemas/   JSON Schemas, the export contract
docs/      this file, methods, runbook, data contract
labels/    labels.csv
scripts/   repository helpers
docker/    pipeline and preview images
```
