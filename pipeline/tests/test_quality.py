from datetime import date

import pytest

from wikipulse.models import ArticleDailyItem, TopArticle
from wikipulse.quality import (
    DataQualityError,
    missing_days,
    validate_article_daily,
    validate_top,
)


def test_duplicate_articles_fail_quality() -> None:
    rows = [
        TopArticle(article="Alpha", views=10, rank=1),
        TopArticle(article="Alpha", views=9, rank=2),
    ]
    with pytest.raises(DataQualityError):
        validate_top(rows)


def test_negative_views_fail_quality() -> None:
    invalid = TopArticle.model_construct(article="Alpha", views=-1, rank=1)
    with pytest.raises(DataQualityError):
        validate_top([invalid])


def test_article_daily_duplicate_day_fails_quality() -> None:
    items = [
        ArticleDailyItem(
            project="en.wikipedia",
            article="Alpha",
            granularity="daily",
            timestamp="2024011500",
            access="all-access",
            agent="user",
            views=5,
        ),
        ArticleDailyItem(
            project="en.wikipedia",
            article="Alpha",
            granularity="daily",
            timestamp="2024011500",
            access="all-access",
            agent="user",
            views=6,
        ),
    ]
    with pytest.raises(DataQualityError):
        validate_article_daily(items)


def test_missing_days_reports_gaps() -> None:
    present = {date(2024, 1, 1), date(2024, 1, 3)}
    assert missing_days(date(2024, 1, 1), date(2024, 1, 3), present) == [date(2024, 1, 2)]
