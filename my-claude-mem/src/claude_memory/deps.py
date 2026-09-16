from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings as ChromaDbSettings
from fastmcp.server.dependencies import get_context
from fastmcp.server.lifespan import Lifespan, lifespan

from claude_memory.settings import Settings

if TYPE_CHECKING:
    from claude_memory.client.hybrid_client import HybridClient


def create_chroma_client(settings: Settings) -> ClientAPI:
    return chromadb.PersistentClient(
        path=str(settings.persistent_path),
        settings=ChromaDbSettings(anonymized_telemetry=False),
    )


async def ensure_memory_space(client: "HybridClient", name: str) -> None:
    existing = {col.name for col in await client.list_collections()}
    if name not in existing:
        await client.create_collection(name=name)


def memory_lifespan(client: "HybridClient", default_memory_space: str) -> Lifespan:
    """Rebuilds the SQL index at startup, creates the default memory space, publishes the hybrid client to tools, and disposes the SQL engine on shutdown."""

    @lifespan
    async def run(server: object) -> AsyncGenerator[dict[str, object]]:
        await client.sync()
        await ensure_memory_space(client, default_memory_space)
        try:
            yield {"hybrid_client": client}
        finally:
            await client.sql_engine.dispose()

    return run


def get_hybrid_client() -> "HybridClient":
    return get_context().lifespan_context["hybrid_client"]


@contextmanager
def borrow_hybrid_client() -> Generator["HybridClient"]:
    """The injector enters whatever a dependency returns, so a plain wrapper keeps the client open."""
    yield get_hybrid_client()
