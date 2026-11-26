"""Event assembly: HDBSCAN over article embeddings, singletons kept as events."""

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import duckdb
import numpy as np
from sklearn.cluster import HDBSCAN

from wikipulse import db
from wikipulse.config import Settings
from wikipulse.embeddings import Embedder, embed_articles

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventMember:
    spike_id: str
    article: str
    title: str
    views: int
    baseline: float | None
    z_score: float | None
    class_probability: float | None
    spike_type: str
    score: float


@dataclass(frozen=True)
class Event:
    event_id: str
    day: date
    label: str
    score: float
    event_type: str
    members: tuple[EventMember, ...]


def _spike_rows(connection: duckdb.DuckDBPyConnection, day: date) -> list[tuple[Any, ...]]:
    return connection.execute(
        """
        SELECT spike_id, article, views, baseline, z_score, class_probability,
               spike_type, score
        FROM spikes WHERE day = ? ORDER BY article
        """,
        [day],
    ).fetchall()


def _titles(connection: duckdb.DuckDBPyConnection, articles: Sequence[str]) -> dict[str, str]:
    if not articles:
        return {}
    placeholders = ", ".join("?" for _ in articles)
    rows = connection.execute(
        f"SELECT article, title FROM article_meta WHERE article IN ({placeholders})",  # noqa: S608
        list(articles),
    ).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _greedy_labels(matrix: np.ndarray) -> np.ndarray:
    """Cluster very small days by cosine similarity; HDBSCAN is unstable on ties."""
    labels = np.full(matrix.shape[0], -1, dtype=int)
    next_label = 0
    for index in range(matrix.shape[0]):
        if labels[index] != -1:
            continue
        labels[index] = next_label
        for other in range(index + 1, matrix.shape[0]):
            if labels[other] == -1 and float(matrix[index] @ matrix[other]) >= 0.92:
                labels[other] = next_label
        next_label += 1
    return labels


def _cluster_labels(matrix: np.ndarray) -> np.ndarray:
    if matrix.shape[0] < 6:
        return _greedy_labels(matrix)
    labels = np.asarray(
        HDBSCAN(min_cluster_size=2, min_samples=1, metric="euclidean").fit_predict(matrix),
        dtype=int,
    )
    clusters = sorted({int(label) for label in labels if int(label) != -1})
    for index, label in enumerate(labels.tolist()):
        if int(label) != -1:
            continue
        best_cluster = None
        best_similarity = 0.0
        for cluster in clusters:
            centroid = matrix[labels == cluster].mean(axis=0)
            similarity = float(matrix[index] @ centroid)
            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster
        if best_cluster is not None and best_similarity >= 0.93:
            labels[index] = best_cluster
    return labels


def build_events(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    day: date,
    embedder: Embedder,
) -> list[Event]:
    """Cluster one day's spikes; noise points and isolated articles become singletons."""
    rows = _spike_rows(connection, day)
    if not rows:
        return []
    articles = [str(row[1]) for row in rows]
    titles = _titles(connection, articles)
    members_raw = [
        EventMember(
            spike_id=str(row[0]),
            article=str(row[1]),
            title=titles.get(str(row[1]), str(row[1]).replace("_", " ")),
            views=int(row[2]),
            baseline=row[3],
            z_score=row[4],
            class_probability=row[5],
            spike_type=str(row[6]),
            score=float(row[7]),
        )
        for row in rows
    ]
    vectors = embed_articles(connection, settings, embedder, articles)
    matrix = np.vstack([vectors[article] for article in articles])
    labels = _cluster_labels(matrix)

    groups: list[list[EventMember]] = []
    clustered: dict[int, list[EventMember]] = {}
    for index, label in enumerate(labels.tolist()):
        if int(label) == -1:
            groups.append([members_raw[index]])
        else:
            clustered.setdefault(int(label), []).append(members_raw[index])
    groups.extend(clustered.values())

    events: list[Event] = []
    for group in groups:
        members = sorted(group, key=lambda member: member.score, reverse=True)
        top = members[0]
        identifiers = "|".join(sorted(member.spike_id for member in members))
        digest = hashlib.sha256(f"{day.isoformat()}|{identifiers}".encode()).hexdigest()[:12]
        event_id = f"{day:%Y%m%d}-{digest}"
        events.append(
            Event(
                event_id=event_id,
                day=day,
                label=top.title,
                score=top.score,
                event_type=top.spike_type,
                members=tuple(members),
            )
        )
    events.sort(key=lambda event: (-event.score, event.event_id))
    return events


def member_payload(member: EventMember) -> dict[str, object]:
    """Return the JSON fields the export keeps for one event member."""
    return {
        "spike_id": member.spike_id,
        "article": member.article,
        "title": member.title,
        "views": member.views,
        "baseline": member.baseline,
        "z_score": member.z_score,
        "class_probability": member.class_probability,
        "type": member.spike_type,
        "score": member.score,
    }


def store_events(connection: duckdb.DuckDBPyConnection, events: Sequence[Event]) -> int:
    """Replace all events for the affected days and insert the new set."""
    days = sorted({event.day for event in events})
    for day in days:
        connection.execute("DELETE FROM events WHERE day = ?", [day])
    rows = [
        (
            event.event_id,
            event.day,
            event.label,
            event.score,
            event.event_type,
            json.dumps([member_payload(member) for member in event.members], sort_keys=True),
            db.utc_now(),
        )
        for event in events
    ]
    if rows:
        connection.executemany("INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def cluster_day(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    day: date,
    embedder: Embedder,
) -> list[Event]:
    """Build and persist the events for one day."""
    events = build_events(connection, settings, day, embedder)
    store_events(connection, events)
    return events


def cluster_range(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    start: date,
    end: date,
    embedder: Embedder,
) -> list[Event]:
    """Build and persist events for every day in the range."""
    events: list[Event] = []
    current = start
    while current <= end:
        events.extend(cluster_day(connection, settings, current, embedder))
        current += timedelta(days=1)
    return events
