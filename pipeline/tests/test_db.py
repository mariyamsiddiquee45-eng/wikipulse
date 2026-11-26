from datetime import date
from pathlib import Path

import duckdb

from wikipulse import db
from wikipulse.config import Settings
from wikipulse.models import ContentUrls, EditedPage, Summary, TopArticle, UrlSet


def test_top_upsert_is_idempotent() -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    rows = [TopArticle(article="Alpha", views=100, rank=1)]

    assert db.upsert_top(connection, date(2024, 1, 15), rows) == 1
    assert db.upsert_top(connection, date(2024, 1, 15), rows) == 1

    count = connection.execute("SELECT count(*) FROM top_daily").fetchone()
    assert count == (1,)


def test_mark_day_keeps_earlier_success() -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = date(2024, 1, 15)

    db.mark_day(connection, day, top_ok=True, edits_ok=False)
    db.mark_day(connection, day, top_ok=False, edits_ok=True, error="edits failed once")

    assert db.day_flags(connection, day) == (True, True)
    assert db.day_flags(connection, date(2024, 1, 16)) == (False, False)


def test_runs_record_counts_and_failures() -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    run_id = db.start_run(connection, "ingest")
    db.finish_run(connection, run_id, ok=False, counts={"top_daily": 3}, failures=["one day"])

    row = connection.execute(
        "SELECT kind, ok, counts, failures FROM runs WHERE run_id = ?", [run_id]
    ).fetchone()
    assert row is not None
    assert row[0] == "ingest"
    assert row[1] is False
    assert row[2] == '{"top_daily": 3}'
    assert row[3] == '["one day"]'


def test_article_meta_upsert_and_parquet(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    summary = Summary(
        type="standard",
        title="Alpha",
        extract="First sentence.",
        content_urls=ContentUrls(desktop=UrlSet(page="https://en.wikipedia.org/wiki/Alpha")),
    )
    db.upsert_meta(connection, "Alpha", summary)
    db.upsert_edits(
        connection, date(2024, 1, 15), [EditedPage(page_title="Alpha", edits=2, rank=1)]
    )

    paths = db.write_parquet(connection, settings)

    assert {path.name for path in paths} >= {"article_meta.parquet", "edits.parquet"}
    assert all(path.exists() for path in paths)
