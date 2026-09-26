from typing import Annotated

from chromadb.api.types import CollectionMetadata
from pydantic import BaseModel, Field, computed_field

from vexicon.models.base import ForbiddenKeys
from vexicon.models.entries import Entry

SpaceMetadata = Annotated[
    dict[str, object],
    ForbiddenKeys(frozenset({"readme", "embedding_repo_id", "embedding_max_tokens"})),
    Field(description="Other space metadata."),
]


class SpaceSummary(BaseModel):
    name: str = Field(description="Space name.")
    metadata_raw: CollectionMetadata | None = Field(exclude=True)

    @computed_field(
        description="What the space holds and the conventions its entries follow."
    )
    @property
    def readme(self) -> str | None:
        return (self.metadata_raw or {}).get("readme")

    @computed_field(description="Token cap per entry before truncation.")
    @property
    def embedding_max_tokens(self) -> int | None:
        return (self.metadata_raw or {}).get("embedding_max_tokens")

    @computed_field(description="Embedding model set at creation.")
    @property
    def embedding_repo_id(self) -> str | None:
        return (self.metadata_raw or {}).get("embedding_repo_id")

    @computed_field(description="Other space metadata.")
    @property
    def metadata(self) -> dict[str, object] | None:
        known = {"readme", "embedding_max_tokens", "embedding_repo_id"}
        rest = {
            key: value
            for key, value in (self.metadata_raw or {}).items()
            if key not in known
        }
        return rest or None


class SpaceInfo(SpaceSummary):
    id: str = Field(description="Space ID.")
    count: int = Field(description="Number of entries stored.")
    sample: list[Entry] = Field(description="The first few entries.")
