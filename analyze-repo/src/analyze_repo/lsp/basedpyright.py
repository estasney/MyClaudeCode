import json
import os
import subprocess
import sys
from collections.abc import Generator, Iterable
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO, ClassVar

from pydantic import TypeAdapter

from analyze_repo.lsp.models import (
    ClientCapabilities,
    DidOpenTextDocumentParams,
    DocumentSymbol,
    DocumentSymbolClientCapabilities,
    DocumentSymbolParams,
    ErrorReply,
    ExitParams,
    InitializedParams,
    InitializeParams,
    InitializeResult,
    InterpreterConfiguration,
    LanguageId,
    Location,
    NotificationParams,
    Position,
    ReferenceContext,
    ReferenceParams,
    Reply,
    RequestParams,
    Response,
    ServerRequest,
    ServerRequestMethod,
    ShutdownParams,
    TextDocumentClientCapabilities,
    TextDocumentIdentifier,
    TextDocumentItem,
    TIncomingMessage,
    WorkspaceClientCapabilities,
)

__all__ = [
    "BasedPyright",
    "ResponseError",
    "ServerClosedError",
    "start_basedpyright",
]


class ServerClosedError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("basedpyright closed its stdout")


class ResponseError(RuntimeError):
    def __init__(self, method: str, error: object) -> None:
        super().__init__(f"{method} failed: {error}")


class InterpreterNotFoundError(FileNotFoundError):
    def __init__(self, python_path: Path) -> None:
        super().__init__(f"{python_path} is not an executable file")


def spawn_langserver(repo_root: Path) -> subprocess.Popen[bytes]:
    binary = Path(sys.executable).parent / "basedpyright-langserver"
    return subprocess.Popen(
        [str(binary), "--stdio"],
        cwd=repo_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )


class BasedPyright:
    incoming_message_adapter: ClassVar[TypeAdapter[TIncomingMessage]] = TypeAdapter(
        TIncomingMessage
    )
    document_symbols_adapter: ClassVar[TypeAdapter[list[DocumentSymbol] | None]] = (
        TypeAdapter(list[DocumentSymbol] | None)
    )
    references_adapter: ClassVar[TypeAdapter[list[Location] | None]] = TypeAdapter(
        list[Location] | None
    )
    initialize_adapter: ClassVar[TypeAdapter[InitializeResult]] = TypeAdapter(
        InitializeResult
    )
    shutdown_adapter: ClassVar[TypeAdapter[None]] = TypeAdapter(None)
    language_id: ClassVar[LanguageId] = LanguageId.python

    def find_references(
        self, absolute_path: Path, position: Position
    ) -> list[Location]:
        """The server answers null, not an empty list, when nothing refers to it."""
        params = ReferenceParams(
            text_document=TextDocumentIdentifier(uri=absolute_path.as_uri()),
            position=position,
            context=ReferenceContext(include_declaration=False),
        )
        return self.request(params, self.references_adapter) or []

    def open_document(self, absolute_path: Path) -> None:
        self.notify(
            DidOpenTextDocumentParams(
                text_document=TextDocumentItem(
                    uri=absolute_path.as_uri(),
                    language_id=self.language_id,
                    version=1,
                    text=absolute_path.read_text(encoding="utf-8"),
                )
            )
        )

    def get_document_symbols(self, absolute_path: Path) -> list[DocumentSymbol]:
        params = DocumentSymbolParams(
            text_document=TextDocumentIdentifier(uri=absolute_path.as_uri())
        )
        return self.request(params, self.document_symbols_adapter) or []

    def __init__(self, stdin: IO[bytes], stdout: IO[bytes], python_path: Path) -> None:
        self.stdin = stdin
        self.stdout = stdout
        self.python_path = python_path
        self.next_request_id = 0

    def notify(self, params: NotificationParams) -> None:
        write_message(self.stdin, params.model_dump(by_alias=True))

    def request[ResultT](
        self, params: RequestParams[ResultT], result_adapter: TypeAdapter[ResultT]
    ) -> ResultT:
        self.next_request_id += 1
        write_message(
            self.stdin,
            params.model_dump(by_alias=True, context={"id": self.next_request_id}),
        )
        while True:
            match read_message(self.stdout, self.incoming_message_adapter):
                case Reply(id=reply_id, result=result) if (
                    reply_id == self.next_request_id
                ):
                    return result_adapter.validate_python(result)
                case ErrorReply(id=reply_id, error=error) if (
                    reply_id == self.next_request_id
                ):
                    raise ResponseError(params.method, error)
                case ServerRequest(
                    method=ServerRequestMethod.configuration, id=request_id
                ):
                    self.answer_configuration(request_id)
                case _:
                    pass

    def answer_configuration(self, request_id: int) -> None:
        response = Response(
            id=request_id,
            result=[InterpreterConfiguration(python_path=self.python_path)],
        )
        write_message(self.stdin, response.model_dump(by_alias=True, mode="json"))


@contextmanager
def start_basedpyright(
    repo_root: Path, python_path: Path, absolute_paths: Iterable[Path]
) -> Generator[BasedPyright]:
    """Opens every file before yielding so `references` searches all of them."""
    if not os.access(python_path, os.X_OK) or not python_path.is_file():
        raise InterpreterNotFoundError(python_path)
    process = spawn_langserver(repo_root)
    if process.stdin is None or process.stdout is None:
        raise ServerClosedError
    server = BasedPyright(process.stdin, process.stdout, python_path)
    try:
        server.request(
            InitializeParams(
                process_id=None,
                root_uri=repo_root.as_uri(),
                capabilities=ClientCapabilities(
                    workspace=WorkspaceClientCapabilities(configuration=True),
                    text_document=TextDocumentClientCapabilities(
                        document_symbol=DocumentSymbolClientCapabilities(
                            hierarchical_document_symbol_support=True
                        )
                    ),
                ),
            ),
            server.initialize_adapter,
        )
        server.notify(InitializedParams())
        for absolute_path in absolute_paths:
            server.open_document(absolute_path)
        yield server
    finally:
        stop_langserver(server, process)


def stop_langserver(server: BasedPyright, process: subprocess.Popen[bytes]) -> None:
    """Asks for a clean exit first; terminates only if the server does not comply."""
    with suppress(ServerClosedError, BrokenPipeError):
        server.request(ShutdownParams(), server.shutdown_adapter)
        server.notify(ExitParams())
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait()


def write_message(stdin: IO[bytes], message: dict[str, object]) -> None:
    body = json.dumps(message, separators=(",", ":")).encode()
    stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    stdin.flush()


def read_message(
    stdout: IO[bytes], incoming_adapter: TypeAdapter[TIncomingMessage]
) -> TIncomingMessage:
    content_length = 0
    while (header := stdout.readline()) != b"\r\n":
        if not header:
            raise ServerClosedError
        name, _, value = header.partition(b":")
        if name.strip().lower() == b"content-length":
            content_length = int(value)
    return incoming_adapter.validate_json(stdout.read(content_length))
