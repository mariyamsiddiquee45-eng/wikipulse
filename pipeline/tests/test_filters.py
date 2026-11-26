from wikipulse.filters import article_url, is_article_title, normalize_title, slugify


def test_main_and_namespace_pages_are_not_articles() -> None:
    for title in (
        "Main_Page",
        "Special:Search",
        "Special:Book",
        "Wikipedia:Featured_pictures",
        "Portal:Current_events",
        "File:Example.jpg",
        "Help:Contents",
        "Category:2024_deaths",
        "Template:Infobox",
        "Talk:Albert_Einstein",
        "User:Example",
    ):
        assert not is_article_title(title), title


def test_article_titles_with_colons_are_kept() -> None:
    for title in ("Star_Trek:_Discovery", "Deaths_in_2026", "AC/DC", "Beyoncé"):
        assert is_article_title(title), title


def test_denylist_is_normalized_and_case_insensitive() -> None:
    assert not is_article_title("Pornhub", frozenset({"pornhub"}))
    assert is_article_title("Pornhub", frozenset({"Example"}))


def test_slugify_handles_accents_and_fallback() -> None:
    assert slugify("Beyoncé") == "beyonce"
    assert slugify("Star_Trek:_Discovery") == "star-trek-discovery"
    assert slugify("東京") != ""
    assert article_url("Albert_Einstein") == "https://en.wikipedia.org/wiki/Albert_Einstein"


def test_normalize_title_collapses_spaces() -> None:
    assert normalize_title("  Albert   Einstein ") == "Albert_Einstein"
