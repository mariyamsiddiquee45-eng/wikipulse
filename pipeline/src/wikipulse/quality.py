"""Pandera checks applied to fetched rows before they reach DuckDB."""

from collections.abc import Sequence
from datetime import date

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

from wikipulse.models import ArticleDailyItem, EditedPage, TopArticle


class DataQualityError(ValueError):
    """A fetched batch violates a documented invariant."""


TOP_SCHEMA = DataFrameSchema(
    {
        "article": Column(str, Check.str_length(min_value=1)),
        "views": Column("int64", Check.ge(0)),
        "rank": Column("int64", Check.ge(1)),
    },
    unique=["article"],
    strict=True,
    coerce=True,
)

ARTICLE_SCHEMA = DataFrameSchema(
    {
        "day": Column(object),
        "article": Column(str, Check.str_length(min_value=1)),
        "views": Column("int64", Check.ge(0)),
    },
    unique=["day", "article"],
    strict=True,
    coerce=True,
)

EDITS_SCHEMA = DataFrameSchema(
    {
        "article": Column(str, Check.str_length(min_value=1)),
        "edits": Column("int64", Check.ge(0)),
        "rank": Column("int64", Check.ge(1)),
    },
    unique=["article"],
    strict=True,
    coerce=True,
)


def validate_top(articles: Sequence[TopArticle]) -> None:
    """Check one day of top articles for non-negative views and unique titles."""
    if not articles:
        return
    frame = pd.DataFrame(
        [{"article": item.article, "views": item.views, "rank": item.rank} for item in articles]
    )
    _validate(TOP_SCHEMA, frame)


def validate_edits(pages: Sequence[EditedPage]) -> None:
    """Check one day of edited pages."""
    if not pages:
        return
    frame = pd.DataFrame(
        [{"article": item.page_title, "edits": item.edits, "rank": item.rank} for item in pages]
    )
    _validate(EDITS_SCHEMA, frame)


def validate_article_daily(items: Sequence[ArticleDailyItem]) -> None:
    """Check per-article daily views for duplicates and negative counts."""
    if not items:
        return
    frame = pd.DataFrame(
        [{"day": item.date, "article": item.article, "views": item.views} for item in items]
    )
    _validate(ARTICLE_SCHEMA, frame)


def missing_days(start: date, end: date, present: set[date]) -> list[date]:
    """Return every calendar day in the inclusive range that has no data."""
    if start > end:
        raise ValueError("start must not be after end")
    result: list[date] = []
    current = start
    while current <= end:
        if current not in present:
            result.append(current)
        current = current.fromordinal(current.toordinal() + 1)
    return result


def _validate(schema: DataFrameSchema, frame: pd.DataFrame) -> None:
    try:
        schema.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        raise DataQualityError(str(exc)) from exc
