# WikiPulse

What people suddenly became curious about on English Wikipedia, once a day, grouped into
real-world events.

WikiPulse is a static site. A Python pipeline turns Wikimedia pageview data into JSON
files; a React app reads them from a CDN. There is no runtime server, no account, no
cookie, and no analytics.

Not affiliated with Wikipedia or the Wikimedia Foundation.

## Status

Phase 0, foundation. The product does not run yet.

## Layout

```
pipeline/   Python package (src/wikipulse) and tests
web/        Vite, React, TypeScript app
labels/     labels.csv, the only committed data
docs/       build prompt, data sources, later architecture and runbook
schemas/    JSON Schemas, the source of truth for exported data
scripts/    development helpers
data/       generated, gitignored
```

## Development

Requirements: Python 3.12 and uv, Node.js 24 and npm.

```sh
cd pipeline
uv sync
uv run pytest

cd ../web
npm ci
npm run check
```

## Data

Pageview and edit data come from the Wikimedia Analytics API and are CC0. Article extracts
come from Wikipedia and are CC BY-SA; the site attributes and links them. No Wikipedia
logos, marks, or article images are used.

See `docs/data-sources.md` for the verified endpoints and response shapes.

## License

No license is granted for this repository. Third-party content keeps its own terms.
