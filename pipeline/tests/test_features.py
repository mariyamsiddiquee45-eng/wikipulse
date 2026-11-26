import math
import statistics
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from wikipulse import db
from wikipulse.candidates import Candidate
from wikipulse.config import Settings
from wikipulse.features import (
    classify_shape,
    compute_features,
    peak_shape,
    robust_z,
    weekday_factor,
)
from wikipulse.models import ArticleDailyItem, TopArticle


def _connection(views: list[int], article: str = "Alpha") -> tuple[duckdb.DuckDBPyConnection, date]:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    start = date(2024, 1, 1)
    for offset, value in enumerate(views):
        day = start + timedelta(days=offset)
        db.upsert_top(connection, day, [TopArticle(article=article, views=value, rank=1)])
        db.upsert_article_daily(
            connection,
            [
                ArticleDailyItem(
                    project="en.wikipedia",
                    article=article,
                    granularity="daily",
                    timestamp=f"{day:%Y%m%d}00",
                    access="all-access",
                    agent="user",
                    views=value,
                )
            ],
        )
    return connection, start + timedelta(days=len(views) - 1)


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", candidate_history_days=400)


def test_spike_features_are_computed(tmp_path: Path) -> None:
    connection, day = _connection([100] * 34 + [2000])
    candidate = Candidate(day=day, article="Alpha", views=2000, rank=1, reasons=("new",))

    feature = compute_features(connection, _settings(tmp_path), candidate)

    assert feature is not None
    assert feature.is_spike
    assert feature.views == 2000
    assert feature.z_score > 100
    assert feature.peak_ratio == pytest.approx(20.0)
    assert feature.spike_type == "Flash"
    assert feature.features["minimum_views_flag"] is False
    assert math.isfinite(feature.score)


def test_short_history_is_skipped(tmp_path: Path) -> None:
    connection, day = _connection([100] * 5)
    candidate = Candidate(day=day, article="Alpha", views=100, rank=1, reasons=("new",))
    assert compute_features(connection, _settings(tmp_path), candidate) is None


def test_missing_spike_day_is_skipped(tmp_path: Path) -> None:
    connection, day = _connection([100] * 35)
    candidate = Candidate(
        day=day + timedelta(days=1), article="Alpha", views=100, rank=1, reasons=("new",)
    )
    assert compute_features(connection, _settings(tmp_path), candidate) is None


def test_peak_shape_reports_rise_and_half_life() -> None:
    start = date(2024, 1, 1)
    days = [start + timedelta(days=offset) for offset in range(7)]
    views = [100.0, 95.0, 105.0, 1000.0, 500.0, 120.0, 100.0]
    rise, time_to_peak, half_life = peak_shape(days, views, days[-1], baseline=100.0)
    assert rise == 0.0
    assert time_to_peak == 0.0
    assert half_life == 1.0


def test_weekday_factor_is_clamped_for_short_history() -> None:
    day = date(2024, 1, 1)
    assert weekday_factor([day], [100.0], day) == 1.0


def test_shape_rules_cover_all_types() -> None:
    assert (
        classify_shape(
            rise_days=0,
            half_life_days=1,
            peak_ratio=5,
            baseline=100,
            days_since_last_spike=None,
        )
        == "Flash"
    )
    assert (
        classify_shape(
            rise_days=3,
            half_life_days=None,
            peak_ratio=5,
            baseline=100,
            days_since_last_spike=None,
        )
        == "Slow burn"
    )
    assert (
        classify_shape(
            rise_days=0,
            half_life_days=1,
            peak_ratio=5,
            baseline=100,
            days_since_last_spike=10,
        )
        == "Recurring"
    )
    assert (
        classify_shape(
            rise_days=0,
            half_life_days=None,
            peak_ratio=1.2,
            baseline=10_000,
            days_since_last_spike=None,
        )
        == "Always-on"
    )


@given(
    st.lists(
        st.floats(1, 1_000_000, allow_nan=False, allow_infinity=False),
        min_size=7,
        max_size=28,
    ),
    st.floats(0.1, 10, allow_nan=False, allow_infinity=False),
)
def test_robust_z_is_scale_invariant(baseline: list[float], scale: float) -> None:
    median = statistics.median(baseline)
    mad = statistics.median([abs(value - median) for value in baseline])
    assume(mad > 0)
    unscaled = robust_z(2 * median, baseline)
    scaled = robust_z(2 * median * scale, [value * scale for value in baseline])
    assert scaled == pytest.approx(unscaled, rel=1e-9, abs=1e-6)


@given(
    st.lists(
        st.floats(0, 1_000_000, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=28,
    ),
    st.floats(0, 1_000_000, allow_nan=False, allow_infinity=False),
)
def test_robust_z_is_finite(baseline: list[float], views: float) -> None:
    assert math.isfinite(robust_z(views, baseline))
