import pytest

from analyze_repo.lsp.models import Position
from analyze_repo.syntax import (
    PythonSyntaxTree,
    SyntaxContext,
    utf16_offset_to_byte_offset,
)


@pytest.mark.parametrize(
    ("line", "character", "expected"),
    [
        ("abc", 0, 0),
        ("abc", 3, 3),
        ("é = 1", 2, 3),
        ("😀 = 1", 2, 4),
        ("😀 = 1", 3, 5),
    ],
    ids=["ascii start", "ascii end", "two-byte char", "surrogate pair", "after pair"],
)
def test_utf16_offset_to_byte_offset(line: str, character: int, expected: int) -> None:
    """Arrange: a line holding one-, two-, and four-byte characters.
    Act: convert an LSP UTF-16 column to a byte column.
    Assert: the byte column lands on the same character."""
    result = utf16_offset_to_byte_offset(line.encode("utf-8"), character)
    assert result == expected, (
        f"UTF-16 column {character} of {line!r} is byte {expected}"
    )


@pytest.mark.parametrize(
    ("source", "position", "expected"),
    [
        (
            "foo(x)",
            Position(line=0, character=0),
            SyntaxContext("identifier", "call", "function"),
        ),
        (
            "bar.baz",
            Position(line=0, character=0),
            SyntaxContext("identifier", "attribute", "object"),
        ),
        (
            "bar.baz",
            Position(line=0, character=4),
            SyntaxContext("attribute", "module", None),
        ),
        (
            "obj.method()",
            Position(line=0, character=4),
            SyntaxContext("attribute", "call", "function"),
        ),
        (
            "a.b.c()",
            Position(line=0, character=2),
            SyntaxContext("attribute", "attribute", "object"),
        ),
        (
            "x = obj.method",
            Position(line=0, character=8),
            SyntaxContext("attribute", "assignment", "right"),
        ),
        (
            "foo(key=qux)",
            Position(line=0, character=4),
            SyntaxContext("identifier", "keyword_argument", "name"),
        ),
        (
            "class A(Base): pass",
            Position(line=0, character=6),
            SyntaxContext("identifier", "class_definition", "name"),
        ),
        (
            "class A(Base): pass",
            Position(line=0, character=8),
            SyntaxContext("identifier", "argument_list", None),
        ),
        (
            'x = "😀"; foo(x)',
            Position(line=0, character=10),
            SyntaxContext("identifier", "call", "function"),
        ),
        (
            "x = 1\nfoo(x)",
            Position(line=1, character=0),
            SyntaxContext("identifier", "call", "function"),
        ),
    ],
    ids=[
        "callee",
        "attribute object",
        "attribute name",
        "method call target",
        "middle of a chain",
        "bound method as value",
        "keyword name",
        "class name",
        "base class has no field",
        "column after surrogate pair",
        "second line",
    ],
)
def test_context_at(source: str, position: Position, expected: SyntaxContext) -> None:
    """Arrange: a parsed Python source and an LSP position inside it.
    Act: look up the node at the position.
    Assert: node kind, parent kind, and parent field match the grammar."""
    result = PythonSyntaxTree(source.encode("utf-8")).context_at(position)
    assert result == expected, f"{position} in {source!r} is {expected}, got {result}"
