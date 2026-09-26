# pyright: reportArgumentType=false
import asyncio
import time
from datetime import UTC, datetime
from typing import Annotated

from chromadb import GetResult
from chromadb.api.types import CollectionMetadata, Metadata, QueryResult
from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import ToolResult
from pydantic import BaseModel, Field, computed_field
from pydantic.json_schema import SkipJsonSchema

from vexicon.client.hybrid_client import HybridClient
from vexicon.deps import borrow_hybrid_client
from vexicon.embedding import list_local_repo_ids
from vexicon.text_tools import lines_tool, record_tool, records_tool, table_tool

GetClientDep = Depends(borrow_hybrid_client)

SpaceName = Annotated[
    str,
    Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$",
        description="Space name.",
    ),
]

Readme = Annotated[
    str,
    Field(description="What the space holds and the conventions its entries follow."),
]

WhereField = Field(default=None, description="Metadata filter.")
WhereTextField = Field(default=None, description="Entry text filter.")


def current_epoch_second() -> int:
    return int(time.time())


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


class SpaceInfo(SpaceSummary):
    id: str = Field(description="Space ID.")
    count: int = Field(description="Number of entries stored.")
    sample: list[Entry] = Field(description="The first few entries.")


@table_tool
async def list_spaces(
    ctx: Context,
    limit: int | None = None,
    offset: int | None = None,
    client: HybridClient = GetClientDep,
) -> list[SpaceSummary]:
    """List spaces with their metadata."""
    cols = await client.list_collections(limit=limit, offset=offset)
    return [SpaceSummary(name=c.name, metadata_raw=c.metadata) for c in cols]


@lines_tool
async def list_embedding_models(ctx: Context) -> list[str]:
    """List the embedding model repo_ids that create_space accepts."""
    return await asyncio.to_thread(list_local_repo_ids)


async def create_space(
    space: SpaceName,
    ctx: Context,
    readme: Readme | None = None,
    embedding_repo_id: Annotated[
        str | None,
        Field(
            description="Hugging Face repo_id from list_embedding_models of the "
            "sentence-transformer model that embeds this space's entries."
        ),
    ] = None,
    metadata: Annotated[
        dict[str, object] | None, Field(description="Other space metadata.")
    ] = None,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Create a space."""
    space_metadata = dict(metadata or {})
    if readme is not None:
        space_metadata["readme"] = readme
    await client.create_collection(
        name=space, repo_id=embedding_repo_id, metadata=space_metadata
    )
    await ctx.session.send_resource_list_changed()
    return ToolResult(content=f"Created space {space!r}.")


@record_tool
async def describe_space(
    space: SpaceName,
    ctx: Context,
    sample_size: int = 5,
    client: HybridClient = GetClientDep,
) -> SpaceInfo:
    """Show a space with its entry count and first entries."""
    col = await client.get_collection(space)
    count = await client.count(space)
    sample = await client.peek(space, limit=sample_size)
    return SpaceInfo(
        name=col.name,
        id=str(col.id),
        metadata_raw=col.metadata,
        count=count,
        sample=entries_from(sample),
    )


def merged_space_metadata(
    current: CollectionMetadata | None, changes: dict[str, object]
) -> CollectionMetadata:
    managed = {"embedding_repo_id", "embedding_max_tokens"} & changes.keys()
    if managed:
        raise ToolError(f"Server-managed metadata keys: {', '.join(sorted(managed))}")
    merged = {**(current or {}), **changes}
    return {key: value for key, value in merged.items() if value is not None}


async def update_space(
    space: SpaceName,
    ctx: Context,
    new_name: SpaceName | None = None,
    readme: Readme | None = None,
    metadata: dict[str, object] | None = None,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Rename a space or change its metadata.

    Metadata keys merge into the current metadata; a null value removes the key.
    """
    changes = dict(metadata or {})
    if readme is not None:
        changes["readme"] = readme
    merged = None
    if changes:
        col = await client.get_collection(space)
        merged = merged_space_metadata(col.metadata, changes)
    await client.modify(space, name=new_name, metadata=merged)
    if new_name is not None:
        await ctx.session.send_resource_list_changed()
    return ToolResult(content=f"Updated space {(new_name or space)!r}.")


async def delete_space(
    space: SpaceName,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Delete a space and every entry in it."""
    await client.delete_collection(space)
    await ctx.session.send_resource_list_changed()
    return ToolResult(content=f"Deleted space {space!r}.")


async def add_entries(
    entries: list[NewEntry],
    space: SpaceName,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Store entries that follow the space readme."""
    ids = [entry.id for entry in entries]
    documents = [entry.text for entry in entries]
    metadatas = [
        {**(entry.meta or {}), "created_at": entry.created_at} for entry in entries
    ]
    await client.add(space, ids=ids, documents=documents, metadatas=metadatas)
    lines = [f"Stored {len(ids)} entries in {space!r}.", *ids]
    return ToolResult(content="\n".join(lines))


@records_tool
async def search(
    queries: list[str],
    space: SpaceName,
    ctx: Context,
    limit: Annotated[int, Field(description="Maximum entries per query.")] = 5,
    where: dict[str, object] | None = WhereField,
    where_text: dict[str, object] | None = WhereTextField,
    client: HybridClient = GetClientDep,
) -> list[SearchResult]:
    """Search a space for each query."""
    result = await client.query(
        space,
        query_texts=queries,
        n_results=limit,
        where=where,
        where_document=where_text,
        include=["documents", "metadatas"],
    )
    return search_results_from(queries, result)


@records_tool
async def list_entries(
    space: SpaceName,
    ctx: Context,
    ids: list[str] | None = None,
    where: dict[str, object] | None = WhereField,
    where_text: dict[str, object] | None = WhereTextField,
    limit: int | None = None,
    offset: int | None = None,
    client: HybridClient = GetClientDep,
) -> list[Entry]:
    """Fetch entries from a space."""
    result = await client.get(
        space,
        ids=ids,
        where=where,
        where_document=where_text,
        include=["documents", "metadatas"],
        limit=limit,
        offset=offset,
    )
    return entries_from(result)


async def update_entries(
    params: UpdateEntriesInput,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Update the text or metadata of entries by ID."""
    await client.update(
        params.space,
        ids=params.ids,
        metadatas=params.metadata,
        documents=params.texts,
    )
    return ToolResult(content=f"Updated {len(params.ids)} entries in {params.space!r}.")


async def delete_entries(
    ids: list[str],
    space: SpaceName,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Delete entries by ID."""
    await client.delete(space, ids=ids)
    return ToolResult(content=f"Deleted {len(ids)} entries in {space!r}.")


TOOLS = [
    list_spaces,
    list_embedding_models,
    create_space,
    describe_space,
    update_space,
    delete_space,
    add_entries,
    search,
    list_entries,
    update_entries,
    delete_entries,
]
