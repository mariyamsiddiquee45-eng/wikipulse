"""Article summaries, sentence embeddings and their on-disk cache."""

import logging
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import duckdb
import numpy as np

from wikipulse import db
from wikipulse.client import NotFoundError, WikimediaError
from wikipulse.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_SUMMARY_CHARS = 600


class Embedder(Protocol):
    """Anything that turns texts into L2-normalized vectors."""

    def embed(self, texts: list[str]) -> np.ndarray: ...


class SummarySource(Protocol):
    """The one client call summary ingestion needs."""

    def fetch_summary(self, article: str, force: bool = False) -> Any: ...


class SentenceTransformerEmbedder:
    """all-MiniLM-L6-v2 on CPU, loaded lazily so imports stay cheap."""

    def __init__(self, model_name: str = DEFAULT_MODEL, batch_size: int = 32) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._model: object | None = None

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s", self.model_name)
            self._model = SentenceTransformer(self.model_name, device="cpu")
        model = cast(Any, self._model)
        vectors = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


def embedding_text(connection: duckdb.DuckDBPyConnection, article: str) -> str:
    """Return title plus a short plain-text summary for one article."""
    row = connection.execute(
        "SELECT title, description, summary FROM article_meta WHERE article = ?", [article]
    ).fetchone()
    title = article.replace("_", " ")
    if row is None:
        return title
    stored_title = str(row[0]) if row[0] else title
    description = str(row[1]) if row[1] else ""
    summary = str(row[2]) if row[2] else ""
    text = f"{stored_title}. {description} {summary[:MAX_SUMMARY_CHARS]}"
    return re.sub(r"\s+", " ", text).strip()


def ensure_summaries(
    connection: duckdb.DuckDBPyConnection,
    client: SummarySource,
    articles: Iterable[str],
    force: bool = False,
) -> tuple[int, int]:
    """Fetch and store missing article summaries; returns (fetched, failed)."""
    fetched = 0
    failed = 0
    for article in sorted(set(articles)):
        exists = connection.execute(
            "SELECT 1 FROM article_meta WHERE article = ?", [article]
        ).fetchone()
        if exists is not None and not force:
            continue
        try:
            summary = client.fetch_summary(article, force=force)
        except NotFoundError:
            logger.info("No summary for %s", article)
            failed += 1
            continue
        except WikimediaError as exc:
            logger.warning("Summary failed for %s: %s", article, exc)
            failed += 1
            continue
        db.upsert_meta(connection, article, summary)
        fetched += 1
    return fetched, failed


def load_cache(path: Path) -> tuple[list[str], np.ndarray]:
    """Load the article embedding cache; missing files are empty."""
    if not path.exists():
        return [], np.zeros((0, 0), dtype=np.float32)
    with np.load(path, allow_pickle=False) as stored:
        articles = [str(value) for value in stored["articles"].tolist()]
        vectors = np.asarray(stored["vectors"], dtype=np.float32)
    if vectors.shape[0] != len(articles):
        raise ValueError(f"Embedding cache {path} has mismatched rows")
    return articles, vectors


def save_cache(path: Path, articles: list[str], vectors: np.ndarray) -> None:
    """Write the embedding cache atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle,
            articles=np.asarray(articles, dtype=np.str_),
            vectors=np.asarray(vectors, dtype=np.float32),
        )
    temporary.replace(path)


def embed_articles(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    embedder: Embedder,
    articles: Sequence[str],
    batch_size: int = 32,
) -> dict[str, np.ndarray]:
    """Return one normalized vector per article, embedding and caching only misses."""
    path = settings.data_dir / "embeddings" / "articles.npz"
    cached_articles, cached_vectors = load_cache(path)
    cache = {article: cached_vectors[index] for index, article in enumerate(cached_articles)}
    missing = sorted(set(articles) - set(cache))
    for offset in range(0, len(missing), batch_size):
        batch = missing[offset : offset + batch_size]
        vectors = embedder.embed([embedding_text(connection, article) for article in batch])
        if vectors.shape[0] != len(batch):
            raise ValueError("Embedder returned the wrong number of vectors")
        for article, vector in zip(batch, vectors, strict=True):
            cache[article] = np.asarray(vector, dtype=np.float32)
    if missing:
        ordered = sorted(cache)
        save_cache(path, ordered, np.vstack([cache[article] for article in ordered]))
    return cache
