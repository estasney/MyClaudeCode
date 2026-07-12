# /// script
# requires-python = ">=3.11"
# dependencies = ["tree-sitter-language-pack>=0.13"]
# ///
"""Print a hierarchical map of a repository: directories, files, and the symbols each file defines."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Node
from tree_sitter_language_pack import get_parser


@dataclass(frozen=True)
class LanguageSpec:
    language: str
    symbol_labels: dict[str, str]
    leaf_labels: frozenset[str]
    return_field: str
    return_prefix: str


@dataclass(frozen=True)
class Symbol:
    label: str
    name: str
    signature: str
    line: int
    depth: int


@dataclass
class DirNode:
    dirs: dict[str, DirNode] = field(default_factory=dict)
    files: dict[str, list[Symbol]] = field(default_factory=dict)


@dataclass(frozen=True)
class MapOptions:
    source_only: bool
    max_parse_bytes: int
    signature_limit: int


def language_specs() -> dict[str, LanguageSpec]:
    js_labels = {
        "class_declaration": "class",
        "function_declaration": "function",
        "generator_function_declaration": "function",
        "method_definition": "method",
    }
    ts_labels = js_labels | {
        "abstract_class_declaration": "class",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "enum_declaration": "enum",
    }
    python_labels = {"class_definition": "class", "function_definition": "def"}
    go_labels = {
        "function_declaration": "func",
        "method_declaration": "func",
        "type_spec": "type",
    }
    rust_labels = {
        "function_item": "fn",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "impl_item": "impl",
    }
    js_leaves = frozenset({"function", "method"})
    py = LanguageSpec("python", python_labels, frozenset({"def"}), "return_type", " -> ")
    js = LanguageSpec("javascript", js_labels, js_leaves, "return_type", "")
    return {
        ".py": py,
        ".js": js,
        ".jsx": js,
        ".mjs": js,
        ".ts": LanguageSpec("typescript", ts_labels, js_leaves, "return_type", ""),
        ".tsx": LanguageSpec("tsx", ts_labels, js_leaves, "return_type", ""),
        ".go": LanguageSpec("go", go_labels, frozenset({"func"}), "result", " "),
        ".rs": LanguageSpec("rust", rust_labels, frozenset({"fn"}), "return_type", " -> "),
    }


def node_text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return " ".join(node.text.decode("utf-8", errors="replace").split())


def truncate(text: str, limit: int) -> str:
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def symbol_signature(node: Node, spec: LanguageSpec) -> str:
    params = node.child_by_field_name("parameters") or node.child_by_field_name("parameter")
    returns = node.child_by_field_name(spec.return_field)
    if returns is None:
        return node_text(params)
    return f"{node_text(params)}{spec.return_prefix}{node_text(returns)}"


def arrow_function_symbol(node: Node, spec: LanguageSpec, depth: int) -> Symbol | None:
    if node.type != "variable_declarator":
        return None
    value = node.child_by_field_name("value")
    if value is None or value.type not in {"arrow_function", "function_expression"}:
        return None
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    signature = symbol_signature(value, spec)
    return Symbol("function", node_text(name_node), signature, node.start_point[0] + 1, depth)


def declared_symbol(node: Node, spec: LanguageSpec, depth: int) -> Symbol | None:
    label = spec.symbol_labels.get(node.type)
    if label is None:
        if spec.language in {"javascript", "typescript", "tsx"}:
            return arrow_function_symbol(node, spec, depth)
        return None
    name_node = node.child_by_field_name("name") or node.child_by_field_name("type")
    if name_node is None:
        return None
    signature = symbol_signature(node, spec)
    return Symbol(label, node_text(name_node), signature, node.start_point[0] + 1, depth)


def collect_symbols(root: Node, spec: LanguageSpec) -> list[Symbol]:
    symbols: list[Symbol] = []

    def visit(node: Node, depth: int) -> None:
        symbol = declared_symbol(node, spec, depth)
        next_depth = depth
        if symbol is not None:
            symbols.append(symbol)
            if symbol.label in spec.leaf_labels:
                return
            next_depth = depth + 1
        for child in node.children:
            visit(child, next_depth)

    visit(root, 0)
    return symbols


def parse_file(path: Path, spec: LanguageSpec) -> list[Symbol]:
    source = path.read_bytes()
    parser = get_parser(spec.language)
    tree = parser.parse(source)
    return collect_symbols(tree.root_node, spec)


def repo_files(repo_path: Path) -> list[Path]:
    listing = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    if listing.returncode == 0:
        files = [repo_path / line for line in listing.stdout.splitlines() if line]
        return sorted(path for path in files if path.is_file())
    return walk_files(repo_path)


def walk_files(repo_path: Path) -> list[Path]:
    junk_dirs = {"node_modules", "__pycache__", "venv", "dist", "build", "target"}
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = sorted(
            name for name in dirnames if not name.startswith(".") and name not in junk_dirs
        )
        files.extend(Path(dirpath) / name for name in filenames)
    return sorted(files)


def build_tree(repo_path: Path, entries: list[tuple[Path, list[Symbol]]]) -> DirNode:
    root = DirNode()
    for path, symbols in entries:
        parts = path.relative_to(repo_path).parts
        node = root
        for part in parts[:-1]:
            node = node.dirs.setdefault(part, DirNode())
        node.files[parts[-1]] = symbols
    return root


def format_symbol(symbol: Symbol, indent: str, signature_limit: int) -> str:
    pad = indent + "  " * symbol.depth
    signature = truncate(symbol.signature, signature_limit)
    return f"{pad}{symbol.label} {symbol.name}{signature}  :{symbol.line}"


def render_tree(node: DirNode, indent: str, signature_limit: int) -> list[str]:
    lines: list[str] = []
    for name in sorted(node.dirs):
        lines.append(f"{indent}{name}/")
        lines.extend(render_tree(node.dirs[name], indent + "  ", signature_limit))
    for name in sorted(node.files):
        lines.append(f"{indent}{name}")
        lines.extend(
            format_symbol(symbol, indent + "  ", signature_limit) for symbol in node.files[name]
        )
    return lines


def file_symbols(path: Path, options: MapOptions) -> list[Symbol]:
    spec = language_specs().get(path.suffix)
    if spec is None or path.stat().st_size > options.max_parse_bytes:
        return []
    return parse_file(path, spec)


def map_directory(repo_path: Path, options: MapOptions) -> str:
    entries: list[tuple[Path, list[Symbol]]] = []
    for path in repo_files(repo_path):
        try:
            symbols = file_symbols(path, options)
        except OSError:
            continue
        if symbols or not options.source_only:
            entries.append((path, symbols))
    tree = build_tree(repo_path, entries)
    return "\n".join([f"{repo_path.name}/", *render_tree(tree, "  ", options.signature_limit)])


def map_file(path: Path, options: MapOptions) -> str:
    symbols = file_symbols(path, options)
    lines = [format_symbol(symbol, "  ", options.signature_limit) for symbol in symbols]
    return "\n".join([path.name, *lines])


def build_arg_parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("path", help="Directory or file to map")
    arg_parser.add_argument(
        "--source-only",
        action="store_true",
        help="List only files whose symbols can be parsed; omit other files",
    )
    arg_parser.add_argument(
        "--max-parse-bytes",
        type=int,
        default=512 * 1024,
        help="List files larger than this without parsing their symbols",
    )
    arg_parser.add_argument(
        "--signature-limit",
        type=int,
        default=100,
        help="Truncate symbol signatures longer than this many characters",
    )
    return arg_parser


def main() -> int:
    args = build_arg_parser().parse_args()
    target = Path(args.path).resolve()
    options = MapOptions(
        source_only=args.source_only,
        max_parse_bytes=args.max_parse_bytes,
        signature_limit=args.signature_limit,
    )
    if target.is_file():
        print(map_file(target, options))
        return 0
    if target.is_dir():
        print(map_directory(target, options))
        return 0
    print(f"No such file or directory: {target}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
