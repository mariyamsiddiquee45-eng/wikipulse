"""DuckDB schema, upserts, run tracking and Parquet snapshots."""

import json
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from wikipulse.config import Settings
from wikipulse.models import ArticleDailyItem, EditedPage, SpikeRecord, Summary, TopArticle

_TABLES = (
    "top_daily",
    "article_daily",
    "edits",
    "article_meta",
    "spikes",
    "events",
    "days",
    "runs",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS top_daily (
    day DATE NOT NULL,
    article VARCHAR NOT NULL,
    views BIGINT NOT NULL,
    rank INTEGER NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (day, article)
);
CREATE TABLE IF NOT EXISTS article_daily (
    day DATE NOT NULL,
    article VARCHAR NOT NULL,
    views BIGINT NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (day, article)
);
CREATE TABLE IF NOT EXISTS edits (
    day DATE NOT NULL,
    article VARCHAR NOT NULL,
    edits INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (day, article)
);
CREATE TABLE IF NOT EXISTS article_meta (
    article VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    description VARCHAR,
    summary VARCHAR,
    url VARCHAR NOT NULL,
    fetched_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS days (
    day DATE PRIMARY KEY,
    top_ok BOOLEAN NOT NULL DEFAULT FALSE,
    edits_ok BOOLEAN NOT NULL DEFAULT FALSE,
    error VARCHAR,
    updated_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS spikes (
    spike_id VARCHAR PRIMARY KEY,
    day DATE NOT NULL,
    article VARCHAR NOT NULL,
    views BIGINT NOT NULL,
    baseline DOUBLE,
    z_score DOUBLE,
    peak_ratio DOUBLE,
    rise_days DOUBLE,
    half_life_days DOUBLE,
    yoy_ratio DOUBLE,
    rank_jump INTEGER,
    days_since_last_spike INTEGER,
    edit_surge BOOLEAN NOT NULL DEFAULT FALSE,
    stl_residual DOUBLE,
    time_to_peak_days DOUBLE,
    score DOUBLE NOT NULL,
    spike_type VARCHAR NOT NULL,
    features VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    event_id VARCHAR PRIMARY KEY,
    day DATE NOT NULL,
    label VARCHAR NOT NULL,
    score DOUBLE NOT NULL,
    event_type VARCHAR NOT NULL,
    members VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY,
    kind VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    ok BOOLEAN,
    counts VARCHAR,
    failures VARCHAR
);
"""


def utc_now() -> datetime:
    """Return a naive UTC timestamp for DuckDB TIMESTAMP columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    """Open the DuckDB file and ensure the schema exists."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(settings.db_path))
    init_schema(connection)
    return connection


def init_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Create every table if it does not exist, then add later columns."""
    connection.execute(_SCHEMA)
    connection.execute("ALTER TABLE spikes ADD COLUMN IF NOT EXISTS stl_residual DOUBLE")
    connection.execute("ALTER TABLE spikes ADD COLUMN IF NOT EXISTS time_to_peak_days DOUBLE")


def upsert_top(
    connection: duckdb.DuckDBPyConnection, day: date, articles: Iterable[TopArticle]
) -> int:
    """Insert or replace one day of top-article views; returns the row count."""
    fetched_at = utc_now()
    rows = [(day, item.article, item.views, item.rank, fetched_at) for item in articles]
    if rows:
        connection.executemany("INSERT OR REPLACE INTO top_daily VALUES (?, ?, ?, ?, ?)", rows)
    return len(rows)


def upsert_edits(
    connection: duckdb.DuckDBPyConnection, day: date, pages: Iterable[EditedPage]
) -> int:
    """Insert or replace one day of edited-page counts."""
    fetched_at = utc_now()
    rows = [(day, item.page_title, item.edits, item.rank, fetched_at) for item in pages]
    if rows:
        connection.executemany("INSERT OR REPLACE INTO edits VALUES (?, ?, ?, ?, ?)", rows)
    return len(rows)


def upsert_article_daily(
    connection: duckdb.DuckDBPyConnection, items: Iterable[ArticleDailyItem]
) -> int:
    """Insert or replace per-article daily views."""
    fetched_at = utc_now()
    rows = [(item.date, item.article, item.views, fetched_at) for item in items]
    if rows:
        connection.executemany("INSERT OR REPLACE INTO article_daily VALUES (?, ?, ?, ?)", rows)
    return len(rows)


def upsert_meta(connection: duckdb.DuckDBPyConnection, article: str, summary: Summary) -> None:
    """Insert or replace the summary metadata for one article."""
    url = (
        summary.content_urls.desktop.page
        if summary.content_urls is not None
        else f"https://en.wikipedia.org/wiki/{article}"
    )
    connection.execute(
        "INSERT OR REPLACE INTO article_meta VALUES (?, ?, ?, ?, ?, ?)",
        [article, summary.title, summary.description, summary.extract, url, utc_now()],
    )


def upsert_spikes(connection: duckdb.DuckDBPyConnection, records: Iterable[SpikeRecord]) -> int:
    """Insert or replace detected spikes by spike_id."""
    rows = [
        (
            record.spike_id,
            record.day,
            record.article,
            record.views,
            record.baseline,
            record.z_score,
            record.peak_ratio,
            record.rise_days,
            record.time_to_peak_days,
            record.half_life_days,
            record.yoy_ratio,
            record.rank_jump,
            record.days_since_last_spike,
            record.edit_surge,
            record.stl_residual,
            record.score,
            record.spike_type,
            json.dumps(record.features, sort_keys=True, separators=(",", ":")),
            utc_now(),
        )
        for record in records
    ]
    if rows:
        connection.executemany(
            """
            INSERT OR REPLACE INTO spikes (
                spike_id, day, article, views, baseline, z_score, peak_ratio,
                rise_days, time_to_peak_days, half_life_days, yoy_ratio, rank_jump,
                days_since_last_spike, edit_surge, stl_residual, score, spike_type,
                features, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def last_spike_day(
    connection: duckdb.DuckDBPyConnection, article: str, before: date
) -> date | None:
    """Return the most recent earlier spike day for an article."""
    row = connection.execute(
        "SELECT max(day) FROM spikes WHERE article = ? AND day < ?", [article, before]
    ).fetchone()
    if row is None or row[0] is None:
        return None
    value = row[0]
    return value if isinstance(value, date) else None


def mark_day(
    connection: duckdb.DuckDBPyConnection,
    day: date,
    *,
    top_ok: bool,
    edits_ok: bool,
    error: str | None = None,
) -> None:
    """Record completeness flags for a day without clearing earlier successes."""
    connection.execute(
        """
        INSERT INTO days (day, top_ok, edits_ok, error, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (day) DO UPDATE SET
            top_ok = days.top_ok OR excluded.top_ok,
            edits_ok = days.edits_ok OR excluded.edits_ok,
            error = COALESCE(excluded.error, days.error),
            updated_at = excluded.updated_at
        """,
        [day, top_ok, edits_ok, error, utc_now()],
    )


def day_flags(connection: duckdb.DuckDBPyConnection, day: date) -> tuple[bool, bool]:
    """Return (top_ok, edits_ok) for a day; missing days are (False, False)."""
    row = connection.execute("SELECT top_ok, edits_ok FROM days WHERE day = ?", [day]).fetchone()
    if row is None:
        return False, False
    return bool(row[0]), bool(row[1])


def start_run(connection: duckdb.DuckDBPyConnection, kind: str) -> str:
    """Insert a started run and return its identifier."""
    run_id = uuid.uuid4().hex
    connection.execute(
        "INSERT INTO runs (run_id, kind, started_at) VALUES (?, ?, ?)",
        [run_id, kind, utc_now()],
    )
    return run_id


def finish_run(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    *,
    ok: bool,
    counts: dict[str, int],
    failures: Sequence[str],
) -> None:
    """Complete a run with row counts and failure messages."""
    connection.execute(
        "UPDATE runs SET finished_at = ?, ok = ?, counts = ?, failures = ? WHERE run_id = ?",
        [utc_now(), ok, json.dumps(counts, sort_keys=True), json.dumps(list(failures)), run_id],
    )


def table_counts(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return row counts for every pipeline table."""
    counts: dict[str, int] = {}
    for table in _TABLES:
        row = connection.execute(
            f"SELECT count(*) FROM {table}"  # noqa: S608 - names come from the fixed _TABLES tuple
        ).fetchone()
        counts[table] = int(row[0]) if row is not None else 0
    return counts


def write_parquet(connection: duckdb.DuckDBPyConnection, settings: Settings) -> list[Path]:
    """Write every table to Parquet in a stable order; returns the written paths."""
    settings.parquet_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for table in _TABLES:
        path = settings.parquet_dir / f"{table}.parquet"
        connection.execute(
            f"COPY (SELECT * FROM {table} ORDER BY ALL) TO ? (FORMAT PARQUET)",  # noqa: S608
            [str(path)],
        )
        paths.append(path)
    return paths


def fetch_rows(
    connection: duckdb.DuckDBPyConnection, query: str, params: Sequence[Any] | None = None
) -> list[tuple[Any, ...]]:
    """Run a query and return all rows, keeping DuckDB details out of callers."""
    return connection.execute(query, params or []).fetchall()
