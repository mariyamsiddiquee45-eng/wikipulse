"""Typer command line entry points."""

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import typer

from wikipulse import __version__, db
from wikipulse.candidates import select_candidates
from wikipulse.classifier import ClassifierError, classify_spikes, train_classifier
from wikipulse.client import WikimediaClient
from wikipulse.config import Settings
from wikipulse.embeddings import SentenceTransformerEmbedder, ensure_summaries
from wikipulse.events import cluster_range
from wikipulse.export import ExportError, export_all
from wikipulse.features import FeatureSet, collect_features, detect_range, features_frame
from wikipulse.history import fetch_candidate_history
from wikipulse.ingest import backfill, last_complete_day
from wikipulse.labels import load_labels, run_label_session, sample_spikes
from wikipulse.run_daily import run_daily

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


def _date_range(start: str | None, end: str | None, days: int) -> tuple[date, date]:
    finish = _parse_day(end) if end else last_complete_day()
    begin = _parse_day(start) if start else finish - timedelta(days=days - 1)
    if begin > finish:
        raise typer.BadParameter("--start must not be after --end")
    return begin, finish


def _write_feature_snapshot(features: list[FeatureSet], settings: Settings) -> Path | None:
    if not features:
        return None
    settings.parquet_dir.mkdir(parents=True, exist_ok=True)
    path = settings.parquet_dir / "features.parquet"
    features_frame(features).sort_values(["day", "article"]).to_parquet(path, index=False)
    return path


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
    span = round(years * 365.25) if years is not None else days
    begin, finish = _date_range(start, end, span)

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
    begin, finish = _date_range(start, end, days)

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


@app.command()
def features(
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
    days: Annotated[int, typer.Option(help="Number of days ending at the last complete day.")] = 7,
) -> None:
    """Compute candidate features and write a Parquet snapshot without storing spikes."""
    _configure_logging()
    settings = Settings()
    begin, finish = _date_range(start, end, days)
    connection = db.connect(settings)
    computed = collect_features(connection, settings, begin, finish)
    path = _write_feature_snapshot(computed, settings)
    typer.echo(f"Computed {len(computed)} candidate features.")
    if path is not None:
        typer.echo(f"Wrote {path}")


@app.command()
def detect(
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
    days: Annotated[int, typer.Option(help="Number of days ending at the last complete day.")] = 7,
) -> None:
    """Run features and the rule-based detector, storing detected spikes."""
    _configure_logging()
    settings = Settings()
    begin, finish = _date_range(start, end, days)
    connection = db.connect(settings)
    run_id = db.start_run(connection, "detect")
    computed, inserted = detect_range(connection, settings, begin, finish)
    path = _write_feature_snapshot(computed, settings)
    db.finish_run(
        connection,
        run_id,
        ok=True,
        counts={"features": len(computed), "spikes": inserted},
        failures=[],
    )
    db.write_parquet(connection, settings)
    typer.echo(f"Computed {len(computed)} candidate features; stored {inserted} spikes.")
    if path is not None:
        typer.echo(f"Wrote {path}")


@app.command()
def label(
    count: Annotated[int, typer.Option(help="Number of unlabeled spikes to review.")] = 20,
    seed: Annotated[int, typer.Option(help="Sampling seed for a reproducible draw.")] = 0,
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
    labeler: Annotated[str | None, typer.Option(help="Name recorded with each label.")] = None,
    file: Annotated[Path | None, typer.Option(help="Label CSV path.")] = None,
) -> None:
    """Review spikes in the terminal and append labels to labels.csv."""
    _configure_logging()
    settings = Settings()
    path = file or settings.data_dir.parent / "labels" / "labels.csv"
    existing = load_labels(path)
    connection = db.connect(settings)
    samples = sample_spikes(
        connection,
        count,
        seed=seed,
        start=_parse_day(start) if start else None,
        end=_parse_day(end) if end else None,
        exclude=existing,
    )
    if not samples:
        typer.echo("No unlabeled spikes match. Run ingest, history and detect first.")
        raise typer.Exit(code=1)
    name = labeler or os.environ.get("USERNAME") or "unknown"
    typer.echo(f"Reviewing {len(samples)} spikes as {name}. Labels append to {path}.")
    try:
        labeled, skipped = run_label_session(
            connection,
            samples,
            path=path,
            labeler=name,
            ask=input,
            echo=typer.echo,
        )
    except (EOFError, KeyboardInterrupt):
        typer.echo("\nStopped. Labels written so far are kept.")
        raise typer.Exit(code=0) from None
    typer.echo(f"Labeled {labeled}; skipped {skipped}. Total labels: {len(load_labels(path))}.")


@app.command()
def train(
    model: Annotated[str, typer.Option(help="logistic, lightgbm or both.")] = "both",
    file: Annotated[Path | None, typer.Option(help="Label CSV path.")] = None,
    folds: Annotated[int, typer.Option(help="Expanding-window validation folds.")] = 4,
) -> None:
    """Train the classifier, compare baselines and write the evaluation report."""
    _configure_logging()
    settings = Settings()
    path = file or settings.data_dir.parent / "labels" / "labels.csv"
    kinds = ("logistic", "lightgbm") if model == "both" else (model,)
    if any(kind not in {"logistic", "lightgbm"} for kind in kinds):
        raise typer.BadParameter("--model must be logistic, lightgbm or both")
    connection = db.connect(settings)
    try:
        report = train_classifier(connection, settings, path, kinds, folds)
    except ClassifierError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Trained {report.model_name} on {report.labels} labels; "
        f"event F1 {report.metrics['event_f1']:.3f}."
    )
    typer.echo(f"Model {report.model_path}")
    typer.echo(f"Report {report.report_path}")


@app.command()
def classify(
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
    days: Annotated[int, typer.Option(help="Number of days ending at the last complete day.")] = 7,
) -> None:
    """Score stored spikes with the trained classifier."""
    _configure_logging()
    settings = Settings()
    begin, finish = _date_range(start, end, days)
    connection = db.connect(settings)
    try:
        scored = classify_spikes(connection, settings, begin, finish)
    except ClassifierError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Scored {scored} spikes.")


@app.command()
def cluster(
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
    days: Annotated[int, typer.Option(help="Number of days ending at the last complete day.")] = 7,
    model: Annotated[str, typer.Option(help="Sentence-transformers model name.")] = (
        "sentence-transformers/all-MiniLM-L6-v2"
    ),
) -> None:
    """Fetch summaries, embed spike articles and build daily events."""
    _configure_logging()
    settings = Settings()
    begin, finish = _date_range(start, end, days)
    client = WikimediaClient(settings)
    connection = db.connect(settings)
    run_id = db.start_run(connection, "cluster")
    articles = [
        str(row[0])
        for row in connection.execute(
            "SELECT DISTINCT article FROM spikes WHERE day BETWEEN ? AND ?", [begin, finish]
        ).fetchall()
    ]
    fetched, failed = ensure_summaries(connection, client, articles)
    events = cluster_range(connection, settings, begin, finish, SentenceTransformerEmbedder(model))
    db.finish_run(
        connection,
        run_id,
        ok=True,
        counts={
            "summaries": fetched,
            "summary_failures": failed,
            "events": len(events),
            "spikes": len(articles),
        },
        failures=[],
    )
    db.write_parquet(connection, settings)
    typer.echo(
        f"Summaries {fetched} fetched, {failed} missing; {len(articles)} spikes; "
        f"{len(events)} events."
    )


@app.command()
def export(
    start: Annotated[str | None, typer.Option(help="First day, YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Last day, YYYY-MM-DD.")] = None,
) -> None:
    """Validate and publish the static JSON export."""
    _configure_logging()
    settings = Settings()
    connection = db.connect(settings)
    try:
        summary = export_all(
            settings,
            connection,
            start=_parse_day(start) if start else None,
            end=_parse_day(end) if end else None,
        )
    except ExportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Exported {summary.days} days, {summary.events} events, "
        f"{summary.articles} articles, {summary.search_shards} search shards, "
        f"{summary.files} files to {summary.output_dir}."
    )
    for warning in summary.warnings:
        typer.echo(f"warning: {warning}")


@app.command("run-daily")
def run_daily_command(
    ingest_days: Annotated[int, typer.Option(help="Days to check for missing ingestion.")] = 7,
    window_days: Annotated[int, typer.Option(help="Days to detect, cluster and export.")] = 3,
) -> None:
    """Run the complete incremental pipeline and write status.json."""
    _configure_logging()
    settings = Settings()
    try:
        summary = run_daily(settings, ingest_days=ingest_days, window_days=window_days)
    except Exception as exc:
        typer.echo(f"Daily run failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Daily run through {summary.data_through}: {summary.ingested_days} days, "
        f"{summary.candidates} candidates, {summary.spikes} spikes, "
        f"{summary.events} events, {summary.articles} articles."
    )
    if summary.export is not None:
        typer.echo(
            f"Exported {summary.export.files} files to {summary.export.output_dir}; "
            f"warnings {len(summary.export.warnings)}."
        )
    if summary.failures:
        for failure in summary.failures:
            typer.echo(failure, err=True)
        raise typer.Exit(code=1)
