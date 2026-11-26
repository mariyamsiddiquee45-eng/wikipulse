"""Candidate selection for per-article history fetches.

The pool is new entrants to the top 1000, large rank movers and the recent spike
watch list. Everything else is left alone so a daily run does not fetch history
for all 1000 articles.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import duckdb

from wikipulse.config import Settings
from wikipulse.filters import is_article_title

logger = logging.getLogger(__name__)

NEW_ENTRANT = "new_entrant"
RANK_MOVER = "rank_mover"
WATCHLIST = "watchlist"


@dataclass(frozen=True)
class Candidate:
    """One article worth fetching history for on a given day."""

    day: date
    article: str
    views: int
    rank: int
    reasons: tuple[str, ...]


def select_candidates(
    connection: duckdb.DuckDBPyConnection, day: date, settings: Settings
) -> list[Candidate]:
    """Select new entrants, rank movers and recent spikes from one day's top list."""
    today_rows = connection.execute(
        "SELECT article, views, rank FROM top_daily WHERE day = ? ORDER BY rank", [day]
    ).fetchall()
    if not today_rows:
        return []

    filenames = {row[0] for row in today_rows}
    filtered = [row for row in today_rows if is_article_title(str(row[0]), settings.denylist_items)]
    filtered_articles = {str(row[0]) for row in filtered}
    removed = len(filenames - filtered_articles)
    if removed:
        logger.debug("Filtered %d non-article titles on %s", removed, day)

    window_start = day - timedelta(days=settings.candidate_window_days)
    seen = {
        str(row[0])
        for row in connection.execute(
            "SELECT DISTINCT article FROM top_daily WHERE day BETWEEN ? AND ?",
            [window_start, day - timedelta(days=1)],
        ).fetchall()
    }
    previous_ranks = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            "SELECT article, rank FROM top_daily WHERE day = ?", [day - timedelta(days=1)]
        ).fetchall()
    }
    watchlist = {
        str(row[0])
        for row in connection.execute(
            "SELECT DISTINCT article FROM spikes WHERE day BETWEEN ? AND ?",
            [day - timedelta(days=settings.watchlist_days), day - timedelta(days=1)],
        ).fetchall()
    }

    reasons: dict[str, set[str]] = {}
    for article, _views, rank in filtered:
        name = str(article)
        if name not in seen:
            reasons.setdefault(name, set()).add(NEW_ENTRANT)
        previous = previous_ranks.get(name)
        if previous is not None and previous - int(rank) >= settings.rank_mover_delta:
            reasons.setdefault(name, set()).add(RANK_MOVER)
        if name in watchlist:
            reasons.setdefault(name, set()).add(WATCHLIST)

    selected = [
        Candidate(
            day=day,
            article=str(article),
            views=int(views),
            rank=int(rank),
            reasons=tuple(sorted(reasons[str(article)])),
        )
        for article, views, rank in filtered
        if str(article) in reasons
    ]
    selected.sort(key=lambda candidate: candidate.views, reverse=True)
    if settings.max_candidates_per_day:
        selected = selected[: settings.max_candidates_per_day]
    return selected
