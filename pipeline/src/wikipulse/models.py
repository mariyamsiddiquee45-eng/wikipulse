"""Typed models for the Wikimedia responses the pipeline consumes."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TopArticle(BaseModel):
    article: str = Field(min_length=1)
    views: int = Field(ge=0)
    rank: int = Field(ge=1)


class TopDay(BaseModel):
    project: str
    access: str
    year: str
    month: str
    day: str
    articles: list[TopArticle]

    @property
    def date(self) -> date:
        return date(int(self.year), int(self.month), int(self.day))


class TopResponse(BaseModel):
    items: list[TopDay] = Field(min_length=1)


class ArticleDailyItem(BaseModel):
    project: str
    article: str
    granularity: str
    timestamp: str = Field(pattern=r"^\d{10}$")
    access: str
    agent: str
    views: int = Field(ge=0)

    @property
    def date(self) -> date:
        return date(int(self.timestamp[0:4]), int(self.timestamp[4:6]), int(self.timestamp[6:8]))


class ArticleResponse(BaseModel):
    items: list[ArticleDailyItem] = Field(default_factory=list)


class EditedPage(BaseModel):
    page_title: str = Field(min_length=1)
    edits: int = Field(ge=0)
    rank: int = Field(ge=1)


class EditedResult(BaseModel):
    timestamp: datetime
    top: list[EditedPage]


class EditedItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project: str
    editor_type: str = Field(alias="editor-type")
    page_type: str = Field(alias="page-type")
    granularity: str
    results: list[EditedResult]


class EditedResponse(BaseModel):
    items: list[EditedItem] = Field(default_factory=list)


class UrlSet(BaseModel):
    page: str


class ContentUrls(BaseModel):
    desktop: UrlSet
    mobile: UrlSet | None = None


class Summary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    title: str = Field(min_length=1)
    displaytitle: str | None = None
    description: str | None = None
    extract: str | None = None
    extract_html: str | None = None
    pageid: int | None = None
    wikibase_item: str | None = None
    content_urls: ContentUrls | None = None


class SpikeRecord(BaseModel):
    """One detected spike, ready to upsert into the spikes table."""

    spike_id: str
    day: date
    article: str
    views: int
    baseline: float | None
    z_score: float | None
    peak_ratio: float | None
    rise_days: float | None
    time_to_peak_days: float | None
    half_life_days: float | None
    yoy_ratio: float | None
    rank_jump: int | None
    days_since_last_spike: int | None
    edit_surge: bool
    stl_residual: float | None
    score: float
    spike_type: str
    features: dict[str, float | int | str | bool | None]
