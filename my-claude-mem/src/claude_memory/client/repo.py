from collections.abc import Sequence
from typing import Protocol

from chromadb import Collection
from chromadb.api.types import (
    CollectionMetadata,
    Documents,
    Embeddings,
    GetResult,
    IDs,
    Include,
    Metadatas,
    QueryResult,
    Where,
    WhereDocument,
)


class ChromaClientProtocol(Protocol):
    """Writes to chroma and sqlite. Queries via fusion from both sources"""

    async def list_collections(
        self, limit: int | None = None, offset: int | None = None
    ) -> Sequence[Collection]: ...

    async def create_collection(
        self,
        name: str,
        repo_id: str | None = None,
        metadata: CollectionMetadata | None = None,
    ) -> Collection:
        """Undo deletes the collection."""
        ...

    async def get_collection(self, name: str) -> Collection: ...

    async def delete_collection(self, name: str) -> None:
        """Undo recreates the collection and re-adds the captured documents with embeddings."""
        ...

    async def modify(
        self,
        collection_name: str,
        name: str | None = None,
        metadata: CollectionMetadata | None = None,
    ) -> None:
        """Undo applies the inverse modify."""
        ...

    async def peek(self, collection_name: str, limit: int = 10) -> GetResult: ...

    async def count(self, collection_name: str) -> int: ...

    async def add(
        self,
        collection_name: str,
        ids: IDs,
        documents: Documents,
        metadatas: Metadatas | None = None,
    ) -> None:
        """SQLite receives the state read back from Chroma; undo deletes the ids."""
        ...

    async def update(
        self,
        collection_name: str,
        ids: IDs,
        embeddings: Embeddings | None = None,
        metadatas: Metadatas | None = None,
        documents: Documents | None = None,
    ) -> None:
        """SQLite receives the state read back from Chroma; undo restores the captured prior state."""
        ...

    async def delete(self, collection_name: str, ids: IDs) -> None:
        """Undo re-adds the captured rows with embeddings."""
        ...

    async def sync(self) -> None: ...

    async def get(
        self,
        collection_name: str,
        ids: IDs | None = None,
        where: Where | None = None,
        limit: int | None = None,
        offset: int | None = None,
        where_document: WhereDocument | None = None,
        include: Include | None = None,
    ) -> GetResult: ...

    async def query(
        self,
        collection_name: str,
        query_texts: Documents,
        n_results: int = 10,
        where: Where | None = None,
        where_document: WhereDocument | None = None,
        include: Include | None = None,
    ) -> QueryResult:
        """Fuses vector and keyword rankings per phrase; keyword-only hits carry None distances."""
        ...
