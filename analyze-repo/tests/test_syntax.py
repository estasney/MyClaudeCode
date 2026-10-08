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


@pytest.mark.parametrize(
    ("source", "position", "expected"),
    [
        ("def f(a): pass", Position(line=0, character=6), True),
        ("def f(a: int): pass", Position(line=0, character=6), True),
        ("def f(a: int = 1): pass", Position(line=0, character=6), True),
        ("def f(*args): pass", Position(line=0, character=7), True),
        ("def f():\n    a = 1", Position(line=1, character=4), False),
        ("class A:\n    a: int = 1", Position(line=1, character=4), False),
        ("a = 1", Position(line=0, character=0), False),
    ],
    ids=[
        "bare parameter",
        "typed parameter",
        "typed parameter with default",
        "star parameter",
        "local variable",
        "class attribute",
        "module variable",
    ],
)
def test_is_parameter(source: str, position: Position, *, expected: bool) -> None:
    """Arrange: a parsed Python source and the position of a declared name.
    Act: ask whether the name is a parameter.
    Assert: only names inside a parameter list are parameters."""
    result = PythonSyntaxTree(source.encode("utf-8")).is_parameter(position)
    assert result == expected, f"{position} in {source!r} is_parameter {expected}"


@pytest.mark.parametrize(
    ("source", "position", "expected"),
    [
        ("def f(): pass", Position(line=0, character=4), []),
        ("@tool\ndef f(): pass", Position(line=1, character=4), ["tool"]),
        (
            "@server.tool(name='x')\n@cache\nasync def f(): pass",
            Position(line=2, character=10),
            ["server.tool(name='x')", "cache"],
        ),
        ("@dataclass\nclass A: pass", Position(line=1, character=6), ["dataclass"]),
        ("@tool\ndef f(a): pass", Position(line=1, character=6), []),
    ],
    ids=[
        "undecorated",
        "one decorator",
        "decorators in source order",
        "decorated class",
        "parameter of a decorated function",
    ],
)
def test_list_decorators(source: str, position: Position, expected: list[str]) -> None:
    """Arrange: a parsed Python source and the position of a definition name.
    Act: list the decorators of that definition.
    Assert: decorator expressions come back in source order without the at sign."""
    result = PythonSyntaxTree(source.encode("utf-8")).list_decorators(position)
    assert result == expected, f"{position} in {source!r} has {expected}, got {result}"
