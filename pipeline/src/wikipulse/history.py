"""Per-article history fetches for selected candidates."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Protocol

import duckdb

from wikipulse import db, quality
from wikipulse.candidates import Candidate
from wikipulse.client import WikimediaError
from wikipulse.config import Settings
from wikipulse.models import ArticleResponse

logger = logging.getLogger(__name__)

_BASELINE_DAYS = 28


class HistorySource(Protocol):
    """The fetch one candidate history needs."""

    def fetch_article_daily(
        self, article: str, start: date, end: date, force: bool = False
    ) -> ArticleResponse: ...


@dataclass
class HistorySummary:
    """Article history fetch results."""

    articles_considered: int = 0
    articles_fetched: int = 0
    rows: int = 0
    failures: list[str] = field(default_factory=list)


def has_baseline(
    connection: duckdb.DuckDBPyConnection,
    article: str,
    day: date,
    minimum_days: int = _BASELINE_DAYS,
) -> bool:
    """Return True when the 28 days before a spike are already stored."""
    row = connection.execute(
        """
        SELECT count(*), max(day)
        FROM article_daily
        WHERE article = ? AND day BETWEEN ? AND ?
        """,
        [article, day - timedelta(days=minimum_days + 7), day - timedelta(days=1)],
    ).fetchone()
    if row is None:
        return False
    count, latest = int(row[0]), row[1]
    return count >= minimum_days and latest is not None and latest >= day - timedelta(days=3)


def fetch_candidate_history(
    settings: Settings,
    client: HistorySource,
    connection: duckdb.DuckDBPyConnection,
    candidates: Iterable[Candidate],
    *,
    lookback_days: int | None = None,
    force: bool = False,
) -> HistorySummary:
    """Fetch history for candidates that lack a baseline, one article at a time."""
    unique: dict[str, date] = {}
    for candidate in candidates:
        unique[candidate.article] = max(unique.get(candidate.article, candidate.day), candidate.day)
    summary = HistorySummary(articles_considered=len(unique))
    lookback = lookback_days or settings.candidate_history_days

    for index, (article, day) in enumerate(sorted(unique.items()), start=1):
        if not force and has_baseline(connection, article, day):
            continue
        start = day - timedelta(days=lookback)
        try:
            response = client.fetch_article_daily(article, start, day)
            quality.validate_article_daily(response.items)
            summary.rows += db.upsert_article_daily(connection, response.items)
            summary.articles_fetched += 1
        except (WikimediaError, quality.DataQualityError) as exc:
            summary.failures.append(f"{article}: {exc}")
            logger.warning("History failed for %s: %s", article, exc)
        if index % 10 == 0 or index == len(unique):
            logger.info(
                "History %d/%d candidates; %d fetched, %d rows, %d failures",
                index,
                len(unique),
                summary.articles_fetched,
                summary.rows,
                len(summary.failures),
            )
    return summary
