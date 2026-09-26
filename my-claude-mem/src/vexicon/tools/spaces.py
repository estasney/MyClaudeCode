from fastmcp.server.context import Context
from fastmcp.tools import ToolResult

from vexicon.client.hybrid_client import HybridClient
from vexicon.deps import GetClientDep
from vexicon.models.base import Readme, SpaceName
from vexicon.models.embeddings import EmbeddingRepoId
from vexicon.models.entries import entries_from
from vexicon.models.spaces import SpaceInfo, SpaceMetadata, SpaceSummary
from vexicon.text_tools import record_tool, table_tool


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


async def create_space(
    space: SpaceName,
    ctx: Context,
    readme: Readme | None = None,
    embedding_repo_id: EmbeddingRepoId | None = None,
    metadata: SpaceMetadata | None = None,
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


async def update_space(
    space: SpaceName,
    ctx: Context,
    new_name: SpaceName | None = None,
    readme: Readme | None = None,
    metadata: SpaceMetadata | None = None,
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
        combined = {**(col.metadata or {}), **changes}
        merged = {key: value for key, value in combined.items() if value is not None}
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


SPACE_TOOLS = [
    list_spaces,
    create_space,
    describe_space,
    update_space,
    delete_space,
]
