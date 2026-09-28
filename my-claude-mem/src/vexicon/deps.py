from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings as ChromaDbSettings
from fastmcp.dependencies import Depends
from fastmcp.server.dependencies import get_context
from fastmcp.server.lifespan import Lifespan, lifespan

from vexicon.embedding import release_embedding_models
from vexicon.idle_proxy import IdleUnloadingProxy
from vexicon.settings import Settings

if TYPE_CHECKING:
    from vexicon.client.hybrid_client import HybridClient


def create_chroma_client(settings: Settings) -> ClientAPI:
    return chromadb.PersistentClient(
        path=str(settings.persistent_path),
        settings=ChromaDbSettings(anonymized_telemetry=False),
    )


def close_chroma_client(client: ClientAPI) -> None:
    client.close()  # pyright: ignore[reportAttributeAccessIssue] # Technically not on ClientAPI


def create_chroma_proxy(settings: Settings) -> IdleUnloadingProxy[ClientAPI]:
    """Opens Chroma on first use and closes it, with its embedding models, after idle_seconds."""
    return IdleUnloadingProxy(
        load=lambda: create_chroma_client(settings),
        idle_seconds=settings.idle_seconds,
        unload=close_chroma_client,
        reclaim=release_embedding_models,
    )


def hybrid_client_lifespan(client: "HybridClient") -> Lifespan:
    """Rebuilds the SQL index at startup, publishes the hybrid client to tools, and releases Chroma and the SQL engine on shutdown."""

    @lifespan
    async def run(server: object) -> AsyncGenerator[dict[str, object]]:
        await client.sync()
        try:
            yield {"hybrid_client": client}
        finally:
            await client.chroma.aclose()
            await client.sql_engine.dispose()

    return run


def get_hybrid_client() -> "HybridClient":
    return get_context().lifespan_context["hybrid_client"]


@contextmanager
def borrow_hybrid_client() -> Generator["HybridClient"]:
    """The injector enters whatever a dependency returns, so a plain wrapper keeps the client open."""
    yield get_hybrid_client()


GetClientDep = Depends(borrow_hybrid_client)
