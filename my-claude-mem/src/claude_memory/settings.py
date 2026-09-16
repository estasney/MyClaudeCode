from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from CLAUDE_MEMORY_* environment variables set by the plugin's .mcp.json."""

    model_config = SettingsConfigDict(env_prefix="CLAUDE_MEMORY_", extra="ignore")

    persistent_path: Path = Field(
        description="Directory where the PersistentClient stores its DB."
    )
    index_db_path: Path = Field(
        description="SQLite database file holding the keyword index."
    )
    default_memory_space: str = Field(
        default="claude-memory",
        min_length=3,
        max_length=63,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$",
        description="Memory space created at startup and used when a tool call names none.",
    )
    vector_weight: float = Field(
        default=1.0, ge=0, description="Weight of the vector ranking in fusion."
    )
    keyword_weight: float = Field(
        default=1.0, ge=0, description="Weight of the FTS5 ranking in fusion."
    )
    rrf_rank_offset: int = Field(
        default=60, ge=1, description="Rank offset in reciprocal rank fusion."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
