from collections.abc import Sequence
from pathlib import Path
from typing import assert_never

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import (
    ElicitRequest,
    ElicitRequestedSchema,
    ElicitRequestFormParams,
    ElicitResult,
    InputRequiredResult,
)
from mcp.types.version import MODERN_PROTOCOL_VERSIONS

from analyze_repo.analyzer import RepoAnalyzer, indexer_registry
from analyze_repo.indexing.toolchain import AmbiguousInterpreterError
from analyze_repo.models import (
    AnalysisReport,
    AnalysisStatus,
    ReferenceInfo,
    SearchHit,
    SymbolInfo,
    SymbolScope,
)
from analyze_repo.orm import Language
from analyze_repo.orm.engine import run_migrations
from analyze_repo.queries.search import NotEmbeddedError
from analyze_repo.queries.symbols import UnknownSnapshotError, UnknownSymbolError
from analyze_repo.semantic.embedding import SentenceTransformerEmbedder
from analyze_repo.semantic.summarize import ClaudeSummarizer, SummariesFailedError
from analyze_repo.settings import get_settings


def describe_next_step(status: AnalysisStatus | None) -> str:
    """Free work comes before paid work."""
    match status:
        case None:
            return (
                "Call index_repository to index the working tree and embed its "
                "search documents. It is free."
            )
        case AnalysisStatus(missing_vectors=missing) if missing > 0:
            return (
                f"Call index_repository again to embed the {missing} search "
                "documents without a vector. It is free."
            )
        case AnalysisStatus(missing_summaries=missing) if missing > 0:
            return (
                "search_code, search_symbols and the list tools are ready. Call "
                f"summarize_repository to describe the {missing} bodies without a "
                "summary so search_code matches what code does and not only its "
                "names. It is paid at one model call per body and asks the user "
                "to approve the cost first."
            )
        case AnalysisStatus():
            return (
                "Analysis is complete. search_code, search_symbols and the list "
                "tools are ready."
            )
        case _:
            assert_never(status)


async def request_approval(ctx: Context, message: str) -> bool | InputRequiredResult:
    """True when the user accepts or the client cannot ask. On the 2026-07-28
    protocol the question is a returned request the client answers on its next call."""
    capabilities = ctx.session.client_capabilities
    if capabilities is None or capabilities.elicitation is None:
        return True
    confirmation: ElicitRequestedSchema = {"type": "object", "properties": {}}
    context = ctx.request_context
    if context is None or context.protocol_version not in MODERN_PROTOCOL_VERSIONS:
        answer = await ctx.session.elicit(
            message, confirmation, related_request_id=ctx.request_id
        )
        return answer.action == "accept"
    match ctx.input_responses:
        case None:
            return InputRequiredResult(
                result_type="input_required",
                input_requests={
                    "approval": ElicitRequest(
                        method="elicitation/create",
                        params=ElicitRequestFormParams(
                            message=message, requested_schema=confirmation
                        ),
                    )
                },
            )
        case {"approval": ElicitResult(action=action)}:
            return action == "accept"
        case unexpected:
            raise ValueError(f"expected an answer to the approval, got {unexpected}")


def build_server(analyzer: RepoAnalyzer) -> FastMCP:
    """Each tool calls the analyzer and turns the errors a caller can act on into
    a ToolError that names the tool to call next."""
    server = FastMCP("analyze-repo")

    @server.tool
    async def get_analysis_status(repo_root: str) -> AnalysisReport:
        """Free and read only. Report whether the working tree as it is now has
        been indexed, how many summaries and vectors it still lacks, and the next
        tool to call. The status is null when the tree has no snapshot."""
        status = await analyzer.get_analysis_status(Path(repo_root))
        return AnalysisReport(status=status, next_step=describe_next_step(status))

    @server.tool
    async def index_repository(
        repo_root: str, toolchain_overrides: dict[Language, Path] | None = None
    ) -> AnalysisReport:
        """Free. Index a repository's working tree, keyed by a digest of its file
        contents, and embed its search documents with a local model. The report
        names the next tool to call.

        Each language's toolchain is discovered under the repo root. For python
        that is the one virtual environment directory there. `toolchain_overrides`
        maps a language onto an explicit toolchain path instead.
        """
        try:
            status = await analyzer.index_repository(
                Path(repo_root), toolchain_overrides
            )
        except AmbiguousInterpreterError as error:
            raise ToolError(f"{error} Choose one with toolchain_overrides.") from error
        return AnalysisReport(status=status, next_step=describe_next_step(status))

    @server.tool
    async def summarize_repository(
        snapshot_id: int, ctx: Context
    ) -> AnalysisReport | InputRequiredResult:
        """Paid. Ask the user to approve one model call per class, function and
        method body in the snapshot that lacks a summary, then write the
        summaries and embed the search documents that now include them. Each
        summary is saved as it arrives, so a rerun after an interruption or a
        failure requests only the summaries still missing."""
        try:
            status = await analyzer.get_snapshot_status(snapshot_id)
        except UnknownSnapshotError as error:
            raise ToolError(
                f"{error}. index_repository returns snapshot ids."
            ) from error
        if status.missing_summaries > 0:
            approval = await request_approval(
                ctx,
                f"Summaries missing in {status.snapshot.repo}: "
                f"{status.missing_summaries}. Write them with "
                f"{analyzer.settings.summary_model} at one paid model call each?",
            )
            if isinstance(approval, InputRequiredResult):
                return approval
            if not approval:
                return AnalysisReport(
                    status=status,
                    next_step=(
                        "The user declined the paid summaries. search_code, "
                        "search_symbols and the list tools work without them. Call "
                        "summarize_repository again only when the user asks."
                    ),
                )
        try:
            status = await analyzer.summarize_repository(snapshot_id)
        except SummariesFailedError as error:
            raise ToolError(
                f"{error.message}. Run summarize_repository again to retry the failed ones."
            ) from error
        return AnalysisReport(status=status, next_step=describe_next_step(status))

    @server.tool
    async def search_code(
        snapshot_id: int, question: str, limit: int = 10
    ) -> Sequence[SearchHit]:
        """Symbols relevant to a natural language question, ranked by keyword and
        embedding similarity. A parameter that matches is listed under the function
        that declares it. Entry points are the callers reached from the symbol that
        nothing calls in turn, or the symbol itself when nothing calls it."""
        try:
            return await analyzer.search_code(snapshot_id, question, limit)
        except UnknownSnapshotError as error:
            raise ToolError(
                f"{error}. index_repository returns snapshot ids."
            ) from error
        except NotEmbeddedError as error:
            raise ToolError(
                f"{error}. Run index_repository again to embed them."
            ) from error

    @server.tool
    async def search_symbols(
        snapshot_id: int, name_fragment: str, scope: SymbolScope
    ) -> Sequence[SymbolInfo]:
        """Symbols whose dotted qualified name contains the fragment.

        `module_and_class` scope returns definitions and class members;
        `all` adds parameters and locals.
        """
        try:
            return await analyzer.search_symbols(snapshot_id, name_fragment, scope)
        except UnknownSnapshotError as error:
            raise ToolError(
                f"{error}. index_repository returns snapshot ids."
            ) from error

    @server.tool
    async def list_references(symbol_id: int) -> Sequence[ReferenceInfo]:
        """Every place the symbol is referenced, with its syntactic role."""
        try:
            return await analyzer.list_references(symbol_id)
        except UnknownSymbolError as error:
            raise ToolError(
                f"{error}. search_symbols and search_code return symbol ids."
            ) from error

    @server.tool
    async def list_callers(symbol_id: int) -> Sequence[SymbolInfo]:
        """Symbols whose body calls this symbol."""
        try:
            return await analyzer.list_callers(symbol_id)
        except UnknownSymbolError as error:
            raise ToolError(
                f"{error}. search_symbols and search_code return symbol ids."
            ) from error

    @server.tool
    async def list_callees(symbol_id: int) -> Sequence[SymbolInfo]:
        """Symbols this symbol's body calls."""
        try:
            return await analyzer.list_callees(symbol_id)
        except UnknownSymbolError as error:
            raise ToolError(
                f"{error}. search_symbols and search_code return symbol ids."
            ) from error

    return server


def main() -> None:
    settings = get_settings()
    run_migrations(settings.db_path)
    analyzer = RepoAnalyzer(
        settings,
        SentenceTransformerEmbedder(settings),
        ClaudeSummarizer(settings),
        indexer_registry(),
    )
    build_server(analyzer).run(transport="stdio")


__all__ = [
    "build_server",
    "describe_next_step",
    "main",
    "request_approval",
]
