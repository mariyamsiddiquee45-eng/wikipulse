# WikiPulse

What people suddenly became curious about on English Wikipedia, once a day, grouped into
real-world events.

WikiPulse is a static site. A Python pipeline turns Wikimedia pageview data into JSON
files; a React app reads them from a CDN. There is no runtime server, no account, no
cookie, and no analytics.

Not affiliated with Wikipedia or the Wikimedia Foundation.

## Status

The pipeline and site are built through Phase 11. The repository ships with a 28-day local
export; generated data is never committed. A 331-label pilot trained a classifier, but it
does not beat the rule baseline and is not applied. The Methods page states this. More
non-event labels are needed.

## Layout

```
pipeline/   Python package (src/wikipulse) and tests
web/        Vite, React, TypeScript app, unit, browser and visual tests
labels/     labels.csv, the only committed data
docs/       architecture, methods, runbook, data contract, sources
schemas/    JSON Schemas, the source of truth for exported data
scripts/    repository helpers
docker/     pipeline and preview images
data/       generated, gitignored
```

## Quickstart

Requirements: Python 3.12 with uv, Node.js 24 with npm.

```sh
cp .env.example .env
# set WIKIPULSE_CONTACT to a real address

uv sync --project pipeline
npm ci --prefix web

# build the demo window (see docs/runbook.md for the full five years)
uv run --project pipeline wikipulse ingest --start 2026-11-18 --end 2026-11-25
uv run --project pipeline wikipulse history --start 2026-11-23 --end 2026-11-25 --lookback 120
uv run --project pipeline wikipulse detect --start 2026-11-23 --end 2026-11-25
uv run --project pipeline wikipulse cluster --start 2026-11-23 --end 2026-11-25
uv run --project pipeline wikipulse export

npm run dev --prefix web
```

If no export exists, the web build and tests use committed test fixtures.

## Checks

```sh
cd pipeline
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run pip-audit --skip-editable

cd ../web
npm run check
npx playwright test
npx lhci autorun
```

Lighthouse on the built home page: performance 1.0, accessibility 1.0, LCP about 250 ms,
CLS 0, about 154 KB of script transferred.

## Data and attribution

Pageview and edit data come from the Wikimedia Analytics API and are CC0. Article extracts
come from Wikipedia and are CC BY-SA 4.0; the site attributes and links them. No Wikipedia
logos, marks, or article images are used.

See `docs/data-sources.md` for the verified endpoints and response shapes, and
`docs/methods.md` for what is measured and what is still missing.

## Deployment

Direct upload to Cloudflare Pages. See `docs/runbook.md`.

```sh
npm run build --prefix web
npx wrangler pages deploy web/dist --project-name wikipulse
```

## Containers

```sh
docker compose build
docker compose run --rm pipeline run-daily
docker compose up preview
```

The pipeline image uses CPU-only PyTorch, a pinned base image and a non-root user.

## License

No license is granted for this repository. Third-party content keeps its own terms.
