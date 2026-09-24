import io
import json
from contextlib import AbstractContextManager
from contextlib import nullcontext as does_not_raise
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from analyze_repo.lsp.basedpyright import BasedPyright, ResponseError, ServerClosedError
from analyze_repo.lsp.models import (
    DocumentSymbol,
    DocumentSymbolParams,
    TextDocumentIdentifier,
)


def framed(*messages: dict[str, object]) -> bytes:
    """Encodes server messages with the Content-Length framing LSP uses."""
    out = b""
    for message in messages:
        body = json.dumps(message).encode()
        out += f"Content-Length: {len(body)}\r\n\r\n".encode() + body
    return out


@pytest.mark.parametrize(
    ("server_output", "expectation", "expected"),
    [
        (
            framed({"jsonrpc": "2.0", "id": 1, "result": []}),
            does_not_raise(),
            [],
        ),
        (
            framed(
                {"jsonrpc": "2.0", "method": "window/logMessage", "params": {}},
                {"jsonrpc": "2.0", "id": 1, "result": None},
            ),
            does_not_raise(),
            None,
        ),
        (
            framed(
                {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "no"}}
            ),
            pytest.raises(ResponseError),
            None,
        ),
        (b"", pytest.raises(ServerClosedError), None),
    ],
    ids=["reply", "notification skipped", "error reply", "closed stdout"],
)
def test_request(
    server_output: bytes,
    expectation: AbstractContextManager[object],
    expected: list[DocumentSymbol] | None,
) -> None:
    """Arrange: a client over in-memory pipes with scripted server output.
    Act: send a documentSymbol request.
    Assert: the reply with our id is returned, or the matching error is raised."""
    stdin = io.BytesIO()
    client = BasedPyright(stdin, io.BytesIO(server_output), Path("/usr/bin/python3"))
    params = DocumentSymbolParams(
        text_document=TextDocumentIdentifier(uri="file:///m.py")
    )
    adapter: TypeAdapter[list[DocumentSymbol] | None] = TypeAdapter(
        list[DocumentSymbol] | None
    )
    with expectation:
        result = client.request(params, adapter)
        assert result == expected, (
            f"{server_output!r} should yield {expected}, got {result}"
        )
    sent = json.loads(stdin.getvalue().split(b"\r\n\r\n", 1)[1])
    assert sent["id"] == 1 and sent["method"] == "textDocument/documentSymbol", (
        f"request envelope should hold id 1 and the method, got {sent}"
    )


def sent_messages(stdin: io.BytesIO) -> list[dict[str, object]]:
    """Decodes every framed message the client wrote."""
    return [
        json.loads(chunk.split(b"\r\n\r\n", 1)[1])
        for chunk in stdin.getvalue().split(b"Content-Length: ")
        if chunk
    ]


@pytest.mark.parametrize(
    ("python_path", "expected_configuration"),
    [
        (Path("/opt/venv/bin/python"), [{"pythonPath": "/opt/venv/bin/python"}]),
    ],
)
def test_configuration_request_is_answered_with_interpreter(
    python_path: Path, expected_configuration: list[dict[str, str]]
) -> None:
    """Arrange: the server asks for workspace/configuration before replying.
    Act: send a documentSymbol request.
    Assert: the client answers the server's request with the interpreter, then returns."""
    stdin = io.BytesIO()
    server_output = framed(
        {"jsonrpc": "2.0", "id": 7, "method": "workspace/configuration", "params": {}},
        {"jsonrpc": "2.0", "id": 1, "result": []},
    )
    client = BasedPyright(stdin, io.BytesIO(server_output), python_path)
    params = DocumentSymbolParams(
        text_document=TextDocumentIdentifier(uri="file:///m.py")
    )
    client.request(params, client.document_symbols_adapter)
    answers = [m for m in sent_messages(stdin) if m.get("id") == 7]
    assert answers == [{"jsonrpc": "2.0", "id": 7, "result": expected_configuration}], (
        f"server request 7 should be answered with {expected_configuration}, got {answers}"
    )
