from collections.abc import Mapping, Sequence
from pathlib import Path

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import async_sessionmaker

from analyze_repo import pipeline, queries, summarize
from analyze_repo.db import create_index_engine, run_migrations
from analyze_repo.indexer import PythonIndexer
from analyze_repo.orm import Language
from analyze_repo.pipeline import IndexerRegistration
from analyze_repo.queries import ReferenceInfo, SnapshotInfo, SymbolInfo, SymbolScope
from analyze_repo.settings import Settings, get_settings

__all__ = [
    "build_server",
    "indexer_registry",
    "main",
]


def indexer_registry() -> Mapping[str, IndexerRegistration]:
    """Every suffix the server can index, each naming exactly one indexer."""
    return {
        ".py": IndexerRegistration(language=Language.python, build=PythonIndexer),
    }


def build_server(settings: Settings) -> FastMCP:
    server = FastMCP("analyze-repo")
    new_session = async_sessionmaker(create_index_engine(settings))
    registry = indexer_registry()

    @server.tool
    async def index_repository(
        repo_root: str, toolchains: dict[Language, str]
    ) -> SnapshotInfo:
        """Index a repository's working tree, keyed by a digest of its file contents.

        `toolchains` maps each language to index onto the path of its toolchain;
        for python that is the interpreter of the repository's own environment,
        so imports resolve against its installed packages.
        """
        indexers = pipeline.build_indexers(
            registry, {language: Path(path) for language, path in toolchains.items()}
        )
        async with new_session.begin() as session:
            snapshot = await pipeline.index_working_tree(
                session, Path(repo_root), indexers
            )
            return await queries.snapshot_info(session, snapshot)

    @server.tool
    async def summarize_repository(snapshot_id: int) -> int:
        """Write a model-generated summary for every class, function and method
        in the snapshot that lacks one; returns how many were written."""
        async with new_session.begin() as session:
            snapshot = await queries.get_snapshot(session, snapshot_id)
            repo_root = Path((await snapshot.awaitable_attrs.repo).location)
            return await summarize.summarize_snapshot(
                session,
                snapshot,
                repo_root,
                settings.summary_model,
                settings.summary_concurrency,
            )

    @server.tool
    async def search_symbols(
        snapshot_id: int, name_fragment: str, scope: SymbolScope
    ) -> Sequence[SymbolInfo]:
        """Symbols whose dotted qualified name contains the fragment.

        `module_and_class` scope returns definitions and class members;
        `all` adds parameters and locals.
        """
        async with new_session() as session:
            snapshot = await queries.get_snapshot(session, snapshot_id)
            return await queries.search_symbols(session, snapshot, name_fragment, scope)

    @server.tool
    async def list_references(symbol_id: int) -> Sequence[ReferenceInfo]:
        """Every place the symbol is referenced, with its syntactic role."""
        async with new_session() as session:
            symbol = await queries.get_symbol(session, symbol_id)
            return await queries.list_references(session, symbol)

    @server.tool
    async def list_callers(symbol_id: int) -> Sequence[SymbolInfo]:
        """Symbols whose body calls this symbol."""
        async with new_session() as session:
            symbol = await queries.get_symbol(session, symbol_id)
            return await queries.list_callers(session, symbol)

    @server.tool
    async def list_callees(symbol_id: int) -> Sequence[SymbolInfo]:
        """Symbols this symbol's body calls."""
        async with new_session() as session:
            symbol = await queries.get_symbol(session, symbol_id)
            return await queries.list_callees(session, symbol)

    return server


def main() -> None:
    settings = get_settings()
    run_migrations(settings.db_path)
    build_server(settings).run(transport="stdio")
