import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

import duckdb
import pandas as pd

from wikipulse import db
from wikipulse.classifier import (
    FEATURE_COLUMNS,
    classify_spikes,
    cross_validate,
    expanding_splits,
    train_classifier,
)
from wikipulse.config import Settings
from wikipulse.labels import LabelRow, append_label
from wikipulse.synthetic import generate_synthetic, synthetic_training_frame


def test_expanding_splits_never_leak_future_days() -> None:
    days = pd.Series(
        [date(2024, 1, 1) + timedelta(days=index) for index in range(20) for _ in range(3)]
    )
    splits = expanding_splits(days, n_splits=4)

    assert len(splits) >= 3
    for train_mask, validation_mask in splits:
        assert validation_mask.any()
        assert days[train_mask].max() < days[validation_mask].min()


def test_logistic_meets_metric_floor_on_synthetic_data() -> None:
    dataset = generate_synthetic(days=120, article_count=100, seed=5, spike_rate=0.03)
    frame = synthetic_training_frame(dataset)

    model, metrics, pooled = cross_validate(frame, "logistic", n_splits=3)

    assert model is not None
    assert not pooled.empty
    assert metrics["event_f1"] >= 0.70
    assert metrics["macro_f1"] >= 0.65
    assert metrics["brier"] <= 0.25


def test_lightgbm_meets_metric_floor_on_synthetic_data() -> None:
    dataset = generate_synthetic(days=120, article_count=60, seed=9, spike_rate=0.03)
    frame = synthetic_training_frame(dataset)

    model, metrics, _pooled = cross_validate(frame, "lightgbm", n_splits=2)

    assert model is not None
    assert metrics["event_f1"] >= 0.70


def test_training_and_classification_roundtrip(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    dataset = generate_synthetic(days=90, article_count=40, seed=13, spike_rate=0.05)
    frame = synthetic_training_frame(dataset)
    sample = frame.sample(n=240, random_state=0)

    spike_rows = []
    for record in sample.to_dict("records"):
        features = {
            column: (None if pd.isna(record.get(column)) else float(record[column]))
            for column in FEATURE_COLUMNS
        }
        spike_rows.append(
            (
                str(record["spike_id"]),
                record["day"],
                str(record["article"]),
                int(record["views"]),
                float(record["z_score"]),
                "Flash",
                json.dumps(features),
                db.utc_now(),
            )
        )
    connection.executemany(
        """
        INSERT INTO spikes (spike_id, day, article, views, score, spike_type, features, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        spike_rows,
    )

    labels_path = tmp_path / "labels.csv"
    for record in sample.to_dict("records"):
        append_label(
            labels_path,
            LabelRow(
                spike_id=str(record["spike_id"]),
                article=str(record["article"]),
                date=record["day"],
                label=cast(Literal["event", "noise", "recurring"], str(record["label"])),
                labeler="synthetic",
                labeled_at=datetime(2024, 6, 1),
            ),
        )

    report = train_classifier(connection, settings, labels_path, kinds=("logistic",), n_splits=2)

    assert report.model_path.exists()
    assert report.report_path.exists()
    assert report.labels == 240
    assert classify_spikes(connection, settings) == 240
    scored = connection.execute(
        "SELECT count(*) FROM spikes WHERE class_probability IS NOT NULL"
    ).fetchone()
    assert scored == (240,)
