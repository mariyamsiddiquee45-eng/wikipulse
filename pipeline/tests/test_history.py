from datetime import date, timedelta
from pathlib import Path

import duckdb

from wikipulse import db
from wikipulse.candidates import Candidate
from wikipulse.config import Settings
from wikipulse.history import fetch_candidate_history, has_baseline
from wikipulse.models import ArticleDailyItem, ArticleResponse


class StubHistory:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date, date]] = []

    def fetch_article_daily(
        self, article: str, start: date, end: date, force: bool = False
    ) -> ArticleResponse:
        del force
        self.calls.append((article, start, end))
        items = []
        current = start
        while current <= end:
            items.append(
                ArticleDailyItem(
                    project="en.wikipedia",
                    article=article,
                    granularity="daily",
                    timestamp=f"{current:%Y%m%d}00",
                    access="all-access",
                    agent="user",
                    views=100,
                )
            )
            current += timedelta(days=1)
        return ArticleResponse(items=items)


class NeverCalled(StubHistory):
    def fetch_article_daily(
        self, article: str, start: date, end: date, force: bool = False
    ) -> ArticleResponse:
        raise AssertionError(f"unexpected history fetch for {article}")


def test_history_fetch_stores_rows_and_then_skips(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = date(2024, 1, 31)
    candidate = Candidate(day=day, article="Alpha", views=1000, rank=1, reasons=("new_entrant",))
    client = StubHistory()

    first = fetch_candidate_history(settings, client, connection, [candidate])
    second = fetch_candidate_history(settings, NeverCalled(), connection, [candidate])

    assert first.articles_fetched == 1
    assert first.rows == 401
    assert second.articles_fetched == 0
    assert len(client.calls) == 1
    assert has_baseline(connection, "Alpha", day)
