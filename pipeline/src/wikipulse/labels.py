"""Label file contract, stratified sampling and the terminal labeling loop."""

import csv
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

import duckdb

from wikipulse.filters import article_url

LABEL_COLUMNS = (
    "spike_id",
    "article",
    "date",
    "label",
    "labeler",
    "labeled_at",
    "note",
)
LABELS = frozenset({"event", "noise", "recurring"})
_label = Literal["event", "noise", "recurring"]
SPARKLINE_CHARS = " .:-=+*#%@"


class LabelError(ValueError):
    """A label file or sample violates the contract."""


@dataclass(frozen=True)
class LabelRow:
    spike_id: str
    article: str
    date: date
    label: _label
    labeler: str
    labeled_at: datetime
    note: str = ""


@dataclass(frozen=True)
class SpikeSample:
    spike_id: str
    article: str
    day: date
    views: int
    baseline: float | None
    z_score: float | None
    peak_ratio: float | None
    rise_days: float | None
    half_life_days: float | None
    yoy_ratio: float | None
    edit_surge: bool
    spike_type: str


def load_labels(path: Path) -> dict[str, LabelRow]:
    """Read and validate the label CSV; missing files are an empty set."""
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != LABEL_COLUMNS:
            raise LabelError(f"Expected columns {LABEL_COLUMNS}, got {reader.fieldnames}")
        labels: dict[str, LabelRow] = {}
        for row in reader:
            row_label = row["label"]
            if row_label not in LABELS:
                raise LabelError(f"Unknown label {row_label!r} for {row['spike_id']}")
            row_date = date.fromisoformat(row["date"])
            labeled_at = datetime.fromisoformat(row["labeled_at"])
            if row["spike_id"] in labels:
                raise LabelError(f"Duplicate label for {row['spike_id']}")
            labels[row["spike_id"]] = LabelRow(
                spike_id=row["spike_id"],
                article=row["article"],
                date=row_date,
                label=cast("_label", row_label),
                labeler=row["labeler"],
                labeled_at=labeled_at,
                note=row["note"],
            )
    return labels


def append_label(path: Path, row: LabelRow) -> None:
    """Append one label, writing the header first when the file is new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if new_file:
            writer.writerow(LABEL_COLUMNS)
        writer.writerow(
            [
                row.spike_id,
                row.article,
                row.date.isoformat(),
                row.label,
                row.labeler,
                row.labeled_at.isoformat(),
                row.note,
            ]
        )


def sample_spikes(
    connection: duckdb.DuckDBPyConnection,
    count: int,
    *,
    seed: int = 0,
    start: date | None = None,
    end: date | None = None,
    exclude: Iterable[str] = (),
) -> list[SpikeSample]:
    """Draw a deterministic, year-stratified sample of unlabeled spikes."""
    excluded = set(exclude)
    clauses = ["1 = 1"]
    params: list[object] = []
    if start is not None:
        clauses.append("day >= ?")
        params.append(start)
    if end is not None:
        clauses.append("day <= ?")
        params.append(end)
    rows = connection.execute(
        f"""
        SELECT spike_id, article, day, views, baseline, z_score, peak_ratio,
               rise_days, half_life_days, yoy_ratio, edit_surge, spike_type
        FROM spikes
        WHERE {" AND ".join(clauses)}
        """,  # noqa: S608 - clauses are fixed strings, values are parameters
        params,
    ).fetchall()

    strata: dict[int, list[SpikeSample]] = {}
    for row in rows:
        sample = SpikeSample(
            spike_id=str(row[0]),
            article=str(row[1]),
            day=cast(date, row[2]),
            views=int(row[3]),
            baseline=row[4],
            z_score=row[5],
            peak_ratio=row[6],
            rise_days=row[7],
            half_life_days=row[8],
            yoy_ratio=row[9],
            edit_surge=bool(row[10]),
            spike_type=str(row[11]),
        )
        if sample.spike_id in excluded:
            continue
        strata.setdefault(sample.day.year, []).append(sample)

    rng = random.Random(seed)  # noqa: S311 - sampling for labels, not security
    for samples in strata.values():
        samples.sort(key=lambda sample: sample.spike_id)
        rng.shuffle(samples)

    selected: list[SpikeSample] = []
    years = sorted(strata)
    offsets = {year: 0 for year in years}
    while len(selected) < count:
        progressed = False
        for year in years:
            samples = strata[year]
            offset = offsets[year]
            if offset < len(samples):
                selected.append(samples[offset])
                offsets[year] = offset + 1
                progressed = True
                if len(selected) >= count:
                    break
        if not progressed:
            break
    return selected


def sparkline(values: list[float], width: int = 30) -> str:
    """Render values as a fixed-width ASCII sparkline."""
    if not values:
        return ""
    tail = values[-width:]
    low, high = min(tail), max(tail)
    if high <= low:
        return SPARKLINE_CHARS[0] * len(tail)
    return "".join(
        SPARKLINE_CHARS[int((value - low) / (high - low) * (len(SPARKLINE_CHARS) - 1))]
        for value in tail
    )


def load_sparkline(
    connection: duckdb.DuckDBPyConnection, article: str, day: date, days: int = 30
) -> list[float]:
    """Return recent daily views for an article, oldest first."""
    rows = connection.execute(
        """
        SELECT views FROM article_daily
        WHERE article = ? AND day BETWEEN ? AND ?
        ORDER BY day
        """,
        [article, day - timedelta(days=days), day + timedelta(days=7)],
    ).fetchall()
    return [float(row[0]) for row in rows]


def format_sample(sample: SpikeSample, views: list[float]) -> str:
    """Format one sample for the terminal."""
    z_score = f"{sample.z_score:.1f}" if sample.z_score is not None else "unknown"
    peak = f"{sample.peak_ratio:.1f}" if sample.peak_ratio is not None else "unknown"
    baseline = f"{sample.baseline:.1f}" if sample.baseline is not None else "unknown"
    rise = f"{sample.rise_days:.0f}" if sample.rise_days is not None else "unknown"
    half_life = f"{sample.half_life_days:.0f}" if sample.half_life_days is not None else "unknown"
    yoy = f"{sample.yoy_ratio:.2f}" if sample.yoy_ratio is not None else "unknown"
    return (
        f"{sample.day.isoformat()}  {sample.article}  [{sample.spike_type}]\n"
        f"  views {sample.views:,}  baseline {baseline}  z {z_score}  peak x{peak}\n"
        f"  rise {rise}d  half-life {half_life}d  year-ago x{yoy}  "
        f"edit surge {sample.edit_surge}\n"
        f"  {sparkline(views)}\n"
        f"  {article_url(sample.article)}"
    )


def run_label_session(
    connection: duckdb.DuckDBPyConnection,
    samples: list[SpikeSample],
    *,
    path: Path,
    labeler: str,
    ask: Callable[[str], str],
    echo: Callable[[str], None],
) -> tuple[int, int]:
    """Run the interactive loop; returns (labeled, skipped)."""
    labeled = 0
    skipped = 0
    for index, sample in enumerate(samples, start=1):
        views = load_sparkline(connection, sample.article, sample.day)
        echo(f"[{index}/{len(samples)}]\n{format_sample(sample, views)}")
        while True:
            answer = ask("event / noise / recurring / skip / quit [e/n/r/s/q]: ").strip().lower()
            if answer in {"q", "quit"}:
                return labeled, skipped
            if answer in {"s", "skip", ""}:
                skipped += 1
                break
            choices: dict[str, _label] = {"e": "event", "n": "noise", "r": "recurring"}
            if answer in choices:
                append_label(
                    path,
                    LabelRow(
                        spike_id=sample.spike_id,
                        article=sample.article,
                        date=sample.day,
                        label=choices[answer],
                        labeler=labeler,
                        labeled_at=datetime.now(UTC).replace(tzinfo=None),
                    ),
                )
                labeled += 1
                break
            echo("Enter e, n, r, s or q.")
    return labeled, skipped


def label_counts(labels: Iterable[LabelRow]) -> dict[str, int]:
    """Count labels by class."""
    counts: dict[str, int] = {}
    for row in labels:
        counts[row.label] = counts.get(row.label, 0) + 1
    return counts
