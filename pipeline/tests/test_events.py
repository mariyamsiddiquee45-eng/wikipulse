from datetime import date
from pathlib import Path

import duckdb
import numpy as np

from wikipulse import db
from wikipulse.config import Settings
from wikipulse.events import build_events, store_events
from wikipulse.models import ContentUrls, Summary, UrlSet


class VectorEmbedder:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self.mapping = mapping

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            [self.mapping.get(text.split(".")[0], [0.0, 0.0, 1.0]) for text in texts],
            dtype=np.float32,
        )


def _insert_spike(
    connection: duckdb.DuckDBPyConnection,
    spike_id: str,
    article: str,
    score: float,
    day: date,
) -> None:
    connection.execute(
        """
        INSERT INTO spikes (spike_id, day, article, views, score, spike_type, features, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [spike_id, day, article, 1000, score, "Flash", "{}", db.utc_now()],
    )
    db.upsert_meta(
        connection,
        article,
        Summary(
            type="standard",
            title=article.replace("_", " "),
            extract=f"{article} summary",
            content_urls=ContentUrls(
                desktop=UrlSet(page=f"https://en.wikipedia.org/wiki/{article}")
            ),
        ),
    )


def test_events_cluster_similar_articles_and_keep_singletons(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = date(2026, 11, 25)
    for spike_id, article, score in (
        ("s1", "Space_A", 10.0),
        ("s2", "Space_B", 20.0),
        ("s3", "Music_A", 15.0),
        ("s4", "Music_B", 5.0),
        ("s5", "Other_C", 12.0),
    ):
        _insert_spike(connection, spike_id, article, score, day)
    embedder = VectorEmbedder(
        {
            "Space A": [1.0, 0.0, 0.0],
            "Space B": [1.0, 0.0, 0.0],
            "Music A": [0.0, 1.0, 0.0],
            "Music B": [0.0, 1.0, 0.0],
            "Other C": [0.0, 0.0, 1.0],
        }
    )

    events = build_events(connection, settings, day, embedder)

    sizes = sorted(len(event.members) for event in events)
    assert sizes == [1, 2, 2]
    space = next(event for event in events if len(event.members) == 2 and "Space" in event.label)
    assert space.label == "Space B"
    assert space.members[0].spike_id == "s2"
    assert space.score == 20.0

    stored = store_events(connection, events)
    assert stored == 3
    count = connection.execute("SELECT count(*) FROM events WHERE day = ?", [day]).fetchone()
    assert count == (3,)


def test_event_ids_are_deterministic(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = date(2026, 11, 25)
    _insert_spike(connection, "s1", "Space_A", 10.0, day)
    _insert_spike(connection, "s2", "Space_B", 20.0, day)
    embedder = VectorEmbedder({"Space A": [1.0, 0.0], "Space B": [1.0, 0.0]})

    first = build_events(connection, settings, day, embedder)
    second = build_events(connection, settings, day, embedder)

    assert [event.event_id for event in first] == [event.event_id for event in second]
