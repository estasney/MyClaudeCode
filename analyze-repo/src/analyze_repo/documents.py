import asyncio
import hashlib
import re
from pathlib import Path
from typing import assert_never

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from analyze_repo import orm
from analyze_repo.embedding import Embedder
from analyze_repo.queries import symbols_with_summaries
from analyze_repo.summarize import body_text


def split_words(text: str) -> list[str]:
    """Lowercase words with snake case and camel case identifiers broken apart."""
    return [
        word.lower() for word in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", text)
    ]


def document_text(symbol: orm.Symbol, detail: str | None) -> str:
    """Identifier words lead so keyword and embedding search both see them."""
    lines = [
        " ".join(split_words(symbol.qualified_name)),
        f"{symbol.kind.value} {symbol.qualified_name} in {symbol.file.path}",
        *(f"decorated with {decorator.expression}" for decorator in symbol.decorators),
    ]
    if detail is not None:
        lines.append(detail)
    return "\n".join(lines)


def document_detail(
    repo_root: Path, symbol: orm.Symbol, summary: orm.Summary | None
) -> str | None:
    """Definitions are described by their summary and values by their source."""
    match symbol.kind:
        case orm.SymbolKind.class_ | orm.SymbolKind.function | orm.SymbolKind.method:
            return None if summary is None else summary.text
        case (
            orm.SymbolKind.parameter | orm.SymbolKind.variable | orm.SymbolKind.constant
        ):
            return body_text(repo_root, symbol)
        case _:
            assert_never(symbol.kind)


async def embed_snapshot(
    session: AsyncSession, snapshot: orm.Snapshot, repo_root: Path, embedder: Embedder
) -> int:
    """Rewrites the snapshot's search documents and returns how many vectors were written."""
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
        text = document_text(symbol, document_detail(repo_root, symbol, summary))
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
    unembedded = (
        select(orm.SearchDocument.text_hash, orm.SearchDocument.text)
        .join(orm.Symbol, orm.SearchDocument.symbol)
        .join(orm.File)
        .outerjoin(
            orm.Embedding,
            (orm.Embedding.text_hash == orm.SearchDocument.text_hash)
            & (orm.Embedding.model == embedder.model),
        )
        .where(orm.File.snapshot_id == snapshot.id)
        .where(orm.Embedding.text_hash.is_(None))
        .distinct()
    )
    missing = dict((await session.execute(unembedded)).tuples().all())
    if not missing:
        return 0
    vectors = await asyncio.to_thread(embedder.embed_documents, list(missing.values()))
    session.add_all(
        orm.Embedding(
            text_hash=text_hash, model=embedder.model, vector=vector.tobytes()
        )
        for text_hash, vector in zip(missing, vectors, strict=True)
    )
    await session.flush()
    return len(missing)


__all__ = [
    "document_text",
    "embed_snapshot",
    "split_words",
]
