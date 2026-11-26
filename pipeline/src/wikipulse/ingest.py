"""Resumable ingestion of top pageviews and daily edit analytics."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

import duckdb

from wikipulse import db, quality
from wikipulse.client import WikimediaError
from wikipulse.config import Settings
from wikipulse.models import EditedResponse, TopResponse

logger = logging.getLogger(__name__)


class IngestSource(Protocol):
    """The two fetches a backfill needs."""

    def fetch_top(self, day: date, force: bool = False) -> TopResponse: ...

    def fetch_edited(self, day: date, force: bool = False) -> EditedResponse: ...


def last_complete_day() -> date:
    """Return yesterday in UTC, the newest day the API publishes as complete."""
    return datetime.now(UTC).date() - timedelta(days=1)


@dataclass
class DayIngest:
    """Row counts and failures for one ingested day."""

    day: date
    top_rows: int = 0
    edit_rows: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass
class BackfillSummary:
    """Aggregate result of a backfill run."""

    days_requested: int = 0
    days_skipped: int = 0
    days_ingested: int = 0
    top_rows: int = 0
    edit_rows: int = 0
    failures: list[str] = field(default_factory=list)


def ingest_day(client: IngestSource, connection: duckdb.DuckDBPyConnection, day: date) -> DayIngest:
    """Fetch and upsert one day; failures are recorded in the days table, not raised."""
    result = DayIngest(day=day)
    top_ok = False
    edits_ok = False

    try:
        top = client.fetch_top(day)
        if len(top.items) != 1 or top.items[0].date != day:
            raise WikimediaError(f"Top response does not describe {day}")
        quality.validate_top(top.items[0].articles)
        result.top_rows = db.upsert_top(connection, day, top.items[0].articles)
        top_ok = True
    except (WikimediaError, quality.DataQualityError) as exc:
        result.failures.append(f"top {day}: {exc}")
        logger.warning("Top pageviews failed for %s: %s", day, exc)

    try:
        edited = client.fetch_edited(day)
        pages = [
            page
            for item in edited.items
            for result_item in item.results
            for page in result_item.top
        ]
        quality.validate_edits(pages)
        result.edit_rows = db.upsert_edits(connection, day, pages)
        # Edit analytics publish about two months late; an empty response means
        # "not published yet", never "zero edits", so the day stays retryable.
        edits_ok = bool(pages)
        if not pages:
            logger.info("Edit analytics not published yet for %s; will retry", day)
    except (WikimediaError, quality.DataQualityError) as exc:
        result.failures.append(f"edits {day}: {exc}")
        logger.warning("Edit analytics failed for %s: %s", day, exc)

    db.mark_day(
        connection,
        day,
        top_ok=top_ok,
        edits_ok=edits_ok,
        error="; ".join(result.failures) if result.failures else None,
    )
    return result


def backfill(
    settings: Settings,
    client: IngestSource,
    connection: duckdb.DuckDBPyConnection,
    start: date,
    end: date,
    force: bool = False,
) -> BackfillSummary:
    """Ingest every day in the inclusive range, skipping days already complete."""
    if start > end:
        raise ValueError("start must not be after end")
    total = (end - start).days + 1
    summary = BackfillSummary(days_requested=total)
    logger.info("Backfill %s to %s (%d days)", start, end, total)

    current = start
    position = 0
    while current <= end:
        position += 1
        top_ok, edits_ok = db.day_flags(connection, current)
        if not force and top_ok and edits_ok:
            summary.days_skipped += 1
        else:
            result = ingest_day(client, connection, current)
            if result.ok:
                summary.days_ingested += 1
            else:
                summary.failures.extend(result.failures)
            summary.top_rows += result.top_rows
            summary.edit_rows += result.edit_rows
        if position % 25 == 0 or position == total:
            logger.info(
                "Progress %d/%d days; %d ingested, %d skipped, %d failures",
                position,
                total,
                summary.days_ingested,
                summary.days_skipped,
                len(summary.failures),
            )
        current += timedelta(days=1)
    return summary


def backfill_history(
    settings: Settings,
    client: IngestSource,
    connection: duckdb.DuckDBPyConnection,
    *,
    days: int | None = None,
    end: date | None = None,
    force: bool = False,
) -> BackfillSummary:
    """Backfill the configured history window, ending at the last complete day."""
    finish = end or last_complete_day()
    span = days or settings.history_days
    start = finish - timedelta(days=span - 1)
    return backfill(settings, client, connection, start, finish, force=force)
