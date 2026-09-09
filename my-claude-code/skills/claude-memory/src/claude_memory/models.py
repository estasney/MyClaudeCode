from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Claude Code sets both variables for plugin hooks and skills."""

    claude_plugin_data: Path
    claude_project_dir: Path

    @property
    def db(self) -> Path:
        return self.claude_plugin_data / "memory.db"

    @property
    def project(self) -> str:
        return self.claude_project_dir.name


class Polarity(StrEnum):
    negative = "negative"
    positive = "positive"


class Scope(StrEnum):
    project = "project"
    everywhere = "everywhere"


class Signal(BaseModel):
    """What I did, the user's exact words, and what the words meant."""

    action: str = Field(default="", max_length=250)
    words: str = Field(min_length=1, max_length=250)
    meaning: str = Field(min_length=1, max_length=250)
    polarity: Polarity = Polarity.negative
    happened_at: AwareDatetime

    @field_validator("happened_at")
    @classmethod
    def normalize_to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class Memory(BaseModel):
    """One sentence that, had it been in context, would have changed what I did."""

    text: str = Field(min_length=1, max_length=250)
    scope: Scope = Scope.project
