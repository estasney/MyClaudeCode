from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from analyze_repo import orm, queries
from analyze_repo.db import apply_sqlite_pragmas, run_migrations
from analyze_repo.indexer import (
    IndexedOccurrence,
    IndexedSymbol,
    RepoIndex,
    persist_index,
)
from analyze_repo.lsp import models as lsp
from analyze_repo.syntax import SyntaxContext


@pytest_asyncio.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    db_path = tmp_path / "index.sqlite"
    run_migrations(db_path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    apply_sqlite_pragmas(engine.sync_engine)
    async with async_sessionmaker(engine)() as session:
        yield session
    await engine.dispose()


def indexed_symbol(
    path: Path,
    parent: IndexedSymbol | None,
    qualified_name: str,
    kind: orm.SymbolKind,
    start_line: int,
    end_line: int,
) -> IndexedSymbol:
    return IndexedSymbol(
        path=path,
        parent=parent,
        qualified_name=qualified_name,
        name=qualified_name.rsplit(".", 1)[-1],
        kind=kind,
        range=lsp.Range(
            start=lsp.Position(line=start_line, character=0),
            end=lsp.Position(line=end_line, character=0),
        ),
        selection_start=lsp.Position(line=start_line, character=4),
        body_hash=qualified_name,
    )


@pytest.mark.parametrize(
    ("context", "expected_callers", "expected_callees"),
    [
        (SyntaxContext("identifier", "call", "function"), ["caller"], ["callee"]),
        (SyntaxContext("identifier", "argument_list", None), [], []),
        (SyntaxContext("identifier", "attribute", "object"), [], []),
    ],
    ids=["call site", "passed as argument", "attribute base"],
)
@pytest.mark.asyncio
async def test_call_edges_derive_from_occurrence_role(
    session: AsyncSession,
    context: SyntaxContext,
    expected_callers: list[str],
    expected_callees: list[str],
) -> None:
    """Arrange: two functions where the first's body references the second once.
    Act: persist the index and ask for callers of the second and callees of the first.
    Assert: only a call-site role yields the edge."""
    repo_root = Path("/repo")
    path = repo_root / "m.py"
    caller = indexed_symbol(path, None, "caller", orm.SymbolKind.function, 0, 3)
    callee = indexed_symbol(path, None, "callee", orm.SymbolKind.function, 4, 6)
    occurrence = IndexedOccurrence(
        symbol=callee,
        path=path,
        enclosing=caller,
        position=lsp.Position(line=1, character=4),
        context=context,
    )
    snapshot = orm.Snapshot(
        repo=orm.Repo(name="r", location=str(repo_root)), digest="d"
    )
    session.add(snapshot)
    await persist_index(
        session,
        snapshot,
        repo_root,
        RepoIndex(
            language=orm.Language.python,
            paths=[path],
            symbols=[caller, callee],
            occurrences=[occurrence],
        ),
    )
    rows = {
        row.qualified_name: row
        for row in await queries.search_symbols(
            session, snapshot, "", queries.SymbolScope.all
        )
    }
    callers = await queries.list_callers(
        session, await queries.get_symbol(session, rows["callee"].symbol_id)
    )
    callees = await queries.list_callees(
        session, await queries.get_symbol(session, rows["caller"].symbol_id)
    )
    assert [c.qualified_name for c in callers] == expected_callers, (
        f"role {context} should give callers {expected_callers}, got {callers}"
    )
    assert [c.qualified_name for c in callees] == expected_callees, (
        f"role {context} should give callees {expected_callees}, got {callees}"
    )


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (
            queries.SymbolScope.module_and_class,
            ["Client", "Client.timeout", "Client.connect"],
        ),
        (
            queries.SymbolScope.all,
            ["Client", "Client.timeout", "Client.connect", "Client.connect.host"],
        ),
    ],
    ids=["module and class members", "everything"],
)
@pytest.mark.asyncio
async def test_search_symbols_scope(
    session: AsyncSession, scope: queries.SymbolScope, expected: list[str]
) -> None:
    """Arrange: a class with an attribute and a method that has a parameter.
    Act: search with an empty fragment under each scope.
    Assert: the parameter appears only under the all scope."""
    repo_root = Path("/repo")
    path = repo_root / "m.py"
    client = indexed_symbol(path, None, "Client", orm.SymbolKind.class_, 0, 6)
    timeout = indexed_symbol(
        path, client, "Client.timeout", orm.SymbolKind.variable, 1, 1
    )
    connect = indexed_symbol(
        path, client, "Client.connect", orm.SymbolKind.method, 2, 6
    )
    host = indexed_symbol(
        path, connect, "Client.connect.host", orm.SymbolKind.variable, 2, 2
    )
    snapshot = orm.Snapshot(
        repo=orm.Repo(name="r", location=str(repo_root)), digest="d"
    )
    session.add(snapshot)
    await persist_index(
        session,
        snapshot,
        repo_root,
        RepoIndex(
            language=orm.Language.python,
            paths=[path],
            symbols=[client, timeout, connect, host],
            occurrences=[],
        ),
    )
    found = await queries.search_symbols(session, snapshot, "", scope)
    names = [row.qualified_name for row in found]
    assert names == expected, f"scope {scope} should list {expected}, got {names}"
