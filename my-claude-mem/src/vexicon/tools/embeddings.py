import asyncio
from typing import Annotated

from fastmcp.server.context import Context
from fastmcp.tools import ToolResult
from pydantic import Field
from sentence_transformers import SentenceTransformer

from vexicon.embedding import list_hub_models, list_local_repo_ids
from vexicon.models.embeddings import EmbeddingModel, HubRepoId
from vexicon.text_tools import lines_tool, table_tool


@lines_tool
async def list_embedding_models(ctx: Context) -> list[str]:
    """List the embedding model repo_ids that create_space accepts."""
    return await asyncio.to_thread(list_local_repo_ids)


@table_tool
async def list_hub_embedding_models(
    ctx: Context, limit: Annotated[int, Field(ge=1)] = 20
) -> list[EmbeddingModel]:
    """List the most downloaded sentence-transformers models on Hugging Face."""
    found = await asyncio.to_thread(list_hub_models, limit)
    cached = set(await asyncio.to_thread(list_local_repo_ids))
    return [
        EmbeddingModel(repo_id=m.id, downloads=m.downloads, cached=m.id in cached)
        for m in found
    ]


async def download_embedding_model(repo_id: HubRepoId, ctx: Context) -> ToolResult:
    """Download an embedding model so that create_space can use it."""
    if repo_id in await asyncio.to_thread(list_local_repo_ids):
        return ToolResult(content=f"Model {repo_id!r} is already downloaded.")
    await asyncio.to_thread(SentenceTransformer, repo_id, local_files_only=False)
    return ToolResult(content=f"Downloaded model {repo_id!r}.")


EMBEDDING_TOOLS = [
    list_embedding_models,
    list_hub_embedding_models,
    download_embedding_model,
]
