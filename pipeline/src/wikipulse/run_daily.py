"""End-to-end incremental daily pipeline."""

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from wikipulse import db
from wikipulse.candidates import select_candidates
from wikipulse.classifier import classify_spikes, load_model
from wikipulse.client import WikimediaClient
from wikipulse.config import Settings
from wikipulse.embeddings import Embedder, SentenceTransformerEmbedder, ensure_summaries
from wikipulse.events import cluster_range
from wikipulse.export import ExportSummary, export_all
from wikipulse.features import detect_range
from wikipulse.history import fetch_candidate_history
from wikipulse.ingest import backfill, last_complete_day

logger = logging.getLogger(__name__)


@dataclass
class DailySummary:
    """Counts from one daily run."""

    data_through: str
    ingested_days: int = 0
    candidates: int = 0
    spikes: int = 0
    events: int = 0
    articles: int = 0
    export: ExportSummary | None = None
    failures: list[str] = field(default_factory=list)


def run_daily(
    settings: Settings,
    *,
    client: WikimediaClient | None = None,
    embedder: Embedder | None = None,
    ingest_days: int = 7,
    window_days: int = 3,
) -> DailySummary:
    """Ingest, detect, score, cluster and export; exits non-zero via the caller on failure."""
    connection = db.connect(settings)
    run_id = db.start_run(connection, "run-daily")
    end = last_complete_day()
    window_start = end - timedelta(days=window_days - 1)
    source = client or WikimediaClient(settings)
    summary = DailySummary(data_through=end.isoformat())
    try:
        ingest = backfill(
            settings,
            source,
            connection,
            end - timedelta(days=ingest_days - 1),
            end,
        )
        summary.ingested_days = ingest.days_ingested
        summary.failures.extend(ingest.failures)

        candidates = []
        current = window_start
        while current <= end:
            candidates.extend(select_candidates(connection, current, settings))
            current += timedelta(days=1)
        summary.candidates = len(candidates)
        history = fetch_candidate_history(settings, source, connection, candidates)
        summary.failures.extend(history.failures)

        features, inserted = detect_range(connection, settings, window_start, end)
        summary.spikes = inserted
        if settings.apply_classifier and load_model(settings) is not None:
            classify_spikes(connection, settings, window_start, end)

        spike_articles = [
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT article FROM spikes WHERE day BETWEEN ? AND ?",
                [window_start, end],
            ).fetchall()
        ]
        ensure_summaries(connection, source, spike_articles)
        events = cluster_range(
            connection,
            settings,
            window_start,
            end,
            embedder or SentenceTransformerEmbedder(),
        )
        summary.events = len(events)
        summary.articles = len(spike_articles)
        summary.export = export_all(settings, connection)
        db.finish_run(
            connection,
            run_id,
            ok=not summary.failures,
            counts={
                "days": summary.ingested_days,
                "candidates": summary.candidates,
                "features": len(features),
                "spikes": summary.spikes,
                "events": summary.events,
            },
            failures=summary.failures,
        )
        return summary
    except Exception as exc:
        db.finish_run(
            connection,
            run_id,
            ok=False,
            counts={},
            failures=[*summary.failures, str(exc)],
        )
        logger.exception("Daily run failed")
        raise
