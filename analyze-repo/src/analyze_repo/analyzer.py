import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from analyze_repo.indexing import pipeline
from analyze_repo.indexing.pipeline import IndexerRegistration
from analyze_repo.indexing.python import PythonIndexer
from analyze_repo.indexing.toolchain import (
    PythonToolchainDiscovery,
    platform_venv_layout,
)
from analyze_repo.models import (
    AnalysisStatus,
    ReferenceInfo,
    SearchHit,
    SymbolInfo,
    SymbolScope,
)
from analyze_repo.orm import Language
from analyze_repo.orm.engine import create_index_engine
from analyze_repo.queries import analysis, search, symbols
from analyze_repo.semantic import documents, summarize
from analyze_repo.semantic.embedding import Embedder
from analyze_repo.semantic.summarize import SummariesFailedError, Summarizer
from analyze_repo.settings import Settings


def indexer_registry() -> Mapping[str, IndexerRegistration]:
    """Every suffix the analyzer can index, each naming exactly one indexer."""
    return {
        ".py": IndexerRegistration(
            language=Language.python,
            discovery=PythonToolchainDiscovery(platform_venv_layout()),
            build_indexer=PythonIndexer,
        ),
    }


class RepoAnalyzer:
    """Each call runs in its own session and a writing call commits when it returns."""

    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        summarizer: Summarizer,
        registry: Mapping[str, IndexerRegistration],
    ) -> None:
        self.settings = settings
        self.embedder = embedder
        self.summarizer = summarizer
        self.registry = registry
        self.new_session = async_sessionmaker(create_index_engine(settings))

    async def index_repository(
        self, repo_root: Path, toolchain_overrides: Mapping[Language, Path] | None
    ) -> AnalysisStatus:
        """Free. Indexes the working tree and embeds its search documents locally."""
        indexers = pipeline.build_indexers(
            self.registry, repo_root, toolchain_overrides
        )
        async with self.new_session.begin() as session:
            snapshot = await pipeline.index_working_tree(session, repo_root, indexers)
            snapshot_id = snapshot.id
        await self.embed_documents(snapshot_id)
        return await self.get_snapshot_status(snapshot_id)

    async def summarize_repository(self, snapshot_id: int) -> AnalysisStatus:
        """Paid. Summarizes the bodies without a summary and embeds the documents
        that now describe them."""
        async with self.new_session() as session:
            snapshot = await symbols.get_snapshot(session, snapshot_id)
            repo_root = Path((await snapshot.awaitable_attrs.repo).location)
            missing = await summarize.symbols_missing_summaries(session, snapshot)
        failures = await summarize.summarize_symbols(
            self.new_session,
            missing,
            repo_root,
            self.summarizer,
            self.settings.summary_concurrency,
        )
        await self.embed_documents(snapshot_id)
        if failures:
            raise SummariesFailedError(
                f"{len(failures)} of {len(missing)} summaries failed and the rest were saved",
                failures,
            )
        return await self.get_snapshot_status(snapshot_id)

    async def embed_documents(self, snapshot_id: int) -> None:
        """Rewrites the search documents and embeds each text without a vector."""
        async with self.new_session.begin() as session:
            snapshot = await symbols.get_snapshot(session, snapshot_id)
            repo_root = Path((await snapshot.awaitable_attrs.repo).location)
            await documents.write_documents(session, snapshot, repo_root)
            missing = await documents.texts_missing_vectors(
                session, snapshot, self.embedder.model
            )
        await documents.embed_texts(
            self.new_session,
            missing,
            self.embedder,
            self.settings.embedding_batch_size,
        )

    async def get_analysis_status(self, repo_root: Path) -> AnalysisStatus | None:
        """None when the working tree as it is now has no snapshot."""
        tree = await asyncio.to_thread(pipeline.describe_working_tree, repo_root)
        async with self.new_session() as session:
            snapshot = await pipeline.find_snapshot(session, tree.root, tree.digest)
            if snapshot is None:
                return None
            return await analysis.get_analysis_status(
                session, snapshot, self.embedder.model
            )

    async def get_snapshot_status(self, snapshot_id: int) -> AnalysisStatus:
        async with self.new_session() as session:
            snapshot = await symbols.get_snapshot(session, snapshot_id)
            return await analysis.get_analysis_status(
                session, snapshot, self.embedder.model
            )

    async def search_code(
        self, snapshot_id: int, question: str, limit: int
    ) -> Sequence[SearchHit]:
        async with self.new_session() as session:
            snapshot = await symbols.get_snapshot(session, snapshot_id)
            return await search.search_code(
                session, snapshot, question, self.embedder, self.settings, limit
            )

    async def search_symbols(
        self, snapshot_id: int, name_fragment: str, scope: SymbolScope
    ) -> Sequence[SymbolInfo]:
        async with self.new_session() as session:
            snapshot = await symbols.get_snapshot(session, snapshot_id)
            return await symbols.search_symbols(session, snapshot, name_fragment, scope)

    async def list_references(self, symbol_id: int) -> Sequence[ReferenceInfo]:
        async with self.new_session() as session:
            symbol = await symbols.get_symbol(session, symbol_id)
            return await symbols.list_references(session, symbol)

    async def list_callers(self, symbol_id: int) -> Sequence[SymbolInfo]:
        async with self.new_session() as session:
            symbol = await symbols.get_symbol(session, symbol_id)
            return await symbols.list_callers(session, symbol)

    async def list_callees(self, symbol_id: int) -> Sequence[SymbolInfo]:
        async with self.new_session() as session:
            symbol = await symbols.get_symbol(session, symbol_id)
            return await symbols.list_callees(session, symbol)


__all__ = [
    "RepoAnalyzer",
    "indexer_registry",
]
