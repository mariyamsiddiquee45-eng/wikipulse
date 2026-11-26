from datetime import date, datetime, time

import duckdb

from wikipulse import db
from wikipulse.client import ApiError
from wikipulse.config import Settings
from wikipulse.ingest import backfill, ingest_day
from wikipulse.models import (
    EditedItem,
    EditedResponse,
    TopArticle,
    TopDay,
    TopResponse,
)


def _top(day: date) -> TopResponse:
    return TopResponse(
        items=[
            TopDay(
                project="en.wikipedia",
                access="all-access",
                year=f"{day.year:04d}",
                month=f"{day.month:02d}",
                day=f"{day.day:02d}",
                articles=[TopArticle(article="Alpha", views=100, rank=1)],
            )
        ]
    )


def _edits(day: date) -> EditedResponse:
    return EditedResponse(
        items=[
            EditedItem.model_validate(
                {
                    "project": "en.wikipedia",
                    "editor-type": "all-editor-types",
                    "page-type": "content",
                    "granularity": "daily",
                    "results": [
                        {
                            "timestamp": datetime.combine(day, time()),
                            "top": [{"page_title": "Alpha", "edits": 3, "rank": 1}],
                        }
                    ],
                }
            )
        ]
    )


class StubSource:
    def __init__(
        self, fail_top: set[date] | None = None, fail_edits: set[date] | None = None
    ) -> None:
        self.fail_top = fail_top or set()
        self.fail_edits = fail_edits or set()
        self.top_calls: list[date] = []
        self.edit_calls: list[date] = []

    def fetch_top(self, day: date, force: bool = False) -> TopResponse:
        del force
        self.top_calls.append(day)
        if day in self.fail_top:
            raise ApiError(500, "test", "top failed")
        return _top(day)

    def fetch_edited(self, day: date, force: bool = False) -> EditedResponse:
        del force
        self.edit_calls.append(day)
        if day in self.fail_edits:
            raise ApiError(500, "test", "edits failed")
        return _edits(day)


def test_ingest_day_is_idempotent(settings: Settings) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    source = StubSource()
    day = date(2024, 1, 15)

    first = ingest_day(source, connection, day)
    second = ingest_day(source, connection, day)

    assert first.ok
    assert second.ok
    assert connection.execute("SELECT count(*) FROM top_daily").fetchone() == (1,)
    assert connection.execute("SELECT count(*) FROM edits").fetchone() == (1,)
    assert db.day_flags(connection, day) == (True, True)


def test_backfill_skips_complete_days(settings: Settings) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    source = StubSource()
    day = date(2024, 1, 15)
    ingest_day(source, connection, day)

    summary = backfill(settings, source, connection, day, day)

    assert summary.days_skipped == 1
    assert summary.days_ingested == 0
    assert source.top_calls == [day]


def test_failed_day_is_recorded_and_retried(settings: Settings) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    bad = date(2024, 1, 16)
    source = StubSource(fail_top={bad})

    summary = backfill(settings, source, connection, date(2024, 1, 15), bad)

    assert summary.failures
    assert db.day_flags(connection, bad) == (False, True)

    source.fail_top.clear()
    retry = backfill(settings, source, connection, date(2024, 1, 15), bad)

    assert retry.days_ingested == 1
    assert retry.days_skipped == 1
    assert source.top_calls.count(bad) == 2


def test_unpublished_edits_leave_day_retryable(settings: Settings) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = date(2024, 1, 18)

    class NoEdits(StubSource):
        def fetch_edited(self, day: date, force: bool = False) -> EditedResponse:
            del force
            self.edit_calls.append(day)
            return EditedResponse(items=[])

    source = NoEdits()
    result = ingest_day(source, connection, day)

    assert result.ok
    assert result.edit_rows == 0
    assert db.day_flags(connection, day) == (True, False)


def test_both_sources_failing_keeps_day_incomplete(settings: Settings) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = date(2024, 1, 17)
    source = StubSource(fail_top={day}, fail_edits={day})

    result = ingest_day(source, connection, day)

    assert not result.ok
    assert db.day_flags(connection, day) == (False, False)
    row = connection.execute("SELECT error FROM days WHERE day = ?", [day]).fetchone()
    assert row is not None
    assert "top failed" in row[0]
