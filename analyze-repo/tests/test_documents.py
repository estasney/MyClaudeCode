import pytest

from analyze_repo import orm
from analyze_repo.semantic.documents import document_text, split_words


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("batch_size", ["batch", "size"]),
        (
            "HFEmbeddingFunction.__init__",
            ["hf", "embedding", "function", "init"],
        ),
        ("getHTTPResponse", ["get", "http", "response"]),
        ("How do I set v2?", ["how", "do", "i", "set", "v", "2"]),
    ],
    ids=["snake case", "acronym then camel case", "acronym inside", "prose"],
)
def test_split_words(text: str, expected: list[str]) -> None:
    """Arrange: identifiers and prose.
    Act: split them into words.
    Assert: identifier parts come apart lowercased."""
    result = split_words(text)
    assert result == expected, f"{text!r} should split into {expected}, got {result}"


def test_document_text_leads_with_identifier_words() -> None:
    """Arrange: a decorated function symbol, its signature and its summary.
    Act: build its search document.
    Assert: words then kind and location then decorators then the details."""
    symbol = orm.Symbol(
        qualified_name="create_space",
        name="create_space",
        kind=orm.SymbolKind.function,
        file=orm.File(path="tools/spaces.py", language=orm.Language.python),
        decorators=[orm.Decorator(expression="plain_tool")],
    )
    result = document_text(symbol, ["def create_space(name: str)", "Creates a space."])
    expected = (
        "create space\n"
        "function create_space in tools/spaces.py\n"
        "decorated with plain_tool\n"
        "def create_space(name: str)\n"
        "Creates a space."
    )
    assert result == expected, f"document should read {expected!r}, got {result!r}"
