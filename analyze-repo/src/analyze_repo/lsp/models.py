# pyright: reportIncompatibleVariableOverride=false

import os
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    model_serializer,
)
from pydantic.alias_generators import to_camel

__all__ = [
    "ClientCapabilities",
    "DidOpenTextDocumentParams",
    "DocumentSymbol",
    "DocumentSymbolClientCapabilities",
    "DocumentSymbolParams",
    "ErrorReply",
    "ExitParams",
    "InitializeParams",
    "InitializeResult",
    "InitializedParams",
    "InterpreterConfiguration",
    "LanguageId",
    "Location",
    "NotificationParams",
    "Position",
    "Range",
    "ReferenceContext",
    "ReferenceParams",
    "Reply",
    "RequestParams",
    "Response",
    "ServerRequest",
    "ServerRequestMethod",
    "ShutdownParams",
    "SymbolKind",
    "TIncomingMessage",
    "TextDocumentClientCapabilities",
    "TextDocumentIdentifier",
    "TextDocumentItem",
    "WorkspaceClientCapabilities",
]


class RequestMethod(StrEnum):
    initialize = "initialize"
    shutdown = "shutdown"
    document_symbol = "textDocument/documentSymbol"
    references = "textDocument/references"


class WireModel(BaseModel):
    """Field names are snake_case here and camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
        frozen=True,
    )


class Position(WireModel):
    """Zero-based line and UTF-16 code unit offset, as LSP defines them."""

    line: int
    character: int


class Range(WireModel):
    start: Position
    end: Position


def file_uri_to_path(uri: str) -> Path:
    """Decode before any drive-letter test: pyright spells `C:` as `c%3A`."""
    parts = urlsplit(uri)
    decoded = unquote(parts.path)
    if os.name == "nt":
        if parts.netloc:
            decoded = f"//{parts.netloc}{decoded}"
        elif decoded[:1] == "/" and decoded[2:3] == ":":
            decoded = decoded[1:]
    return Path(decoded).resolve()


class Location(WireModel):
    absolute_path: Annotated[
        Path, BeforeValidator(file_uri_to_path), Field(validation_alias="uri")
    ]
    range: Range


class SymbolKind(IntEnum):
    """The subset basedpyright's `symbolIndexer.ts` emits, numbered per LSP."""

    module = 2
    class_ = 5
    method = 6
    function = 12
    variable = 13
    constant = 14
    type_parameter = 26


class DocumentSymbol(WireModel):
    name: str
    kind: SymbolKind
    range: Range
    selection_range: Range
    children: list["DocumentSymbol"]


class MissingRequestIdError(ValueError):
    def __init__(self) -> None:
        super().__init__("dump a RequestParams with context={'id': <int>}")


class RequestParams[ResultT](WireModel):
    """Subclasses narrow `method` to a Literal, which discriminates the union,
    and bind `ResultT` to the reply's shape.

    Dumping yields the JSON-RPC envelope; the id comes from `context`.
    """

    method: RequestMethod = Field(exclude=True)

    @model_serializer(mode="wrap")
    def to_jsonrpc(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, object]:
        match info.context:
            case {"id": int(request_id)}:
                pass
            case _:
                raise MissingRequestIdError
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": self.method,
            "params": handler(self),
        }


class NotificationMethod(StrEnum):
    initialized = "initialized"
    exit = "exit"
    did_open = "textDocument/didOpen"


class NotificationParams(WireModel):
    """Dumping yields the JSON-RPC envelope; notifications carry no id."""

    method: NotificationMethod = Field(exclude=True)

    @model_serializer(mode="wrap")
    def to_jsonrpc(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        return {"jsonrpc": "2.0", "method": self.method, "params": handler(self)}


class InitializedParams(NotificationParams):
    method: Literal[NotificationMethod.initialized] = Field(
        default=NotificationMethod.initialized, exclude=True
    )


class LanguageId(StrEnum):
    python = "python"
    typescript = "typescript"


class TextDocumentItem(WireModel):
    uri: str
    language_id: LanguageId
    version: int
    text: str


class DidOpenTextDocumentParams(NotificationParams):
    method: Literal[NotificationMethod.did_open] = Field(
        default=NotificationMethod.did_open, exclude=True
    )
    text_document: TextDocumentItem


class WorkspaceClientCapabilities(WireModel):
    configuration: bool


class DocumentSymbolClientCapabilities(WireModel):
    hierarchical_document_symbol_support: bool


class TextDocumentClientCapabilities(WireModel):
    document_symbol: DocumentSymbolClientCapabilities


class ClientCapabilities(WireModel):
    workspace: WorkspaceClientCapabilities
    text_document: TextDocumentClientCapabilities


class WorkDoneProgressOptions(WireModel):
    work_done_progress: bool


class ServerCapabilities(WireModel):
    document_symbol_provider: bool | WorkDoneProgressOptions
    references_provider: bool | WorkDoneProgressOptions


class InitializeResult(WireModel):
    capabilities: ServerCapabilities


class InitializeParams(RequestParams[InitializeResult]):
    method: Literal[RequestMethod.initialize] = Field(
        default=RequestMethod.initialize, exclude=True
    )
    process_id: int | None
    root_uri: str
    capabilities: ClientCapabilities


class TextDocumentIdentifier(WireModel):
    uri: str


class DocumentSymbolParams(RequestParams[list[DocumentSymbol] | None]):
    method: Literal[RequestMethod.document_symbol] = Field(
        default=RequestMethod.document_symbol, exclude=True
    )
    text_document: TextDocumentIdentifier


class ReferenceContext(WireModel):
    include_declaration: bool


class ReferenceParams(RequestParams[list[Location] | None]):
    method: Literal[RequestMethod.references] = Field(
        default=RequestMethod.references, exclude=True
    )
    text_document: TextDocumentIdentifier
    position: Position
    context: ReferenceContext


class ShutdownParams(RequestParams[None]):
    method: Literal[RequestMethod.shutdown] = Field(
        default=RequestMethod.shutdown, exclude=True
    )


class ExitParams(NotificationParams):
    method: Literal[NotificationMethod.exit] = Field(
        default=NotificationMethod.exit, exclude=True
    )


class ServerMessage(WireModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]


class Reply(ServerMessage):
    id: int
    result: JsonValue


class ResponseErrorBody(WireModel):
    code: int
    message: str
    data: JsonValue = None


class ErrorReply(ServerMessage):
    id: int
    error: ResponseErrorBody


class ServerRequestMethod(StrEnum):
    configuration = "workspace/configuration"


class ServerRequest(ServerMessage):
    id: int
    method: ServerRequestMethod
    params: JsonValue


class Notification(ServerMessage):
    method: str
    params: JsonValue


type TIncomingMessage = Reply | ErrorReply | ServerRequest | Notification


class Response[ResultT](WireModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int
    result: ResultT


class InterpreterConfiguration(WireModel):
    """Answer to `workspace/configuration` for section `python`."""

    python_path: Path
