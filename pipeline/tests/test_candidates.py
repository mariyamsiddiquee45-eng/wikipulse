from datetime import date
from pathlib import Path

import duckdb

from wikipulse import db
from wikipulse.candidates import NEW_ENTRANT, RANK_MOVER, WATCHLIST, select_candidates
from wikipulse.config import Settings
from wikipulse.models import TopArticle


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {"data_dir": tmp_path / "data", "max_candidates_per_day": 0}
    values.update(overrides)
    return Settings.model_validate(values)


def _seed(connection: duckdb.DuckDBPyConnection) -> date:
    start = date(2024, 1, 1)
    for offset in range(30):
        day = date.fromordinal(start.toordinal() + offset)
        db.upsert_top(
            connection,
            day,
            [
                TopArticle(article="Alpha", views=1000, rank=1),
                TopArticle(article="Bravo", views=400, rank=500),
                TopArticle(article="Delta", views=700, rank=10),
            ],
        )
    final = date(2024, 1, 31)
    db.upsert_top(
        connection,
        final,
        [
            TopArticle(article="Alpha", views=1100, rank=1),
            TopArticle(article="Bravo", views=800, rank=20),
            TopArticle(article="Charlie", views=900, rank=5),
            TopArticle(article="Delta", views=700, rank=9),
            TopArticle(article="Special:Search", views=5000, rank=2),
        ],
    )
    connection.execute(
        "INSERT INTO spikes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "spike-1",
            date(2024, 1, 30),
            "Alpha",
            1000,
            100.0,
            5.0,
            3.0,
            1.0,
            1.0,
            1.0,
            0,
            0,
            False,
            10.0,
            "Flash",
            "{}",
            db.utc_now(),
        ],
    )
    return final


def test_candidate_pool_uses_all_three_rules(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = _seed(connection)

    candidates = select_candidates(connection, day, _settings(tmp_path))

    reasons = {candidate.article: candidate.reasons for candidate in candidates}
    assert set(reasons) == {"Alpha", "Bravo", "Charlie"}
    assert NEW_ENTRANT in reasons["Charlie"]
    assert RANK_MOVER in reasons["Bravo"]
    assert WATCHLIST in reasons["Alpha"]
    assert "Special:Search" not in reasons


def test_candidate_cap_keeps_highest_views(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    day = _seed(connection)

    candidates = select_candidates(connection, day, _settings(tmp_path, max_candidates_per_day=1))

    assert [candidate.article for candidate in candidates] == ["Alpha"]


def test_missing_day_returns_no_candidates(tmp_path: Path) -> None:
    connection = duckdb.connect(":memory:")
    db.init_schema(connection)
    assert select_candidates(connection, date(2024, 1, 31), _settings(tmp_path)) == []
