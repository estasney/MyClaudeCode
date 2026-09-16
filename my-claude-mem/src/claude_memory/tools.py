# pyright: reportArgumentType=false
import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated

from chromadb import GetResult
from chromadb.api.types import Metadata, QueryResult
from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import ToolResult
from pydantic import BaseModel, Field

from claude_memory.client.hybrid_client import HybridClient
from claude_memory.deps import borrow_hybrid_client
from claude_memory.embedding import list_local_repo_ids
from claude_memory.settings import get_settings
from claude_memory.text_tools import lines_tool, record_tool, records_tool, table_tool

GetClientDep = Depends(borrow_hybrid_client)

MemorySpaceName = Annotated[
    str,
    Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$",
        description="Memory space name.",
    ),
]

MemorySpaceField = Field(
    default=None,
    description="Memory space to use; omit for the default memory space.",
    examples=[None],
)


def resolve_memory_space(memory_space: str | None) -> str:
    return memory_space or get_settings().default_memory_space


class RecallInput(BaseModel):
    queries: list[str] = Field(
        description="Texts to search with; vector and keyword rankings are fused per text.",
        examples=[["how does the user like tests structured"]],
    )
    memory_space: str | None = MemorySpaceField
    limit: int = Field(
        default=5, description="Max memories per query text.", examples=[5]
    )
    where: dict[str, object] | None = Field(
        default=None, description="Metadata filter.", examples=[None]
    )
    where_text: dict[str, object] | None = Field(
        default=None, description="Memory text filter.", examples=[None]
    )


class ListMemoriesInput(BaseModel):
    memory_space: str | None = MemorySpaceField
    ids: list[str] | None = Field(
        default=None, description="Specific memory IDs to fetch.", examples=[None]
    )
    where: dict[str, object] | None = Field(
        default=None, description="Metadata filter.", examples=[None]
    )
    where_text: dict[str, object] | None = Field(
        default=None, description="Memory text filter.", examples=[None]
    )
    limit: int | None = Field(
        default=None, description="Max rows to return.", examples=[None]
    )
    offset: int | None = Field(
        default=None, description="Row offset for pagination.", examples=[None]
    )


class ReviseInput(BaseModel):
    ids: list[str] = Field(
        description="IDs of memories to revise.", examples=[["id-1"]]
    )
    memory_space: str | None = MemorySpaceField
    metadata: list[dict[str, object]] | None = Field(
        default=None, description="New metadata per ID.", examples=[None]
    )
    memories: list[str] | None = Field(
        default=None, description="New memory text per ID.", examples=[None]
    )


class MemorySpaceSummary(BaseModel):
    name: str = Field(description="Memory space name.")
    metadata: dict[str, object] | None = Field(
        description="Memory space metadata; embedding_max_tokens is the absolute "
        "per-memory token cap (aim for half that per chunk), and embedding_repo_id "
        "names the model when one was set at creation."
    )


class Memory(BaseModel):
    id: str = Field(description="Memory ID.")
    created: datetime | None = Field(description="When the memory was stored.")
    metadata: dict[str, object] | None = Field(
        description="Metadata other than created_at; None when there is none."
    )
    text: str | None = Field(description="Memory text.")


def memory_from(memory_id: str, text: str | None, metadata: Metadata | None) -> Memory:
    rest = dict(metadata or {})
    created_at = rest.pop("created_at", None)
    return Memory(
        id=memory_id,
        created=datetime.fromtimestamp(created_at, tz=UTC)
        if isinstance(created_at, int | float)
        else None,
        metadata=rest or None,
        text=text,
    )


def memories_from(result: GetResult) -> list[Memory]:
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    return [
        memory_from(
            memory_id,
            documents[index] if index < len(documents) else None,
            metadatas[index] if index < len(metadatas) else None,
        )
        for index, memory_id in enumerate(result["ids"])
    ]


class Recall(BaseModel):
    query: str = Field(description="The query text these memories answer.")
    memories: list[Memory] = Field(description="Memories ranked by fused score.")


def recalls_from(queries: list[str], result: QueryResult) -> list[Recall]:
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    return [
        Recall(
            query=query,
            memories=[
                memory_from(
                    memory_id,
                    documents[phrase][index] if phrase < len(documents) else None,
                    metadatas[phrase][index] if phrase < len(metadatas) else None,
                )
                for index, memory_id in enumerate(phrase_ids)
            ],
        )
        for phrase, (query, phrase_ids) in enumerate(
            zip(queries, result["ids"], strict=True)
        )
    ]


class MemorySpaceInfo(MemorySpaceSummary):
    id: str = Field(description="Memory space ID.")
    count: int = Field(description="Number of memories stored.")
    sample: list[Memory] = Field(description="The first few memories.")


@table_tool
async def list_memory_spaces(
    ctx: Context,
    limit: int | None = None,
    offset: int | None = None,
    client: HybridClient = GetClientDep,
) -> list[MemorySpaceSummary]:
    """List all memory spaces with their metadata, with optional pagination."""
    cols = await client.list_collections(limit=limit, offset=offset)
    return [MemorySpaceSummary(name=c.name, metadata=c.metadata) for c in cols]


@lines_tool
async def list_embedding_models(ctx: Context) -> list[str]:
    """List repo_ids of locally available sentence-transformer embedding models.

    Any of these is a valid repo_id for create_memory_space; omitting repo_id
    uses the default embedding function.
    """
    return await asyncio.to_thread(list_local_repo_ids)


async def create_memory_space(
    memory_space: MemorySpaceName,
    ctx: Context,
    repo_id: str | None = None,
    metadata: dict[str, object] | None = None,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Create a new memory space; repo_id picks a HF sentence-transformer model, e.g. sentence-transformers/multi-qa-mpnet-base-cos-v1.

    If the user asks for a specific model, verify it against list_embedding_models first; omit repo_id to use the default embedding function.
    """
    await client.create_collection(
        name=memory_space, repo_id=repo_id, metadata=metadata
    )
    await ctx.session.send_resource_list_changed()
    return ToolResult(content=f"Created memory space {memory_space!r}.")


@record_tool
async def describe_memory_space(
    ctx: Context,
    memory_space: str | None = MemorySpaceField,
    sample_size: int = 5,
    client: HybridClient = GetClientDep,
) -> MemorySpaceInfo:
    """Return name, id, metadata, memory count, and the first few memories of a memory space."""
    name = resolve_memory_space(memory_space)
    col = await client.get_collection(name)
    count = await client.count(name)
    sample = await client.peek(name, limit=sample_size)
    return MemorySpaceInfo(
        name=col.name,
        id=str(col.id),
        metadata=col.metadata,
        count=count,
        sample=memories_from(sample),
    )


async def rename_memory_space(
    memory_space: MemorySpaceName,
    new_name: MemorySpaceName,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Rename a memory space."""
    await client.modify(memory_space, name=new_name)
    await ctx.session.send_resource_list_changed()
    return ToolResult(content=f"Renamed memory space {memory_space!r} to {new_name!r}.")


async def delete_memory_space(
    memory_space: MemorySpaceName,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Delete a memory space and every memory in it."""
    await client.delete_collection(memory_space)
    await ctx.session.send_resource_list_changed()
    return ToolResult(content=f"Deleted memory space {memory_space!r}.")


async def remember(
    memories: list[str],
    ctx: Context,
    memory_space: str | None = MemorySpaceField,
    metadata: list[dict[str, object]] | None = None,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Store memories; IDs are generated and each memory is stamped with a created_at epoch-second metadata field for recency filtering. Returns the new IDs.

    The memory space's embedding_max_tokens (see list_memory_spaces) is the absolute per-memory cap; longer text is silently truncated before embedding. Chunk long text to roughly half that cap for best embedding quality.
    """
    name = resolve_memory_space(memory_space)
    created_at = int(time.time())
    ids = [uuid.uuid4().hex for _ in memories]
    stamped = [
        {**(metadata[i] if metadata else {}), "created_at": created_at}
        for i in range(len(memories))
    ]
    await client.add(name, ids=ids, documents=memories, metadatas=stamped)
    lines = [f"Stored {len(ids)} memories in {name!r}.", *ids]
    return ToolResult(content="\n".join(lines))


@records_tool
async def recall(
    params: RecallInput,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> list[Recall]:
    """Hybrid search over a memory space: vector and keyword rankings fused per query text. Returns one ranked list per query text."""
    result = await client.query(
        resolve_memory_space(params.memory_space),
        query_texts=params.queries,
        n_results=params.limit,
        where=params.where,
        where_document=params.where_text,
        include=["documents", "metadatas"],
    )
    return recalls_from(params.queries, result)


@records_tool
async def list_memories(
    params: ListMemoriesInput,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> list[Memory]:
    """Fetch memories from a memory space with optional filtering."""
    result = await client.get(
        resolve_memory_space(params.memory_space),
        ids=params.ids,
        where=params.where,
        where_document=params.where_text,
        include=["documents", "metadatas"],
        limit=params.limit,
        offset=params.offset,
    )
    return memories_from(result)


async def revise(
    params: ReviseInput,
    ctx: Context,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Revise the text or metadata of memories by ID."""
    name = resolve_memory_space(params.memory_space)
    await client.update(
        name,
        ids=params.ids,
        metadatas=params.metadata,
        documents=params.memories,
    )
    return ToolResult(content=f"Revised {len(params.ids)} memories in {name!r}.")


async def forget(
    ids: list[str],
    ctx: Context,
    memory_space: str | None = MemorySpaceField,
    client: HybridClient = GetClientDep,
) -> ToolResult:
    """Delete memories by ID."""
    name = resolve_memory_space(memory_space)
    await client.delete(name, ids=ids)
    return ToolResult(content=f"Forgot {len(ids)} memories in {name!r}.")


TOOLS = [
    list_memory_spaces,
    list_embedding_models,
    create_memory_space,
    describe_memory_space,
    rename_memory_space,
    delete_memory_space,
    remember,
    recall,
    list_memories,
    revise,
    forget,
]
