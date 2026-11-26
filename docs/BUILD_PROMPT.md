# WikiPulse build prompt for opencode

Working name: WikiPulse. Save as docs/BUILD_PROMPT.md in the repository and give it to opencode phase by phase.

## 1. Role and working rules

You are a senior full-stack and machine learning engineer building WikiPulse from scratch in an empty git repository. Work in the phases listed in section 13.

Before each phase: read this file and AGENTS.md, then post a short plan (files, interfaces, tests). Implement it. After each phase: run every check, fix failures, commit, tag, and stop with a summary and the exact commands to verify. Do not begin the next phase until told.

Rules that apply to everything:

- Never invent API fields or endpoints. Fetch real responses first, save them as fixtures, then write code against them. Check the current official documentation for every endpoint and prefer documented, non-deprecated ones.
- No emojis anywhere: code, comments, commits, documentation, UI text, logs.
- Comments explain why, never what: units, policy constraints, workarounds. No narration comments, no banner comments, no commented-out code, no TODO without an issue number. Public functions get a one or two line docstring.
- Small, typed, well-named functions. No dead code and no unused dependencies. Justify every new dependency in the commit body.
- If a requirement is ambiguous, ask instead of guessing.
- UI copy is plain and direct.

## 2. Product

WikiPulse is a public website that shows, once a day, what people suddenly became curious about on English Wikipedia, grouped into real-world events. It is built on Wikimedia pageview data (CC0). It is not affiliated with Wikipedia or the Wikimedia Foundation.

There are no accounts, no cookies, no analytics and no stored user data. At runtime the product is a static site: a Python pipeline produces JSON files and a React app reads them from a CDN. There is no server of ours to attack or overload.

## 3. Locked decisions

- Scope: English Wikipedia only (en.wikipedia, all-access).
- History: 5 years, backfilled in a resumable way.
- Pipeline host: a low-end machine (about 8 GB RAM, dual-core i3, no GPU). Peak RAM under 4 GB. CPU-only PyTorch, no GPU libraries.
- Hosting: Cloudflare Pages by direct upload of the build output, on a free pages.dev address until a custom domain exists. Develop on localhost. Never hardcode a domain; read it from configuration.
- Theme: Wikipedia-inspired (Vector style), light and dark, with our own name and logo. Never use Wikipedia logos, marks or article images.
- Repository: GitHub, no license file. Generated data is never committed to main.
- Docker: last phase only.
- Theme preference is stored in localStorage only. Nothing else is stored.

## 4. Repository layout

```
pipeline/   Python package (src/wikipulse) and its tests
web/        Vite, React, TypeScript app
labels/     labels.csv, the only data committed
docs/       architecture, methods, runbook, data contract
schemas/    JSON Schemas for exported data, single source of truth
scripts/    development helpers
.github/    workflows, pull request template, dependabot
AGENTS.md  README.md  CHANGELOG.md
```

The data/ directory is gitignored. It holds the raw response cache, DuckDB file, Parquet files, models, reports and exports.

## 5. Git workflow

- Default branch is main, always green and releasable. Never commit to main directly. One branch per task, named type/short-kebab-description with the types feat, fix, refactor, test, docs, chore.
- Conventional Commits: `type(scope): imperative summary`, at most 72 characters. Types: feat, fix, refactor, test, docs, chore, build, ci, perf. Scopes: pipeline, ml, web, schema, ci, docs, deps. Add a body wrapped at 72 characters when the reason is not obvious.
- One logical change per commit. Tests are committed with the code they cover. Build and tests pass at every commit. Never mix formatting changes with logic changes.
- Never commit secrets, .env files (provide .env.example), anything under data/, model binaries, node\_modules, or files over 1 MB that are not intended assets.
- Merge by pull request using rebase-merge, so history stays linear and keeps the individual commits.
- At the end of each phase, update CHANGELOG.md from the commits (git-cliff or equivalent) and tag v0.N.0 where N is the phase number.
- Pre-commit hooks: ruff, ruff format, mypy, eslint, prettier, gitleaks and commitlint. CI runs the same checks.

Expected opening commits:

```
chore: initialize repository layout and gitignore
build(pipeline): add pyproject with uv, ruff, mypy and pytest
build(web): scaffold Vite React TypeScript app
ci: add lint, type-check and test workflow
docs: add AGENTS.md and README skeleton
```

## 6. Code standards

Python: 3.12, uv, pyproject.toml, src layout, ruff for lint and format, mypy strict, pytest, hypothesis, pandera for data validation, pydantic for configuration and API models, typer for the CLI. Standard logging, never print. One settings object fed by environment variables with defaults. CLI commands: `wikipulse ingest`, `features`, `detect`, `train`, `classify`, `cluster`, `export`, `label`, `run-daily`.

TypeScript: strict mode, no `any`, eslint, prettier, Vitest, Playwright. API types are generated from schemas/.

## 7. Data pipeline

**Wikimedia client.** Base URL is configurable. Every request carries a User-Agent of the form `WikiPulse/<version> (<contact from environment>)`. Requests are sequential with a minimum delay (default 0.5 s), exponential backoff with jitter on 429 and 5xx, honoring Retry-After, with a hard retry cap. Every raw response is cached on disk by request key. Completed past days are immutable and never fetched again. Backfill is idempotent and resumable and logs progress. Validate every response with pydantic and fail loudly on format changes.

**Sources.** (1) The daily top 1000 articles for en.wikipedia, all-access, for every day in the window (about 1,830 calls for 5 years). (2) Per-article daily views (agent user) for candidate articles. (3) Most-edited pages per day, only if the API provides daily data; verify against the live API, and if it does not, drop the edit-surge feature and say so in the Methods page. (4) Article summaries as plain text for labeling events.

**Storage.** DuckDB plus Parquet under data/. Tables: top\_daily, article\_daily, edits, article\_meta, spikes, events, runs. All writes are upserts by natural key. The runs table records start, finish, row counts and failures.

**Filtering.** Exclude Main\_Page, the namespaces Special:, Wikipedia:, Portal:, File:, Help:, Category:, Template: and Talk:, plus a configurable denylist. Unit-test the filter with real titles.

**Candidates.** The pool is new entrants to the top 1000 (absent for the previous 28 days), the largest rank movers, and a persistent watch list of recently spiking articles. Fetch per-article history only for candidates.

**Missing data.** Days with absent or failed data are recorded, excluded from baselines and shown as gaps. Never impute silently.

**Daily run.** `wikipulse run-daily` ingests missing days, then runs features, detection, classification, clustering, export and validation. It exits non-zero on failure and writes status.json. Budget: under 15 minutes of compute for an incremental run on the target machine, excluding rate-limit waits.

## 8. Machine learning

**Features per candidate spike:** robust z-score (median and MAD over 28 days, adjusted for day of week), STL residual score (when at least one year of history exists), same-day-last-year ratio, rise time, time to peak, half-life, peak-to-baseline ratio, rank jump versus the previous day, days since the last spike, minimum-views flag, and edit surge when available.

**Baselines.** A: rule-based detector (z-score above a threshold and a views floor). B: raw rank. C: fixed ratio to the previous week.

**Labels.** labels/labels.csv with columns spike\_id, article, date, label (event, noise or recurring), labeler, labeled\_at, note. `wikipulse label` is a terminal tool that shows a compact sparkline, the features and the article URL. It supports stratified sampling across the five years, later uncertainty sampling, and resuming. The target is at least 300 labels covering all classes. The human does the labeling.

**Classifier.** Logistic regression and LightGBM inside an sklearn Pipeline, class weights, fixed seeds. Evaluate with expanding-window time-series cross-validation, never random splits. Report per-class precision, recall and F1, precision-recall curves, a confusion matrix, calibration and precision at k, compared against baselines A to C. Report permutation importance and gain importance. Generate a failure-case report (top false positives and false negatives with sparklines) as markdown. Save the model with metadata: feature list, data hash, date and metrics. A regression test guards a metric floor on a fixed fixture.

**Embeddings and clustering.** all-MiniLM-L6-v2 through sentence-transformers on CPU with the CPU-only PyTorch wheel. Input is title plus summary. Cache one embedding per article and process in batches. Cluster each day's spikes with scikit-learn HDBSCAN on L2-normalized vectors with a minimum cluster size of 2. Singletons become single-article events. The event label is its highest-scoring member. Everything is deterministic with fixed seeds. A link-graph signal is a later improvement.

**Spike types.** Flash, Slow burn, Recurring and Always-on, assigned by documented rules or k-means on rise time, half-life and peak-to-baseline ratio.

**Honesty.** The Methods page shows the evaluation numbers from the latest report, with sample size and limitations.

## 9. Static data contract

Exports go to data/export/ and are validated against schemas/ before anything is published.

- manifest.json: schema\_version, generated\_at, data\_through (last complete day), first\_day, last\_day, counts and file hashes.
- status.json: last\_run, ok, warnings.
- days/YYYY-MM-DD.json: events with id, label, score, type, member articles (views, baseline, z-score, class probability) and a short extract with attribution fields. Each day file stays under 150 KB gzipped.
- articles/\<shard>/\<slug>.json: compact daily history with spike markers, for articles that ever spiked.
- search/\<prefix>.json: search index sharded by the first two characters of the slug, loaded lazily.

A breaking change requires a schema\_version bump and a migration note. Output is deterministic: identical inputs produce identical bytes. The frontend uses the manifest for cache-busting.

## 10. Frontend

**Stack.** Vite, React, TypeScript strict, React Router, Tailwind with design tokens as CSS variables, only the d3 modules needed (hierarchy, scale, shape, force), Framer Motion, MiniSearch. No UI kit and no other runtime dependency without justification. System font stacks or self-hosted fonts. No third-party requests of any kind.

**Theme.** Match Wikipedia's Vector look closely: light gray page background, white content surface, near-black text, blue links, purple visited links, thin gray borders, serif headings (Georgia and Linux Libertine stack), system sans body. Dark mode uses dark neutral surfaces and softened blue links. Follow prefers-color-scheme with a manual toggle stored in localStorage, and avoid a flash of the wrong theme on load. All colors come from tokens and meet WCAG AA contrast in both modes.

**Pages.** Home, Day (/d/YYYY-MM-DD), Event (/e/id), Article (/a/slug), Search (/search?q=), Methods, About and attribution, Privacy, 404.

**Home.** A hero SVG illustration, the data-through date with a stale-data banner when data is older than 48 hours, a bubble pack (size is score, color is spike type), a ranked list, and a date scrubber. The ranked list is the primary content and the bubbles are an enhancement. Everything works by keyboard. prefers-reduced-motion disables animation. All states are deep-linkable.

**Article page.** History chart with spike markers and recurring flags, extract text with attribution, and a link to the source article.

**Content rules.** Render Wikipedia extracts as plain text, never HTML. Attribute Wikipedia text (CC BY-SA) with a link to the source article. Credit Wikimedia for pageview data. The footer says: Not affiliated with Wikipedia or the Wikimedia Foundation.

**SVG assets.** Created by the human's AI and stored in web/src/assets/svg. A `check-svg` script fails CI on script elements, event-handler attributes, external references, or files over 30 KB. Decorative SVGs are aria-hidden and meaningful ones have text alternatives. Use CSS variables so they follow the theme.

**Performance.** Initial JavaScript under 200 KB gzipped, route-level code splitting, LCP under 2.5 s on a mid-range mobile profile, CLS under 0.1, Lighthouse performance and accessibility at least 95, enforced in CI.

**SEO and states.** Per-route title and description, Open Graph tags, semantic HTML with one h1 per page, sitemap.xml and robots.txt generated when a domain is configured. Loading skeletons, empty states, network error states with retry, and clear messages for missing days.

## 11. Security and privacy

- No runtime server, no API of ours, no persisted user input, no secrets in the repository.
- web/public/\_headers for Cloudflare Pages with: Content-Security-Policy (default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'; object-src 'none'), X-Content-Type-Options nosniff, a strict Referrer-Policy, a restrictive Permissions-Policy, Cross-Origin-Opener-Policy same-origin, long immutable caching for hashed assets and short caching for JSON. No inline scripts or styles; solve any tooling conflict in the build configuration instead of allowing unsafe-inline. Add no permissive CORS headers, since all data is same-origin.
- Treat Wikimedia content and AI-generated assets as untrusted: validate on ingest, escape on render, never use dangerouslySetInnerHTML.
- Dependencies: lockfiles committed, exact pins for the pipeline, npm audit and pip-audit in CI, weekly Dependabot, gitleaks in hooks and CI, minimal GitHub Actions permissions, actions pinned to commit SHAs.
- A test verifies the headers file exists and contains the required directives.
- The Privacy page states: no cookies, no tracking, theme preference kept in local storage only.

## 12. Testing

**Pipeline.**

- Unit tests for every pure function.
- Property-based tests (Hypothesis) for detector and feature invariants: scale invariance of the z-score, no NaN, handling of zeros and short histories.
- Contract tests against recorded real API fixtures, plus a canary test against the live API for one day, excluded from default runs, to detect format drift.
- pandera data-quality checks on every table.
- Idempotency and resume tests, including killing a backfill midway and restarting.
- A synthetic generator with planted spikes of known type and magnitude over at least 2 million article-days; assert recall and false-positive rate per magnitude band.
- End-to-end replay of a real multi-month fixture.
- Performance tests with time and memory budgets on 5 years of synthetic top-1000 data (about 1.8 million rows) and 100,000 article histories.
- Failure injection: 429, timeouts, malformed JSON, missing days, duplicate rows, renamed fields.
- Determinism test: same input, same output bytes.
- ML tests: no leakage across dates, fixed seeds, metric floor on a fixed fixture, calibration sanity.
- Export tests: schema validity, size budgets, manifest hashes.

**Web.**

- Vitest unit and component tests using fixtures from real exports plus a synthetic 5-year dataset that stresses rendering and search.
- Playwright end-to-end tests on Chromium, Firefox, WebKit and mobile viewports covering every page, both themes, keyboard-only use, reduced motion, network failure, stale-data banner and missing days.
- axe accessibility checks on every page in both themes.
- Visual regression on key pages in light and dark.
- Lighthouse CI with budgets, a link checker, the SVG checker and the headers test.

**Gates.** Coverage: pipeline core (features, detector, filters, export) at least 90 percent, overall pipeline at least 85 percent, web at least 80 percent. CI must pass on every pull request. Flaky tests are fixed or removed, never retried blindly. Test names describe behavior.

## 13. Phases and acceptance criteria

**Phase 0, foundation.** Repository layout, tooling, hooks, CI skeleton, AGENTS.md (a condensed version of sections 1, 5 and 6 so rules persist across sessions), README skeleton, pull request template, Dependabot. Accept: a fresh clone passes the full check command locally and in CI.

**Phase 1, ingestion.** Client, cache, response models, DuckDB schema, resumable 5-year top-daily backfill, fixtures, tests. Accept: backfill resumes after a kill, a rerun fetches nothing, data-quality tests pass.

**Phase 2, candidates and history.** Filtering, candidate selection, per-article history, edits if available. Accept: the candidate pool logic is documented and tested on fixtures.

**Phase 3, features and baseline detector.** Synthetic generator, features, rule-based detector, spike-shape metrics. Accept: recall and false-positive targets on synthetic data are documented and gated, property tests pass, the performance budget is met.

**Phase 4, labeling.** Labeling CLI, sampling, label file format and validation. Then stop. The human labels at least 300 spikes before Phase 5.

**Phase 5, classifier.** Training, time-series cross-validation, baseline comparison, reports, model artifact, integration into the daily run. Accept: the report is generated and metric floors are tested.

**Phase 6, embeddings and events.** Summaries, embedding cache, HDBSCAN clustering, event assembly, spike types. Accept: deterministic output, memory within budget, cluster sanity tests.

**Phase 7, export and contracts.** Schemas, exports, manifest, sharded search, size budgets, TypeScript type generation, end-to-end `run-daily` with status.json. Accept: validation blocks publishing on any violation.

**Phase 8, frontend foundation.** Tokens, light and dark themes, layout, routing, data layer, accessibility baseline, SVG tooling, placeholder hero. Accept: Lighthouse and axe budgets pass on the skeleton.

**Phase 9, frontend pages.** All pages, bubble pack, scrubber, article charts, search, Methods page reading the latest metrics, all states. Accept: end-to-end tests pass across browsers and both themes.

**Phase 10, hardening and release.** Security headers, SEO, performance budgets, large-data tests, visual regression, documentation (architecture, methods, runbook), Cloudflare Pages direct-upload deployment with a documented command, a daily scheduled run (cron or systemd timer on the host, documented), stale-data detection. Accept: the production checklist is green.

**Phase 11, Docker.** Pipeline image (CPU-only PyTorch, non-root user, pinned base image), compose file for the pipeline and local preview, healthcheck, documentation, image build in CI. Accept: the daily run works from a clean machine through compose, and image size is reported.

## 15. Definition of done for every phase

All checks pass locally and in CI. Documentation and CHANGELOG are updated. The phase is tagged. No TODO without an issue number. No emojis. The working tree is clean. The final message summarizes what was built, what was tested, and the commands to verify it.
