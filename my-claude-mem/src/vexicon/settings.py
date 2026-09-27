from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Device(StrEnum):
    auto = "auto"
    cpu = "cpu"
    cuda = "cuda"


class Settings(BaseSettings):
    """Read from VEXICON_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="VEXICON_", extra="ignore")

    persistent_path: Path = Field(
        description="Directory where the PersistentClient stores its DB."
    )
    index_db_path: Path = Field(
        description="SQLite database file holding the keyword index."
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
    device: Device = Field(
        default=Device.auto, description="Device that runs embedding models."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
