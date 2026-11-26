"""Sequential, cached Wikimedia API client with bounded retries."""

import hashlib
import json
import logging
import os
import random
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import quote

import requests

from wikipulse import __version__
from wikipulse.config import Settings
from wikipulse.models import ArticleResponse, EditedResponse, Summary, TopResponse

logger = logging.getLogger(__name__)

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_PLACEHOLDER_CONTACT = "you@example.com"


class HttpResponse(Protocol):
    """The response surface the client uses; requests.Response satisfies it."""

    status_code: int
    text: str
    headers: Mapping[str, str]

    def json(self) -> Any: ...


class HttpSession(Protocol):
    """The session surface the client uses; requests.Session satisfies it."""

    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse: ...


class WikimediaError(Exception):
    """Base error for API and cache failures."""


class MissingContactError(WikimediaError):
    """Raised when no contact address is configured for the User-Agent header."""


class ApiError(WikimediaError):
    """A non-retryable API response or an exhausted retry budget."""

    def __init__(self, status: int | None, url: str, detail: str) -> None:
        self.status = status
        self.url = url
        self.detail = detail
        super().__init__(f"HTTP {status} for {url}: {detail}")


class NotFoundError(ApiError):
    """A 404 from Wikimedia, which can mean missing data or a missing page."""


class WikimediaClient:
    """Fetch Wikimedia JSON sequentially, cache every response, and retry transient errors."""

    def __init__(
        self,
        settings: Settings,
        session: HttpSession | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        random_source: random.Random | None = None,
    ) -> None:
        contact = settings.contact.strip()
        if not contact or contact == _PLACEHOLDER_CONTACT:
            raise MissingContactError(
                "Set WIKIPULSE_CONTACT to a real contact address before making live requests."
            )
        self.settings = settings
        self._session: HttpSession = (
            session if session is not None else cast(HttpSession, requests.Session())
        )
        self._sleep = sleep
        self._monotonic = monotonic
        self._random = random_source or random.Random()  # noqa: S311 - jitter only, not security
        self._last_request_at: float | None = None

    @property
    def user_agent(self) -> str:
        return f"WikiPulse/{__version__} ({self.settings.contact})"

    def fetch_top(self, day: date, force: bool = False) -> TopResponse:
        """Return the top 1000 articles for one completed day."""
        url = (
            f"{self.settings.pageviews_base_url.rstrip('/')}"
            f"/metrics/pageviews/top/en.wikipedia/all-access/{day:%Y/%m/%d}"
        )
        path = self.settings.cache_dir / "pageviews_top" / f"{day.isoformat()}.json"
        return TopResponse.model_validate(self.get_json(url, path, force=force))

    def fetch_article_daily(
        self, article: str, start: date, end: date, force: bool = False
    ) -> ArticleResponse:
        """Return user-agent daily views for one article and date range."""
        if start > end:
            raise ValueError("start must not be after end")
        encoded = quote(article, safe="")
        url = (
            f"{self.settings.pageviews_base_url.rstrip('/')}"
            f"/metrics/pageviews/per-article/en.wikipedia/all-access/user/{encoded}"
            f"/daily/{start:%Y%m%d}/{end:%Y%m%d}"
        )
        key = hashlib.sha256(
            f"{article}|{start.isoformat()}|{end.isoformat()}".encode()
        ).hexdigest()
        path = self.settings.cache_dir / "pageviews_article" / f"{key}.json"
        try:
            return ArticleResponse.model_validate(self.get_json(url, path, force=force))
        except NotFoundError:
            logger.info("No pageview history for %s between %s and %s", article, start, end)
            return ArticleResponse(items=[])

    def fetch_edited(self, day: date, force: bool = False) -> EditedResponse:
        """Return the top 100 edited content pages for one completed day."""
        url = (
            f"{self.settings.pageviews_base_url.rstrip('/')}"
            f"/metrics/edited-pages/top-by-edits/en.wikipedia/all-editor-types/content/{day:%Y/%m/%d}"
        )
        path = self.settings.cache_dir / "edited_pages" / f"{day.isoformat()}.json"
        try:
            return EditedResponse.model_validate(self.get_json(url, path, force=force))
        except NotFoundError:
            logger.info("No edit analytics for %s", day)
            return EditedResponse(items=[])

    def fetch_summary(self, article: str, force: bool = False) -> Summary:
        """Return the plain-text summary for an article; raises NotFoundError for a missing page."""
        encoded = quote(article, safe="")
        url = f"{self.settings.summary_base_url.rstrip('/')}/page/summary/{encoded}"
        key = hashlib.sha256(article.encode()).hexdigest()
        path = self.settings.cache_dir / "summaries" / f"{key}.json"
        payload = self.get_json(
            url, path, max_age=timedelta(days=30) if not force else None, force=force
        )
        return Summary.model_validate(payload)

    def get_json(
        self,
        url: str,
        cache_path: Path,
        max_age: timedelta | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Return cached JSON when fresh, otherwise fetch and cache it atomically."""
        if not force and cache_path.exists():
            age = datetime.now(UTC) - datetime.fromtimestamp(cache_path.stat().st_mtime, UTC)
            if max_age is None or age <= max_age:
                return self._read_cache(cache_path)
        payload = self._request_json(url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(cache_path)
        return payload

    def _read_cache(self, cache_path: Path) -> dict[str, Any]:
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WikimediaError(f"Unreadable cache file {cache_path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise WikimediaError(f"Cache file {cache_path} does not contain an object")
        return cast(dict[str, Any], loaded)

    def _request_json(self, url: str) -> dict[str, Any]:
        last_detail = ""
        for attempt in range(self.settings.max_retries + 1):
            self._throttle()
            try:
                response = self._session.get(
                    url,
                    headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                    timeout=self.settings.request_timeout_seconds,
                )
            except requests.RequestException as exc:
                last_detail = str(exc)
                if attempt == self.settings.max_retries:
                    raise ApiError(None, url, last_detail) from exc
                self._sleep(self._backoff_seconds(attempt, None))
                continue
            self._last_request_at = self._monotonic()
            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise WikimediaError(f"Malformed JSON from {url}") from exc
                if not isinstance(payload, dict):
                    raise WikimediaError(f"Unexpected JSON shape from {url}")
                return cast(dict[str, Any], payload)
            last_detail = response.text[:500]
            if response.status_code in _RETRY_STATUS and attempt < self.settings.max_retries:
                retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
                self._sleep(self._backoff_seconds(attempt, retry_after))
                continue
            if response.status_code == 404:
                raise NotFoundError(404, url, last_detail)
            raise ApiError(response.status_code, url, last_detail)
        raise ApiError(None, url, last_detail)

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        wait = self.settings.request_delay_seconds - (self._monotonic() - self._last_request_at)
        if wait > 0:
            self._sleep(wait)

    def _backoff_seconds(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return retry_after
        base: float = min(30.0, 1.0 * (2**attempt))
        return base + float(self._random.uniform(0, 1))

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None
