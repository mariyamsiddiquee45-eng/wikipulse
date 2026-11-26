"""Typer command line entry points."""

import logging
from datetime import date, timedelta
from typing import Annotated

import typer

from wikipulse import __version__, db
from wikipulse.candidates import select_candidates
from wikipulse.client import WikimediaClient
from wikipulse.config import Settings
from wikipulse.history import fetch_candidate_history
from wikipulse.ingest import backfill, last_complete_day

app = typer.Typer(help="WikiPulse data pipeline.", no_args_is_help=True)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"Expected YYYY-MM-DD, got {value!r}") from exc


@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", help="Show the version and exit.")] = False,
) -> None:
    """WikiPulse data pipeline."""
    if version:
        typer.echo(__version__)
        raise typer.Exit


@app.command()
def ingest(
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
    days: Annotated[int, typer.Option(help="Number of days ending at the last complete day.")] = 7,
    years: Annotated[
        float | None, typer.Option(help="History window in years, overrides --days.")
    ] = None,
    force: Annotated[bool, typer.Option(help="Refetch days already marked complete.")] = False,
) -> None:
    """Ingest top pageviews and daily edit analytics into DuckDB."""
    _configure_logging()
    settings = Settings()
    finish = _parse_day(end) if end else last_complete_day()
    span = round(years * 365.25) if years is not None else days
    begin = _parse_day(start) if start else finish - timedelta(days=span - 1)
    if begin > finish:
        raise typer.BadParameter("--start must not be after --end")

    client = WikimediaClient(settings)
    connection = db.connect(settings)
    run_id = db.start_run(connection, "ingest")
    summary = backfill(settings, client, connection, begin, finish, force=force)
    counts = {
        "top_daily": summary.top_rows,
        "edits": summary.edit_rows,
        "days": summary.days_ingested,
    }
    db.finish_run(
        connection, run_id, ok=not summary.failures, counts=counts, failures=summary.failures
    )
    paths = db.write_parquet(connection, settings)
    typer.echo(
        f"Ingested {summary.days_ingested} days ({summary.top_rows} top rows, "
        f"{summary.edit_rows} edit rows); skipped {summary.days_skipped}; "
        f"{len(summary.failures)} failures."
    )
    typer.echo(f"Wrote {len(paths)} Parquet files to {settings.parquet_dir}")
    if summary.failures:
        for failure in summary.failures:
            typer.echo(failure, err=True)
        raise typer.Exit(code=1)


@app.command()
def history(
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
    days: Annotated[int, typer.Option(help="Number of days ending at the last complete day.")] = 7,
    lookback: Annotated[
        int | None, typer.Option(help="Days of history before each candidate day.")
    ] = None,
    force: Annotated[
        bool, typer.Option(help="Refetch articles that already have a baseline.")
    ] = False,
) -> None:
    """Fetch per-article history for new entrants, rank movers and recent spikes."""
    _configure_logging()
    settings = Settings()
    finish = _parse_day(end) if end else last_complete_day()
    begin = _parse_day(start) if start else finish - timedelta(days=days - 1)
    if begin > finish:
        raise typer.BadParameter("--start must not be after --end")

    client = WikimediaClient(settings)
    connection = db.connect(settings)
    run_id = db.start_run(connection, "history")
    all_candidates = []
    current = begin
    while current <= finish:
        all_candidates.extend(select_candidates(connection, current, settings))
        current += timedelta(days=1)
    summary = fetch_candidate_history(
        settings, client, connection, all_candidates, lookback_days=lookback, force=force
    )
    db.finish_run(
        connection,
        run_id,
        ok=not summary.failures,
        counts={"articles": summary.articles_fetched, "article_daily": summary.rows},
        failures=summary.failures,
    )
    db.write_parquet(connection, settings)
    typer.echo(
        f"Candidates {summary.articles_considered}; fetched {summary.articles_fetched} "
        f"articles; {summary.rows} rows; {len(summary.failures)} failures."
    )
    if summary.failures:
        for failure in summary.failures:
            typer.echo(failure, err=True)
        raise typer.Exit(code=1)
