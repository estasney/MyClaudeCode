# /// script
# requires-python = ">=3.11"
# dependencies = ["basedpyright>=1.13"]
# ///
"""Count references for every module-level symbol in a Python codebase using basedpyright's LSP.

Symbols with zero references are dead-code candidates.

Usage: uv run refcount.py <project_root> [--zero-only] [--json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from itertools import count
from pathlib import Path


@dataclass(frozen=True)
class CountableSymbol:
    """A symbol worth counting references for, located by its selectionRange start."""

    name: str
    kind: str
    line: int
    character: int


@dataclass(frozen=True)
class SymbolReferences:
    file: str
    line: int
    kind: str
    symbol: str
    references: int


@dataclass
class LspServer:
    proc: subprocess.Popen[bytes]
    request_ids: count[int] = field(default_factory=lambda: count(1))

    def write_message(self, msg: dict[str, object]) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("language server stdin is closed")
        raw = json.dumps(msg).encode()
        self.proc.stdin.writelines([f"Content-Length: {len(raw)}\r\n\r\n".encode(), raw])
        self.proc.stdin.flush()

    def notify(self, method: str, params: object) -> None:
        self.write_message({"jsonrpc": "2.0", "method": method, "params": params})

    def read(self) -> dict[str, object]:
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
            raise RuntimeError("language server closed the connection")
        body = self.proc.stdout.read(int(headers["content-length"]))
        message: object = json.loads(body)
        if not isinstance(message, dict):
            raise TypeError("language server sent a non-object message")
        return message

    def request(self, method: str, params: object) -> object:
        req_id = next(self.request_ids)
        self.write_message({"jsonrpc": "2.0", "method": method, "params": params, "id": req_id})
        while True:
            match self.read():
                case {"id": rid, "result": result} if rid == req_id:
                    return result
                case {"id": rid, "error": err} if rid == req_id:
                    raise RuntimeError(f"{method}: {err}")
                case _:
                    continue  # server notifications, diagnostics, logs

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
    bundled = Path(sys.executable).parent / "basedpyright-langserver"
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


def project_files(root: Path) -> list[Path]:
    skipped = {"node_modules", "__pycache__"}
    return [
        p
        for p in sorted(root.rglob("*.py"))
        if not any(part.startswith(".") or part in skipped for part in p.parts)
    ]


def count_references(srv: LspServer, target: Path) -> list[SymbolReferences]:
    # LSP SymbolKind values worth counting
    kind_labels = {5: "class", 12: "function", 13: "variable", 14: "constant"}
    results: list[SymbolReferences] = []
    for path in project_files(target):
        uri = path.as_uri()
        srv.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": path.read_text(),
                }
            },
        )
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
                    file=str(path.relative_to(target)),
                    line=sym.line + 1,
                    kind=sym.kind,
                    symbol=sym.name,
                    references=len(refs) if isinstance(refs, list) else 0,
                )
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="project root to analyze")
    parser.add_argument(
        "--zero-only", action="store_true", help="show only symbols with zero references"
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="emit JSON instead of a table"
    )
    args = parser.parse_args()
    target = args.root.resolve()
    if not target.is_dir():
        parser.error(f"{target} is not a directory")

    srv = LspServer(
        subprocess.Popen(
            [language_server_command(), "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    )
    srv.initialize(workspace_root(target))
    results = count_references(srv, target)
    srv.shutdown()

    shown = [r for r in results if r.references == 0] if args.zero_only else results
    if args.as_json:
        print(json.dumps([asdict(r) for r in shown], indent=2))
        return
    for r in sorted(shown, key=lambda r: r.references):
        print(f"{r.references:>4}  {r.kind:<8} {r.symbol}  ({r.file}:{r.line})")


if __name__ == "__main__":
    main()
