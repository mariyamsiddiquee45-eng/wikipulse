# AGENTS.md

Condensed working rules for every session. Read `docs/BUILD_PROMPT.md` before a phase.

## Workflow

- Work phase by phase. Before a phase: read the build prompt and this file, then post a
  short plan covering files, interfaces, and tests.
- After a phase: run every check, fix failures, commit, update `CHANGELOG.md`, tag
  `v0.N.0`, and stop with a summary plus exact verification commands.
- Do not start the next phase until told.
- If a requirement is ambiguous, ask instead of guessing.

## Rules

- Never invent API fields or endpoints. Fetch the real response, save it as a fixture, and
  code against it. Prefer current, non-deprecated official endpoints.
- No emojis in code, comments, commits, documentation, UI text, or logs.
- Comments explain why only: units, policy constraints, workarounds. No narration, banner
  comments, commented-out code, or TODOs without an issue number. Public functions get a
  one or two line docstring.
- Small, typed, well-named functions. No dead code, no unused dependencies. Justify every
  new dependency in the commit body.
- UI copy is plain and direct.
- Never commit secrets, `.env` files, `data/`, model binaries, `node_modules`, or files
  over 1 MB that are not intended assets.

## Git

- Default branch `main` is always green. Never commit to it directly after bootstrap; one
  branch per task, named `type/short-kebab-description` with types `feat`, `fix`,
  `refactor`, `test`, `docs`, `chore`.
- Conventional Commits: `type(scope): imperative summary`, at most 72 characters.
  Types: feat, fix, refactor, test, docs, chore, build, ci, perf. Scopes: pipeline, ml,
  web, schema, ci, docs, deps. Explain non-obvious reasons in a body wrapped at 72.
- One logical change per commit; tests ship with the code they cover. Build and tests pass
  at every commit. Never mix formatting with logic.
- Merge by pull request with rebase-merge. Update `CHANGELOG.md` and tag at each phase.

## Python

- Python 3.12, `uv`, `pyproject.toml`, `src/` layout.
- `ruff` lint and format, `mypy` strict, `pytest`, `hypothesis`, `pandera`, `pydantic`,
  `typer`.
- Standard logging, never `print`. One settings object from environment variables with
  defaults.
- CLI: `wikipulse ingest`, `features`, `detect`, `train`, `classify`, `cluster`, `export`,
  `label`, `run-daily`.

## TypeScript

- Strict mode, no `any`, eslint, prettier, Vitest, Playwright.
- API types are generated from `schemas/`.

## Checks

```sh
cd pipeline && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd web && npm run check
```
