"""Test support: recorded fixtures and a fake HTTP transport."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    loaded = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return cast(dict[str, Any], loaded)


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(
        self,
        status_code: int,
        payload: object | None = None,
        text: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no JSON payload")
        return self._payload


class FakeSession:
    """Return queued responses and record every request."""

    def __init__(self, responses: Sequence[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> FakeResponse:
        del timeout
        self.calls.append((url, headers))
        if not self._responses:
            raise AssertionError(f"unexpected request to {url}")
        return self._responses.pop(0)
