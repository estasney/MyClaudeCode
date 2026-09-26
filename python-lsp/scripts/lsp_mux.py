#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""lsp_mux: present several LSP servers to an editor as a single stdio server.

Usage: lsp_mux.py [config.toml | config.json]

Tracing: LSP_MUX_LOG=<path> appends log lines and child stderr to a file;
LSP_MUX_DEBUG=1 traces routing, LSP_MUX_DEBUG=2 also dumps wire messages.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import signal
import sys
import threading
from collections.abc import Coroutine, Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import BinaryIO, Protocol, Self, assert_never, cast
from urllib.parse import unquote, urlsplit

import tomllib

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]
type MsgId = int | str

JSONRPC = "2.0"
TAG = "__lsp_mux__"

# JSON-RPC error codes (LSP spec).
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

# Notifications every server receives (lifecycle + document sync).
BROADCAST_NOTIFICATIONS = frozenset(
    {
        "initialized",
        "exit",
        "$/setTrace",
        "textDocument/didOpen",
        "textDocument/didChange",
        "textDocument/willSave",
        "textDocument/didSave",
        "textDocument/didClose",
        "workspace/didChangeConfiguration",
        "workspace/didChangeWatchedFiles",
        "workspace/didChangeWorkspaceFolders",
        "workspace/didCreateFiles",
        "workspace/didRenameFiles",
        "workspace/didDeleteFiles",
        "notebookDocument/didOpen",
        "notebookDocument/didChange",
        "notebookDocument/didSave",
        "notebookDocument/didClose",
    }
)

# Requests fanned out to every capable server, results merged.
MERGED_REQUESTS = frozenset({"textDocument/codeAction"})

# method -> top-level ServerCapabilities key that gates it.
CAPABILITY_FOR_METHOD: dict[str, str] = {
    "textDocument/completion": "completionProvider",
    "completionItem/resolve": "completionProvider",
    "textDocument/hover": "hoverProvider",
    "textDocument/signatureHelp": "signatureHelpProvider",
    "textDocument/declaration": "declarationProvider",
    "textDocument/definition": "definitionProvider",
    "textDocument/typeDefinition": "typeDefinitionProvider",
    "textDocument/implementation": "implementationProvider",
    "textDocument/references": "referencesProvider",
    "textDocument/documentHighlight": "documentHighlightProvider",
    "textDocument/documentSymbol": "documentSymbolProvider",
    "textDocument/codeAction": "codeActionProvider",
    "codeAction/resolve": "codeActionProvider",
    "textDocument/codeLens": "codeLensProvider",
    "codeLens/resolve": "codeLensProvider",
    "textDocument/documentLink": "documentLinkProvider",
    "documentLink/resolve": "documentLinkProvider",
    "textDocument/documentColor": "colorProvider",
    "textDocument/colorPresentation": "colorProvider",
    "textDocument/formatting": "documentFormattingProvider",
    "textDocument/rangeFormatting": "documentRangeFormattingProvider",
    "textDocument/onTypeFormatting": "documentOnTypeFormattingProvider",
    "textDocument/rename": "renameProvider",
    "textDocument/prepareRename": "renameProvider",
    "textDocument/foldingRange": "foldingRangeProvider",
    "textDocument/selectionRange": "selectionRangeProvider",
    "textDocument/semanticTokens/full": "semanticTokensProvider",
    "textDocument/semanticTokens/full/delta": "semanticTokensProvider",
    "textDocument/semanticTokens/range": "semanticTokensProvider",
    "textDocument/linkedEditingRange": "linkedEditingRangeProvider",
    "textDocument/prepareCallHierarchy": "callHierarchyProvider",
    "callHierarchy/incomingCalls": "callHierarchyProvider",
    "callHierarchy/outgoingCalls": "callHierarchyProvider",
    "textDocument/prepareTypeHierarchy": "typeHierarchyProvider",
    "typeHierarchy/supertypes": "typeHierarchyProvider",
    "typeHierarchy/subtypes": "typeHierarchyProvider",
    "textDocument/inlayHint": "inlayHintProvider",
    "inlayHint/resolve": "inlayHintProvider",
    "textDocument/diagnostic": "diagnosticProvider",
    "workspace/diagnostic": "diagnosticProvider",
    "textDocument/moniker": "monikerProvider",
    "workspace/symbol": "workspaceSymbolProvider",
    "workspaceSymbol/resolve": "workspaceSymbolProvider",
    "workspace/executeCommand": "executeCommandProvider",
    "workspace/willCreateFiles": "workspace",
    "workspace/willRenameFiles": "workspace",
    "workspace/willDeleteFiles": "workspace",
}


def log(*parts: object) -> None:
    print("[lsp_mux]", *parts, file=sys.stderr, flush=True)


def debug_level() -> int:
    raw = os.environ.get("LSP_MUX_DEBUG", "")
    return int(raw) if raw.isdigit() else 0


def debug(*parts: object) -> None:
    if debug_level() >= 1:
        log("debug:", *parts)


def trace_wire(direction: str, message: JsonValue) -> None:
    if debug_level() >= 2:
        text = json.dumps(message, separators=(",", ":"))
        log("wire:", direction, text[:2000])


def configure_log_file() -> None:
    """Send stderr (ours and the child servers') to LSP_MUX_LOG when set."""
    path = os.environ.get("LSP_MUX_LOG")
    if not path:
        return
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    stderr_fd = sys.stderr.fileno()
    if os.dup2(fd, stderr_fd) != stderr_fd:  # child servers inherit fd 2 as well
        raise OSError("could not redirect stderr to the log file")
    os.close(fd)
    log("---- start", "pid", os.getpid(), "platform", sys.platform, sys.version)
    log("argv:", sys.argv, "cwd:", os.getcwd())


# --------------------------------------------------------------------------
# JSON helpers: narrow untyped JSON at the boundary
# --------------------------------------------------------------------------


def as_object(value: JsonValue) -> JsonObject:
    return value if isinstance(value, dict) else {}


def as_list(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def as_str(value: JsonValue) -> str | None:
    return value if isinstance(value, str) else None


def as_int(value: JsonValue) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def as_msg_id(value: JsonValue) -> MsgId | None:
    match value:
        case bool():
            return None
        case int() | str():
            return value
        case _:
            return None


def load_json(data: bytes) -> JsonValue:
    return cast(JsonValue, json.loads(data))


# --------------------------------------------------------------------------
# JSON-RPC messages
# --------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class RpcError:
    code: int
    message: str
    data: JsonValue = None

    @classmethod
    def from_json(cls, raw: JsonObject) -> Self:
        code = as_int(raw.get("code"))
        message = as_str(raw.get("message"))
        return cls(
            code=INTERNAL_ERROR if code is None else code,
            message="server error" if message is None else message,
            data=raw.get("data"),
        )

    def to_json(self) -> JsonObject:
        body: JsonObject = {"code": self.code, "message": self.message}
        if self.data is not None:
            body["data"] = self.data
        return body


@dataclass(slots=True, frozen=True)
class Request:
    id: MsgId
    method: str
    params: JsonValue


@dataclass(slots=True, frozen=True)
class Notification:
    method: str
    params: JsonValue


@dataclass(slots=True, frozen=True)
class Response:
    id: MsgId
    result: JsonValue = None
    error: RpcError | None = None


type Message = Request | Notification | Response


def parse_message(raw: JsonValue) -> Message | None:
    """Classify one decoded JSON-RPC frame; None when it fits no shape."""
    if not isinstance(raw, dict):
        return None
    method = as_str(raw.get("method"))
    id_ = as_msg_id(raw.get("id"))
    if method is not None and id_ is not None:
        return Request(id_, method, raw.get("params"))
    if method is not None:
        return Notification(method, raw.get("params"))
    if id_ is None:
        return None
    error = raw.get("error")
    if isinstance(error, dict):
        return Response(id_, error=RpcError.from_json(error))
    return Response(id_, result=raw.get("result"))


def encode_message(message: Message) -> JsonObject:
    match message:
        case Request(id=id_, method=method, params=params):
            return {"jsonrpc": JSONRPC, "id": id_, "method": method, "params": params}
        case Notification(method=method, params=params):
            return {"jsonrpc": JSONRPC, "method": method, "params": params}
        case Response(id=id_, error=RpcError() as error):
            return {"jsonrpc": JSONRPC, "id": id_, "error": error.to_json()}
        case Response(id=id_, result=result):
            return {"jsonrpc": JSONRPC, "id": id_, "result": result}
        case _:
            assert_never(message)


# --------------------------------------------------------------------------
# Document identity: one value type, equal by construction
# --------------------------------------------------------------------------


class Platform(Enum):
    posix = auto()
    windows = auto()


def current_platform() -> Platform:
    return Platform.windows if os.name == "nt" else Platform.posix


def path_separator(platform: Platform) -> str:
    match platform:
        case Platform.posix:
            return "/"
        case Platform.windows:
            return "\\"


def normalize_local_path(path: str, platform: Platform) -> str:
    """Canonical spelling of a local path for equality and prefix tests."""
    match platform:
        case Platform.posix:
            return path
        case Platform.windows:
            return path.replace("/", "\\").casefold()


def local_path_from_uri(netloc: str, uri_path: str, platform: Platform) -> str:
    """Decode a file URI's path component into a canonical local path.

    Decoding happens before any drive-letter test, which is where urllib's
    url2pathname goes wrong: pyright spells ``C:`` as ``c%3A``.
    """
    decoded = unquote(uri_path)
    match platform:
        case Platform.posix:
            return decoded
        case Platform.windows:
            if netloc:  # file://server/share/... -> \\server\share\...
                decoded = f"//{netloc}{decoded}"
            elif decoded[:1] == "/" and decoded[2:3] == ":":  # /c:/... -> c:/...
                decoded = decoded[1:]
            return normalize_local_path(decoded, platform)


@dataclass(slots=True, frozen=True)
class DocumentId:
    """Identity of a document independent of how its URI is spelled.

    Two ids compare equal when they name the same file, whatever the case
    of the drive letter or the percent-encoding. The spelling used to build
    the id is kept so a publish can go out under the client's own URI.
    """

    key: str
    is_file: bool
    uri: str = field(compare=False, hash=False)

    @classmethod
    def from_uri(cls, uri: str, platform: Platform) -> Self:
        parts = urlsplit(uri)
        if parts.scheme != "file":
            return cls(key=uri, is_file=False, uri=uri)
        key = local_path_from_uri(parts.netloc, parts.path, platform)
        return cls(key=key, is_file=True, uri=uri)


@dataclass(slots=True, frozen=True)
class OpenDocument:
    """A document the client has open, under its own URI spelling, at its latest version."""

    id: DocumentId
    version: int | None


class Membership(Enum):
    inside = auto()
    outside = auto()
    unfiltered = auto()  # no roots configured, or not a local file


@dataclass(slots=True, frozen=True)
class Workspace:
    """Root folders as canonical path keys; membership is a pure prefix test."""

    platform: Platform
    roots: frozenset[str] = frozenset()

    def root_key(self, uri: str) -> str | None:
        doc = DocumentId.from_uri(uri, self.platform)
        if not doc.is_file:
            return None
        return doc.key.rstrip(path_separator(self.platform))

    def with_folders(self, added: Iterable[str], removed: Iterable[str]) -> Self:
        added_keys = {key for uri in added if (key := self.root_key(uri)) is not None}
        removed_keys = {
            key for uri in removed if (key := self.root_key(uri)) is not None
        }
        return type(self)(self.platform, (self.roots | added_keys) - removed_keys)

    def with_local_root(self, path: str) -> Self:
        key = normalize_local_path(path, self.platform)
        return type(self)(self.platform, self.roots | {key})

    def membership(self, doc: DocumentId) -> Membership:
        if not self.roots or not doc.is_file:
            return Membership.unfiltered
        sep = path_separator(self.platform)
        for root in self.roots:
            if doc.key == root or doc.key.startswith(root + sep):
                return Membership.inside
        return Membership.outside


# --------------------------------------------------------------------------
# LSP payload shapes the proxy inspects
# --------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class TextDocumentRef:
    uri: str
    version: int | None


def parse_text_document(params: JsonValue) -> TextDocumentRef | None:
    text_document = as_object(as_object(params).get("textDocument"))
    uri = as_str(text_document.get("uri"))
    if uri is None:
        return None
    return TextDocumentRef(uri, as_int(text_document.get("version")))


@dataclass(slots=True, frozen=True)
class PublishDiagnostics:
    uri: str
    version: int | None
    diagnostics: list[JsonValue]


def parse_publish_diagnostics(params: JsonValue) -> PublishDiagnostics | None:
    body = as_object(params)
    uri = as_str(body.get("uri"))
    if uri is None:
        return None
    return PublishDiagnostics(
        uri, as_int(body.get("version")), as_list(body.get("diagnostics"))
    )


def with_pull_diagnostics(capabilities: JsonValue) -> JsonObject:
    """Client capabilities extended with pull diagnostics, which the mux answers.

    A server that sees this stops publishing diagnostics on its own schedule
    and waits to be asked, so every result it returns matches the document
    version the mux asked about.
    """
    extended = copy.deepcopy(as_object(capabilities))
    text_document = as_object(extended.get("textDocument"))
    text_document["diagnostic"] = {"dynamicRegistration": True}
    extended["textDocument"] = text_document
    workspace = as_object(extended.get("workspace"))
    workspace["diagnostics"] = {"refreshSupport": True}
    extended["workspace"] = workspace
    return extended


def partition_by_method(
    entries: list[JsonValue], method: str
) -> tuple[list[JsonValue], list[JsonValue]]:
    """Split registrations (or unregistrations) into those for method and the rest."""
    matching = [entry for entry in entries if as_object(entry).get("method") == method]
    rest = [entry for entry in entries if as_object(entry).get("method") != method]
    return matching, rest


def workspace_folder_uris(folders: JsonValue) -> list[str]:
    return [
        uri
        for folder in as_list(folders)
        if (uri := as_str(as_object(folder).get("uri"))) is not None
    ]


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def config_str(raw: JsonObject, key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"config field {key!r} must be a string")
    return value


def config_int(raw: JsonObject, key: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    parsed = as_int(value)
    if parsed is None:
        raise TypeError(f"config field {key!r} must be an integer")
    return parsed


def config_str_list(raw: JsonObject, key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise TypeError(f"config field {key!r} must be a list of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"config field {key!r} must be a list of strings")
        items.append(item)
    return tuple(items)


def config_bool(raw: JsonObject, key: str) -> bool:
    value = raw.get(key)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise TypeError(f"config field {key!r} must be a boolean")
    return value


def config_object(raw: JsonObject, key: str) -> JsonObject | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"config field {key!r} must be an object")
    return value


@dataclass(slots=True, frozen=True)
class ServerConfig:
    name: str
    cmd: str | None = None
    args: tuple[str, ...] = ()
    port: int | None = None
    host: str = "127.0.0.1"
    initialization_options: JsonObject | None = None
    settings: JsonObject | None = None
    # The mux pulls this server's diagnostics instead of taking its pushes.
    pull_diagnostics: bool = False

    def __post_init__(self) -> None:
        if self.cmd is None and self.port is None:
            raise ValueError(f"server {self.name!r}: needs 'cmd' or 'port'")

    @classmethod
    def from_json(cls, raw: JsonObject, index: int) -> Self:
        cmd = config_str(raw, "cmd")
        name = config_str(raw, "name")
        return cls(
            name=name if name is not None else (cmd or f"server{index}"),
            cmd=cmd,
            args=config_str_list(raw, "args"),
            port=config_int(raw, "port"),
            host=config_str(raw, "host") or "127.0.0.1",
            initialization_options=config_object(raw, "initializationOptions"),
            settings=config_object(raw, "settings"),
            pull_diagnostics=config_bool(raw, "pullDiagnostics"),
        )


DEFAULT_CONFIG: tuple[ServerConfig, ...] = (
    ServerConfig(
        name="basedpyright",
        cmd="uvx",
        args=("--from", "basedpyright", "basedpyright-langserver", "--stdio"),
        pull_diagnostics=True,
    ),
    ServerConfig(name="ruff", cmd="uvx", args=("ruff", "server")),
)


def load_config(path: Path | None) -> tuple[ServerConfig, ...]:
    if path is None:
        return DEFAULT_CONFIG
    data = path.read_bytes()
    document: JsonValue
    match path.suffix:
        case ".toml":
            document = tomllib.loads(data.decode())
        case _:
            document = load_json(data)
    entries = as_list(as_object(document).get("servers"))
    servers = tuple(
        ServerConfig.from_json(as_object(entry), i) for i, entry in enumerate(entries)
    )
    if not servers:
        raise ValueError("configuration defines no servers")
    return servers


# --------------------------------------------------------------------------
# JSON-RPC framing
# --------------------------------------------------------------------------


class Writer(Protocol):
    """What Endpoint needs from a writer (StreamWriter satisfies this)."""

    def write(self, data: bytes) -> None: ...
    async def drain(self) -> None: ...


class Endpoint:
    """One side of an LSP byte stream: framed reads and locked writes."""

    def __init__(self, reader: asyncio.StreamReader, writer: Writer, label: str):
        self.reader: asyncio.StreamReader = reader
        self.writer: Writer = writer
        self.label: str = label
        self.lock: asyncio.Lock = asyncio.Lock()

    async def read(self) -> JsonValue | None:
        """Read one decoded frame; None on clean EOF."""
        length: int | None = None
        while True:
            line = await self.reader.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                break
            name, _, value = line.partition(b":")
            if name.lower() == b"content-length":
                length = int(value)
        if length is None:
            raise RuntimeError("frame missing Content-Length header")
        body = await self.reader.readexactly(length)
        message = load_json(body)
        trace_wire(f"{self.label} ->", message)
        return message

    async def send(self, message: Message) -> None:
        encoded = encode_message(message)
        trace_wire(f"{self.label} <-", encoded)
        body = json.dumps(encoded, separators=(",", ":")).encode()
        frame = b"Content-Length: %d\r\n\r\n%s" % (len(body), body)
        async with self.lock:
            self.writer.write(frame)
            await self.writer.drain()

    async def notify(self, method: str, params: JsonValue) -> None:
        await self.send(Notification(method, params))


class ThreadWriter:
    """Writer over a blocking binary stream; flushes off the event loop.

    Used for console stdout on Windows, where the Proactor loop cannot
    attach pipe transports to the standard handles.
    """

    def __init__(self, raw: BinaryIO):
        self.raw: BinaryIO = raw
        self.buffer: bytearray = bytearray()

    def write(self, data: bytes) -> None:
        self.buffer += data

    async def drain(self) -> None:
        pending, self.buffer = bytes(self.buffer), bytearray()
        if pending:
            await asyncio.to_thread(self.flush, pending)

    def flush(self, data: bytes) -> None:
        written = self.raw.write(data)
        if written != len(data):
            raise OSError("short write to stdout")
        self.raw.flush()


def pump_stdin(reader: asyncio.StreamReader, loop: asyncio.AbstractEventLoop) -> None:
    """Daemon thread: blocking stdin reads fed into an asyncio StreamReader.

    Reads the raw descriptor with os.read: a daemon thread blocked inside
    BufferedReader holds its lock and aborts interpreter finalization.
    """
    fd = sys.stdin.fileno()
    while chunk := os.read(fd, 65536):
        if loop.call_soon_threadsafe(reader.feed_data, chunk).cancelled():
            return  # the loop is shutting down; stop pumping
    if loop.call_soon_threadsafe(reader.feed_eof).cancelled():
        log("stdin EOF arrived after the loop closed")


def use_thread_bridge() -> bool:
    return sys.platform == "win32" or bool(os.environ.get("LSP_MUX_THREAD_STDIO"))


async def stdio_endpoint() -> Endpoint:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    if use_thread_bridge():
        threading.Thread(
            target=pump_stdin, args=(reader, loop), name="stdin", daemon=True
        ).start()
        debug("client stdio: thread bridge")
        return Endpoint(reader, ThreadWriter(sys.stdout.buffer), "client")
    read_transport, read_protocol = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer
    )
    transport, protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(transport, protocol, None, loop)
    debug("client stdio: pipe transports", read_transport, read_protocol)
    return Endpoint(reader, writer, "client")


# --------------------------------------------------------------------------
# Server connection
# --------------------------------------------------------------------------


class ShuttingDown(Exception):
    """Raised internally to unwind the task group after 'exit'."""


class RemoteError(Exception):
    def __init__(self, error: RpcError):
        super().__init__(error.message)
        self.error: RpcError = error


@dataclass(slots=True)
class Pending:
    future: asyncio.Future[JsonValue]
    client_id: MsgId | None  # set when the request originated at the client


@dataclass(slots=True)
class DocumentHold:
    """Diagnostics gate for a document with an in-flight edit.

    Created when didOpen/didChange passes through; merged publishes for the
    document are withheld until every server has reported for this version
    (a publish without a version counts). Once the settle timer expires, the
    hold stops waiting for push servers, whose silence means their previous
    diagnostics still stand. Pull servers are always waited for: their answer
    for this version is already on its way, and anything they reported before
    it describes older text.
    """

    version: int | None
    servers_reported: set[int]
    timer: asyncio.Task[None] | None = None
    expired: bool = False


def covers_held_version(hold: DocumentHold, version: int | None) -> bool:
    """Whether a publish is current enough to count toward releasing a hold.

    Publishes without a version (basedpyright's close-time clears) are taken
    at face value as current.
    """
    if hold.version is None or version is None:
        return True
    return version >= hold.version


async def wait_for_event(event: asyncio.Event) -> None:
    """Block until set; Event.wait() returns True, which carries no information."""
    if not await event.wait():
        raise RuntimeError("asyncio.Event.wait returned without the event set")


class TaskKeeper:
    """Holds references to fire-and-forget tasks until they finish."""

    def __init__(self) -> None:
        self.tasks: set[asyncio.Task[None]] = set()

    def spawn(self, coro: Coroutine[None, None, None]) -> None:
        task = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


class Server:
    """A child (or socket-connected) LSP server."""

    def __init__(self, config: ServerConfig, index: int, tasks: TaskKeeper):
        self.config: ServerConfig = config
        self.index: int = index
        self.tasks: TaskKeeper = tasks
        self.capabilities: JsonObject = {}
        self.proc: asyncio.subprocess.Process | None = None
        self.connection: Endpoint | None = None
        self.next_id: int = 0
        self.pending: dict[int, Pending] = {}
        # client request id -> id we used toward this server (for $/cancelRequest)
        self.inflight_for_client: dict[MsgId, int] = {}

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def endpoint(self) -> Endpoint:
        if self.connection is None:
            raise RuntimeError(f"server {self.name!r} has not been started")
        return self.connection

    async def start(self) -> None:
        cfg = self.config
        if cfg.cmd is None:
            debug(f"{self.name}: connecting to {cfg.host}:{cfg.port}")
            reader, writer = await asyncio.open_connection(cfg.host, cfg.port)
            self.connection = Endpoint(reader, writer, self.name)
            return
        debug(f"{self.name}: spawning", [cfg.cmd, *cfg.args])
        proc = await asyncio.create_subprocess_exec(
            cfg.cmd,
            *cfg.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=sys.stderr,
        )
        if proc.stdout is None or proc.stdin is None:
            raise RuntimeError(f"server {self.name!r}: subprocess has no stdio pipes")
        debug(f"{self.name}: spawned pid {proc.pid}")
        self.proc = proc
        self.connection = Endpoint(proc.stdout, proc.stdin, self.name)

    def supports(self, capability: str) -> bool:
        return bool(self.capabilities.get(capability))

    def send_request(
        self, method: str, params: JsonValue, *, client_id: MsgId | None = None
    ) -> asyncio.Future[JsonValue]:
        """Forward a request; resolves with the result or raises RemoteError."""
        endpoint = self.endpoint
        self.next_id += 1
        id_ = self.next_id
        future: asyncio.Future[JsonValue] = asyncio.get_running_loop().create_future()
        self.pending[id_] = Pending(future, client_id)
        if client_id is not None:
            self.inflight_for_client[client_id] = id_
        self.tasks.spawn(endpoint.send(Request(id_, method, params)))
        return future

    def resolve(self, response: Response) -> bool:
        """Route a response from this server to its waiting future."""
        pending = (
            self.pending.pop(response.id, None)
            if isinstance(response.id, int)
            else None
        )
        if pending is None:
            return False
        if (
            pending.client_id is not None
            and pending.client_id in self.inflight_for_client
        ):
            del self.inflight_for_client[pending.client_id]
        if pending.future.cancelled():
            return True
        if response.error is not None:
            pending.future.set_exception(RemoteError(response.error))
        else:
            pending.future.set_result(response.result)
        return True

    def fail_all(self, reason: str) -> None:
        for pending in self.pending.values():
            if not pending.future.done():
                pending.future.set_exception(
                    RemoteError(RpcError(INTERNAL_ERROR, reason))
                )
        self.pending.clear()
        self.inflight_for_client.clear()


# --------------------------------------------------------------------------
# Proxy
# --------------------------------------------------------------------------


class Proxy:
    def __init__(
        self,
        client: Endpoint,
        servers: Sequence[Server],
        tasks: TaskKeeper,
        platform: Platform,
        settle_seconds: float = 1.0,
    ):
        self.client: Endpoint = client
        self.servers: list[Server] = list(servers)
        self.primary: Server = self.servers[0]
        self.tasks: TaskKeeper = tasks
        self.platform: Platform = platform
        self.settle_seconds: float = settle_seconds
        # proxy-assigned id -> originating server, for server->client requests
        self.pending_client_requests: dict[int, tuple[Server, MsgId]] = {}
        self.next_client_id: int = 0
        # document -> {server index: diagnostics list}
        self.diagnostics: dict[DocumentId, dict[int, list[JsonValue]]] = {}
        # document -> gate withholding merged publishes while an edit settles
        self.holds: dict[DocumentId, DocumentHold] = {}
        # document -> its client URI spelling and latest version
        self.open_documents: dict[DocumentId, OpenDocument] = {}
        self.workspace: Workspace = Workspace(platform)
        # executeCommand command name -> server
        self.command_owners: dict[str, Server] = {}
        self.exiting: asyncio.Event = asyncio.Event()
        # 'exit' arrives as a notification and is handled inline, while requests
        # run as tasks: without this gate it can overtake an in-flight shutdown.
        self.shutdown_requested: bool = False
        self.shutdown_finished: asyncio.Event = asyncio.Event()

    def document(self, uri: str) -> DocumentId:
        """The client's id for this document when open, else a fresh one."""
        doc = DocumentId.from_uri(uri, self.platform)
        open_doc = self.open_documents.get(doc)
        return doc if open_doc is None else open_doc.id

    # ---- lifecycle -------------------------------------------------------

    async def run(self) -> None:
        for server in self.servers:
            await server.start()
        async with asyncio.TaskGroup() as group:
            loops: list[asyncio.Task[None]] = [
                group.create_task(self.server_loop(server), name=server.name)
                for server in self.servers
            ]
            loops.append(group.create_task(self.client_loop(), name="client"))
            loops.append(group.create_task(self.watch_exit(), name="exit-watch"))
            debug("running", len(loops), "loops")

    async def watch_exit(self) -> None:
        await wait_for_event(self.exiting)
        procs = [s.proc for s in self.servers if s.proc is not None]
        try:
            async with asyncio.timeout(5):
                codes = await asyncio.gather(*(p.wait() for p in procs))
                debug("server exit codes:", codes)
        except TimeoutError:
            for proc in procs:
                if proc.returncode is None:
                    proc.kill()
        raise ShuttingDown  # unwind the TaskGroup, cancelling the loops

    # ---- client -> proxy -------------------------------------------------

    async def client_loop(self) -> None:
        while (raw := await self.client.read()) is not None:
            match parse_message(raw):
                case Request() as request:
                    # Mark here, not inside the task: a client that pipelines
                    # shutdown and exit leaves both buffered, and the exit
                    # notification is handled before the task first runs.
                    if request.method == "shutdown":
                        self.shutdown_requested = True
                    self.tasks.spawn(self.client_request(request))
                case Notification() as notification:
                    await self.client_notification(notification)
                case Response() as response:  # to a server-initiated request
                    await self.route_client_response(response)
                case None:
                    log("unrecognized message from client:", raw)
        self.exiting.set()

    async def client_request(self, request: Request) -> None:
        id_, method, params = request.id, request.method, request.params
        try:
            match method:
                case "initialize":
                    result = await self.initialize(params)
                case "shutdown":
                    for server, outcome in zip(
                        self.servers, await self.gather_all("shutdown", None)
                    ):
                        if isinstance(outcome, BaseException):
                            log(f"{server.name}: shutdown failed:", outcome)
                    self.shutdown_finished.set()
                    result = None
                case "workspace/executeCommand":
                    result = await self.execute_command(id_, params)
                case _ if method in MERGED_REQUESTS:
                    result = await self.fan_out(id_, method, params)
                case "codeAction/resolve":
                    result = await self.resolve_tagged(id_, method, params)
                case _:
                    server = self.route(method)
                    result = await server.send_request(method, params, client_id=id_)
            await self.client.send(Response(id_, result=result))
        except RemoteError as exc:
            await self.client.send(Response(id_, error=exc.error))
        except Exception as exc:  # noqa: BLE001 - report, keep serving
            log(f"request {method} failed:", exc)
            await self.client.send(
                Response(id_, error=RpcError(INTERNAL_ERROR, str(exc)))
            )

    async def client_notification(self, notification: Notification) -> None:
        method, params = notification.method, notification.params
        match method:
            case "$/cancelRequest":
                await self.cancel(as_msg_id(as_object(params).get("id")))
            case "exit":
                await self.await_shutdown()
                for server in self.servers:
                    if server.connection is not None:
                        await server.endpoint.notify("exit", None)
                self.exiting.set()
            case "workspace/didChangeConfiguration":
                for server in self.servers:
                    settings = server.config.settings
                    payload: JsonValue = (
                        params if settings is None else {"settings": settings}
                    )
                    await server.endpoint.notify(method, payload)
            case _ if method in BROADCAST_NOTIFICATIONS:
                self.track_client_state(method, params)
                for server in self.servers:
                    await server.endpoint.notify(method, params)
                # Pull only after the edit is written, so the answer covers it.
                if (edited := self.edited_document(method, params)) is not None:
                    for server in self.servers:
                        if server.config.pull_diagnostics:
                            self.pull_open_documents(server, first=edited)
            case _:
                await self.primary.endpoint.notify(method, params)

    async def await_shutdown(self) -> None:
        """Let an in-flight shutdown finish before forwarding 'exit'.

        A client that fires shutdown and exit without waiting in between would
        otherwise have the servers see exit first, which they treat as a crash.
        """
        if not self.shutdown_requested or self.shutdown_finished.is_set():
            return
        with suppress(TimeoutError):
            async with asyncio.timeout(2):
                await wait_for_event(self.shutdown_finished)

    async def cancel(self, client_id: MsgId | None) -> None:
        if client_id is None:
            return
        for server in self.servers:
            if (mapped := server.inflight_for_client.get(client_id)) is not None:
                await server.endpoint.notify("$/cancelRequest", {"id": mapped})

    async def route_client_response(self, response: Response) -> None:
        entry = (
            self.pending_client_requests.pop(response.id, None)
            if isinstance(response.id, int)
            else None
        )
        if entry is None:
            log("response for unknown id from client:", response.id)
            return
        server, original_id = entry
        await server.endpoint.send(
            Response(original_id, result=response.result, error=response.error)
        )

    # ---- initialize ------------------------------------------------------

    async def initialize(self, params: JsonValue) -> JsonValue:
        request = as_object(params)
        self.record_workspace_roots(request)
        futures: list[asyncio.Future[JsonValue]] = []
        for server in self.servers:
            per_server = dict(request)
            match server.config.initialization_options:
                case None if server is self.primary:
                    pass  # primary inherits the client's initializationOptions
                case None:
                    per_server["initializationOptions"] = None
                case options:
                    per_server["initializationOptions"] = options
            if server.config.pull_diagnostics:
                per_server["capabilities"] = with_pull_diagnostics(
                    request.get("capabilities")
                )
            futures.append(server.send_request("initialize", per_server))
        results = [as_object(result) for result in await asyncio.gather(*futures)]

        for server, result in zip(self.servers, results):
            server.capabilities = as_object(result.get("capabilities"))
            self.register_commands(server)
            debug(
                f"{server.name}: initialized;",
                "serverInfo:",
                result.get("serverInfo"),
                "capabilities:",
                sorted(server.capabilities),
            )
        debug("workspace roots:", sorted(self.workspace.roots))

        merged = copy.deepcopy(results[0])
        capabilities = as_object(merged.get("capabilities"))
        merged["capabilities"] = capabilities
        for server in self.servers[1:]:
            for key, value in server.capabilities.items():
                if key not in capabilities:
                    capabilities[key] = value
        capabilities["codeActionProvider"] = self.merge_code_action_capability()
        commands: list[JsonValue] = [*sorted(self.command_owners)]
        capabilities["executeCommandProvider"] = {"commands": commands}
        return merged

    def record_workspace_roots(self, params: JsonObject) -> None:
        """Seed the roots from initialize: workspaceFolders, else rootUri, else rootPath."""
        uris = workspace_folder_uris(params.get("workspaceFolders"))
        root_uri = as_str(params.get("rootUri"))
        if not uris and root_uri is not None:
            uris = [root_uri]
        self.workspace = self.workspace.with_folders(uris, ())
        root_path = as_str(params.get("rootPath"))
        if not self.workspace.roots and root_path is not None:
            self.workspace = self.workspace.with_local_root(root_path)

    def register_commands(self, server: Server) -> None:
        provider = as_object(server.capabilities.get("executeCommandProvider"))
        for command in as_list(provider.get("commands")):
            if isinstance(command, str) and command not in self.command_owners:
                self.command_owners[command] = server

    def merge_code_action_capability(self) -> JsonValue:
        providers = [
            s.capabilities["codeActionProvider"]
            for s in self.servers
            if s.supports("codeActionProvider")
        ]
        if not providers:
            return False
        kinds: set[str] = set()
        resolve = False
        for provider in providers:
            body = as_object(provider)
            kinds.update(
                kind
                for kind in as_list(body.get("codeActionKinds"))
                if isinstance(kind, str)
            )
            resolve = resolve or bool(body.get("resolveProvider"))
        if not kinds and not resolve:
            return True
        merged: JsonObject = {}
        if kinds:
            kind_list: list[JsonValue] = [*sorted(kinds)]
            merged["codeActionKinds"] = kind_list
        if resolve:
            merged["resolveProvider"] = True
        return merged

    # ---- request routing -------------------------------------------------

    def route(self, method: str) -> Server:
        capability = CAPABILITY_FOR_METHOD.get(method)
        if capability is None or self.primary.supports(capability):
            return self.primary
        for server in self.servers[1:]:
            if server.supports(capability):
                return server
        return self.primary  # let the primary answer with its own error

    async def gather_all(
        self, method: str, params: JsonValue
    ) -> list[JsonValue | BaseException]:
        return await asyncio.gather(
            *(s.send_request(method, params) for s in self.servers),
            return_exceptions=True,
        )

    async def fan_out(self, id_: MsgId, method: str, params: JsonValue) -> JsonValue:
        capability = CAPABILITY_FOR_METHOD[method]
        targets = [s for s in self.servers if s.supports(capability)]
        if not targets:
            raise RemoteError(
                RpcError(METHOD_NOT_FOUND, f"no server supports {method}")
            )
        results = await asyncio.gather(
            *(s.send_request(method, params, client_id=id_) for s in targets),
            return_exceptions=True,
        )
        merged: list[JsonValue] = []
        for server, result in zip(targets, results):
            match result:
                case BaseException():
                    log(f"{server.name}: {method} failed:", result)
                case list():
                    merged.extend(self.tag_origin(item, server) for item in result)
                case _:
                    pass
        return merged

    def tag_origin(self, item: JsonValue, server: Server) -> JsonValue:
        if isinstance(item, dict) and "command" not in item:  # CodeAction literal
            item["data"] = {TAG: server.index, "data": item.get("data")}
        return item

    async def resolve_tagged(
        self, id_: MsgId, method: str, params: JsonValue
    ) -> JsonValue:
        body = as_object(params)
        tag = as_object(body.get("data"))
        index = as_int(tag.get(TAG))
        if index is None or not 0 <= index < len(self.servers):
            server = self.route(method)
            return await server.send_request(method, params, client_id=id_)
        server = self.servers[index]
        untagged = dict(body)
        original = tag.get("data")
        if original is None:
            del untagged["data"]
        else:
            untagged["data"] = original
        return await server.send_request(method, untagged, client_id=id_)

    async def execute_command(self, id_: MsgId, params: JsonValue) -> JsonValue:
        fallback = self.route("workspace/executeCommand")
        command = as_str(as_object(params).get("command"))
        server = (
            fallback if command is None else self.command_owners.get(command, fallback)
        )
        return await server.send_request(
            "workspace/executeCommand", params, client_id=id_
        )

    # ---- server -> proxy -------------------------------------------------

    async def server_loop(self, server: Server) -> None:
        while (raw := await server.endpoint.read()) is not None:
            match parse_message(raw):
                case Request() as request:
                    await self.server_request(server, request)
                case Notification(
                    method="textDocument/publishDiagnostics", params=params
                ):
                    await self.publish_diagnostics(server, params)
                case Notification() as notification:
                    await self.client.send(notification)
                case Response() as response if server.resolve(response):
                    pass
                case _:
                    log(f"{server.name}: unmatched message:", raw)
        server.fail_all(f"{server.name} closed its connection")
        if not self.exiting.is_set():
            code = server.proc.returncode if server.proc is not None else None
            log(f"{server.name}: connection closed unexpectedly; returncode {code}")
            if server is self.primary:
                self.exiting.set()

    async def server_request(self, server: Server, request: Request) -> None:
        """Answer a pull server's diagnostic bookkeeping here; forward the rest.

        The client never advertised pull diagnostics, so their registrations
        and refresh requests are the mux's to handle.
        """
        match request.method:
            case "client/registerCapability" if server.config.pull_diagnostics:
                await self.strip_pull_entries(server, request, "registrations")
            case "client/unregisterCapability" if server.config.pull_diagnostics:
                await self.strip_pull_entries(server, request, "unregisterations")
            case "workspace/diagnostic/refresh" if server.config.pull_diagnostics:
                await server.endpoint.send(Response(request.id, result=None))
                self.pull_open_documents(server)
            case _:
                await self.forward_server_request(server, request)

    async def strip_pull_entries(
        self, server: Server, request: Request, key: str
    ) -> None:
        """Drop textDocument/diagnostic entries; the mux pulls whatever is registered."""
        params = as_object(request.params)
        pulls, rest = partition_by_method(
            as_list(params.get(key)), "textDocument/diagnostic"
        )
        debug(f"{server.name}: {request.method} consumed", pulls)
        if not rest:
            await server.endpoint.send(Response(request.id, result=None))
            return
        forwarded = dict(params)
        forwarded[key] = rest
        await self.forward_server_request(
            server, Request(request.id, request.method, forwarded)
        )

    async def forward_server_request(self, server: Server, request: Request) -> None:
        self.next_client_id += 1
        proxy_id = self.next_client_id
        self.pending_client_requests[proxy_id] = (server, request.id)
        await self.client.send(Request(proxy_id, request.method, request.params))

    async def publish_diagnostics(self, server: Server, params: JsonValue) -> None:
        publish = parse_publish_diagnostics(params)
        if publish is None:
            return
        doc = self.document(publish.uri)
        debug(
            f"{server.name}: publish {len(publish.diagnostics)} diagnostics",
            "version",
            publish.version,
            "uri",
            publish.uri,
            "-> client uri",
            doc.uri,
            "key",
            doc.key,
            "open docs",
            [open_doc.id.uri for open_doc in self.open_documents.values()],
        )
        if server.config.pull_diagnostics and doc in self.open_documents:
            debug(f"{server.name}: ignoring push for open {doc.uri}; it is pulled")
            return
        match self.workspace.membership(doc):
            case Membership.outside:
                debug(
                    f"{server.name}: {doc.key} outside workspace roots; emitting empty"
                )
                await self.client.notify(
                    "textDocument/publishDiagnostics",
                    {"uri": doc.uri, "diagnostics": []},
                )
                return
            case Membership.inside | Membership.unfiltered:
                pass
        await self.accept_diagnostics(server, doc, publish.version, publish.diagnostics)

    async def accept_diagnostics(
        self,
        server: Server,
        doc: DocumentId,
        version: int | None,
        diagnostics: list[JsonValue],
    ) -> None:
        """Store one server's diagnostics for a document; emit unless a hold waits."""
        per_doc = self.diagnostics.setdefault(doc, {})
        per_doc[server.index] = diagnostics
        hold = self.holds.get(doc)
        if hold is None:
            debug(f"{server.name}: no hold for {doc.uri}; emitting now")
            await self.emit_merged(doc, version=version)
            return
        if covers_held_version(hold, version):
            hold.servers_reported.add(server.index)
        debug(
            f"{server.name}: hold version {hold.version};",
            "reported",
            sorted(hold.servers_reported),
            "of",
            len(self.servers),
        )
        if self.hold_satisfied(hold):
            self.release_hold(doc)
            await self.emit_merged(doc, version=hold.version)

    # ---- pulled diagnostics -----------------------------------------------

    def edited_document(self, method: str, params: JsonValue) -> DocumentId | None:
        """The document an open or change notification put new text into."""
        match method:
            case "textDocument/didOpen" | "textDocument/didChange":
                ref = parse_text_document(params)
                return None if ref is None else self.document(ref.uri)
            case _:
                return None

    def pull_open_documents(
        self, server: Server, first: DocumentId | None = None
    ) -> None:
        """Ask a pull server about every open document, first ahead of the rest.

        An edit to one document can change the diagnostics of any document
        that imports it, so every open document is asked again.
        """
        open_docs = list(self.open_documents.values())
        ordered = [doc for doc in open_docs if doc.id == first] + [
            doc for doc in open_docs if doc.id != first
        ]
        for open_doc in ordered:
            if self.workspace.membership(open_doc.id) is not Membership.outside:
                self.tasks.spawn(self.pull(server, open_doc))

    async def pull(self, server: Server, open_doc: OpenDocument) -> None:
        """Request one document's diagnostics and accept them if still current.

        A failed pull counts as an empty report, so a hold waiting on it can
        still release.
        """
        params: JsonObject = {"textDocument": {"uri": open_doc.id.uri}}
        try:
            report = await server.send_request("textDocument/diagnostic", params)
            diagnostics = as_list(as_object(report).get("items"))
        except RemoteError as exc:
            log(f"{server.name}: pull for {open_doc.id.uri} failed:", exc)
            diagnostics = []
        if self.open_documents.get(open_doc.id) != open_doc:
            debug(
                f"{server.name}: pull for {open_doc.id.uri}",
                "version",
                open_doc.version,
                "superseded; dropping",
            )
            return
        await self.accept_diagnostics(
            server, open_doc.id, open_doc.version, diagnostics
        )

    # ---- diagnostics settling ---------------------------------------------

    def track_client_state(self, method: str, params: JsonValue) -> None:
        match method:
            case "textDocument/didOpen":
                ref = parse_text_document(params)
                if ref is None:
                    return
                doc = DocumentId.from_uri(ref.uri, self.platform)
                debug("didOpen", ref.uri, "version", ref.version, "key", doc.key)
                self.open_documents[doc] = OpenDocument(doc, ref.version)
                self.begin_hold(doc, ref.version)
            case "textDocument/didChange":
                ref = parse_text_document(params)
                if ref is None:
                    return
                debug("didChange", ref.uri, "version", ref.version)
                doc = self.document(ref.uri)
                if doc in self.open_documents:
                    self.open_documents[doc] = OpenDocument(doc, ref.version)
                self.begin_hold(doc, ref.version)
            case "textDocument/didClose":
                ref = parse_text_document(params)
                if ref is None:
                    return
                doc = self.document(ref.uri)
                debug("didClose", ref.uri)
                self.release_hold(doc)
                if doc in self.open_documents:
                    del self.open_documents[doc]
            case "workspace/didChangeWorkspaceFolders":
                event = as_object(as_object(params).get("event"))
                self.workspace = self.workspace.with_folders(
                    workspace_folder_uris(event.get("added")),
                    workspace_folder_uris(event.get("removed")),
                )
            case _:
                pass

    def begin_hold(self, doc: DocumentId, version: int | None) -> None:
        if self.workspace.membership(doc) is Membership.outside:
            return
        self.release_hold(doc)
        hold = DocumentHold(version=version, servers_reported=set())
        hold.timer = asyncio.ensure_future(self.expire_hold(doc))
        self.holds[doc] = hold

    def release_hold(self, doc: DocumentId) -> None:
        hold = self.holds.pop(doc, None)
        if hold is not None and hold.timer is not None and not hold.timer.cancel():
            debug("hold timer for", doc.uri, "had already finished")

    def hold_satisfied(self, hold: DocumentHold) -> bool:
        """Whether every server the hold still waits for has reported."""
        awaited = {
            server.index
            for server in self.servers
            if server.config.pull_diagnostics or not hold.expired
        }
        return awaited <= hold.servers_reported

    async def expire_hold(self, doc: DocumentId) -> None:
        await asyncio.sleep(self.settle_seconds)
        hold = self.holds.get(doc)
        if hold is None:
            return
        hold.expired = True
        hold.timer = None  # this task: releasing the hold must not cancel it
        debug(
            f"hold expired for {doc.uri};",
            "reported",
            sorted(hold.servers_reported),
            "of",
            len(self.servers),
        )
        if self.hold_satisfied(hold):
            self.release_hold(doc)
            await self.emit_merged(doc, version=hold.version)

    async def emit_merged(self, doc: DocumentId, version: int | None) -> None:
        per_doc = self.diagnostics.get(doc, {})
        diagnostics: list[JsonValue] = [
            diagnostic for index in sorted(per_doc) for diagnostic in per_doc[index]
        ]
        merged: JsonObject = {"uri": doc.uri, "diagnostics": diagnostics}
        if version is not None:
            merged["version"] = version
        debug(
            "emit merged for",
            doc.uri,
            "version",
            version,
            "per server",
            {self.servers[i].name: len(d) for i, d in per_doc.items()},
        )
        await self.client.notify("textDocument/publishDiagnostics", merged)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


async def amain(configs: Iterable[ServerConfig]) -> None:
    client = await stdio_endpoint()
    tasks = TaskKeeper()
    servers = [Server(config, index, tasks) for index, config in enumerate(configs)]
    proxy = Proxy(client, servers, tasks, current_platform())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, proxy.exiting.set)
        except NotImplementedError:  # Windows event loops
            break
    try:
        await proxy.run()
    except* ShuttingDown:
        pass


def main(argv: Sequence[str]) -> int:
    configure_log_file()
    match argv:
        case []:
            configs = load_config(None)
        case [path]:
            configs = load_config(Path(path))
        case _:
            print(__doc__, file=sys.stderr)
            return 2
    asyncio.run(amain(configs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
