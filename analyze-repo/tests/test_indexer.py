from pathlib import Path

import pytest

from analyze_repo import orm
from analyze_repo.indexer import collect_symbols, find_enclosing_symbol
from analyze_repo.lsp import models as lsp


def document_symbol(
    name: str,
    kind: lsp.SymbolKind,
    start_line: int,
    end_line: int,
    children: list[lsp.DocumentSymbol],
) -> lsp.DocumentSymbol:
    span = lsp.Range(
        start=lsp.Position(line=start_line, character=0),
        end=lsp.Position(line=end_line, character=0),
    )
    return lsp.DocumentSymbol(
        name=name, kind=kind, range=span, selection_range=span, children=children
    )


@pytest.mark.parametrize(
    ("tree", "expected"),
    [
        (
            [document_symbol("Client", lsp.SymbolKind.class_, 0, 2, [])],
            [("Client", orm.SymbolKind.class_, None)],
        ),
        (
            [
                document_symbol(
                    "Client",
                    lsp.SymbolKind.class_,
                    0,
                    2,
                    [document_symbol("timeout", lsp.SymbolKind.variable, 1, 1, [])],
                )
            ],
            [
                ("Client", orm.SymbolKind.class_, None),
                ("Client.timeout", orm.SymbolKind.variable, "Client"),
            ],
        ),
        (
            [
                document_symbol(
                    "connect",
                    lsp.SymbolKind.function,
                    0,
                    3,
                    [
                        document_symbol("self", lsp.SymbolKind.variable, 0, 0, []),
                        document_symbol("retry", lsp.SymbolKind.function, 1, 2, []),
                    ],
                )
            ],
            [
                ("connect", orm.SymbolKind.function, None),
                ("connect.self", orm.SymbolKind.variable, "connect"),
                ("connect.retry", orm.SymbolKind.function, "connect"),
            ],
        ),
        ([document_symbol("os", lsp.SymbolKind.module, 0, 0, [])], []),
        ([document_symbol("T", lsp.SymbolKind.type_parameter, 0, 0, [])], []),
    ],
    ids=[
        "class",
        "class attribute",
        "function parameter and nested function",
        "import alias dropped",
        "type parameter dropped",
    ],
)
def test_collect_symbols(
    tree: list[lsp.DocumentSymbol],
    expected: list[tuple[str, orm.SymbolKind, str | None]],
) -> None:
    """Arrange: a document-symbol tree from the language server.
    Act: collect the symbols from the module level.
    Assert: definitions appear in tree order with dotted names and their parent."""
    result = [
        (
            symbol.qualified_name,
            symbol.kind,
            None if symbol.parent is None else symbol.parent.qualified_name,
        )
        for symbol in collect_symbols(Path("m.py"), tree, [b""] * 4, None)
    ]
    assert result == expected, f"tree {tree} should collect as {expected}, got {result}"


@pytest.mark.parametrize(
    ("tree", "position", "expected"),
    [
        (
            [document_symbol("outer", lsp.SymbolKind.function, 0, 5, [])],
            lsp.Position(line=2, character=0),
            "outer",
        ),
        (
            [
                document_symbol(
                    "outer",
                    lsp.SymbolKind.function,
                    0,
                    5,
                    [document_symbol("inner", lsp.SymbolKind.function, 2, 4, [])],
                )
            ],
            lsp.Position(line=3, character=0),
            "outer.inner",
        ),
        (
            [document_symbol("outer", lsp.SymbolKind.function, 0, 5, [])],
            lsp.Position(line=5, character=0),
            None,
        ),
        (
            [document_symbol("outer", lsp.SymbolKind.function, 0, 5, [])],
            lsp.Position(line=9, character=0),
            None,
        ),
    ],
    ids=["single container", "innermost wins", "end is exclusive", "outside all"],
)
def test_find_enclosing_symbol(
    tree: list[lsp.DocumentSymbol], position: lsp.Position, expected: str | None
) -> None:
    """Arrange: collected symbols whose ranges may nest.
    Act: look up the enclosing symbol at a position.
    Assert: the innermost containing range is returned, or None outside every range."""
    symbols = list(collect_symbols(Path("m.py"), tree, [b""] * 6, None))
    found = find_enclosing_symbol(symbols, position)
    name = None if found is None else found.qualified_name
    assert name == expected, f"{position} should sit inside {expected}, got {name}"
