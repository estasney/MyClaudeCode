#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""lsp_mux: present several LSP servers to an editor as a single stdio server.

Claude Code registers one language server per file extension, so basedpyright
and ruff cannot both claim ``.py``. This proxy fans out to both and reports
itself as a single server.

Clean-room implementation of the multiplexing behavior described by the
lsp-proxy project (techee/lsp-proxy). No third-party dependencies.

Routing model
-------------
* The first configured server is *primary*. It receives every request the
  proxy does not route elsewhere.
* All servers receive lifecycle and document-synchronization notifications
  (didOpen/didChange/...), so each can produce diagnostics.
* ``textDocument/publishDiagnostics`` from all servers is merged per URI.
* A request whose capability the primary does not advertise is routed to the
  first server that does (e.g. formatting -> ruff when basedpyright is
  primary).
* ``textDocument/codeAction`` fans out to every server advertising the
  capability; results are concatenated. Each action's ``data`` field is
  tagged so ``codeAction/resolve`` returns to the originating server.
* ``workspace/executeCommand`` routes by command name, using the command
  registries advertised at ``initialize``.
* Server-initiated requests (``workspace/configuration``,
  ``client/registerCapability``, ...) are forwarded to the client with
  remapped ids; responses are routed back to the originating server.
* ``workspace/didChangeConfiguration`` carries a server's own ``settings``
  when its config declares them, and the client's payload otherwise. Without
  this, every server would be handed whatever settings the client meant for
  the primary.

Usage
-----
    lsp_mux.py [config.toml | config.json]

With no argument the proxy runs the built-in basedpyright + ruff
configuration. Configure it as the language-server executable.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import threading
import tomllib
from collections.abc import Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol, Self

type Json = dict[str, Any]
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


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class ServerConfig:
    name: str
    cmd: str | None = None
    args: tuple[str, ...] = ()
    port: int | None = None
    host: str = "127.0.0.1"
    initialization_options: Json | None = None
    settings: Json | None = None

    def __post_init__(self) -> None:
        if self.cmd is None and self.port is None:
            raise ValueError(f"server {self.name!r}: needs 'cmd' or 'port'")

    @classmethod
    def from_mapping(cls, raw: Json, index: int) -> Self:
        return cls(
            name=raw.get("name", raw.get("cmd", f"server{index}")),
            cmd=raw.get("cmd"),
            args=tuple(raw.get("args", ())),
            port=raw.get("port"),
            host=raw.get("host", "127.0.0.1"),
            initialization_options=raw.get("initializationOptions"),
            settings=raw.get("settings"),
        )


DEFAULT_CONFIG: tuple[ServerConfig, ...] = (
    ServerConfig(
        name="basedpyright",
        cmd="uvx",
        args=("--from", "basedpyright", "basedpyright-langserver", "--stdio"),
    ),
    ServerConfig(name="ruff", cmd="uvx", args=("ruff", "server")),
)


def load_config(path: Path | None) -> tuple[ServerConfig, ...]:
    if path is None:
        return DEFAULT_CONFIG
    data = path.read_bytes()
    match path.suffix:
        case ".toml":
            entries = tomllib.loads(data.decode())["servers"]
        case _:
            entries = json.loads(data)["servers"]
    servers = tuple(
        ServerConfig.from_mapping(entry, i) for i, entry in enumerate(entries)
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

    def __init__(self, reader: asyncio.StreamReader, writer: Writer):
        self.reader: asyncio.StreamReader = reader
        self.writer: Writer = writer
        self.lock: asyncio.Lock = asyncio.Lock()

    async def read(self) -> Json | None:
        """Read one message; None on clean EOF."""
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
        return json.loads(body)

    async def write(self, message: Json) -> None:
        body = json.dumps(message, separators=(",", ":")).encode()
        frame = b"Content-Length: %d\r\n\r\n%s" % (len(body), body)
        async with self.lock:
            self.writer.write(frame)
            await self.writer.drain()

    async def request(self, id_: MsgId, method: str, params: Any) -> None:
        await self.write(
            {"jsonrpc": JSONRPC, "id": id_, "method": method, "params": params}
        )

    async def notify(self, method: str, params: Any) -> None:
        await self.write({"jsonrpc": JSONRPC, "method": method, "params": params})

    async def respond(
        self, id_: MsgId, *, result: Any = None, error: Json | None = None
    ) -> None:
        reply: Json = {"jsonrpc": JSONRPC, "id": id_}
        if error is not None:
            reply["error"] = error
        else:
            reply["result"] = result
        await self.write(reply)


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
        self.raw.write(data)
        self.raw.flush()


def pump_stdin(reader: asyncio.StreamReader, loop: asyncio.AbstractEventLoop) -> None:
    """Daemon thread: blocking stdin reads fed into an asyncio StreamReader.

    Reads the raw descriptor with os.read: a daemon thread blocked inside
    BufferedReader holds its lock and aborts interpreter finalization.
    """
    fd = sys.stdin.fileno()
    while chunk := os.read(fd, 65536):
        loop.call_soon_threadsafe(reader.feed_data, chunk)
    loop.call_soon_threadsafe(reader.feed_eof)


def use_thread_bridge() -> bool:
    return sys.platform == "win32" or bool(os.environ.get("LSP_MUX_THREAD_STDIO"))


async def stdio_endpoint() -> Endpoint:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    if use_thread_bridge():
        threading.Thread(
            target=pump_stdin, args=(reader, loop), name="stdin", daemon=True
        ).start()
        return Endpoint(reader, ThreadWriter(sys.stdout.buffer))
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer
    )
    transport, protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(transport, protocol, None, loop)
    return Endpoint(reader, writer)


# --------------------------------------------------------------------------
# Server connection
# --------------------------------------------------------------------------


class ShuttingDown(Exception):
    """Raised internally to unwind the task group after 'exit'."""


class RemoteError(Exception):
    def __init__(self, error: Json):
        super().__init__(error.get("message", "server error"))
        self.error = error


@dataclass(slots=True)
class Pending:
    future: asyncio.Future[Any]
    client_id: MsgId | None  # set when the request originated at the client


class Server:
    """A child (or socket-connected) LSP server."""

    def __init__(self, config: ServerConfig, index: int):
        self.config = config
        self.index = index
        self.capabilities: Json = {}
        self.proc: asyncio.subprocess.Process | None = None
        self.connection: Endpoint | None = None
        self.next_id = 0
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
            reader, writer = await asyncio.open_connection(cfg.host, cfg.port)
            self.connection = Endpoint(reader, writer)
            return
        proc = await asyncio.create_subprocess_exec(
            cfg.cmd,
            *cfg.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=sys.stderr,
        )
        if proc.stdout is None or proc.stdin is None:
            raise RuntimeError(f"server {self.name!r}: subprocess has no stdio pipes")
        self.proc = proc
        self.connection = Endpoint(proc.stdout, proc.stdin)

    def supports(self, capability: str) -> bool:
        return bool(self.capabilities.get(capability))

    def send_request(
        self, method: str, params: Any, *, client_id: MsgId | None = None
    ) -> asyncio.Future[Any]:
        """Forward a request; resolves with the result or raises RemoteError."""
        endpoint = self.endpoint
        self.next_id += 1
        id_ = self.next_id
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self.pending[id_] = Pending(future, client_id)
        if client_id is not None:
            self.inflight_for_client[client_id] = id_
        asyncio.ensure_future(endpoint.request(id_, method, params))
        return future

    def resolve(self, id_: MsgId, message: Json) -> bool:
        """Route a response from this server to its waiting future."""
        pending = self.pending.pop(id_, None) if isinstance(id_, int) else None
        if pending is None:
            return False
        if pending.client_id is not None:
            self.inflight_for_client.pop(pending.client_id, None)
        if pending.future.cancelled():
            return True
        if "error" in message:
            pending.future.set_exception(RemoteError(message["error"]))
        else:
            pending.future.set_result(message.get("result"))
        return True

    def fail_all(self, reason: str) -> None:
        for pending in self.pending.values():
            if not pending.future.done():
                pending.future.set_exception(
                    RemoteError({"code": INTERNAL_ERROR, "message": reason})
                )
        self.pending.clear()
        self.inflight_for_client.clear()


# --------------------------------------------------------------------------
# Proxy
# --------------------------------------------------------------------------


class Proxy:
    def __init__(self, client: Endpoint, servers: Sequence[Server]):
        self.client = client
        self.servers = list(servers)
        self.primary = self.servers[0]
        # proxy-assigned id -> originating server, for server->client requests
        self.pending_client_requests: dict[int, tuple[Server, MsgId]] = {}
        self.next_client_id = 0
        # uri -> {server index: diagnostics list}
        self.diagnostics_by_uri: dict[str, dict[int, list[Json]]] = {}
        # executeCommand command name -> server
        self.command_owners: dict[str, Server] = {}
        self.exiting: asyncio.Event = asyncio.Event()
        # 'exit' arrives as a notification and is handled inline, while requests
        # run as tasks: without this gate it can overtake an in-flight shutdown.
        self.shutdown_requested: bool = False
        self.shutdown_finished: asyncio.Event = asyncio.Event()

    # ---- lifecycle -------------------------------------------------------

    async def run(self) -> None:
        for server in self.servers:
            await server.start()
        async with asyncio.TaskGroup() as group:
            for server in self.servers:
                group.create_task(self.server_loop(server), name=server.name)
            group.create_task(self.client_loop(), name="client")
            group.create_task(self.watch_exit(group), name="exit-watch")

    async def watch_exit(self, group: asyncio.TaskGroup) -> None:
        await self.exiting.wait()
        procs = [s.proc for s in self.servers if s.proc is not None]
        try:
            async with asyncio.timeout(5):
                await asyncio.gather(*(p.wait() for p in procs))
        except TimeoutError:
            for proc in procs:
                if proc.returncode is None:
                    proc.kill()
        raise ShuttingDown  # unwind the TaskGroup, cancelling the loops

    # ---- client -> proxy -------------------------------------------------

    async def client_loop(self) -> None:
        while (message := await self.client.read()) is not None:
            match message:
                case {"method": str(method), "id": id_}:
                    # Mark here, not inside the task: a client that pipelines
                    # shutdown and exit leaves both buffered, and the exit
                    # notification is handled before the task first runs.
                    if method == "shutdown":
                        self.shutdown_requested = True
                    asyncio.ensure_future(
                        self.client_request(id_, method, message.get("params"))
                    )
                case {"method": str(method)}:
                    await self.client_notification(method, message.get("params"))
                case {"id": id_}:  # response to a server-initiated request
                    self.route_client_response(id_, message)
                case _:
                    log("unrecognized message from client:", message)
        self.exiting.set()

    async def client_request(self, id_: MsgId, method: str, params: Any) -> None:
        try:
            match method:
                case "initialize":
                    result = await self.initialize(params)
                case "shutdown":
                    await self.gather_all("shutdown", None)
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
            await self.client.respond(id_, result=result)
        except RemoteError as exc:
            await self.client.respond(id_, error=exc.error)
        except Exception as exc:  # noqa: BLE001 - report, keep serving
            log(f"request {method} failed:", exc)
            await self.client.respond(
                id_, error={"code": INTERNAL_ERROR, "message": str(exc)}
            )

    async def client_notification(self, method: str, params: Any) -> None:
        match method:
            case "$/cancelRequest" if isinstance(params, dict):
                await self.cancel(params.get("id"))
            case "exit":
                await self.await_shutdown()
                for server in self.servers:
                    if server.connection is not None:
                        await server.endpoint.notify("exit", None)
                self.exiting.set()
            case "workspace/didChangeConfiguration":
                for server in self.servers:
                    settings = server.config.settings
                    payload = params if settings is None else {"settings": settings}
                    await server.endpoint.notify(method, payload)
            case _ if method in BROADCAST_NOTIFICATIONS:
                for server in self.servers:
                    await server.endpoint.notify(method, params)
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
                await self.shutdown_finished.wait()

    async def cancel(self, client_id: MsgId | None) -> None:
        if client_id is None:
            return
        for server in self.servers:
            if (mapped := server.inflight_for_client.get(client_id)) is not None:
                await server.endpoint.notify("$/cancelRequest", {"id": mapped})

    def route_client_response(self, id_: MsgId, message: Json) -> None:
        entry = (
            self.pending_client_requests.pop(id_, None)
            if isinstance(id_, int)
            else None
        )
        if entry is None:
            log("response for unknown id from client:", id_)
            return
        server, original_id = entry
        reply: Json = {"jsonrpc": JSONRPC, "id": original_id}
        for key in ("result", "error"):
            if key in message:
                reply[key] = message[key]
        asyncio.ensure_future(server.endpoint.write(reply))

    # ---- initialize ------------------------------------------------------

    async def initialize(self, params: Any) -> Json:
        params = params if isinstance(params, dict) else {}
        futures = []
        for server in self.servers:
            per_server = dict(params)
            match server.config.initialization_options:
                case None if server is self.primary:
                    pass  # primary inherits the client's initializationOptions
                case None:
                    per_server["initializationOptions"] = None
                case options:
                    per_server["initializationOptions"] = options
            futures.append(server.send_request("initialize", per_server))
        results = await asyncio.gather(*futures)

        for server, result in zip(self.servers, results):
            server.capabilities = result.get("capabilities", {})
            self.register_commands(server)

        merged = json.loads(json.dumps(results[0]))  # deep copy of primary's reply
        capabilities: Json = merged.setdefault("capabilities", {})
        for server in self.servers[1:]:
            for key, value in server.capabilities.items():
                if key not in capabilities:
                    capabilities[key] = value
        capabilities["codeActionProvider"] = self.merge_code_action_capability()
        capabilities["executeCommandProvider"] = {
            "commands": sorted(self.command_owners)
        }
        return merged

    def register_commands(self, server: Server) -> None:
        provider = server.capabilities.get("executeCommandProvider")
        if isinstance(provider, dict):
            for command in provider.get("commands", ()):
                self.command_owners.setdefault(command, server)

    def merge_code_action_capability(self) -> bool | Json:
        providers = [
            s.capabilities["codeActionProvider"]
            for s in self.servers
            if s.supports("codeActionProvider")
        ]
        if not providers:
            return False
        kinds = {
            kind
            for provider in providers
            if isinstance(provider, dict)
            for kind in provider.get("codeActionKinds", ())
        }
        resolve = any(
            isinstance(p, dict) and p.get("resolveProvider") for p in providers
        )
        if not kinds and not resolve:
            return True
        merged: Json = {}
        if kinds:
            merged["codeActionKinds"] = sorted(kinds)
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

    async def gather_all(self, method: str, params: Any) -> list[Any]:
        return await asyncio.gather(
            *(s.send_request(method, params) for s in self.servers),
            return_exceptions=True,
        )

    async def fan_out(self, id_: MsgId, method: str, params: Any) -> list[Json]:
        capability = CAPABILITY_FOR_METHOD[method]
        targets = [s for s in self.servers if s.supports(capability)]
        if not targets:
            raise RemoteError(
                {"code": METHOD_NOT_FOUND, "message": f"no server supports {method}"}
            )
        results = await asyncio.gather(
            *(s.send_request(method, params, client_id=id_) for s in targets),
            return_exceptions=True,
        )
        merged: list[Json] = []
        for server, result in zip(targets, results):
            match result:
                case BaseException():
                    log(f"{server.name}: {method} failed:", result)
                case list():
                    merged.extend(self.tag_origin(item, server) for item in result)
        return merged

    def tag_origin(self, item: Json, server: Server) -> Json:
        if isinstance(item, dict) and "command" not in item:  # CodeAction literal
            item["data"] = {TAG: server.index, "data": item.get("data")}
        return item

    async def resolve_tagged(self, id_: MsgId, method: str, params: Any) -> Any:
        match params:
            case {"data": {"__lsp_mux__": int(index), "data": original}}:
                server = self.servers[index]
                params = {**params, "data": original}
                if original is None:
                    del params["data"]
            case _:
                server = self.route(method)
        return await server.send_request(method, params, client_id=id_)

    async def execute_command(self, id_: MsgId, params: Any) -> Any:
        fallback = self.route("workspace/executeCommand")
        match params:
            case {"command": str(command)}:
                server = self.command_owners.get(command, fallback)
            case _:
                server = fallback
        return await server.send_request(
            "workspace/executeCommand", params, client_id=id_
        )

    # ---- server -> proxy -------------------------------------------------

    async def server_loop(self, server: Server) -> None:
        while (message := await server.endpoint.read()) is not None:
            match message:
                case {"method": str(method), "id": id_}:
                    await self.forward_server_request(server, id_, method, message)
                case {"method": "textDocument/publishDiagnostics", "params": params}:
                    await self.publish_diagnostics(server, params)
                case {"method": str(method)}:
                    await self.client.notify(method, message.get("params"))
                case {"id": id_} if server.resolve(id_, message):
                    pass
                case _:
                    log(f"{server.name}: unmatched message:", message)
        server.fail_all(f"{server.name} closed its connection")
        if not self.exiting.is_set():
            log(f"{server.name}: connection closed unexpectedly")
            if server is self.primary:
                self.exiting.set()

    async def forward_server_request(
        self, server: Server, id_: MsgId, method: str, message: Json
    ) -> None:
        self.next_client_id += 1
        proxy_id = self.next_client_id
        self.pending_client_requests[proxy_id] = (server, id_)
        await self.client.request(proxy_id, method, message.get("params"))

    async def publish_diagnostics(self, server: Server, params: Json) -> None:
        uri = params.get("uri")
        if not isinstance(uri, str):
            return
        per_uri = self.diagnostics_by_uri.setdefault(uri, {})
        per_uri[server.index] = params.get("diagnostics", [])
        merged: Json = {
            "uri": uri,
            "diagnostics": [
                diagnostic for index in sorted(per_uri) for diagnostic in per_uri[index]
            ],
        }
        if "version" in params:
            merged["version"] = params["version"]
        await self.client.notify("textDocument/publishDiagnostics", merged)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


async def amain(configs: Iterable[ServerConfig]) -> None:
    client = await stdio_endpoint()
    servers = [Server(config, index) for index, config in enumerate(configs)]
    proxy = Proxy(client, servers)
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
