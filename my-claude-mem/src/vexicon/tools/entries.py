# pyright: reportArgumentType=false
from typing import Annotated

from fastmcp.server.context import Context
from fastmcp.tools import ToolResult
from pydantic import Field

from vexicon.client.hybrid_client import HybridClient
from vexicon.deps import GetClientDep
from vexicon.models.base import SpaceName
from vexicon.models.entries import (
    Entry,
    NewEntry,
    SearchResult,
    UpdateEntriesInput,
    entries_from,
    search_results_from,
)
from vexicon.text_tools import records_tool

WhereField = Field(default=None, description="Metadata filter.")
WhereTextField = Field(default=None, description="Entry text filter.")


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


ENTRY_TOOLS = [
    add_entries,
    search,
    list_entries,
    update_entries,
    delete_entries,
]
