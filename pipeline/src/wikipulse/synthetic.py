"""Synthetic article-day generator with planted spikes of known type and magnitude."""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

WEEKDAY_FACTORS = np.array([0.92, 1.02, 1.0, 1.0, 1.01, 1.04, 0.95])
SPIKE_TYPES = ("Flash", "Slow burn", "Recurring")


@dataclass(frozen=True)
class SyntheticDataset:
    """A generated frame plus the peak days that count as true spikes."""

    frame: pd.DataFrame
    spikes: pd.DataFrame


def generate_synthetic(
    *,
    days: int = 120,
    article_count: int = 50,
    seed: int = 7,
    spike_rate: float = 0.01,
) -> SyntheticDataset:
    """Generate article-day views with weekly seasonality and planted spike shapes."""
    if days < 35 or article_count < 1:
        raise ValueError("need at least 35 days and one article")
    rng = np.random.default_rng(seed)
    start = date(2024, 1, 1)
    day_list = [start + timedelta(days=offset) for offset in range(days)]
    rows: list[tuple[date, str, int, bool, float]] = []

    for article_index in range(article_count):
        article = f"Article_{article_index:04d}"
        base = float(rng.lognormal(mean=6.0, sigma=0.7)) + 120.0
        if rng.random() < 0.05:
            base *= 8.0
        noise = rng.normal(0.0, 0.12, size=days)
        weekday = WEEKDAY_FACTORS[[day.weekday() for day in day_list]]
        views = np.maximum(1.0, base * weekday * (1.0 + noise))
        true_spike = np.zeros(days, dtype=bool)
        magnitudes = np.zeros(days)

        spike_days = set(rng.choice(days, size=rng.poisson(spike_rate * days), replace=False))
        for index in sorted(spike_days):
            if index < 28 or index >= days:
                continue
            magnitude = float(rng.uniform(4.0, 15.0))
            kind = str(rng.choice(SPIKE_TYPES, p=[0.6, 0.25, 0.15]))
            if kind == "Slow burn":
                ramp = min(3, days - index)
                for offset in range(ramp):
                    views[index + offset] *= magnitude * (0.4 + 0.2 * offset)
                peak = index + ramp - 1
            elif kind == "Recurring":
                peak = index
                views[index] *= magnitude
                follow = index + 14
                if follow < days:
                    views[follow] *= magnitude * 0.9
                    true_spike[follow] = True
                    magnitudes[follow] = magnitude
            else:
                peak = index
                views[index] *= magnitude
            true_spike[peak] = True
            magnitudes[peak] = magnitude

        for offset, day in enumerate(day_list):
            rows.append(
                (
                    day,
                    article,
                    round(float(views[offset])),
                    bool(true_spike[offset]),
                    float(magnitudes[offset]),
                )
            )

    frame = pd.DataFrame(rows, columns=["day", "article", "views", "true_spike", "magnitude"])
    spikes = frame[frame["true_spike"]].copy()
    return SyntheticDataset(frame=frame, spikes=spikes)


def evaluate_detector(
    frame: pd.DataFrame,
    *,
    z_threshold: float = 3.0,
    minimum_views: int = 1000,
    baseline_days: int = 28,
) -> dict[str, float]:
    """Compute recall by magnitude band and the false-positive rate."""
    ordered = frame.sort_values(["article", "day"]).copy()
    grouped = ordered.groupby("article", sort=False)["views"]
    median = grouped.transform(
        lambda values: values.shift(1).rolling(baseline_days, min_periods=7).median()
    )
    mad = grouped.transform(
        lambda values: (
            values.shift(1)
            .rolling(baseline_days, min_periods=7)
            .apply(lambda window: float(np.median(np.abs(window - np.median(window)))), raw=True)
        )
    )
    sigma = 1.4826 * mad
    sigma = sigma.where(sigma > 0, 1.0)
    ordered["z_score"] = (ordered["views"] - median) / sigma
    ordered["predicted"] = (ordered["z_score"] >= z_threshold) & (ordered["views"] >= minimum_views)

    result: dict[str, float] = {}
    for low, high in ((3.0, 5.0), (5.0, 10.0), (10.0, float("inf"))):
        band = ordered[
            ordered["true_spike"] & (ordered["magnitude"] >= low) & (ordered["magnitude"] < high)
        ]
        key = f"recall_{int(low)}_{'plus' if high == float('inf') else int(high)}"
        result[key] = float(band["predicted"].mean()) if not band.empty else 1.0
    non_spikes = ordered[~ordered["true_spike"]]
    result["false_positive_rate"] = (
        float(non_spikes["predicted"].mean()) if not non_spikes.empty else 0.0
    )
    result["spike_count"] = float(ordered["true_spike"].sum())
    return result
