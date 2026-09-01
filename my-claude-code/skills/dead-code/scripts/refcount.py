# /// script
# requires-python = ">=3.11"
# dependencies = ["basedpyright>=1.13"]
# ///
"""Count references for every module-level symbol in a Python codebase using basedpyright's LSP.

Symbols with zero references are dead-code candidates.

Usage: uv run refcount.py <project_root> [<path> ...] [--zero-only] [--json]

Each optional path is a Python file or directory inside the project root; when
given, only their symbols are counted. References are searched project-wide.
"""

from __future__ import annotations

import argparse
import json
import queue
import shutil
import subprocess
import sys
import threading
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from itertools import count
from pathlib import Path
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class CountableSymbol:
    """A symbol worth counting references for, located by its selectionRange start."""

    name: str
    kind: str
    line: int
    character: int


@dataclass(frozen=True)
class ReferenceSource:
    file: str
    count: int


@dataclass(frozen=True)
class SymbolReferences:
    file: str
    line: int
    kind: str
    symbol: str
    references: int
    referenced_from: list[ReferenceSource]


@dataclass
class LspServer:
    proc: subprocess.Popen[bytes]
    timeout: float
    debug: bool
    request_ids: count[int] = field(default_factory=lambda: count(1))
    workspace_scanned: bool = False
    inbox: queue.Queue[dict[str, object] | Exception | None] = field(default_factory=queue.Queue)
    recent: deque[str] = field(default_factory=lambda: deque(maxlen=10))

    @classmethod
    def start(cls, command: str, timeout: float, debug: bool) -> LspServer:
        proc = subprocess.Popen(
            [command, "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None if debug else subprocess.DEVNULL,
        )
        srv = cls(proc, timeout, debug)
        threading.Thread(target=srv.pump_messages, daemon=True).start()
        return srv

    def trace(self, direction: str, message: dict[str, object]) -> None:
        summary = summarize(message)
        if direction == "<-":
            self.recent.append(summary)
        if self.debug:
            print(f"refcount {direction} {summary}", file=sys.stderr)

    def pump_messages(self) -> None:
        """Reader thread: move every server message into the inbox; None marks the end of the stream."""
        try:
            while (message := self.read_message()) is not None:
                self.inbox.put(message)
            self.inbox.put(None)
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            self.inbox.put(exc)

    def write_message(self, msg: dict[str, object]) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("language server stdin is closed")
        raw = json.dumps(msg).encode()
        self.trace("->", msg)
        self.proc.stdin.writelines([f"Content-Length: {len(raw)}\r\n\r\n".encode(), raw])
        self.proc.stdin.flush()

    def notify(self, method: str, params: object) -> None:
        self.write_message({"jsonrpc": "2.0", "method": method, "params": params})

    def read_message(self) -> dict[str, object] | None:
        if self.proc.stdout is None:
            raise RuntimeError("language server stdout is closed")
        headers: dict[str, str] = {}
        while True:
            line = self.proc.stdout.readline().decode().strip()
            if not line:
                break
            key, sep, val = line.partition(":")
            if sep:
                headers[key.lower()] = val.strip()
        if "content-length" not in headers:
            return None
        body = self.proc.stdout.read(int(headers["content-length"]))
        message: object = json.loads(body)
        if not isinstance(message, dict):
            raise TypeError("language server sent a non-object message")
        return message

    def read(self, waiting_for: str) -> dict[str, object]:
        try:
            message = self.inbox.get(timeout=self.timeout)
        except queue.Empty:
            history = "; ".join(self.recent) or "nothing"
            detail = f"waiting for {waiting_for}. Last received: {history}"
            raise TimeoutError(f"no message from language server in {self.timeout:g}s while {detail}") from None
        if message is None:
            raise RuntimeError(f"language server closed the connection while waiting for {waiting_for}")
        if isinstance(message, Exception):
            raise message
        self.trace("<-", message)
        return message

    def request(self, method: str, params: object) -> object:
        req_id = next(self.request_ids)
        self.write_message({"jsonrpc": "2.0", "method": method, "params": params, "id": req_id})
        while True:
            match self.read(f"the {method} response (id {req_id})"):
                case {"id": rid, "result": result} if rid == req_id:
                    return result
                case {"id": rid, "error": err} if rid == req_id:
                    raise RuntimeError(f"{method}: {err}")
                case _:
                    continue  # server notifications, diagnostics, logs

    def wait_for_diagnostics(self, path: Path) -> None:
        while True:
            match self.read(f"publishDiagnostics for {path}"):
                case {"method": "textDocument/publishDiagnostics", "params": {"uri": str(u)}} if (
                    path_from_uri(u) == path
                ):
                    return
                case _:
                    continue

    def open_document(self, path: Path) -> str:
        """Open path on the server and return its URI.

        The first open waits for diagnostics: the server scans the workspace on a timer
        after initialize, and references requested before that scan find nothing.
        """
        uri = path.as_uri()
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": path.read_text(encoding="utf-8"),
                }
            },
        )
        if not self.workspace_scanned:
            self.wait_for_diagnostics(path)
            self.workspace_scanned = True
        return uri

    def initialize(self, root: Path) -> None:
        result = self.request(
            "initialize",
            {
                "processId": None,
                "rootUri": root.as_uri(),
                "capabilities": {
                    "textDocument": {
                        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True}
                    }
                },
                "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
            },
        )
        if not isinstance(result, dict):
            raise TypeError(f"initialize: unexpected response {result!r}")
        self.notify("initialized", {})

    def shutdown(self) -> None:
        result = self.request("shutdown", None)
        if result is not None:
            raise RuntimeError(f"shutdown: unexpected response {result!r}")
        self.notify("exit", None)


def summarize(message: dict[str, object]) -> str:
    """One line per JSON-RPC message: method or id, plus the document URI when there is one."""
    head = str(message.get("method") or f"response #{message.get('id')}")
    if "error" in message:
        head = f"error #{message.get('id')}: {message['error']}"
    params = message.get("params")
    if not isinstance(params, dict):
        return head
    if isinstance(params.get("message"), str):
        return f"{head}: {params['message']}"
    uri = params.get("uri")
    if not isinstance(uri, str):
        text_document = params.get("textDocument")
        uri = text_document.get("uri") if isinstance(text_document, dict) else None
    return f"{head} {uri}" if isinstance(uri, str) else head


def path_from_uri(uri: str) -> Path:
    """Decode a file URI; the server spells a Windows drive as /c%3A/ where Path.as_uri gives /C:/."""
    path = unquote(urlparse(uri).path)
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path)


def workspace_root(target: Path) -> Path:
    """Ascend out of the package containing target, so absolute imports resolve.

    Rooting the server inside a package breaks import binding, which zeroes every
    cross-file reference count.
    """
    root = target
    while (root / "__init__.py").exists():
        root = root.parent
    return root


def language_server_command() -> str:
    """Resolve basedpyright-langserver, preferring the copy uv installed alongside this interpreter."""
    bin_dir = Path(sys.executable).parent
    for bundled in (bin_dir / "basedpyright-langserver", bin_dir / "basedpyright-langserver.exe"):
        if bundled.exists():
            return str(bundled)
    on_path = shutil.which("basedpyright-langserver")
    if on_path is None:
        raise RuntimeError("basedpyright-langserver not found; run this script with uv run")
    return on_path


def selection_start(sym: dict[str, object]) -> tuple[int, int] | None:
    selection = sym.get("selectionRange")
    if not isinstance(selection, dict):
        return None
    start = selection.get("start")
    if not isinstance(start, dict):
        return None
    line, character = start.get("line"), start.get("character")
    if isinstance(line, int) and isinstance(character, int):
        return line, character
    return None


def countable_symbols(symbols: object, kind_labels: dict[int, str]) -> list[CountableSymbol]:
    """Select the module-level symbols worth counting from a documentSymbol response.

    Only the top level of the hierarchy is taken: a class counts as one unit, so its
    methods and attributes are never queried individually, and anything inside a
    function body is a local whose count says nothing about dead code. __all__ is
    skipped: star imports credit their references to the exported symbols themselves,
    so its own count is always zero and says nothing.
    """
    out: list[CountableSymbol] = []
    if not isinstance(symbols, list):
        return out
    for sym in symbols:
        if not isinstance(sym, dict):
            continue
        name = sym.get("name")
        kind = sym.get("kind")
        start = selection_start(sym)
        if name == "__all__":
            continue
        if isinstance(name, str) and isinstance(kind, int) and kind in kind_labels and start is not None:
            out.append(CountableSymbol(name, kind_labels[kind], start[0], start[1]))
    return out


def target_problem(root: Path, target: Path) -> str | None:
    if not target.is_relative_to(root):
        return f"{target} is outside {root}"
    if not target.exists():
        return f"{target} does not exist"
    if target.is_file() and target.suffix != ".py":
        return f"{target} is not a Python file"
    return None


def python_files(targets: list[Path]) -> list[Path]:
    skipped = {"node_modules", "__pycache__"}
    found: set[Path] = set()
    for target in targets:
        candidates = [target] if target.is_file() else target.rglob("*.py")
        found.update(
            p
            for p in candidates
            if not any(part.startswith(".") or part in skipped for part in p.parts)
        )
    return sorted(found)


def reference_sources(refs: object, root: Path) -> list[ReferenceSource]:
    per_file: Counter[str] = Counter()
    if not isinstance(refs, list):
        return []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        uri = ref.get("uri")
        if not isinstance(uri, str):
            continue
        path = path_from_uri(uri)
        per_file[str(path.relative_to(root) if path.is_relative_to(root) else path)] += 1
    return [ReferenceSource(file, n) for file, n in sorted(per_file.items(), key=lambda kv: (-kv[1], kv[0]))]


def count_references(srv: LspServer, root: Path, targets: list[Path]) -> list[SymbolReferences]:
    # LSP SymbolKind values worth counting
    kind_labels = {5: "class", 12: "function", 13: "variable", 14: "constant"}
    results: list[SymbolReferences] = []
    for path in python_files(targets):
        uri = srv.open_document(path)
        symbols = srv.request("textDocument/documentSymbol", {"textDocument": {"uri": uri}})
        for sym in countable_symbols(symbols, kind_labels):
            refs = srv.request(
                "textDocument/references",
                {
                    "textDocument": {"uri": uri},
                    "position": {"line": sym.line, "character": sym.character},
                    "context": {"includeDeclaration": False},
                },
            )
            results.append(
                SymbolReferences(
                    file=str(path.relative_to(root)),
                    line=sym.line + 1,
                    kind=sym.kind,
                    symbol=sym.name,
                    references=len(refs) if isinstance(refs, list) else 0,
                    referenced_from=reference_sources(refs, root),
                )
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="project root; references are searched here")
    parser.add_argument(
        "paths",
        type=Path,
        nargs="*",
        help="Python files or directories whose symbols get counted, relative to root (default: all)",
    )
    parser.add_argument(
        "--zero-only", action="store_true", help="show only symbols with zero references"
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="emit JSON instead of a table"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="seconds to wait for any single language server message before failing (default: 120)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="trace every message to stderr and pass the language server's stderr through",
    )
    args = parser.parse_args()
    root: Path = args.root.resolve()
    if not root.is_dir():
        parser.error(f"{root} is not a directory")
    targets: list[Path] = [(root / p).resolve() for p in args.paths] or [root]
    for target in targets:
        problem = target_problem(root, target)
        if problem is not None:
            parser.error(problem)

    srv = LspServer.start(language_server_command(), timeout=args.timeout, debug=args.debug)
    try:
        srv.initialize(workspace_root(root))
        results = count_references(srv, root, targets)
        srv.shutdown()
    finally:
        srv.proc.kill()

    shown = [r for r in results if r.references == 0] if args.zero_only else results
    if args.as_json:
        print(json.dumps([asdict(r) for r in shown], indent=2))
        return
    for r in sorted(shown, key=lambda r: r.references):
        sources = ", ".join(f"{s.file} ({s.count})" for s in r.referenced_from)
        suffix = f"  <- {sources}" if sources else ""
        print(f"{r.references:>4}  {r.kind:<8} {r.symbol}  ({r.file}:{r.line}){suffix}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"refcount: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
