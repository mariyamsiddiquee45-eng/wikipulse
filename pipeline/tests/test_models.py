from datetime import date

from tests.support import load_fixture
from wikipulse.models import ArticleResponse, EditedResponse, Summary, TopResponse


def test_top_fixture_matches_the_model() -> None:
    response = TopResponse.model_validate(load_fixture("pageviews_top_2024-01-15.json"))
    day = response.items[0]
    assert day.date == date(2024, 1, 15)
    assert day.project == "en.wikipedia"
    assert day.access == "all-access"
    assert len(day.articles) == 999
    assert day.articles[0].article == "Main_Page"
    assert day.articles[0].views == 5046651


def test_article_fixture_matches_the_model() -> None:
    response = ArticleResponse.model_validate(
        load_fixture("pageviews_article_albert_einstein.json")
    )
    days = [item.date for item in response.items]
    assert days[0] == date(2024, 1, 1)
    assert days[-1] == date(2024, 1, 15)
    assert response.items[0].views == 26079
    assert all(item.agent == "user" for item in response.items)


def test_edited_pages_fixture_matches_the_model() -> None:
    response = EditedResponse.model_validate(load_fixture("edited_pages_2024-01-15.json"))
    item = response.items[0]
    assert item.granularity == "daily"
    assert item.editor_type == "all-editor-types"
    assert item.page_type == "content"
    assert item.results[0].top[0].page_title == "2023\u201324_NFL_playoffs"
    assert item.results[0].top[0].edits == 167


def test_summary_fixture_matches_the_model() -> None:
    summary = Summary.model_validate(load_fixture("summary_albert_einstein.json"))
    assert summary.title == "Albert Einstein"
    assert summary.extract is not None
    assert summary.extract_html is not None
    assert summary.content_urls is not None
    assert summary.content_urls.desktop.page.endswith("/Albert_Einstein")
