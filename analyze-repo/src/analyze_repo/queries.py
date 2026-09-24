from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from analyze_repo import orm

__all__ = [
    "ReferenceInfo",
    "SnapshotInfo",
    "SymbolInfo",
    "SymbolScope",
    "get_snapshot",
    "get_symbol",
    "list_callees",
    "list_callers",
    "list_references",
    "search_symbols",
    "snapshot_info",
]


class SnapshotInfo(BaseModel):
    snapshot_id: int
    repo: str
    digest: str
    files: int
    symbols: int
    occurrences: int


class SymbolInfo(BaseModel):
    symbol_id: int
    qualified_name: str
    kind: orm.SymbolKind
    path: str
    start_line: int
    end_line: int
    summary: str | None


class ReferenceInfo(BaseModel):
    path: str
    line: int
    column: int
    node_kind: str
    parent_kind: str
    parent_field: str | None
    enclosing_symbol: str | None


class UnknownSnapshotError(LookupError):
    def __init__(self, snapshot_id: int) -> None:
        super().__init__(f"no snapshot with id {snapshot_id}")


class UnknownSymbolError(LookupError):
    def __init__(self, symbol_id: int) -> None:
        super().__init__(f"no symbol with id {symbol_id}")


def symbol_info(symbol: orm.Symbol, summary: orm.Summary | None) -> SymbolInfo:
    return SymbolInfo(
        symbol_id=symbol.id,
        qualified_name=symbol.qualified_name,
        kind=symbol.kind,
        path=symbol.file.path,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        summary=None if summary is None else summary.text,
    )


def symbols_with_summaries() -> Select[tuple[orm.Symbol, orm.Summary]]:
    """Pairs each symbol with its summary; the outer join yields None when absent,
    which SQLAlchemy's typing does not express."""
    return (
        select(orm.Symbol, orm.Summary)
        .join(orm.File)
        .outerjoin(orm.Summary, orm.Summary.body_hash == orm.Symbol.body_hash)
        .options(selectinload(orm.Symbol.file))
    )


def is_call_site() -> ColumnElement[bool]:
    return (orm.Occurrence.parent_kind == "call") & (
        orm.Occurrence.parent_field == "function"
    )


async def get_snapshot(session: AsyncSession, snapshot_id: int) -> orm.Snapshot:
    snapshot = await session.get(orm.Snapshot, snapshot_id)
    if snapshot is None:
        raise UnknownSnapshotError(snapshot_id)
    return snapshot


async def get_symbol(session: AsyncSession, symbol_id: int) -> orm.Symbol:
    symbol = await session.get(orm.Symbol, symbol_id)
    if symbol is None:
        raise UnknownSymbolError(symbol_id)
    return symbol


async def count_rows(session: AsyncSession, statement: Select[tuple[int]]) -> int:
    count = await session.scalar(select(func.count()).select_from(statement.subquery()))
    return count or 0


async def snapshot_info(session: AsyncSession, snapshot: orm.Snapshot) -> SnapshotInfo:
    files = select(orm.File.id).where(orm.File.snapshot_id == snapshot.id)
    symbols = select(orm.Symbol.id).where(orm.Symbol.file_id.in_(files))
    occurrences = select(orm.Occurrence.id).where(orm.Occurrence.file_id.in_(files))
    return SnapshotInfo(
        snapshot_id=snapshot.id,
        repo=(await snapshot.awaitable_attrs.repo).name,
        digest=snapshot.digest,
        files=await count_rows(session, files),
        symbols=await count_rows(session, symbols),
        occurrences=await count_rows(session, occurrences),
    )


class SymbolScope(StrEnum):
    """Which nesting levels a symbol search covers."""

    module_and_class = "module_and_class"
    all = "all"


async def search_symbols(
    session: AsyncSession,
    snapshot: orm.Snapshot,
    name_fragment: str,
    scope: SymbolScope,
) -> Sequence[SymbolInfo]:
    """Parameters and locals have a function or method as parent, which
    `module_and_class` leaves out."""
    parent = aliased(orm.Symbol)
    statement = (
        symbols_with_summaries()
        .outerjoin(parent, orm.Symbol.parent.of_type(parent))
        .where(orm.File.snapshot_id == snapshot.id)
        .where(orm.Symbol.qualified_name.contains(name_fragment))
        .order_by(orm.File.path, orm.Symbol.start_line)
    )
    if scope is SymbolScope.module_and_class:
        statement = statement.where(
            (parent.id.is_(None)) | (parent.kind == orm.SymbolKind.class_)
        )
    return [
        symbol_info(symbol, summary)
        for symbol, summary in await session.execute(statement)
    ]


async def list_references(
    session: AsyncSession, symbol: orm.Symbol
) -> Sequence[ReferenceInfo]:
    enclosing = aliased(orm.Symbol)
    statement = (
        select(orm.Occurrence, orm.File.path, enclosing.qualified_name)
        .join(orm.File, orm.Occurrence.file)
        .outerjoin(enclosing, orm.Occurrence.enclosing_symbol)
        .where(orm.Occurrence.symbol_id == symbol.id)
        .order_by(orm.File.path, orm.Occurrence.line, orm.Occurrence.column)
    )
    return [
        ReferenceInfo(
            path=path,
            line=occurrence.line,
            column=occurrence.column,
            node_kind=occurrence.node_kind,
            parent_kind=occurrence.parent_kind,
            parent_field=occurrence.parent_field,
            enclosing_symbol=enclosing_name,
        )
        for occurrence, path, enclosing_name in await session.execute(statement)
    ]


async def list_callers(
    session: AsyncSession, symbol: orm.Symbol
) -> Sequence[SymbolInfo]:
    """Symbols whose body contains a call to `symbol`."""
    call_sites = (
        select(orm.Occurrence.enclosing_symbol_id)
        .where(orm.Occurrence.symbol_id == symbol.id)
        .where(is_call_site())
    )
    statement = symbols_with_summaries().where(orm.Symbol.id.in_(call_sites))
    return [
        symbol_info(caller, summary)
        for caller, summary in await session.execute(statement)
    ]


async def list_callees(
    session: AsyncSession, symbol: orm.Symbol
) -> Sequence[SymbolInfo]:
    """Symbols that `symbol`'s body calls."""
    called = (
        select(orm.Occurrence.symbol_id)
        .where(orm.Occurrence.enclosing_symbol_id == symbol.id)
        .where(is_call_site())
    )
    statement = symbols_with_summaries().where(orm.Symbol.id.in_(called))
    return [
        symbol_info(callee, summary)
        for callee, summary in await session.execute(statement)
    ]
