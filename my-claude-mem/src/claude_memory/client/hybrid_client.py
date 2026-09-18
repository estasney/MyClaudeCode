import asyncio
from collections.abc import Sequence
from typing import cast

from chromadb import Collection
from chromadb.api import ClientAPI
from chromadb.api.types import (
    CollectionMetadata,
    Documents,
    Embeddable,
    EmbeddingFunction,
    Embeddings,
    GetResult,
    IDs,
    Include,
    Metadatas,
    QueryResult,
    Where,
    WhereDocument,
)
from fastmcp.exceptions import ToolError
from sqlalchemy import bindparam, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from claude_memory import orm
from claude_memory.embedding import resolve_embedding_function
from claude_memory.queries.fusion import (
    KeywordHit,
    assemble_query_result,
    fuse,
    group_by_phrase,
)
from claude_memory.queries.matching import match_expression
from claude_memory.queries.selects import collection_id_select, keyword_search_select


def collection_metadata(
    metadata: CollectionMetadata | None, repo_id: str | None, max_tokens: int | None
) -> CollectionMetadata | None:
    embedding_meta = {
        "embedding_repo_id": repo_id,
        "embedding_max_tokens": max_tokens,
    }
    merged = {
        **(metadata or {}),
        **{key: value for key, value in embedding_meta.items() if value is not None},
    }
    return merged or None


class HybridClient:
    """Implements ChromaClientProtocol over one Chroma client and one SQLite engine."""

    def __init__(
        self,
        chroma_client: ClientAPI,
        sql_engine: AsyncEngine,
        vector_weight: float,
        keyword_weight: float,
        rrf_rank_offset: int,
    ) -> None:
        self.chroma_client = chroma_client
        self.sql_engine = sql_engine
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.rrf_rank_offset = rrf_rank_offset

    async def list_collections(
        self, limit: int | None = None, offset: int | None = None
    ) -> Sequence[Collection]:
        collections, sql_collection_names = await asyncio.gather(
            self._list_collections_chroma(), self._list_collections_sqlite()
        )
        matched = [col for col in collections if col.name in sql_collection_names]
        start = offset or 0
        end = None if limit is None else start + limit
        return matched[start:end]

    async def _list_collections_chroma(self) -> Sequence[Collection]:
        return await asyncio.to_thread(self.chroma_client.list_collections)

    async def _list_collections_sqlite(self) -> Sequence[str]:
        async with self.sql_engine.begin() as connection:
            query = await connection.execute(select(orm.Collection.name))
            return query.scalars().all()

    async def create_collection(
        self,
        name: str,
        repo_id: str | None = None,
        metadata: CollectionMetadata | None = None,
    ) -> Collection:
        def write_chroma() -> Collection:
            embedding_function, max_tokens = resolve_embedding_function(repo_id)
            return self.chroma_client.create_collection(
                name=name,
                embedding_function=cast(
                    "EmbeddingFunction[Embeddable]", embedding_function
                ),
                metadata=collection_metadata(metadata, repo_id, max_tokens),
            )

        async def write_sql(connection: AsyncConnection, col: Collection) -> None:
            await connection.execute(insert(orm.Collection).values(name=col.name))

        collection = await asyncio.to_thread(write_chroma)
        async with self.sql_engine.begin() as connection:
            await write_sql(connection, collection)
        return collection

    async def get_collection(self, name: str) -> Collection:
        return await asyncio.to_thread(self.chroma_client.get_collection, name=name)

    async def delete_collection(self, name: str) -> None:
        def write_chroma() -> None:
            self.chroma_client.delete_collection(name=name)

        async def write_sql(connection: AsyncConnection) -> None:
            await connection.execute(
                delete(orm.Collection).where(orm.Collection.name == name)
            )

        await asyncio.to_thread(write_chroma)
        async with self.sql_engine.begin() as connection:
            await write_sql(connection)

    async def modify(
        self,
        collection_name: str,
        name: str | None = None,
        metadata: CollectionMetadata | None = None,
    ) -> None:
        def write_chroma() -> None:
            col = self.chroma_client.get_collection(name=collection_name)
            col.modify(name=name, metadata=metadata)

        async def write_sql(connection: AsyncConnection) -> None:
            if name is not None:
                await connection.execute(
                    update(orm.Collection)
                    .where(orm.Collection.name == collection_name)
                    .values(name=name)
                )

        await asyncio.to_thread(write_chroma)
        async with self.sql_engine.begin() as connection:
            await write_sql(connection)

    async def add(
        self,
        collection_name: str,
        ids: IDs,
        documents: Documents,
        metadatas: Metadatas | None = None,
    ) -> None:
        if len(set(ids)) != len(ids):
            raise ToolError("Memory IDs repeat within the batch")

        def write_chroma() -> GetResult:
            col = self.chroma_client.get_collection(name=collection_name)
            existing = col.get(ids=ids, include=[])["ids"]
            if existing:
                raise ToolError(
                    f"Memory IDs already exist in {collection_name!r}: "
                    + ", ".join(existing)
                )
            col.add(ids=ids, documents=documents, metadatas=metadatas)
            return col.get(ids=ids, include=["documents", "metadatas"])

        async def read_collection_id(connection: AsyncConnection) -> int:
            collection_id = await connection.scalar(
                select(orm.Collection.id).where(orm.Collection.name == collection_name)
            )
            if collection_id is None:
                raise ToolError(f"Collection {collection_name!r} is not indexed")
            return collection_id

        async def write_sql(
            connection: AsyncConnection, collection_id: int, written: GetResult
        ) -> None:
            written_documents = written["documents"]
            written_metadatas = written["metadatas"]
            if written_documents is None or written_metadatas is None:
                raise ToolError("Chroma result lacks documents or metadatas")
            rows = [
                {
                    "collection_id": collection_id,
                    "chroma_id": chroma_id,
                    "document": document,
                    "metadata": metadata,
                }
                for chroma_id, document, metadata in zip(
                    written["ids"], written_documents, written_metadatas, strict=True
                )
            ]
            await connection.execute(insert(orm.Document), rows)

        async with self.sql_engine.connect() as connection:
            collection_id = await read_collection_id(connection)
        written = await asyncio.to_thread(write_chroma)
        async with self.sql_engine.begin() as connection:
            await write_sql(connection, collection_id, written)

    async def update(
        self,
        collection_name: str,
        ids: IDs,
        embeddings: Embeddings | None = None,
        metadatas: Metadatas | None = None,
        documents: Documents | None = None,
    ) -> None:
        def write_chroma() -> GetResult:
            col = self.chroma_client.get_collection(name=collection_name)
            col.update(
                ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents
            )
            return col.get(ids=ids, include=["documents", "metadatas"])

        async def write_sql(connection: AsyncConnection, current: GetResult) -> None:
            collection_id = (
                select(orm.Collection.id)
                .where(orm.Collection.name == collection_name)
                .scalar_subquery()
            )
            statement = (
                update(orm.Document)
                .where(
                    orm.Document.collection_id == collection_id,
                    orm.Document.chroma_id == bindparam("key"),
                )
                .values(document=bindparam("text"), meta=bindparam("fields"))
            )
            current_documents = current["documents"]
            current_metadatas = current["metadatas"]
            if current_documents is None or current_metadatas is None:
                raise ToolError("Chroma result lacks documents or metadatas")
            rows = [
                {"key": chroma_id, "text": document, "fields": metadata}
                for chroma_id, document, metadata in zip(
                    current["ids"],
                    current_documents,
                    current_metadatas,
                    strict=True,
                )
            ]
            await connection.execute(statement, rows)

        current = await asyncio.to_thread(write_chroma)
        async with self.sql_engine.begin() as connection:
            await write_sql(connection, current)

    async def delete(self, collection_name: str, ids: IDs) -> None:
        def write_chroma() -> None:
            col = self.chroma_client.get_collection(name=collection_name)
            col.delete(ids=ids)

        async def write_sql(connection: AsyncConnection) -> None:
            collection_id = (
                select(orm.Collection.id)
                .where(orm.Collection.name == collection_name)
                .scalar_subquery()
            )
            await connection.execute(
                delete(orm.Document).where(
                    orm.Document.collection_id == collection_id,
                    orm.Document.chroma_id.in_(ids),
                )
            )

        await asyncio.to_thread(write_chroma)
        async with self.sql_engine.begin() as connection:
            await write_sql(connection)

    async def sync(self) -> None:
        def read_chroma() -> list[tuple[str, GetResult]]:
            return [
                (col.name, col.get(include=["documents", "metadatas"]))
                for col in self.chroma_client.list_collections()
            ]

        async def write_sql(
            connection: AsyncConnection, snapshot: list[tuple[str, GetResult]]
        ) -> None:
            await connection.execute(delete(orm.Document))
            await connection.execute(delete(orm.Collection))
            for name, rows in snapshot:
                collection_id = await connection.scalar(
                    insert(orm.Collection)
                    .values(name=name)
                    .returning(orm.Collection.id)
                )
                documents = rows["documents"]
                metadatas = rows["metadatas"]
                if documents is None or metadatas is None:
                    raise ToolError("Chroma result lacks documents or metadatas")
                document_rows = [
                    {
                        "collection_id": collection_id,
                        "chroma_id": chroma_id,
                        "document": document,
                        "metadata": metadata,
                    }
                    for chroma_id, document, metadata in zip(
                        rows["ids"], documents, metadatas, strict=True
                    )
                ]
                if document_rows:
                    await connection.execute(insert(orm.Document), document_rows)

        snapshot = await asyncio.to_thread(read_chroma)
        async with self.sql_engine.begin() as connection:
            await write_sql(connection, snapshot)

    async def query(
        self,
        collection_name: str,
        query_texts: Documents,
        n_results: int = 10,
        where: Where | None = None,
        where_document: WhereDocument | None = None,
        include: Include | None = None,
    ) -> QueryResult:
        included: Include = include or ["metadatas", "documents", "distances"]

        def query_chroma() -> QueryResult:
            return self.chroma_client.get_collection(name=collection_name).query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=included,
            )

        async def query_sql() -> list[list[KeywordHit]]:
            expressions = [
                (index, expression)
                for index, phrase in enumerate(query_texts)
                if (expression := match_expression(phrase)) is not None
            ]
            async with self.sql_engine.connect() as connection:
                collection_id = await connection.scalar(
                    collection_id_select(collection_name)
                )
                if collection_id is None:
                    raise ToolError(f"Collection {collection_name!r} is not indexed")
                if not expressions:
                    return group_by_phrase([], len(query_texts))
                result = await connection.execute(
                    keyword_search_select(
                        collection_id, expressions, n_results, where, where_document
                    )
                )
                return group_by_phrase(result.tuples().all(), len(query_texts))

        vector, keyword = await asyncio.gather(
            asyncio.to_thread(query_chroma), query_sql()
        )
        fused = [
            fuse(
                vector_ids,
                [hit.chroma_id for hit in hits],
                self.vector_weight,
                self.keyword_weight,
                self.rrf_rank_offset,
            )[:n_results]
            for vector_ids, hits in zip(vector["ids"], keyword, strict=True)
        ]
        return assemble_query_result(vector, keyword, fused, included)

    async def peek(self, collection_name: str, limit: int = 10) -> GetResult:
        def fn() -> GetResult:
            return self.chroma_client.get_collection(name=collection_name).peek(
                limit=limit
            )

        return await asyncio.to_thread(fn)

    async def count(self, collection_name: str) -> int:
        def fn() -> int:
            return self.chroma_client.get_collection(name=collection_name).count()

        return await asyncio.to_thread(fn)

    async def get(
        self,
        collection_name: str,
        ids: IDs | None = None,
        where: Where | None = None,
        limit: int | None = None,
        offset: int | None = None,
        where_document: WhereDocument | None = None,
        include: Include | None = None,
    ) -> GetResult:
        def fn() -> GetResult:
            return self.chroma_client.get_collection(name=collection_name).get(
                ids=ids,
                where=where,
                limit=limit,
                offset=offset,
                where_document=where_document,
                include=include or ["metadatas", "documents"],
            )

        return await asyncio.to_thread(fn)
