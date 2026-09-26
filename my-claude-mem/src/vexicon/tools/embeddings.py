import asyncio

from fastmcp.server.context import Context

from vexicon.embedding import list_local_repo_ids
from vexicon.text_tools import lines_tool


@lines_tool
async def list_embedding_models(ctx: Context) -> list[str]:
    """List the embedding model repo_ids that create_space accepts."""
    return await asyncio.to_thread(list_local_repo_ids)


EMBEDDING_TOOLS = [list_embedding_models]
