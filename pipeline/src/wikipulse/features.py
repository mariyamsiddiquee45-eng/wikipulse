"""Spike features and the rule-based baseline detector."""

import hashlib
import logging
import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from wikipulse import db
from wikipulse.candidates import Candidate, select_candidates
from wikipulse.config import Settings
from wikipulse.models import SpikeRecord

logger = logging.getLogger(__name__)

BASELINE_DAYS = 28
MIN_BASELINE_ROWS = 7
PEAK_WINDOW_DAYS = 7


@dataclass(frozen=True)
class FeatureSet:
    """Computed features for one candidate spike on one day."""

    day: date
    article: str
    views: int
    baseline: float
    z_score: float
    stl_residual: float | None
    yoy_ratio: float | None
    rise_days: float | None
    time_to_peak_days: float | None
    half_life_days: float | None
    peak_ratio: float
    rank_jump: int | None
    days_since_last_spike: int | None
    edit_surge: bool
    score: float
    spike_type: str
    is_spike: bool
    features: dict[str, float | int | str | bool | None]

    @property
    def spike_id(self) -> str:
        return hashlib.sha256(f"{self.day.isoformat()}|{self.article}".encode()).hexdigest()[:16]

    def to_record(self) -> SpikeRecord:
        """Convert to the DuckDB row model."""
        return SpikeRecord(
            spike_id=self.spike_id,
            day=self.day,
            article=self.article,
            views=self.views,
            baseline=self.baseline,
            z_score=self.z_score,
            peak_ratio=self.peak_ratio,
            rise_days=self.rise_days,
            time_to_peak_days=self.time_to_peak_days,
            half_life_days=self.half_life_days,
            yoy_ratio=self.yoy_ratio,
            rank_jump=self.rank_jump,
            days_since_last_spike=self.days_since_last_spike,
            edit_surge=self.edit_surge,
            stl_residual=self.stl_residual,
            score=self.score,
            spike_type=self.spike_type,
            features=self.features,
        )


def robust_z(views: float, baseline: list[float], weekday_factor: float = 1.0) -> float:
    """Return a median/MAD z-score; a zero MAD falls back to unit scale."""
    median = statistics.median(baseline)
    mad = statistics.median([abs(value - median) for value in baseline])
    sigma = 1.4826 * mad
    if sigma <= 0:
        sigma = 1.0
    return (views - median * weekday_factor) / sigma


def weekday_factor(days: list[date], values: list[float], target: date) -> float:
    """Return the target weekday's median relative to the overall median, clamped."""
    same = [
        value for day, value in zip(days, values, strict=True) if day.weekday() == target.weekday()
    ]
    if len(same) < 2:
        return 1.0
    base = statistics.median(values)
    if base <= 0:
        return 1.0
    return max(0.1, min(10.0, statistics.median(same) / base))


def peak_shape(
    days: list[date], views: list[float], current: date, baseline: float
) -> tuple[float | None, float | None, float | None]:
    """Return rise days, time to peak and half-life using only data up to current."""
    window = [
        (day, value)
        for day, value in zip(days, views, strict=True)
        if current - timedelta(days=PEAK_WINDOW_DAYS) <= day <= current
    ]
    if not window:
        return None, None, None
    peak_index = max(range(len(window)), key=lambda index: window[index][1])
    peak_day, peak_value = window[peak_index]

    threshold = baseline + 0.1 * (peak_value - baseline)
    rise = 0
    index = peak_index
    while index > 0 and window[index - 1][1] > threshold:
        rise += 1
        index -= 1

    above_double = [day for day, value in window if value >= 2 * max(baseline, 1.0)]
    time_to_peak = float((peak_day - above_double[0]).days) if above_double else 0.0

    half_life: float | None = None
    half_target = baseline + (peak_value - baseline) / 2
    for day, value in window[peak_index + 1 :]:
        if value <= half_target:
            half_life = float((day - peak_day).days)
            break
    return float(rise), time_to_peak, half_life


def classify_shape(
    *,
    rise_days: float | None,
    half_life_days: float | None,
    peak_ratio: float,
    baseline: float,
    days_since_last_spike: int | None,
) -> str:
    """Assign one of Flash, Slow burn, Recurring, Always-on by documented rules."""
    if baseline >= 5000 and peak_ratio < 2:
        return "Always-on"
    if days_since_last_spike is not None and days_since_last_spike <= 30:
        return "Recurring"
    if rise_days is not None and rise_days >= 3:
        return "Slow burn"
    if half_life_days is not None and half_life_days <= 2:
        return "Flash"
    return "Flash" if peak_ratio >= 2 else "Always-on"


def is_spike(z_score: float, views: int, settings: Settings) -> bool:
    """Apply baseline A: robust z above the threshold with a views floor."""
    return z_score >= settings.z_threshold and views >= settings.minimum_views


def _stl_residual(views: list[float]) -> float | None:
    if len(views) < 365 or len(set(views)) < 3:
        return None
    try:
        fitted = STL(np.asarray(views, dtype=float), period=7, robust=True).fit()
    except (ValueError, np.linalg.LinAlgError):
        return None
    residuals = np.asarray(fitted.resid, dtype=float)
    mad = float(np.median(np.abs(residuals - np.median(residuals))))
    sigma = 1.4826 * mad
    if sigma <= 0:
        return None
    return round(float(residuals[-1] / sigma), 6)


def compute_features(
    connection: duckdb.DuckDBPyConnection, settings: Settings, candidate: Candidate
) -> FeatureSet | None:
    """Compute features from stored history; returns None when history is insufficient."""
    start = candidate.day - timedelta(days=settings.candidate_history_days)
    rows = connection.execute(
        """
        SELECT day, views FROM article_daily
        WHERE article = ? AND day BETWEEN ? AND ?
        ORDER BY day
        """,
        [candidate.article, start, candidate.day],
    ).fetchall()
    days = [row[0] for row in rows]
    views = [float(row[1]) for row in rows]
    if not days or days[-1] != candidate.day:
        return None

    baseline_days = [
        day for day in days if candidate.day - timedelta(days=BASELINE_DAYS) <= day < candidate.day
    ]
    if len(baseline_days) < MIN_BASELINE_ROWS:
        return None
    baseline_set = set(baseline_days)
    baseline_values = [value for day, value in zip(days, views, strict=True) if day in baseline_set]
    factor = weekday_factor(baseline_days, baseline_values, candidate.day)
    z_score = robust_z(views[-1], baseline_values, factor)
    baseline = statistics.median(baseline_values) * factor

    rise, time_to_peak, half_life = peak_shape(days, views, candidate.day, baseline)
    peak_ratio = views[-1] / max(baseline, 1.0)
    yoy_ratio: float | None = None
    year_ago = candidate.day - timedelta(days=364)
    if year_ago in days:
        year_value = views[days.index(year_ago)]
        if year_value > 0:
            yoy_ratio = views[-1] / year_value

    rank_row = connection.execute(
        "SELECT rank FROM top_daily WHERE day = ? AND article = ?",
        [candidate.day, candidate.article],
    ).fetchone()
    previous_rank = connection.execute(
        "SELECT rank FROM top_daily WHERE day = ? AND article = ?",
        [candidate.day - timedelta(days=1), candidate.article],
    ).fetchone()
    rank_jump = (
        int(previous_rank[0]) - int(rank_row[0])
        if rank_row is not None and previous_rank is not None
        else None
    )

    last_spike = db.last_spike_day(connection, candidate.article, candidate.day)
    days_since = (candidate.day - last_spike).days if last_spike is not None else None
    week_values = [
        value
        for day, value in zip(days, views, strict=True)
        if candidate.day - timedelta(days=7) <= day < candidate.day
    ]
    week_ratio = views[-1] / statistics.median(week_values) if week_values else None
    edit_row = connection.execute(
        "SELECT 1 FROM edits WHERE day = ? AND article = ?",
        [candidate.day, candidate.article],
    ).fetchone()
    edit_surge = edit_row is not None
    stl_value = _stl_residual(views)
    spike_type = classify_shape(
        rise_days=rise,
        half_life_days=half_life,
        peak_ratio=peak_ratio,
        baseline=baseline,
        days_since_last_spike=days_since,
    )
    score = z_score * math.log10(1 + views[-1])
    detected = is_spike(z_score, int(views[-1]), settings)

    features: dict[str, float | int | str | bool | None] = {
        "views": int(views[-1]),
        "baseline": round(baseline, 3),
        "z_score": round(z_score, 6),
        "stl_residual": stl_value,
        "yoy_ratio": round(yoy_ratio, 6) if yoy_ratio is not None else None,
        "rise_days": rise,
        "time_to_peak_days": time_to_peak,
        "half_life_days": half_life,
        "peak_ratio": round(peak_ratio, 6),
        "rank_jump": rank_jump,
        "rank": candidate.rank,
        "week_ratio": round(week_ratio, 6) if week_ratio is not None else None,
        "days_since_last_spike": days_since,
        "edit_surge": edit_surge,
        "minimum_views_flag": int(views[-1]) < settings.minimum_views,
        "is_spike": detected,
        "spike_type": spike_type,
    }
    return FeatureSet(
        day=candidate.day,
        article=candidate.article,
        views=int(views[-1]),
        baseline=round(baseline, 3),
        z_score=round(z_score, 6),
        stl_residual=stl_value,
        yoy_ratio=round(yoy_ratio, 6) if yoy_ratio is not None else None,
        rise_days=rise,
        time_to_peak_days=time_to_peak,
        half_life_days=half_life,
        peak_ratio=round(peak_ratio, 6),
        rank_jump=rank_jump,
        days_since_last_spike=days_since,
        edit_surge=edit_surge,
        score=round(score, 6),
        spike_type=spike_type,
        is_spike=detected,
        features=features,
    )


def collect_features(
    connection: duckdb.DuckDBPyConnection, settings: Settings, start: date, end: date
) -> list[FeatureSet]:
    """Compute features for every candidate in the inclusive date range."""
    results: list[FeatureSet] = []
    current = start
    while current <= end:
        candidates = select_candidates(connection, current, settings)
        for candidate in candidates:
            feature = compute_features(connection, settings, candidate)
            if feature is not None:
                results.append(feature)
        current += timedelta(days=1)
    return results


def detect_range(
    connection: duckdb.DuckDBPyConnection, settings: Settings, start: date, end: date
) -> tuple[list[FeatureSet], int]:
    """Compute and store spikes one day at a time so recurring checks see earlier days."""
    results: list[FeatureSet] = []
    inserted = 0
    current = start
    while current <= end:
        day_features: list[FeatureSet] = []
        for candidate in select_candidates(connection, current, settings):
            feature = compute_features(connection, settings, candidate)
            if feature is not None:
                day_features.append(feature)
        detected = [feature for feature in day_features if feature.is_spike]
        inserted += db.upsert_spikes(connection, [feature.to_record() for feature in detected])
        results.extend(day_features)
        current += timedelta(days=1)
    return results, inserted


def features_frame(features: list[FeatureSet]) -> pd.DataFrame:
    """Return a pandas DataFrame for the Parquet feature snapshot."""
    return pd.DataFrame(
        [
            {
                "spike_id": feature.spike_id,
                "day": feature.day,
                "article": feature.article,
                **feature.features,
                "score": feature.score,
            }
            for feature in features
        ]
    )
