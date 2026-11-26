"""Configuration loaded from WIKIPULSE_* environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """One settings object for the pipeline, with file locations derived from data_dir."""

    model_config = SettingsConfigDict(env_prefix="WIKIPULSE_", env_file=".env", extra="ignore")

    contact: str = ""
    pageviews_base_url: str = "https://wikimedia.org/api/rest_v1"
    summary_base_url: str = "https://en.wikipedia.org/api/rest_v1"
    request_delay_seconds: float = Field(default=0.5, ge=0)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=4, ge=0)
    data_dir: Path = _REPO_ROOT / "data"
    site_url: str = ""
    history_days: int = Field(default=1825, ge=1)
    denylist: str = ""
    z_threshold: float = 3.0
    minimum_views: int = 1000
    candidate_window_days: int = 28
    rank_mover_delta: int = 100
    watchlist_days: int = 14
    candidate_history_days: int = Field(default=400, ge=35)
    max_candidates_per_day: int = Field(default=200, ge=0)
    max_article_files: int = Field(default=12000, ge=0)
    apply_classifier: bool = False

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "wikipulse.duckdb"

    @property
    def parquet_dir(self) -> Path:
        return self.data_dir / "parquet"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "export"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def denylist_items(self) -> frozenset[str]:
        return frozenset(item.strip() for item in self.denylist.split(",") if item.strip())
