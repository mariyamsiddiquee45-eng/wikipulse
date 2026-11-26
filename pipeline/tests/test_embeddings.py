from pathlib import Path

import duckdb
import numpy as np

from wikipulse import db
from wikipulse.config import Settings
from wikipulse.embeddings import (
    embed_articles,
    embedding_text,
    ensure_summaries,
    load_cache,
    save_cache,
)
from wikipulse.models import ContentUrls, Summary, UrlSet


class KeywordEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls.append(texts)
        rows = []
        for text in texts:
            if "Space" in text:
                rows.append([1.0, 0.0, 0.0])
            elif "Music" in text:
                rows.append([0.0, 1.0, 0.0])
            else:
                rows.append([0.0, 0.0, 1.0])
        return np.asarray(rows, dtype=np.float32)


class NeverEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        raise AssertionError("unexpected embedding call")


class FakeSummaryClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_summary(self, article: str, force: bool = False) -> Summary:
        del force
        self.calls.append(article)
        return Summary(
            type="standard",
            title=article.replace("_", " "),
            extract=f"Summary for {article}",
            content_urls=ContentUrls(
                desktop=UrlSet(page=f"https://en.wikipedia.org/wiki/{article}")
            ),
        )


def _summary(article: str, extract: str) -> Summary:
    return Summary(
        type="standard",
        title=article.replace("_", " "),
        extract=extract,
        content_urls=ContentUrls(desktop=UrlSet(page=f"https://en.wikipedia.org/wiki/{article}")),
    )


def test_embedding_text_includes_summary(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    db.upsert_meta(connection, "Space_A", _summary("Space_A", "A mission to space."))

    assert "A mission to space" in embedding_text(connection, "Space_A")
    assert embedding_text(connection, "Missing") == "Missing"


def test_embedding_cache_only_embeds_misses(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    embedder = KeywordEmbedder()

    vectors = embed_articles(connection, settings, embedder, ["Space_A", "Music_A"])
    cached = embed_articles(connection, settings, NeverEmbedder(), ["Space_A", "Music_A"])

    assert embedder.calls == [["Music A", "Space A"]]
    assert np.allclose(vectors["Space_A"], cached["Space_A"])
    articles, matrix = load_cache(settings.data_dir / "embeddings" / "articles.npz")
    assert articles == ["Music_A", "Space_A"]
    assert matrix.shape == (2, 3)


def test_save_and_load_cache_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "cache.npz"
    save_cache(path, ["Alpha"], np.asarray([[1.0, 2.0]], dtype=np.float32))
    articles, matrix = load_cache(path)
    assert articles == ["Alpha"]
    assert matrix.shape == (1, 2)


def test_summaries_are_fetched_once(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    client = FakeSummaryClient()

    first = ensure_summaries(connection, client, ["Alpha", "Beta"])
    second = ensure_summaries(connection, client, ["Alpha", "Beta"])

    assert first == (2, 0)
    assert second == (0, 0)
    assert client.calls == ["Alpha", "Beta"]
