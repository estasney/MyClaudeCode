import sys
import venv
from collections.abc import AsyncIterator
from pathlib import Path
from textwrap import dedent
from typing import Literal

import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.client.elicitation import ElicitRequestParams, ElicitResult
from fastmcp.client.transports import FastMCPTransport

from analyze_repo.analyzer import RepoAnalyzer
from analyze_repo.mcp import build_server
from analyze_repo.models import SymbolScope


@pytest_asyncio.fixture
async def client(analyzer: RepoAnalyzer) -> AsyncIterator[Client[FastMCPTransport]]:
    """The server as `main` builds it, over the in-memory transport."""
    async with Client(build_server(analyzer)) as client:
        yield client


@pytest.mark.parametrize(
    ("working_tree", "callee", "expected_callers"),
    [
        (
            {
                "lib.py": dedent("""\
                    def helper() -> int:
                        return 1
                    """),
                "app.py": dedent("""\
                    from lib import helper


                    def run() -> int:
                        return helper()
                    """),
            },
            "helper",
            ["run"],
        ),
        (
            {
                "lib.py": dedent("""\
                    class Client:
                        def connect(self) -> None:
                            pass
                    """),
                "app.py": dedent("""\
                    from lib import Client


                    def open_client() -> None:
                        Client().connect()
                    """),
            },
            "Client.connect",
            ["open_client"],
        ),
        (
            {
                "lib.py": dedent("""\
                    class Client:
                        def connect(self) -> None:
                            self.open()

                        def open(self) -> None:
                            pass
                    """),
            },
            "Client.open",
            ["Client.connect"],
        ),
        (
            {
                "lib.py": dedent("""\
                    def helper(value: int) -> int:
                        return value
                    """),
                "app.py": dedent("""\
                    from lib import helper


                    def run() -> list[int]:
                        return list(map(helper, [1]))
                    """),
            },
            "helper",
            [],
        ),
    ],
    indirect=["working_tree"],
    ids=[
        "function called from another module",
        "method called through an instance",
        "method called through self",
        "function passed as a callback",
    ],
)
@pytest.mark.asyncio
async def test_list_callers_over_mcp(
    client: Client[FastMCPTransport],
    working_tree: Path,
    callee: str,
    expected_callers: list[str],
) -> None:
    """Arrange: a working tree whose files reference one symbol in a known way.
    Act: index it through the server, look the symbol up by name, and ask who calls it.
    Assert: only bodies that call the symbol are listed as callers."""
    indexed = await client.call_tool(
        "index_repository",
        {
            "repo_root": str(working_tree),
            "toolchain_overrides": {"python": sys.executable},
        },
    )
    found = await client.call_tool(
        "search_symbols",
        {
            "snapshot_id": indexed.data.status.snapshot.snapshot_id,
            "name_fragment": callee,
            "scope": SymbolScope.module_and_class,
        },
    )
    symbol_ids = {row.qualified_name: row.symbol_id for row in found.data}
    callers = await client.call_tool("list_callers", {"symbol_id": symbol_ids[callee]})
    names = [row.qualified_name for row in callers.data]
    assert names == expected_callers, (
        f"callers of {callee} should be {expected_callers}, got {names}"
    )


@pytest.mark.parametrize(
    "working_tree",
    [
        {
            "lib.py": dedent("""\
                def helper() -> int:
                    return 1
                """),
        },
    ],
    indirect=True,
    ids=["one module"],
)
@pytest.mark.asyncio
async def test_index_repository_reuses_the_snapshot_of_an_unchanged_tree(
    client: Client[FastMCPTransport], working_tree: Path
) -> None:
    """Arrange: a working tree.
    Act: index it twice through the server.
    Assert: the second call answers with the first snapshot, not a new one."""
    arguments = {
        "repo_root": str(working_tree),
        "toolchain_overrides": {"python": sys.executable},
    }
    first = await client.call_tool("index_repository", arguments)
    second = await client.call_tool("index_repository", arguments)
    assert second.data == first.data, (
        f"re-indexing an unchanged tree should return {first.data}, got {second.data}"
    )


@pytest.mark.parametrize(
    "working_tree",
    [
        {
            ".gitignore": "env/\n",
            "lib.py": dedent("""\
                def helper() -> int:
                    return 1
                """),
        },
    ],
    indirect=True,
    ids=["one module beside a venv"],
)
@pytest.mark.asyncio
async def test_index_repository_discovers_the_venv_under_the_root(
    client: Client[FastMCPTransport], working_tree: Path
) -> None:
    """Arrange: a working tree holding a real venv under a name of its own.
    Act: index it through the server without a toolchain override.
    Assert: the module's symbol is indexed through the discovered interpreter."""
    venv.EnvBuilder(with_pip=False, symlinks=True).create(working_tree / "env")
    indexed = await client.call_tool(
        "index_repository", {"repo_root": str(working_tree)}
    )
    found = await client.call_tool(
        "search_symbols",
        {
            "snapshot_id": indexed.data.status.snapshot.snapshot_id,
            "name_fragment": "helper",
            "scope": SymbolScope.module_and_class,
        },
    )
    names = [row.qualified_name for row in found.data]
    assert names == ["helper"], f"discovered indexing should find helper, got {names}"


@pytest.mark.parametrize(
    "working_tree",
    [
        {
            "spaces.py": dedent("""\
                def tool(function):
                    return function


                class Client:
                    def create_space(self, name: str, batch_size: int) -> None:
                        pass


                @tool
                def create_space(name: str, batch_size: int = 32) -> None:
                    Client().create_space(name, batch_size)


                def delete_entries(ids: list[str]) -> None:
                    pass
                """),
        },
    ],
    indirect=True,
    ids=["tool over a client method"],
)
@pytest.mark.asyncio
async def test_search_code_answers_with_the_owner_and_its_entry_point(
    client: Client[FastMCPTransport], working_tree: Path
) -> None:
    """Arrange: a decorated tool that forwards its batch size to a client method.
    Act: index the tree then ask how to set the batch size of a space.
    Assert: both functions lead under their batch size parameter and the client
    method is reached from the decorated tool."""
    indexed = await client.call_tool(
        "index_repository",
        {
            "repo_root": str(working_tree),
            "toolchain_overrides": {"python": sys.executable},
        },
    )
    snapshot_id = indexed.data.status.snapshot.snapshot_id
    found = await client.call_tool(
        "search_code",
        {
            "snapshot_id": snapshot_id,
            "question": "How do I set the batch size of a space?",
            "limit": 2,
        },
    )
    hits = {hit.symbol.qualified_name: hit for hit in found.data}
    assert set(hits) == {"create_space", "Client.create_space"}, (
        f"the two batch size owners should lead, got {list(hits)}"
    )
    parameters = [
        parameter.qualified_name
        for parameter in hits["Client.create_space"].matched_parameters
    ]
    assert "Client.create_space.batch_size" in parameters, (
        f"the batch size parameter should match under its method, got {parameters}"
    )
    entry_points = [
        (entry.qualified_name, entry.decorators)
        for entry in hits["Client.create_space"].entry_points
    ]
    assert entry_points == [("create_space", ["tool"])], (
        f"the client method should be reached from the tool, got {entry_points}"
    )


@pytest.mark.parametrize(
    "working_tree",
    [{"lib.py": "def helper() -> int:\n    return 1\n"}],
    indirect=True,
    ids=["one module"],
)
@pytest.mark.asyncio
async def test_index_repository_names_the_paid_summarize_call_next(
    client: Client[FastMCPTransport], working_tree: Path
) -> None:
    """Arrange: a working tree with one function.
    Act: index it through the server.
    Assert: every document is embedded and the report names summarize_repository
    for the one body without a summary."""
    indexed = await client.call_tool(
        "index_repository",
        {
            "repo_root": str(working_tree),
            "toolchain_overrides": {"python": sys.executable},
        },
    )
    status = indexed.data.status
    assert (status.missing_vectors, status.missing_summaries) == (0, 1), (
        f"the free call should embed everything and summarize nothing, got {status}"
    )
    assert "summarize_repository" in indexed.data.next_step, (
        f"the next step should name the paid call, got {indexed.data.next_step}"
    )


@pytest.mark.parametrize(
    "working_tree",
    [{"lib.py": "def helper() -> int:\n    return 1\n"}],
    indirect=True,
    ids=["one module"],
)
@pytest.mark.asyncio
async def test_summarize_repository_reports_the_analysis_complete(
    client: Client[FastMCPTransport], working_tree: Path
) -> None:
    """Arrange: an indexed working tree with one function.
    Act: summarize it through the server.
    Assert: nothing is missing and the report says the analysis is complete."""
    indexed = await client.call_tool(
        "index_repository",
        {
            "repo_root": str(working_tree),
            "toolchain_overrides": {"python": sys.executable},
        },
    )
    summarized = await client.call_tool(
        "summarize_repository",
        {"snapshot_id": indexed.data.status.snapshot.snapshot_id},
    )
    status = summarized.data.status
    assert (status.missing_vectors, status.missing_summaries) == (0, 0), (
        f"the paid call should leave nothing missing, got {status}"
    )
    assert summarized.data.next_step.startswith("Analysis is complete"), (
        f"the next step should report completion, got {summarized.data.next_step}"
    )


@pytest.mark.parametrize(
    "working_tree",
    [{"lib.py": "def helper() -> int:\n    return 1\n"}],
    indirect=True,
    ids=["one module"],
)
@pytest.mark.asyncio
async def test_get_analysis_status_names_index_repository_once_the_tree_changes(
    client: Client[FastMCPTransport], working_tree: Path
) -> None:
    """Arrange: an indexed working tree whose module is then edited.
    Act: ask for its analysis status.
    Assert: the edited tree has no status and index_repository is named next."""
    await client.call_tool(
        "index_repository",
        {
            "repo_root": str(working_tree),
            "toolchain_overrides": {"python": sys.executable},
        },
    )
    (working_tree / "lib.py").write_text("def helper() -> int:\n    return 2\n")
    reported = await client.call_tool(
        "get_analysis_status", {"repo_root": str(working_tree)}
    )
    assert reported.data.status is None, (
        f"an edited tree should have no snapshot, got {reported.data.status}"
    )
    assert "index_repository" in reported.data.next_step, (
        f"the next step should name the free call, got {reported.data.next_step}"
    )


@pytest.mark.parametrize(
    "working_tree",
    [{"lib.py": "def helper() -> int:\n    return 1\n"}],
    indirect=True,
    ids=["one module"],
)
@pytest.mark.asyncio
async def test_get_analysis_status_repeats_the_report_of_the_free_call(
    client: Client[FastMCPTransport], working_tree: Path
) -> None:
    """Arrange: an indexed working tree.
    Act: ask for its analysis status.
    Assert: the status report equals the report index_repository returned."""
    indexed = await client.call_tool(
        "index_repository",
        {
            "repo_root": str(working_tree),
            "toolchain_overrides": {"python": sys.executable},
        },
    )
    reported = await client.call_tool(
        "get_analysis_status", {"repo_root": str(working_tree)}
    )
    assert reported.data == indexed.data, (
        f"the status should repeat {indexed.data}, got {reported.data}"
    )


@pytest.mark.parametrize(
    ("working_tree", "mode", "action", "expected_missing_summaries"),
    [
        ({"lib.py": "def helper() -> int:\n    return 1\n"}, "auto", "accept", 0),
        ({"lib.py": "def helper() -> int:\n    return 1\n"}, "legacy", "accept", 0),
        ({"lib.py": "def helper() -> int:\n    return 1\n"}, "auto", "decline", 1),
        ({"lib.py": "def helper() -> int:\n    return 1\n"}, "legacy", "decline", 1),
    ],
    indirect=["working_tree"],
    ids=[
        "accepted as a returned request",
        "accepted over the session",
        "declined as a returned request",
        "declined over the session",
    ],
)
@pytest.mark.asyncio
async def test_summarize_repository_asks_the_user_before_paying(
    analyzer: RepoAnalyzer,
    working_tree: Path,
    mode: Literal["auto", "legacy"],
    action: Literal["accept", "decline"],
    expected_missing_summaries: int,
) -> None:
    """Arrange: an indexed module and a client whose user answers every approval
    with one action. auto negotiates the 2026-07-28 protocol and legacy an
    earlier one.
    Act: summarize the snapshot through that client.
    Assert: the user is asked once and the summary is written only on accept."""
    questions: list[str] = []

    async def answer(
        message: str,
        response_type: type | None,
        params: ElicitRequestParams,
        context: object,
    ) -> ElicitResult:
        questions.append(message)
        return ElicitResult(action=action)

    async with Client(
        build_server(analyzer), mode=mode, elicitation_handler=answer
    ) as client:
        indexed = await client.call_tool(
            "index_repository",
            {
                "repo_root": str(working_tree),
                "toolchain_overrides": {"python": sys.executable},
            },
        )
        summarized = await client.call_tool(
            "summarize_repository",
            {"snapshot_id": indexed.data.status.snapshot.snapshot_id},
        )
    outcome = (len(questions), summarized.data.status.missing_summaries)
    assert outcome == (1, expected_missing_summaries), (
        f"one question and {expected_missing_summaries} missing summaries expected "
        f"after {action}, got {outcome} with questions {questions}"
    )
