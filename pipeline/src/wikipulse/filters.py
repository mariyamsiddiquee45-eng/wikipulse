"""Article filtering, title normalization and URL slugs."""

import hashlib
import re
import unicodedata
from urllib.parse import quote, unquote

MAIN_PAGE = "Main_Page"

EXCLUDED_NAMESPACES = frozenset(
    {
        "special",
        "wikipedia",
        "portal",
        "file",
        "help",
        "category",
        "template",
        "talk",
        "user",
        "draft",
        "module",
        "mediawiki",
        "book",
        "timedtext",
    }
)


def normalize_title(title: str) -> str:
    """Return a MediaWiki-style title with spaces collapsed to underscores."""
    return re.sub(r"\s+", "_", title.strip())


def is_article_title(title: str, denylist: frozenset[str] = frozenset()) -> bool:
    """Return True only for main-namespace pages that are not the main page or denied."""
    normalized = normalize_title(title)
    if not normalized or normalized == MAIN_PAGE:
        return False
    if ":" in normalized:
        prefix = normalized.split(":", 1)[0].strip().lower().replace("_", " ")
        if prefix.replace(" ", "") in {name.replace(" ", "") for name in EXCLUDED_NAMESPACES}:
            return False
    denied = {normalize_title(item).lower() for item in denylist}
    return normalized.lower() not in denied


def slugify(title: str) -> str:
    """Return a stable, URL-safe slug; non-Latin titles fall back to a short hash."""
    text = unquote(title).replace("_", " ")
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or hashlib.sha256(title.encode()).hexdigest()[:12]


def article_url(title: str) -> str:
    """Return the English Wikipedia URL for a title."""
    return f"https://en.wikipedia.org/wiki/{quote(normalize_title(title), safe='')}"
