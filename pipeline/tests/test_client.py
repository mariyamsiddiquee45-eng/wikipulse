from datetime import date
from pathlib import Path

import pytest

from tests.support import FakeResponse, FakeSession, load_fixture
from wikipulse.client import (
    ApiError,
    MissingContactError,
    NotFoundError,
    WikimediaClient,
    WikimediaError,
)
from wikipulse.config import Settings


def test_fetch_top_sends_policy_user_agent(settings: Settings) -> None:
    session = FakeSession([FakeResponse(200, load_fixture("pageviews_top_2024-01-15.json"))])
    client = WikimediaClient(settings, session=session, sleep=lambda _: None)

    response = client.fetch_top(date(2024, 1, 15))

    assert response.items[0].day == "15"
    assert session.calls[0][1]["User-Agent"] == "WikiPulse/0.0.0 (test@example.com)"


def test_fetch_top_uses_cache_without_network(settings: Settings) -> None:
    first = WikimediaClient(
        settings,
        session=FakeSession([FakeResponse(200, load_fixture("pageviews_top_2024-01-15.json"))]),
        sleep=lambda _: None,
    )
    expected = first.fetch_top(date(2024, 1, 15))

    second = WikimediaClient(settings, session=FakeSession([]), sleep=lambda _: None)
    assert second.fetch_top(date(2024, 1, 15)) == expected


def test_retry_honors_retry_after(settings: Settings) -> None:
    sleeps: list[float] = []
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "2"}),
            FakeResponse(200, load_fixture("pageviews_top_2024-01-15.json")),
        ]
    )
    client = WikimediaClient(settings, session=session, sleep=sleeps.append)

    client.fetch_top(date(2024, 1, 15))

    assert 2.0 in sleeps


def test_missing_summary_raises_not_found(settings: Settings) -> None:
    client = WikimediaClient(
        settings,
        session=FakeSession([FakeResponse(404, text='{"status":404}')]),
        sleep=lambda _: None,
    )
    with pytest.raises(NotFoundError):
        client.fetch_summary("No_Such_Article")


def test_non_retryable_error_raises_api_error(settings: Settings) -> None:
    client = WikimediaClient(
        settings,
        session=FakeSession([FakeResponse(403, text="forbidden")]),
        sleep=lambda _: None,
    )
    with pytest.raises(ApiError):
        client.fetch_top(date(2024, 1, 15))


def test_malformed_json_fails_loudly(settings: Settings) -> None:
    client = WikimediaClient(
        settings,
        session=FakeSession([FakeResponse(200, text="not json")]),
        sleep=lambda _: None,
    )
    with pytest.raises(WikimediaError):
        client.fetch_top(date(2024, 1, 15))


def test_placeholder_contact_is_rejected(tmp_path: Path) -> None:
    settings = Settings(contact="you@example.com", data_dir=tmp_path / "data")
    with pytest.raises(MissingContactError):
        WikimediaClient(settings)


def test_missing_article_history_returns_empty(settings: Settings) -> None:
    client = WikimediaClient(
        settings,
        session=FakeSession([FakeResponse(404, text='{"status":404}')]),
        sleep=lambda _: None,
    )
    response = client.fetch_article_daily("Missing", date(2024, 1, 1), date(2024, 1, 2))
    assert response.items == []
