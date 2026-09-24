from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "Settings",
    "get_settings",
]


class Settings(BaseSettings):
    """Read from ANALYZE_REPO_* environment variables set by the plugin's .mcp.json."""

    model_config = SettingsConfigDict(env_prefix="ANALYZE_REPO_", extra="ignore")

    data_dir: Path = Field(
        description="Plugin data directory holding the database and cloned repos."
    )
    summary_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model id the semantic pass asks for symbol summaries.",
    )
    summary_concurrency: int = Field(
        default=4, description="Summary requests in flight at once."
    )

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "index.sqlite"

    @property
    def repos_dir(self) -> Path:
        path = self.data_dir / "repos"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
