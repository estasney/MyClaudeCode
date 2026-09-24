import sys
from collections.abc import AsyncIterator
from pathlib import Path
from textwrap import dedent

import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport

from analyze_repo.db import run_migrations
from analyze_repo.queries import SymbolScope
from analyze_repo.server import build_server
from analyze_repo.settings import Settings


@pytest_asyncio.fixture
async def client(tmp_path: Path) -> AsyncIterator[Client[FastMCPTransport]]:
    """The server as `main` builds it, over the in-memory transport."""
    settings = Settings(data_dir=tmp_path / "data")
    run_migrations(settings.db_path)
    async with Client(build_server(settings)) as client:
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
        {"repo_root": str(working_tree), "toolchains": {"python": sys.executable}},
    )
    found = await client.call_tool(
        "search_symbols",
        {
            "snapshot_id": indexed.data.snapshot_id,
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
        "toolchains": {"python": sys.executable},
    }
    first = await client.call_tool("index_repository", arguments)
    second = await client.call_tool("index_repository", arguments)
    assert second.data == first.data, (
        f"re-indexing an unchanged tree should return {first.data}, got {second.data}"
    )
