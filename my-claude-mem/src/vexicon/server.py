from fastmcp import FastMCP
from fastmcp.tools import Tool

from vexicon.client.hybrid_client import HybridClient
from vexicon.db import create_index_engine, run_migrations
from vexicon.deps import create_chroma_client, hybrid_client_lifespan
from vexicon.resources import SpacesProvider
from vexicon.settings import Settings, get_settings
from vexicon.tools import TOOLS


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
        device=settings.device,
    )
    mcp = FastMCP(
        "vexicon",
        instructions="A general knowledge store that saves notes and reference "
        "material in named spaces for later search.",
        lifespan=hybrid_client_lifespan(client),
    )
    tags = {"vexicon"}
    for tool in TOOLS:
        if isinstance(tool, Tool):
            mcp.add_tool(tool.model_copy(update={"tags": tags}))
        else:
            mcp.tool(tool, tags=tags)
    mcp.add_provider(SpacesProvider(chroma_client))
    return mcp


def main() -> None:
    """Entry point for the vexicon script; stdio is the only transport."""
    build_server(get_settings()).run(transport="stdio")
