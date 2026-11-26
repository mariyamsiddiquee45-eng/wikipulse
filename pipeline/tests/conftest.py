"""Shared pytest fixtures."""

from pathlib import Path

import pytest

from tests.support import FakeResponse, FakeSession, load_fixture
from wikipulse.config import Settings

__all__ = ["FakeResponse", "FakeSession", "load_fixture"]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        contact="test@example.com",
        data_dir=tmp_path / "data",
        request_delay_seconds=0.0,
        max_retries=2,
    )
