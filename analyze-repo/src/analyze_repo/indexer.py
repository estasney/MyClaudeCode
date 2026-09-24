import hashlib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from analyze_repo import orm
from analyze_repo.lsp import models as lsp
from analyze_repo.lsp.basedpyright import start_basedpyright
from analyze_repo.lsp.protocol import LanguageServer
from analyze_repo.syntax import PythonSyntaxTree, SyntaxContext

__all__ = [
    "IndexedOccurrence",
    "IndexedSymbol",
    "PythonIndexer",
    "RepoIndex",
    "collect_symbols",
    "find_enclosing_symbol",
    "persist_index",
]


@dataclass(frozen=True)
class IndexedSymbol:
    """A definition found by the language server, before it becomes a row."""

    path: Path
    parent: "IndexedSymbol | None"
    qualified_name: str
    name: str
    kind: orm.SymbolKind
    range: lsp.Range
    selection_start: lsp.Position
    body_hash: str


@dataclass(frozen=True)
class IndexedOccurrence:
    """One place that refers to `symbol`, with its syntactic role."""

    symbol: IndexedSymbol
    path: Path
    enclosing: IndexedSymbol | None
    position: lsp.Position
    context: SyntaxContext


@dataclass(frozen=True)
class RepoIndex:
    language: orm.Language
    paths: Sequence[Path]
    symbols: Sequence[IndexedSymbol]
    occurrences: Sequence[IndexedOccurrence]


def to_symbol_kind(kind: lsp.SymbolKind) -> orm.SymbolKind | None:
    """Kinds with no row of their own (modules, type parameters) map to None."""
    match kind:
        case lsp.SymbolKind.class_:
            return orm.SymbolKind.class_
        case lsp.SymbolKind.function:
            return orm.SymbolKind.function
        case lsp.SymbolKind.method:
            return orm.SymbolKind.method
        case lsp.SymbolKind.variable:
            return orm.SymbolKind.variable
        case lsp.SymbolKind.constant:
            return orm.SymbolKind.constant
        case _:
            return None


def hash_lines(lines: Sequence[bytes], range: lsp.Range) -> str:
    return hashlib.sha256(
        b"\n".join(lines[range.start.line : range.end.line + 1])
    ).hexdigest()


def collect_symbols(
    path: Path,
    document_symbols: Iterable[lsp.DocumentSymbol],
    lines: Sequence[bytes],
    parent: IndexedSymbol | None,
) -> Iterator[IndexedSymbol]:
    """Walks the symbol tree depth first; each symbol records its enclosing one."""
    prefix = "" if parent is None else f"{parent.qualified_name}."
    for document_symbol in document_symbols:
        kind = to_symbol_kind(document_symbol.kind)
        if kind is None:
            continue
        symbol = IndexedSymbol(
            path=path,
            parent=parent,
            qualified_name=f"{prefix}{document_symbol.name}",
            name=document_symbol.name,
            kind=kind,
            range=document_symbol.range,
            selection_start=document_symbol.selection_range.start,
            body_hash=hash_lines(lines, document_symbol.range),
        )
        yield symbol
        yield from collect_symbols(path, document_symbol.children, lines, symbol)


def contains(range: lsp.Range, position: lsp.Position) -> bool:
    start = (range.start.line, range.start.character)
    end = (range.end.line, range.end.character)
    return start <= (position.line, position.character) < end


def find_enclosing_symbol(
    symbols: Iterable[IndexedSymbol], position: lsp.Position
) -> IndexedSymbol | None:
    """Symbol ranges nest, so the innermost container starts last."""
    containing = [symbol for symbol in symbols if contains(symbol.range, position)]
    if not containing:
        return None
    return max(
        containing,
        key=lambda symbol: (symbol.range.start.line, symbol.range.start.character),
    )


def collect_occurrences(
    symbol: IndexedSymbol,
    locations: Iterable[lsp.Location],
    symbols_by_path: Mapping[Path, Sequence[IndexedSymbol]],
    trees: Mapping[Path, PythonSyntaxTree],
) -> Iterator[IndexedOccurrence]:
    """Locations outside the indexed files have no row to attach to and are dropped."""
    for location in locations:
        tree = trees.get(location.absolute_path)
        if tree is None:
            continue
        position = location.range.start
        yield IndexedOccurrence(
            symbol=symbol,
            path=location.absolute_path,
            enclosing=find_enclosing_symbol(
                symbols_by_path[location.absolute_path], position
            ),
            position=position,
            context=tree.context_at(position),
        )


def index_repo(server: LanguageServer, absolute_paths: Sequence[Path]) -> RepoIndex:
    """Blocking: every call on `server` waits for the language server's reply."""
    sources = {path: path.read_bytes() for path in absolute_paths}
    trees = {path: PythonSyntaxTree(source) for path, source in sources.items()}
    symbols_by_path = {
        path: list(
            collect_symbols(path, server.get_document_symbols(path), tree.lines, None)
        )
        for path, tree in trees.items()
    }
    symbols = [symbol for group in symbols_by_path.values() for symbol in group]
    occurrences = [
        occurrence
        for symbol in symbols
        for occurrence in collect_occurrences(
            symbol,
            server.find_references(symbol.path, symbol.selection_start),
            symbols_by_path,
            trees,
        )
    ]
    return RepoIndex(
        language=orm.Language.python,
        paths=absolute_paths,
        symbols=symbols,
        occurrences=occurrences,
    )


@dataclass(frozen=True)
class PythonIndexer:
    """basedpyright over LSP, resolving imports through the repository's interpreter."""

    python_path: Path

    @property
    def language(self) -> orm.Language:
        return orm.Language.python

    def index(self, root: Path, files: Sequence[Path]) -> RepoIndex:
        with start_basedpyright(root, self.python_path, files) as server:
            return index_repo(server, files)


async def persist_index(
    session: AsyncSession, snapshot: orm.Snapshot, repo_root: Path, index: RepoIndex
) -> None:
    files = {
        path: orm.File(
            snapshot=snapshot,
            path=path.relative_to(repo_root).as_posix(),
            language=index.language,
        )
        for path in index.paths
    }
    rows: dict[IndexedSymbol, orm.Symbol] = {}
    for symbol in index.symbols:
        rows[symbol] = orm.Symbol(
            file=files[symbol.path],
            parent=None if symbol.parent is None else rows[symbol.parent],
            qualified_name=symbol.qualified_name,
            name=symbol.name,
            kind=symbol.kind,
            start_line=symbol.range.start.line,
            end_line=symbol.range.end.line,
            body_hash=symbol.body_hash,
        )
    session.add_all(files.values())
    session.add_all(rows.values())
    session.add_all(
        orm.Occurrence(
            file=files[occurrence.path],
            symbol=rows[occurrence.symbol],
            enclosing_symbol=(
                None if occurrence.enclosing is None else rows[occurrence.enclosing]
            ),
            line=occurrence.position.line,
            column=occurrence.position.character,
            node_kind=occurrence.context.node_kind,
            parent_kind=occurrence.context.parent_kind,
            parent_field=occurrence.context.parent_field,
        )
        for occurrence in index.occurrences
    )
    await session.flush()
