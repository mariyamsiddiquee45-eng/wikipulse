from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from wikipulse import db
from wikipulse.labels import (
    SPARKLINE_CHARS,
    LabelError,
    LabelRow,
    SpikeSample,
    append_label,
    format_sample,
    label_counts,
    load_labels,
    run_label_session,
    sample_spikes,
    sparkline,
)


def _insert_spike(
    connection: duckdb.DuckDBPyConnection,
    spike_id: str,
    article: str,
    day: date,
    z_score: float = 5.0,
) -> None:
    connection.execute(
        """
        INSERT INTO spikes (spike_id, day, article, views, score, spike_type, features, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [spike_id, day, article, 1000, z_score, "Flash", "{}", db.utc_now()],
    )


def test_label_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "labels.csv"
    row = LabelRow(
        spike_id="a1",
        article="Alpha",
        date=date(2024, 1, 1),
        label="event",
        labeler="tester",
        labeled_at=datetime(2024, 1, 2, 3, 4, 5),
        note="real event",
    )
    append_label(path, row)

    loaded = load_labels(path)

    assert loaded["a1"] == row
    assert label_counts(loaded.values()) == {"event": 1}


def test_invalid_label_value_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "labels.csv"
    path.write_text(
        "spike_id,article,date,label,labeler,labeled_at,note\n"
        "a1,Alpha,2024-01-01,maybe,tester,2024-01-02T03:04:05,\n",
        encoding="utf-8",
    )
    with pytest.raises(LabelError, match="Unknown label"):
        load_labels(path)


def test_duplicate_spike_label_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "labels.csv"
    row = LabelRow(
        spike_id="a1",
        article="Alpha",
        date=date(2024, 1, 1),
        label="event",
        labeler="tester",
        labeled_at=datetime(2024, 1, 2),
    )
    append_label(path, row)
    append_label(path, row)
    with pytest.raises(LabelError, match="Duplicate"):
        load_labels(path)


def test_sampling_is_year_stratified_and_deterministic(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    for year in range(2021, 2026):
        for index in range(3):
            _insert_spike(
                connection, f"{year}-{index}", f"Article_{year}_{index}", date(year, 6, 1)
            )

    first = sample_spikes(connection, 10, seed=7)
    second = sample_spikes(connection, 10, seed=7)

    assert len(first) == 10
    assert [sample.spike_id for sample in first] == [sample.spike_id for sample in second]
    years = [sample.day.year for sample in first]
    assert set(years) == {2021, 2022, 2023, 2024, 2025}
    assert all(years.count(year) == 2 for year in set(years))


def test_sampling_excludes_labeled_ids(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    _insert_spike(connection, "a1", "Alpha", date(2024, 1, 1))
    _insert_spike(connection, "a2", "Beta", date(2024, 1, 2))

    samples = sample_spikes(connection, 5, exclude={"a1"})

    assert [sample.spike_id for sample in samples] == ["a2"]


def test_sparkline_is_fixed_width_and_uses_expected_chars() -> None:
    line = sparkline([1, 5, 2, 9, 3], width=4)
    assert len(line) == 4
    assert set(line) <= set(SPARKLINE_CHARS)
    assert sparkline([5, 5, 5]) == SPARKLINE_CHARS[0] * 3
    assert sparkline([]) == ""


def test_session_appends_valid_rows(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    path = tmp_path / "labels.csv"
    samples = [
        SpikeSample(
            spike_id="a1",
            article="Alpha",
            day=date(2024, 1, 1),
            views=1000,
            baseline=100.0,
            z_score=9.0,
            peak_ratio=10.0,
            rise_days=0.0,
            half_life_days=None,
            yoy_ratio=None,
            edit_surge=False,
            spike_type="Flash",
        ),
        SpikeSample(
            spike_id="a2",
            article="Beta",
            day=date(2024, 1, 2),
            views=2000,
            baseline=200.0,
            z_score=8.0,
            peak_ratio=10.0,
            rise_days=1.0,
            half_life_days=2.0,
            yoy_ratio=1.5,
            edit_surge=True,
            spike_type="Slow burn",
        ),
    ]
    answers = iter(["e", "n"])
    echoed: list[str] = []

    labeled, skipped = run_label_session(
        connection,
        samples,
        path=path,
        labeler="tester",
        ask=lambda _prompt: next(answers),
        echo=echoed.append,
    )

    assert (labeled, skipped) == (2, 0)
    assert label_counts(load_labels(path).values()) == {"event": 1, "noise": 1}
    assert any("en.wikipedia.org/wiki/Beta" in line for line in echoed)


def test_format_sample_includes_url() -> None:
    sample = SpikeSample(
        spike_id="a1",
        article="Albert_Einstein",
        day=date(2024, 1, 1),
        views=100,
        baseline=10.0,
        z_score=3.0,
        peak_ratio=10.0,
        rise_days=0.0,
        half_life_days=None,
        yoy_ratio=None,
        edit_surge=False,
        spike_type="Flash",
    )
    assert "https://en.wikipedia.org/wiki/Albert_Einstein" in format_sample(sample, [1, 2])
