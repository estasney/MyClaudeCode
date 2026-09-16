from fastmcp import FastMCP
from fastmcp.tools import Tool

from claude_memory.client.hybrid_client import HybridClient
from claude_memory.db import create_index_engine, run_migrations
from claude_memory.deps import create_chroma_client, memory_lifespan
from claude_memory.resources import MemorySpacesProvider
from claude_memory.settings import Settings, get_settings
from claude_memory.tools import TOOLS


def build_server(settings: Settings) -> FastMCP:
    """Migrates the keyword index before serving."""
    settings.persistent_path.mkdir(parents=True, exist_ok=True)
    settings.index_db_path.parent.mkdir(parents=True, exist_ok=True)
    run_migrations(settings.index_db_path)
    chroma_client = create_chroma_client(settings)
    client = HybridClient(
        chroma_client=chroma_client,
        sql_engine=create_index_engine(settings),
        vector_weight=settings.vector_weight,
        keyword_weight=settings.keyword_weight,
        rrf_rank_offset=settings.rrf_rank_offset,
    )
    mcp = FastMCP(
        "memory", lifespan=memory_lifespan(client, settings.default_memory_space)
    )
    tags = {"memory"}
    for tool in TOOLS:
        if isinstance(tool, Tool):
            mcp.add_tool(tool.model_copy(update={"tags": tags}))
        else:
            mcp.tool(tool, tags=tags)
    mcp.add_provider(MemorySpacesProvider(chroma_client))
    return mcp


def main() -> None:
    """Entry point for the claude-memory script; stdio is the only transport."""
    build_server(get_settings()).run(transport="stdio")
