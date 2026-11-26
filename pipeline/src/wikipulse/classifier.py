"""Classifier training, expanding-window evaluation, reports and scoring."""

import hashlib
import itertools
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from wikipulse.config import Settings
from wikipulse.labels import LabelRow, load_labels

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "views",
    "baseline",
    "z_score",
    "stl_residual",
    "peak_ratio",
    "rise_days",
    "time_to_peak_days",
    "half_life_days",
    "yoy_ratio",
    "rank_jump",
    "rank",
    "week_ratio",
    "days_since_last_spike",
    "edit_surge",
]
MIN_LABELS = 60


class ClassifierError(ValueError):
    """Training or scoring cannot proceed with the available data."""


@dataclass
class TrainingReport:
    """Artifacts and metrics from one training run."""

    model_name: str
    model_path: Path
    report_path: Path
    metrics: dict[str, Any]
    labels: int
    classes: list[str]


def expanding_splits(days: pd.Series, n_splits: int = 4) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return expanding-window train/validation masks; validation never precedes training."""
    unique = np.sort(days.unique())
    if len(unique) < 8:
        raise ClassifierError("Need at least eight distinct days for time-series validation")
    start = max(1, len(unique) // 2)
    fold = max(1, (len(unique) - start) // n_splits)
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for index in range(n_splits):
        train_end = start + index * fold
        validation_end = len(unique) if index == n_splits - 1 else train_end + fold
        train_days = set(unique[:train_end])
        validation_days = set(unique[train_end:validation_end])
        if not validation_days:
            break
        splits.append(
            (
                days.isin(train_days).to_numpy(),
                days.isin(validation_days).to_numpy(),
            )
        )
    if not splits:
        raise ClassifierError("No validation window could be built")
    return splits


def _fit_model(kind: str, features: pd.DataFrame, labels: pd.Series) -> Pipeline:
    if kind == "logistic":
        classifier: Any = LogisticRegression(
            max_iter=3000, class_weight="balanced", random_state=42
        )
    elif kind == "lightgbm":
        classifier = LGBMClassifier(
            n_estimators=250,
            learning_rate=0.06,
            num_leaves=15,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            n_jobs=2,
            verbose=-1,
            importance_type="gain",
        )
    else:
        raise ClassifierError(f"Unknown model {kind!r}")
    pipeline = Pipeline([("scale", StandardScaler()), ("model", classifier)])
    if kind == "lightgbm":
        weights = compute_sample_weight("balanced", labels)
        pipeline.fit(features, labels, model__sample_weight=weights)
    else:
        pipeline.fit(features, labels)
    return pipeline


def _feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = pd.DataFrame(index=frame.index)
    for column in FEATURE_COLUMNS:
        if column in frame.columns:
            data[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            data[column] = np.nan
    data["edit_surge"] = data["edit_surge"].fillna(0.0)
    return data.fillna(-1.0)


def _event_probability(model: Pipeline, features: pd.DataFrame) -> np.ndarray:
    classes = list(model.named_steps["model"].classes_)
    probabilities = model.predict_proba(features)
    index = classes.index("event") if "event" in classes else probabilities.shape[1] - 1
    return np.asarray(probabilities[:, index], dtype=float)


def evaluate_predictions(
    truth: pd.Series,
    predicted: np.ndarray,
    event_probability: np.ndarray,
    classes: list[str],
) -> dict[str, Any]:
    """Compute per-class metrics, calibration, PR points and precision at k."""
    labels = sorted(classes)
    per_class, macro = _classification_metrics(truth, predicted, labels)
    matrix = confusion_matrix(truth, predicted, labels=labels).tolist()
    precision, recall, _ = precision_recall_curve(truth == "event", event_probability)
    if len(precision):
        step = max(1, len(precision) // 50)
        pr_points = [
            {"precision": round(float(p), 6), "recall": round(float(r), 6)}
            for p, r in zip(precision[::step], recall[::step], strict=False)
        ]
    else:
        pr_points = []
    calibration = _calibration(truth == "event", event_probability)
    precision_at_k = _precision_at_k(truth == "event", event_probability)
    return {
        "macro_f1": macro,
        "event_f1": per_class.get("event", {}).get("f1", 0.0),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "classes": labels,
        "precision_at_k": precision_at_k,
        "calibration": calibration,
        "pr_curve": pr_points,
        "brier": round(float(brier_score_loss(truth == "event", event_probability)), 6),
    }


def _classification_metrics(
    truth: pd.Series, predicted: np.ndarray, labels: list[str]
) -> tuple[dict[str, dict[str, float]], float]:
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, predicted, labels=labels, zero_division=0
    )
    per_class = {
        label: {
            "precision": round(float(precision[index]), 6),
            "recall": round(float(recall[index]), 6),
            "f1": round(float(f1[index]), 6),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    }
    macro = round(
        float(np.mean([per_class[label]["f1"] for label in labels])),
        6,
    )
    return per_class, macro


def _calibration(truth: pd.Series, probabilities: np.ndarray) -> list[dict[str, float | str]]:
    bins = np.linspace(0.0, 1.0, 11)
    buckets: list[dict[str, float | str]] = []
    for low, high in itertools.pairwise(bins):
        mask = (probabilities >= low) & (
            probabilities < high if high < 1.0 else probabilities <= high
        )
        count = int(mask.sum())
        if count:
            buckets.append(
                {
                    "bin": f"{low:.1f}-{high:.1f}",
                    "count": count,
                    "predicted": round(float(probabilities[mask].mean()), 6),
                    "observed": round(float(truth[mask].mean()), 6),
                }
            )
    return buckets


def _precision_at_k(truth: pd.Series, probabilities: np.ndarray) -> dict[str, float]:
    result: dict[str, float] = {}
    order = np.argsort(-probabilities)
    for k in (10, 50, 100):
        if len(truth) >= k:
            selected = truth.to_numpy()[order[:k]]
            result[str(k)] = round(float(selected.mean()), 6)
    return result


def baseline_metrics(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Evaluate baselines A (rule), B (rank) and C (weekly ratio) on the same rows."""
    truth = (frame["label"] == "event").astype(int)
    predictions = {
        "A_rule": (frame["z_score"] >= 3.0) & (frame["views"] >= 1000),
        "B_rank": frame["rank"] <= 100,
        "C_week_ratio": frame["week_ratio"] >= 2.0,
    }
    result: dict[str, dict[str, float]] = {}
    for name, predicted in predictions.items():
        precision, recall, f1, _ = precision_recall_fscore_support(
            truth, predicted.astype(int), labels=[0, 1], zero_division=0
        )
        result[name] = {
            "precision": round(float(precision[1]), 6),
            "recall": round(float(recall[1]), 6),
            "f1": round(float(f1[1]), 6),
        }
    return result


def cross_validate(
    frame: pd.DataFrame, kind: str, n_splits: int = 4
) -> tuple[Pipeline | None, dict[str, Any], pd.DataFrame]:
    """Run expanding-window validation and pool out-of-fold predictions."""
    ordered = frame.sort_values(["day", "spike_id"]).reset_index(drop=True)
    features = _feature_frame(ordered)
    labels = ordered["label"].astype(str)
    validation_frames: list[pd.DataFrame] = []
    for train_mask, validation_mask in expanding_splits(ordered["day"], n_splits):
        train_labels = labels[train_mask]
        if train_labels.nunique() < 2:
            continue
        model = _fit_model(kind, features[train_mask], train_labels)
        validation = ordered[validation_mask].copy()
        validation["predicted"] = model.predict(features[validation_mask])
        validation["event_probability"] = _event_probability(model, features[validation_mask])
        validation_frames.append(validation)
    if not validation_frames:
        return None, {}, pd.DataFrame()
    pooled = pd.concat(validation_frames, ignore_index=True)
    metrics = evaluate_predictions(
        pooled["label"].astype(str),
        pooled["predicted"].astype(str).to_numpy(),
        pooled["event_probability"].to_numpy(dtype=float),
        sorted(labels.unique().tolist()),
    )
    return model, metrics, pooled


def build_training_frame(
    connection: duckdb.DuckDBPyConnection, labels: dict[str, LabelRow]
) -> pd.DataFrame:
    """Join stored spike features with human labels."""
    rows = connection.execute("SELECT spike_id, day, features FROM spikes").fetchall()
    records: list[dict[str, Any]] = []
    for spike_id, day, features_json in rows:
        label = labels.get(str(spike_id))
        if label is None:
            continue
        features = json.loads(features_json)
        if not isinstance(features, dict):
            continue
        records.append(
            {
                "spike_id": str(spike_id),
                "day": day,
                "label": label.label,
                **features,
            }
        )
    return pd.DataFrame(records)


def train_classifier(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    labels_path: Path,
    kinds: tuple[str, ...] = ("logistic", "lightgbm"),
    n_splits: int = 4,
) -> TrainingReport:
    """Train, evaluate against baselines, save the best model and write the report."""
    labels = load_labels(labels_path)
    frame = build_training_frame(connection, labels)
    if len(frame) < MIN_LABELS:
        raise ClassifierError(f"Need at least {MIN_LABELS} labels to train; found {len(frame)}")
    if frame["label"].nunique() < 2:
        raise ClassifierError("Need at least two label classes to train")
    results: dict[str, dict[str, Any]] = {}
    pooled_frames: dict[str, pd.DataFrame] = {}
    for kind in kinds:
        model, metrics, pooled = cross_validate(frame, kind, n_splits)
        if model is not None:
            results[kind] = metrics
            pooled_frames[kind] = pooled
    if not results:
        raise ClassifierError("No model produced a usable validation window")
    best_name = max(results, key=lambda name: float(results[name]["event_f1"]))
    best_metrics = results[best_name]
    pooled = pooled_frames[best_name]
    baselines = baseline_metrics(pooled)
    # The saved artifact must be trained on all labels, not just the last fold.
    final_model = _fit_model(best_name, _feature_frame(frame), frame["label"].astype(str))
    importance_sample = frame.sample(n=min(1000, len(frame)), random_state=42)
    permutation = permutation_importance(
        final_model,
        _feature_frame(importance_sample),
        importance_sample["label"].astype(str),
        n_repeats=5,
        random_state=42,
        scoring="f1_macro",
    )
    permutation_importance_values = {
        column: round(float(value), 6)
        for column, value in zip(FEATURE_COLUMNS, permutation.importances_mean, strict=True)
    }
    gain_importance: dict[str, float] = {}
    inner_model = final_model.named_steps["model"]
    if hasattr(inner_model, "feature_importances_"):
        gain_importance = {
            column: round(float(value), 6)
            for column, value in zip(FEATURE_COLUMNS, inner_model.feature_importances_, strict=True)
        }

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    model_path = settings.models_dir / "classifier.joblib"
    joblib.dump(final_model, model_path)
    data_hash = hashlib.sha256(
        frame.sort_values("spike_id")[["spike_id", "label", *FEATURE_COLUMNS]]
        .to_csv(index=False)
        .encode()
    ).hexdigest()
    metadata = {
        "model": best_name,
        "features": FEATURE_COLUMNS,
        "data_hash": data_hash,
        "generated_at": datetime.now(UTC).isoformat(),
        "labels": len(frame),
        "classes": sorted(frame["label"].unique().tolist()),
        "metrics": best_metrics,
        "baselines": baselines,
        "permutation_importance": permutation_importance_values,
        "gain_importance": gain_importance,
        "n_splits": n_splits,
    }
    (settings.models_dir / "classifier.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = settings.reports_dir / "classifier.md"
    report_path.write_text(
        render_report(best_name, results, baselines, frame, metadata), encoding="utf-8"
    )
    (settings.reports_dir / "classifier.json").write_text(
        json.dumps({"model": best_name, "metrics": results, "baselines": baselines}, indent=2),
        encoding="utf-8",
    )
    return TrainingReport(
        model_name=best_name,
        model_path=model_path,
        report_path=report_path,
        metrics=best_metrics,
        labels=len(frame),
        classes=sorted(frame["label"].unique().tolist()),
    )


def render_report(
    best_name: str,
    results: dict[str, dict[str, Any]],
    baselines: dict[str, dict[str, float]],
    frame: pd.DataFrame,
    metadata: dict[str, Any],
) -> str:
    """Render the markdown evaluation report."""
    lines = [
        "# Classifier evaluation",
        "",
        f"Generated: {metadata['generated_at']}",
        f"Labels: {metadata['labels']} ({', '.join(metadata['classes'])})",
        f"Validation: expanding-window time-series splits, {metadata['n_splits']} folds",
        "No random splits are used.",
        "",
        "## Models",
        "",
        "| Model | Event precision | Event recall | Event F1 | Macro F1 | Brier |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, metrics in results.items():
        event = metrics["per_class"].get("event", {})
        lines.append(
            f"| {name} | {event.get('precision', 0):.3f} | {event.get('recall', 0):.3f} | "
            f"{event.get('f1', 0):.3f} | {metrics['macro_f1']:.3f} | {metrics['brier']:.3f} |"
        )
    lines += [
        "",
        f"Selected: {best_name}",
        "",
        "## Baselines",
        "",
        "| Baseline | Precision | Recall | F1 |",
        "| --- | --- | --- | --- |",
    ]
    for name, metrics in baselines.items():
        lines.append(
            f"| {name} | {metrics['precision']:.3f} | {metrics['recall']:.3f} | "
            f"{metrics['f1']:.3f} |"
        )
    best = results[best_name]
    lines += [
        "",
        "## Per-class metrics",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label, values in best["per_class"].items():
        lines.append(
            f"| {label} | {values['precision']:.3f} | {values['recall']:.3f} | "
            f"{values['f1']:.3f} | {values['support']} |"
        )
    lines += ["", "## Confusion matrix", "", "```"]
    for row in best["confusion_matrix"]:
        lines.append(" ".join(str(value) for value in row))
    lines += ["```", "", "## Precision at k", ""]
    for k, value in best["precision_at_k"].items():
        lines.append(f"- {k}: {value:.3f}")
    lines += [
        "",
        "## Calibration",
        "",
        "| Bin | Count | Predicted | Observed |",
        "| --- | --- | --- | --- |",
    ]
    for bucket in best["calibration"]:
        lines.append(
            f"| {bucket['bin']} | {bucket['count']} | {bucket['predicted']:.3f} | "
            f"{bucket['observed']:.3f} |"
        )
    lines += [
        "",
        "## Permutation importance",
        "",
        "| Feature | Mean F1 drop |",
        "| --- | --- |",
    ]
    for feature, value in sorted(
        metadata["permutation_importance"].items(), key=lambda item: item[1], reverse=True
    ):
        lines.append(f"| {feature} | {value:.4f} |")
    if metadata["gain_importance"]:
        lines += [
            "",
            "## LightGBM gain importance",
            "",
            "| Feature | Gain |",
            "| --- | --- |",
        ]
        for feature, value in sorted(
            metadata["gain_importance"].items(), key=lambda item: item[1], reverse=True
        ):
            lines.append(f"| {feature} | {value:.4f} |")
    lines += [
        "",
        "## Limitations",
        "",
        f"- Only {len(frame)} labeled spikes were available; classes may be imbalanced.",
        "- Labels are human judgments about newsworthiness, not ground truth.",
        "- Half-life is unknown for spikes detected on their peak day.",
        "- Edit-surge data publishes late and is missing for recent spikes.",
        "",
    ]
    return "\n".join(lines)


def load_model(settings: Settings) -> Pipeline | None:
    """Load the saved classifier, or None when it has not been trained."""
    path = settings.models_dir / "classifier.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def _rows_to_frame(rows: list[tuple[Any, ...]]) -> pd.DataFrame:
    records = []
    for spike_id, day, features_json in rows:
        features = json.loads(features_json)
        if isinstance(features, dict):
            records.append({"spike_id": str(spike_id), "day": day, **features})
    return pd.DataFrame(records)


def classify_spikes(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    start: date | None = None,
    end: date | None = None,
) -> int:
    """Score stored spikes with the trained model and write probability and class."""
    model = load_model(settings)
    if model is None:
        raise ClassifierError("No trained model; run wikipulse train after labeling")
    clauses = []
    params: list[Any] = []
    if start is not None:
        clauses.append("day >= ?")
        params.append(start)
    if end is not None:
        clauses.append("day <= ?")
        params.append(end)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"SELECT spike_id, day, features FROM spikes {where}",  # noqa: S608 - fixed clauses
        params,
    ).fetchall()
    if not rows:
        return 0
    frame = _rows_to_frame(rows)
    features = _feature_frame(frame)
    probabilities = _event_probability(model, features)
    predicted = model.predict(features)
    updates = [
        (float(probabilities[index]), str(predicted[index]), str(frame.iloc[index]["spike_id"]))
        for index in range(len(frame))
    ]
    connection.executemany(
        "UPDATE spikes SET class_probability = ?, predicted_class = ? WHERE spike_id = ?",
        updates,
    )
    return len(updates)
