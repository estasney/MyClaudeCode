import asyncio
import hashlib
import re
from collections.abc import Mapping, Sequence
from itertools import batched
from pathlib import Path
from typing import assert_never

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from analyze_repo import orm
from analyze_repo.queries.symbols import symbols_with_summaries
from analyze_repo.semantic.embedding import Embedder
from analyze_repo.semantic.summarize import body_text


def split_words(text: str) -> list[str]:
    """Lowercase words with snake case and camel case identifiers broken apart."""
    return [
        word.lower() for word in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", text)
    ]


def document_text(symbol: orm.Symbol, details: Sequence[str]) -> str:
    """Identifier words lead so keyword and embedding search both see them."""
    lines = [
        " ".join(split_words(symbol.qualified_name)),
        f"{symbol.kind.value} {symbol.qualified_name} in {symbol.file.path}",
        *(f"decorated with {decorator.expression}" for decorator in symbol.decorators),
        *details,
    ]
    return "\n".join(lines)


def document_details(
    repo_root: Path, symbol: orm.Symbol, summary: orm.Summary | None
) -> list[str]:
    """Definitions are described by their signature and summary and values by their source."""
    match symbol.kind:
        case orm.SymbolKind.class_ | orm.SymbolKind.function | orm.SymbolKind.method:
            details = [] if symbol.signature is None else [symbol.signature]
            return details if summary is None else [*details, summary.text]
        case (
            orm.SymbolKind.parameter | orm.SymbolKind.variable | orm.SymbolKind.constant
        ):
            return [body_text(repo_root, symbol)]
        case _:
            assert_never(symbol.kind)


async def write_documents(
    session: AsyncSession, snapshot: orm.Snapshot, repo_root: Path
) -> None:
    """Replaces the snapshot's search documents."""
    parent = aliased(orm.Symbol)
    searchable = (
        symbols_with_summaries()
        .outerjoin(parent, orm.Symbol.parent.of_type(parent))
        .where(orm.File.snapshot_id == snapshot.id)
        .where(
            orm.Symbol.kind.not_in((orm.SymbolKind.variable, orm.SymbolKind.constant))
            | parent.id.is_(None)
            | (parent.kind == orm.SymbolKind.class_)
        )
    )
    documents: list[orm.SearchDocument] = []
    for symbol, summary in await session.execute(searchable):
        text = document_text(symbol, document_details(repo_root, symbol, summary))
        documents.append(
            orm.SearchDocument(
                symbol=symbol,
                text=text,
                text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
    snapshot_symbols = (
        select(orm.Symbol.id).join(orm.File).where(orm.File.snapshot_id == snapshot.id)
    )
    await session.execute(
        delete(orm.SearchDocument).where(
            orm.SearchDocument.symbol_id.in_(snapshot_symbols)
        )
    )
    session.add_all(documents)
    await session.flush()


async def texts_missing_vectors(
    session: AsyncSession, snapshot: orm.Snapshot, model: str
) -> dict[str, str]:
    """Search document texts of the snapshot that model has not embedded keyed by text hash."""
    unembedded = (
        select(orm.SearchDocument.text_hash, orm.SearchDocument.text)
        .join(orm.Symbol, orm.SearchDocument.symbol)
        .join(orm.File)
        .outerjoin(
            orm.Embedding,
            (orm.Embedding.text_hash == orm.SearchDocument.text_hash)
            & (orm.Embedding.model == model),
        )
        .where(orm.File.snapshot_id == snapshot.id)
        .where(orm.Embedding.text_hash.is_(None))
        .distinct()
    )
    return dict((await session.execute(unembedded)).tuples().all())


async def embed_texts(
    new_session: async_sessionmaker[AsyncSession],
    texts_by_hash: Mapping[str, str],
    embedder: Embedder,
    batch_size: int,
) -> int:
    """Commits the vectors of each batch as it is embedded so an interrupted run keeps them."""
    for batch in batched(texts_by_hash.items(), batch_size):
        vectors = await asyncio.to_thread(
            embedder.embed_documents, [text for _, text in batch]
        )
        async with new_session.begin() as session:
            session.add_all(
                orm.Embedding(
                    text_hash=text_hash, model=embedder.model, vector=vector.tobytes()
                )
                for (text_hash, _), vector in zip(batch, vectors, strict=True)
            )
    return len(texts_by_hash)


__all__ = [
    "document_text",
    "embed_texts",
    "split_words",
    "texts_missing_vectors",
    "write_documents",
]
