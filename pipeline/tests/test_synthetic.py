import time

import pytest

from wikipulse.synthetic import evaluate_detector, generate_synthetic


def test_synthetic_generator_plants_known_spikes() -> None:
    dataset = generate_synthetic(days=90, article_count=12, seed=3)
    assert len(dataset.frame) == 90 * 12
    assert not dataset.spikes.empty
    assert (dataset.spikes["magnitude"] >= 4.0).all()


def test_rule_detector_meets_recall_and_false_positive_targets() -> None:
    dataset = generate_synthetic(days=180, article_count=80, seed=11, spike_rate=0.02)
    metrics = evaluate_detector(dataset.frame)

    assert metrics["recall_5_10"] >= 0.85
    assert metrics["recall_10_plus"] >= 0.85
    assert metrics["false_positive_rate"] <= 0.03


def test_generator_rejects_too_short_history() -> None:
    with pytest.raises(ValueError, match="35 days"):
        generate_synthetic(days=10, article_count=2)


@pytest.mark.slow
def test_two_million_article_days_inside_budget() -> None:
    started = time.perf_counter()
    dataset = generate_synthetic(days=2000, article_count=1000, seed=1, spike_rate=0.0005)
    elapsed = time.perf_counter() - started
    assert len(dataset.frame) == 2_000_000
    assert elapsed < 180
