from datetime import UTC, datetime

from chromadb import GetResult
from chromadb.api.types import Metadata, QueryResult
from pydantic import BaseModel, Field, computed_field
from pydantic.json_schema import SkipJsonSchema

from vexicon.models.base import SpaceName, current_epoch_second


class NewEntry(BaseModel):
    text: str = Field(
        description="Entry text within half of the space's embedding_max_tokens."
    )
    id: str = Field(
        description="Kebab-case mnemonic ID.",
        min_length=1,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
    )
    meta: dict[str, object] | None = Field(default=None, description="Entry metadata.")
    created_at: SkipJsonSchema[int] = Field(default_factory=current_epoch_second)


class UpdateEntriesInput(BaseModel):
    ids: list[str] = Field(description="IDs of entries to update.")
    space: SpaceName
    metadata: list[dict[str, object]] | None = Field(
        default=None, description="New metadata per ID."
    )
    texts: list[str] | None = Field(default=None, description="New entry text per ID.")


class Entry(BaseModel):
    id: str = Field(description="Entry ID.")
    text: str | None = Field(description="Entry text.")
    metadata_raw: Metadata | None = Field(exclude=True)

    @computed_field(description="When the entry was stored.")
    @property
    def created(self) -> datetime | None:
        created_at = (self.metadata_raw or {}).get("created_at")
        if isinstance(created_at, int | float):
            return datetime.fromtimestamp(created_at, tz=UTC)
        return None

    @computed_field(description="Other entry metadata.")
    @property
    def metadata(self) -> Metadata | None:
        rest = {
            key: value
            for key, value in (self.metadata_raw or {}).items()
            if key != "created_at"
        }
        return rest or None


def entries_from(result: GetResult) -> list[Entry]:
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    return [
        Entry(
            id=entry_id,
            text=documents[index] if index < len(documents) else None,
            metadata_raw=metadatas[index] if index < len(metadatas) else None,
        )
        for index, entry_id in enumerate(result["ids"])
    ]


class SearchResult(BaseModel):
    query: str = Field(description="The query text these entries answer.")
    entries: list[Entry] = Field(description="Entries ranked by fused score.")


def search_results_from(queries: list[str], result: QueryResult) -> list[SearchResult]:
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    return [
        SearchResult(
            query=query,
            entries=[
                Entry(
                    id=entry_id,
                    text=documents[phrase][index] if phrase < len(documents) else None,
                    metadata_raw=metadatas[phrase][index]
                    if phrase < len(metadatas)
                    else None,
                )
                for index, entry_id in enumerate(phrase_ids)
            ],
        )
        for phrase, (query, phrase_ids) in enumerate(
            zip(queries, result["ids"], strict=True)
        )
    ]
