"""Deterministic static export with JSON Schema validation and manifest hashes."""

import gzip
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from wikipulse.config import Settings
from wikipulse.filters import article_url, slugify
from wikipulse.labels import load_labels

SCHEMA_VERSION = 1
SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"
DAY_GZIP_LIMIT = 150 * 1024
EXTRACT_CHARS = 400


class ExportError(ValueError):
    """The export would violate a schema or a size budget."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    bytes: int
    gzip_bytes: int


@dataclass
class ExportSummary:
    """Counts and paths from one export."""

    output_dir: Path
    days: int = 0
    events: int = 0
    articles: int = 0
    search_shards: int = 0
    files: int = 0
    data_through: date | None = None
    warnings: list[str] = field(default_factory=list)


def export_all(
    settings: Settings,
    connection: duckdb.DuckDBPyConnection,
    start: date | None = None,
    end: date | None = None,
) -> ExportSummary:
    """Build the export in a staging directory, validate it, then publish it."""
    data_through = _data_through(connection)
    staging = settings.data_dir / "export.tmp"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    summary = ExportSummary(output_dir=settings.export_dir, data_through=data_through)
    try:
        records = _build(settings, connection, staging, summary, data_through, start, end)
        manifest = _manifest(settings, summary, records, data_through)
        _validate("manifest", manifest)
        _write_json(staging, "manifest.json", manifest)
        shutil.rmtree(settings.export_dir, ignore_errors=True)
        staging.replace(settings.export_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return summary


def _build(
    settings: Settings,
    connection: duckdb.DuckDBPyConnection,
    staging: Path,
    summary: ExportSummary,
    data_through: date | None,
    start: date | None,
    end: date | None,
) -> list[FileRecord]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if start is not None:
        clauses.append("day >= ?")
        params.append(start)
    if end is not None:
        clauses.append("day <= ?")
        params.append(end)
    event_rows = connection.execute(
        f"""
        SELECT event_id, day, label, score, event_type, members
        FROM events WHERE {" AND ".join(clauses)}
        ORDER BY day, score DESC, event_id
        """,  # noqa: S608 - fixed clauses, parameterized values
        params,
    ).fetchall()
    by_day: dict[date, list[tuple[Any, ...]]] = {}
    article_scores: dict[str, float] = {}
    for row in event_rows:
        by_day.setdefault(row[1], []).append(row)
        for member in json.loads(row[5]):
            article_scores[str(member["article"])] = max(
                article_scores.get(str(member["article"]), 0.0), float(member["score"])
            )

    meta = _article_meta(connection, list(article_scores))
    ordered_articles = sorted(article_scores, key=lambda name: (-article_scores[name], name))
    if settings.max_article_files:
        ordered_articles = ordered_articles[: settings.max_article_files]
    slugs = _assign_slugs(ordered_articles)
    exported_articles = set(slugs)

    records: list[FileRecord] = []
    days_written: list[str] = []
    for day in sorted(by_day):
        day_document = _day_document(day, by_day[day], meta, slugs)
        _validate("day", day_document)
        record = _write_json(staging, f"days/{day.isoformat()}.json", day_document)
        if record.gzip_bytes > DAY_GZIP_LIMIT:
            raise ExportError(f"Day file {record.path} exceeds the 150 KB gzip budget")
        records.append(record)
        days_written.append(day.isoformat())
        summary.events += len(day_document["events"])

    spike_map = _spike_map(connection, exported_articles)
    last_days = _last_days(connection, exported_articles)
    for article in ordered_articles:
        document = _article_document(
            connection, article, slugs[article], meta, spike_map, data_through
        )
        if document is None:
            continue
        _validate("article", document)
        records.append(
            _write_json(
                staging,
                f"articles/{slugs[article][:2]}/{slugs[article]}.json",
                document,
            )
        )

    shards = _search_shards(ordered_articles, slugs, meta, last_days)
    for prefix, payload in shards.items():
        _validate("search", payload)
        records.append(_write_json(staging, f"search/{prefix}.json", payload))

    methods = _methods_document(settings, data_through)
    _validate("methods", methods)
    records.append(_write_json(staging, "methods.json", methods))

    status = _status_document(settings, connection, data_through)
    _validate("status", status)
    records.append(_write_json(staging, "status.json", status))

    summary.days = len(days_written)
    summary.articles = len(exported_articles)
    summary.search_shards = len(shards)
    summary.files = len(records)
    summary.warnings = status["warnings"]
    return records


def _data_through(connection: duckdb.DuckDBPyConnection) -> date | None:
    row = connection.execute("SELECT max(day) FROM days WHERE top_ok").fetchone()
    return row[0] if row is not None else None


def _article_meta(
    connection: duckdb.DuckDBPyConnection, articles: list[str]
) -> dict[str, dict[str, Any]]:
    if not articles:
        return {}
    placeholders = ", ".join("?" for _ in articles)
    rows = connection.execute(
        f"SELECT article, title, description, summary, url FROM article_meta "  # noqa: S608
        f"WHERE article IN ({placeholders})",
        articles,
    ).fetchall()
    stored = {
        str(row[0]): {
            "title": str(row[1]),
            "description": row[2],
            "extract": row[3],
            "url": str(row[4]),
        }
        for row in rows
    }
    for article in articles:
        stored.setdefault(
            article,
            {
                "title": article.replace("_", " "),
                "description": None,
                "extract": None,
                "url": article_url(article),
            },
        )
    return stored


def _assign_slugs(articles: list[str]) -> dict[str, str]:
    slugs: dict[str, str] = {}
    taken: set[str] = set()
    for article in articles:
        base = slugify(article)
        candidate = base
        if candidate in taken:
            candidate = f"{base}-{hashlib.sha256(article.encode()).hexdigest()[:6]}"
        taken.add(candidate)
        slugs[article] = candidate
    return slugs


def _day_document(
    day: date,
    events: list[tuple[Any, ...]],
    meta: dict[str, dict[str, Any]],
    slugs: dict[str, str],
) -> dict[str, Any]:
    documents = []
    for event_id, _day, label, score, event_type, members_json in events:
        members = []
        for member in json.loads(members_json):
            article = str(member["article"])
            info = meta[article]
            members.append(
                {
                    "article": article,
                    "title": info["title"],
                    "slug": slugs.get(article, slugify(article)),
                    "views": int(member["views"]),
                    "baseline": member["baseline"],
                    "z_score": member["z_score"],
                    "class_probability": member["class_probability"],
                    "type": member["type"],
                    "score": float(member["score"]),
                }
            )
        top = members[0]
        info = meta[str(top["article"])]
        extract = info["extract"]
        documents.append(
            {
                "id": str(event_id),
                "label": str(label),
                "score": round(float(score), 6),
                "type": str(event_type),
                "members": members,
                "extract": {
                    "text": (extract[:EXTRACT_CHARS] if isinstance(extract, str) else None),
                    "url": info["url"],
                    "license": "CC BY-SA 4.0",
                },
            }
        )
    return {"schema_version": SCHEMA_VERSION, "day": day.isoformat(), "events": documents}


def _spike_map(
    connection: duckdb.DuckDBPyConnection, articles: set[str]
) -> dict[str, list[tuple[Any, ...]]]:
    if not articles:
        return {}
    placeholders = ", ".join("?" for _ in articles)
    rows = connection.execute(
        f"""
        SELECT article, day, spike_type, z_score, score
        FROM spikes WHERE article IN ({placeholders})
        ORDER BY day
        """,  # noqa: S608 - placeholders only
        list(articles),
    ).fetchall()
    result: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        result.setdefault(str(row[0]), []).append(row)
    return result


def _article_document(
    connection: duckdb.DuckDBPyConnection,
    article: str,
    slug: str,
    meta: dict[str, dict[str, Any]],
    spike_map: dict[str, list[tuple[Any, ...]]],
    data_through: date | None,
) -> dict[str, Any] | None:
    rows = connection.execute(
        "SELECT day, views FROM article_daily WHERE article = ? ORDER BY day", [article]
    ).fetchall()
    if not rows:
        return None
    if data_through is not None:
        rows = [row for row in rows if row[0] <= data_through]
    if not rows:
        return None
    spike_days = {row[1] for row in spike_map.get(article, [])}
    info = meta[article]
    history = [
        {"d": row[0].isoformat(), "v": int(row[1]), "s": row[0] in spike_days} for row in rows
    ]
    spikes = [
        {
            "day": row[1].isoformat(),
            "type": str(row[2]),
            "z_score": row[3],
            "score": float(row[4]),
        }
        for row in spike_map.get(article, [])
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "article": article,
        "title": info["title"],
        "slug": slug,
        "url": info["url"],
        "description": info["description"],
        "extract": info["extract"],
        "first_day": rows[0][0].isoformat(),
        "last_day": rows[-1][0].isoformat(),
        "history": history,
        "spikes": spikes,
    }


def _last_days(connection: duckdb.DuckDBPyConnection, articles: set[str]) -> dict[str, str]:
    if not articles:
        return {}
    placeholders = ", ".join("?" for _ in articles)
    rows = connection.execute(
        f"SELECT article, max(day) FROM article_daily "  # noqa: S608
        f"WHERE article IN ({placeholders}) GROUP BY article",
        list(articles),
    ).fetchall()
    return {str(row[0]): row[1].isoformat() for row in rows}


def _search_shards(
    articles: list[str],
    slugs: dict[str, str],
    meta: dict[str, dict[str, Any]],
    last_days: dict[str, str],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for article in articles:
        slug = slugs[article]
        info = meta[article]
        grouped.setdefault(slug[:2], []).append(
            {
                "slug": slug,
                "title": info["title"],
                "description": info["description"],
                "url": info["url"],
                "last_day": last_days.get(article, "1970-01-01"),
            }
        )
    shards: dict[str, dict[str, Any]] = {}
    for prefix, entries in grouped.items():
        shards[prefix] = {
            "schema_version": SCHEMA_VERSION,
            "prefix": prefix,
            "articles": sorted(entries, key=lambda entry: entry["slug"]),
        }
    return shards


def _methods_document(settings: Settings, data_through: date | None) -> dict[str, Any]:
    labels = load_labels(settings.data_dir.parent / "labels" / "labels.csv")
    classes = sorted({row.label for row in labels.values()})
    classifier = None
    metadata_path = settings.models_dir / "classifier.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metrics = metadata.get("metrics", {})
        classifier = {
            "model": metadata.get("model", "unknown"),
            "event_f1": float(metrics.get("event_f1", 0.0)),
            "macro_f1": float(metrics.get("macro_f1", 0.0)),
            "brier": float(metrics.get("brier", 0.0)),
            "labels": int(metadata.get("labels", 0)),
            "generated_at": str(metadata.get("generated_at", "")),
            "baselines": metadata.get("baselines", {}),
        }
    limitations = [
        f"Human labels: {len(labels)} of the 300 target.",
        "Edit-surge data publishes about two months late, so recent spikes lack it.",
        "Half-life is unknown for spikes detected on their peak day.",
        "Events are grouped by title and summary embeddings; there is no link-graph signal yet.",
        "Single-article events are not independently confirmed as real-world events.",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (
            f"{data_through.isoformat()}T00:00:00Z"
            if data_through is not None
            else "1970-01-01T00:00:00Z"
        ),
        "labels": len(labels),
        "classes": classes,
        "detector": {
            "z_threshold": settings.z_threshold,
            "minimum_views": settings.minimum_views,
        },
        "classifier": classifier,
        "limitations": limitations,
    }


def _status_document(
    settings: Settings,
    connection: duckdb.DuckDBPyConnection,
    data_through: date | None,
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT finished_at, ok FROM runs WHERE finished_at IS NOT NULL "
        "ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    last_run = row[0].isoformat() + "Z" if row is not None and row[0] is not None else None
    ok = bool(row[1]) if row is not None else True
    warnings: list[str] = []
    if not (settings.models_dir / "classifier.joblib").exists():
        warnings.append("Classifier is not trained; rule-based scores are shown.")
    labels = load_labels(settings.data_dir.parent / "labels" / "labels.csv")
    if len(labels) < 300:
        warnings.append(f"Only {len(labels)} human labels; the target is 300.")
    if data_through is not None:
        edit_gap = connection.execute(
            "SELECT count(*) FROM days WHERE top_ok AND NOT edits_ok AND day >= ?",
            [data_through - timedelta(days=60)],
        ).fetchone()
        if edit_gap is not None and int(edit_gap[0]) > 0:
            warnings.append("Edit analytics are missing for some recent days.")
    if data_through is None:
        warnings.append("No complete pageview day has been ingested.")
    return {
        "schema_version": SCHEMA_VERSION,
        "last_run": last_run,
        "ok": ok,
        "warnings": warnings,
        "data_through": data_through.isoformat() if data_through else None,
    }


def _manifest(
    settings: Settings,
    summary: ExportSummary,
    records: list[FileRecord],
    data_through: date | None,
) -> dict[str, Any]:
    days = sorted(
        record.path.removeprefix("days/").removesuffix(".json")
        for record in records
        if record.path.startswith("days/")
    )
    generated_at = (
        f"{data_through.isoformat()}T00:00:00Z"
        if data_through is not None
        else "1970-01-01T00:00:00Z"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "data_through": data_through.isoformat() if data_through else None,
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "days": days,
        "counts": {
            "days": summary.days,
            "events": summary.events,
            "articles": summary.articles,
            "search_shards": summary.search_shards,
            "files": len(records),
        },
        "files": [
            {
                "path": record.path,
                "sha256": record.sha256,
                "bytes": record.bytes,
                "gzip_bytes": record.gzip_bytes,
            }
            for record in sorted(records, key=lambda record: record.path)
        ],
    }


def _write_json(staging: Path, relative: str, document: dict[str, Any]) -> FileRecord:
    path = staging / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    path.write_bytes(payload)
    return FileRecord(
        path=relative,
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
        gzip_bytes=len(gzip.compress(payload, compresslevel=9, mtime=0)),
    )


def _validate(schema_name: str, document: dict[str, Any]) -> None:
    schema_path = SCHEMA_DIR / f"{schema_name}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        Draft202012Validator(schema).validate(document)
    except ValidationError as exc:
        raise ExportError(f"{schema_name} validation failed: {exc.message}") from exc
