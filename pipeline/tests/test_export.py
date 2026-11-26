import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pytest

from wikipulse import db
from wikipulse.config import Settings
from wikipulse.events import build_events, store_events
from wikipulse.export import ExportError, _validate, export_all
from wikipulse.models import ArticleDailyItem, ContentUrls, Summary, TopArticle, UrlSet


class VectorEmbedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            [self.vectors.get(text.split(".")[0], [0.0, 0.0, 1.0]) for text in texts],
            dtype=np.float32,
        )


def _seed(settings: Settings) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = date(2026, 11, 25)
    for offset in range(8):
        history_day = day - timedelta(days=offset)
        db.upsert_article_daily(
            connection,
            [
                ArticleDailyItem(
                    project="en.wikipedia",
                    article=article,
                    granularity="daily",
                    timestamp=f"{history_day:%Y%m%d}00",
                    access="all-access",
                    agent="user",
                    views=100 + offset,
                )
                for article in ("Space_A", "Space_B")
            ],
        )
    db.upsert_top(connection, day, [TopArticle(article="Space_A", views=1000, rank=1)])
    db.mark_day(connection, day, top_ok=True, edits_ok=False)
    for article, score in (("Space_A", 10.0), ("Space_B", 20.0)):
        connection.execute(
            """
            INSERT INTO spikes (
                spike_id, day, article, views, score, spike_type, features, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [f"spike-{article}", day, article, 1000, score, "Flash", "{}", db.utc_now()],
        )
        db.upsert_meta(
            connection,
            article,
            Summary(
                type="standard",
                title=article.replace("_", " "),
                description=f"{article} description",
                extract=f"{article} extract",
                content_urls=ContentUrls(
                    desktop=UrlSet(page=f"https://en.wikipedia.org/wiki/{article}")
                ),
            ),
        )
    events = build_events(
        connection,
        settings,
        day,
        VectorEmbedder({"Space A": [1.0, 0.0], "Space B": [1.0, 0.0]}),
    )
    store_events(connection, events)
    return connection


def test_export_writes_valid_manifest_and_files(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = _seed(settings)

    summary = export_all(settings, connection)

    assert summary.days == 1
    assert summary.events == 1
    assert summary.articles == 2
    assert summary.search_shards == 1
    manifest = json.loads((settings.export_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["data_through"] == "2026-11-25"
    assert manifest["days"] == ["2026-11-25"]
    day_file = json.loads(
        (settings.export_dir / "days" / "2026-11-25.json").read_text(encoding="utf-8")
    )
    assert day_file["events"][0]["label"] == "Space B"
    assert day_file["events"][0]["extract"]["license"] == "CC BY-SA 4.0"
    for record in manifest["files"]:
        path = settings.export_dir / record["path"]
        assert path.exists()
        assert record["bytes"] == path.stat().st_size


def test_export_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = _seed(settings)
    export_all(settings, connection)
    first = {
        path.relative_to(settings.export_dir).as_posix(): path.read_bytes()
        for path in sorted(settings.export_dir.rglob("*"))
        if path.is_file()
    }

    export_all(settings, connection)
    second = {
        path.relative_to(settings.export_dir).as_posix(): path.read_bytes()
        for path in sorted(settings.export_dir.rglob("*"))
        if path.is_file()
    }

    assert first == second


def test_invalid_document_is_rejected() -> None:
    with pytest.raises(ExportError):
        _validate("day", {"schema_version": 1, "day": "not-a-date", "events": []})
