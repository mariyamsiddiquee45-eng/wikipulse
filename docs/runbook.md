# Runbook

## Requirements

- Python 3.12 with uv 0.13 or newer.
- Node.js 24 with npm 11.
- About 10 GB of free disk for a five-year cache and tables.
- A real contact address for the Wikimedia User-Agent. Do not use the example value.

## Setup

```sh
cp .env.example .env
# edit WIKIPULSE_CONTACT
uv sync --project pipeline
npm ci --prefix web
uv run --project pipeline pre-commit install
uv run --project pipeline pre-commit install --hook-type commit-msg
```

Commands run from the repository root unless noted. The CLI is installed in
`pipeline/.venv` by `uv sync`.

## Backfill

Top pageviews and edit analytics for five years:

```sh
uv run --project pipeline wikipulse ingest --years 5
```

The backfill is idempotent and resumable: completed days are skipped, and a killed process
can be restarted. Edit analytics lag, so the newest days remain incomplete and are retried
on later runs.

Per-article history is fetched for candidates, not for all articles:

```sh
uv run --project pipeline wikipulse history --start 2026-11-23 --end 2026-11-25 --lookback 400
```

For the demo repository, a short window is enough:

```sh
uv run --project pipeline wikipulse ingest --start 2026-11-18 --end 2026-11-25
uv run --project pipeline wikipulse history --start 2026-11-23 --end 2026-11-25 --lookback 120
uv run --project pipeline wikipulse detect --start 2026-11-23 --end 2026-11-25
uv run --project pipeline wikipulse cluster --start 2026-11-23 --end 2026-11-25
uv run --project pipeline wikipulse export
```

## Daily run

```sh
uv run --project pipeline wikipulse run-daily --ingest-days 7 --window-days 3
```

It ingests missing days, refreshes candidate history, detects spikes, scores them if a model
exists, fetches summaries, clusters events, and validates the export. It exits non-zero on a
failed run and writes `data/export/status.json`.

## Containers

The pipeline image uses CPU-only PyTorch, a pinned base image and a non-root user. The
preview image serves the built site; it uses committed test fixtures unless a real export is
present when the image is built.

```sh
cp .env.example .env
docker compose build
docker compose run --rm pipeline run-daily
docker compose up preview
```

The preview is at http://localhost:8080. Image sizes are printed by the CI docker job.

## Labels and classifier

Review spikes in the terminal, one at a time, with a sparkline, features and the article URL.
The class definitions and session rules are in `docs/labeling.md`.

```sh
uv run --project pipeline wikipulse label --count 20 --labeler your-name
```

The loop resumes by skipping already labeled spike ids. At least 300 labels are required
before training:

```sh
uv run --project pipeline wikipulse train --model both
uv run --project pipeline wikipulse classify --start 2026-11-23 --end 2026-11-25
```

Training writes `data/models/classifier.joblib`, metadata and a markdown report under
`data/reports/`. The Methods page reads the exported metrics, not the training files.

## Local site

```sh
npm run dev --prefix web
```

This copies `data/export` to `web/public/data`, generates the synchronous bootstrap and
serves the app. If there is no export, committed test fixtures are used.

Production preview:

```sh
npm run build --prefix web
npm run preview --prefix web
```

## Deploy to Cloudflare Pages

One-time project creation, direct upload:

```sh
npx wrangler pages project create wikipulse --production-branch main
```

Deploy after a successful export and build:

```sh
npx wrangler pages deploy web/dist --project-name wikipulse
```

The free `*.pages.dev` address works until a custom domain exists. Never hardcode the origin:
set `WIKIPULSE_SITE_URL` before running `npm run seo --prefix web` to generate `sitemap.xml`
and `robots.txt`; otherwise those files are omitted.

`web/public/_headers` is copied into the build and applies the CSP, referrer, permissions and
caching rules. Do not add permissive CORS headers; the data is same-origin.

## Schedule

Linux cron, 06:30 local time:

```cron
30 6 * * * cd /srv/wikipulse && uv run --project pipeline wikipulse run-daily >> data/run-daily.log 2>&1
```

Windows Task Scheduler, daily:

```powershell
powershell.exe -NoProfile -Command "Set-Location S:\wikiLights; uv run --project pipeline wikipulse run-daily"
```

Use the real path and run the task under an account that can write `data/`.

## Stale data

The site compares `manifest.data_through` to the browser clock and shows a banner after 48
hours. `status.json` also records the last run, its success and warnings. Check both when a
deployment looks empty.

## Troubleshooting

- `MissingContactError`: set `WIKIPULSE_CONTACT` in `.env` to a real address.
- Edit analytics absent: expected for roughly the last two months; the day stays retryable.
- Embedding model download is slow: the first `cluster` or `run-daily` downloads about
  90 MB from Hugging Face. Later runs use the cache.
- Article page falls back to Wikipedia: the export article cap was reached, or the article
  never spiked in the exported period.
- Export refused: a schema or the 150 KB gzip day budget failed. The previous published
  export is left intact.
- Lighthouse CLS above budget: run `npm run data` so the bootstrap is regenerated before the
  build.
