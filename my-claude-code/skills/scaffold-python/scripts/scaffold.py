# /// script
# requires-python = ">=3.12"
# dependencies = ["libcst>=1.4", "typer>=0.12"]
# ///
"""Grow a Python source tree from a symbol map: a repo-tree style listing of files and the symbols they should gain."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, assert_never

import libcst as cst
import typer
from libcst.metadata import CodeRange, MetadataWrapper, PositionProvider

# Map grammar. Indentation nests. Each line is one of:
#   dir/                        directory, relative to its parent
#   module.py                   file; children are its module-level symbols
#   @decorator                  applies to the next class or def at the same indent
#   class Name(Bases)           children are members: fields, methods, nested classes
#   def name(params) -> Ret     body is `raise NotImplementedError`, or `...` under a
#                               Protocol class or an @overload decorator
#   name: Type = default        annotated field or module variable
# A trailing `:line` marker, as printed by repo-tree, is ignored.


@dataclass(frozen=True)
class FieldSpec:
    name: str
    line: int
    statement: cst.SimpleStatementLine


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    line: int
    definition: cst.FunctionDef


@dataclass(frozen=True)
class ClassSpec:
    name: str
    line: int
    header: cst.ClassDef
    members: list[Member]


type Member = ClassSpec | FunctionSpec | FieldSpec


@dataclass(frozen=True)
class FileSpec:
    path: Path
    line: int
    members: list[Member]


@dataclass(frozen=True)
class Tree:
    files: list[FileSpec]


@dataclass(frozen=True)
class Issue:
    line: int
    message: str


@dataclass(frozen=True)
class Decoration:
    line: int
    text: str


type Owner = Path | FileSpec | ClassSpec | FunctionSpec | FieldSpec


@dataclass
class Frame:
    indent: int
    owner: Owner
    child_indent: int | None = None
    decorations: list[Decoration] = field(default_factory=list)


def is_protocol(definition: cst.ClassDef) -> bool:
    for base in definition.bases:
        match base.value:
            case (
                cst.Name(value="Protocol")
                | cst.Attribute(attr=cst.Name(value="Protocol"))
            ):
                return True
            case cst.Subscript(
                value=cst.Name(value="Protocol")
                | cst.Attribute(attr=cst.Name(value="Protocol"))
            ):
                return True
            case _:
                continue
    return False


def parse_member(
    text: str, line: int, decorations: list[Decoration], protocol: bool
) -> Member | Issue:
    is_definition = text.startswith(("class ", "def ", "async def "))
    overload = any(
        d.text[1:].split("(")[0].rsplit(".", 1)[-1] == "overload" for d in decorations
    )
    body = (
        "..."
        if protocol or overload or text.startswith("class ")
        else "raise NotImplementedError"
    )
    try:
        decorators = [
            cst.Decorator(decorator=cst.parse_expression(d.text[1:]))
            for d in decorations
        ]
        node = cst.parse_statement(
            f"{text}:\n    {body}\n" if is_definition else f"{text}\n"
        )
    except cst.ParserSyntaxError as error:
        return Issue(line, error.message)
    match node:
        case cst.ClassDef(name=cst.Name(value=name)):
            return ClassSpec(name, line, node.with_changes(decorators=decorators), [])
        case cst.FunctionDef(name=cst.Name(value=name)):
            return FunctionSpec(name, line, node.with_changes(decorators=decorators))
        case cst.SimpleStatementLine(body=[cst.AnnAssign(target=cst.Name(value=name))]):
            return FieldSpec(name, line, node)
        case _:
            return Issue(line, "expected dir/, module.py, class, def, or name: Type")


def add_entry(
    tree: Tree, owner: Owner, text: str, line: int, decorations: list[Decoration]
) -> Owner | Issue:
    if "…" in text:
        return Issue(line, "truncated signature")
    is_path = text.endswith(("/", ".py"))
    if decorations and (
        is_path or not text.startswith(("class ", "def ", "async def "))
    ):
        return Issue(decorations[0].line, "decorator without a class or def")
    match owner:
        case Path():
            if not is_path:
                return Issue(line, "symbol outside a module")
            if text.endswith("/"):
                return owner / text.removesuffix("/")
            spec = FileSpec(owner / text, line, [])
            if any(f.path == spec.path for f in tree.files):
                return Issue(line, f"{spec.path} listed twice")
            tree.files.append(spec)
            return spec
        case FileSpec() | ClassSpec():
            if is_path:
                return Issue(line, "path inside a module")
            protocol = isinstance(owner, ClassSpec) and is_protocol(owner.header)
            member = parse_member(text, line, decorations, protocol)
            if not isinstance(member, Issue):
                owner.members.append(member)
            return member
        case FunctionSpec() | FieldSpec():
            return Issue(line, "nothing may nest under a def or field")
        case _:
            assert_never(owner)


def parse_map(text: str) -> tuple[Tree, list[Issue]]:
    """Boundary parse of a symbol map; every issue names its map line."""
    tree = Tree([])
    issues: list[Issue] = []
    stack = [Frame(-1, Path())]
    for line, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        content = re.sub(r"\s+:\d+$", "", raw.rstrip())
        indent = len(content) - len(content.lstrip(" "))
        while stack[-1].indent >= indent:
            issues.extend(
                Issue(d.line, "decorator without a class or def")
                for d in stack.pop().decorations
            )
        parent = stack[-1]
        if parent.child_indent is None:
            parent.child_indent = indent
        elif parent.child_indent != indent:
            issues.append(Issue(line, "inconsistent indentation"))
            continue
        if content.strip().startswith("@"):
            parent.decorations.append(Decoration(line, content.strip()))
            continue
        decorations, parent.decorations = parent.decorations, []
        entry = add_entry(tree, parent.owner, content.strip(), line, decorations)
        if isinstance(entry, Issue):
            issues.append(entry)
            continue
        stack.append(Frame(indent, entry))
    issues.extend(
        Issue(d.line, "decorator without a class or def")
        for frame in stack
        for d in frame.decorations
    )
    return tree, sorted(issues, key=lambda issue: issue.line)


type Statement = cst.SimpleStatementLine | cst.BaseCompoundStatement


@dataclass(frozen=True)
class Merge:
    body: list[Statement]
    added: set[str]
    issues: list[Issue]


@dataclass(frozen=True)
class Addition:
    qualname: str
    line: int


@dataclass(frozen=True)
class FileChange:
    path: Path
    created: bool
    code: str
    additions: list[Addition]


def statement_names(statement: cst.CSTNode) -> list[str] | None:
    """Names the statement binds, or None when the statement kind is not a symbol definition."""
    match statement:
        case cst.FunctionDef(name=name) | cst.ClassDef(name=name):
            return [name.value]
        case cst.SimpleStatementLine(
            body=[cst.AnnAssign(target=cst.Name(value=value))]
        ):
            return [value]
        case cst.SimpleStatementLine(body=[cst.Assign(targets=targets)]):
            names = [t.target.value for t in targets if isinstance(t.target, cst.Name)]
            return names if len(names) == len(targets) else None
        case _:
            return None


def body_statements(definition: cst.ClassDef) -> list[Statement]:
    match definition.body:
        case cst.IndentedBlock(body=body):
            pass
        case cst.SimpleStatementSuite():
            return []
        case _:
            raise TypeError(f"unexpected class body {type(definition.body).__name__}")
    statements: list[Statement] = []
    for statement in body:
        match statement:
            case cst.SimpleStatementLine() | cst.BaseCompoundStatement():
                statements.append(statement)
            case _:
                raise TypeError(f"unexpected class member {type(statement).__name__}")
    return statements


def appended(
    existing: list[Statement], new: list[Statement], blanks: int
) -> list[Statement]:
    """Existing statements untouched, new ones separated by blank lines around compound statements."""
    body = list(existing)
    for statement in new:
        compound = isinstance(statement, cst.BaseCompoundStatement) or (
            bool(body) and isinstance(body[-1], cst.BaseCompoundStatement)
        )
        count = blanks if body and compound else 0
        body.append(
            statement.with_changes(
                leading_lines=[cst.EmptyLine(indent=False) for _ in range(count)]
            )
        )
    return body


def statement(member: Member) -> Statement:
    match member:
        case FieldSpec(statement=node):
            return node
        case FunctionSpec(definition=node):
            return node
        case ClassSpec(header=header, members=[]):
            return header
        case ClassSpec(header=header, members=members):
            body = appended([], [statement(m) for m in members], 1)
            return header.with_changes(body=cst.IndentedBlock(body=body))
        case _:
            assert_never(member)


def qualnames(member: Member, prefix: str) -> set[str]:
    """The member's qualified name and, for a class, those of everything inside it."""
    names = {prefix + member.name}
    if isinstance(member, ClassSpec):
        for inner in member.members:
            names |= qualnames(inner, f"{prefix}{member.name}.")
    return names


def merge_members(
    body: list[Statement], members: list[Member], prefix: str, blanks: int
) -> Merge:
    """Add members to a module or class body; classes that already exist are merged, other collisions are issues."""
    body = list(body)
    existing = {
        name: index
        for index, current in enumerate(body)
        for name in statement_names(current) or []
    }
    added: set[str] = set()
    issues: list[Issue] = []
    new: list[Statement] = []
    for member in members:
        qualname = prefix + member.name
        current = body[existing[member.name]] if member.name in existing else None
        match member, current:
            case ClassSpec(), cst.ClassDef():
                merged = merge_members(
                    body_statements(current), member.members, qualname + ".", 1
                )
                if merged.body:
                    body[existing[member.name]] = current.with_changes(
                        body=cst.IndentedBlock(body=merged.body)
                    )
                added |= merged.added
                issues += merged.issues
            case _, None:
                new.append(statement(member))
                added |= qualnames(member, prefix)
            case _, _:
                issues.append(Issue(member.line, f"{qualname} already exists"))
    return Merge(appended(body, new, blanks), added, issues)


def symbol_lines(
    statements: Sequence[Statement],
    positions: Mapping[cst.CSTNode, CodeRange],
    prefix: str,
) -> dict[str, int]:
    """Qualified name to first line for every symbol, descending into classes."""
    lines: dict[str, int] = {}
    for current in statements:
        for name in statement_names(current) or []:
            lines.setdefault(prefix + name, positions[current].start.line)
        if isinstance(current, cst.ClassDef):
            nested = symbol_lines(
                body_statements(current), positions, f"{prefix}{current.name.value}."
            )
            for name, line in nested.items():
                lines.setdefault(name, line)
    return lines


def plan_file(
    source_root: Path, spec: FileSpec
) -> tuple[FileChange | None, list[Issue]]:
    target_path = source_root / spec.path
    created = not target_path.exists()
    if created:
        target = cst.Module(body=[])
    else:
        try:
            target = cst.parse_module(target_path.read_text(encoding="utf-8"))
        except cst.ParserSyntaxError as error:
            return None, [
                Issue(spec.line, f"{spec.path} does not parse: {error.message}")
            ]
    merge = merge_members(list(target.body), spec.members, "", 2)
    if merge.issues:
        return None, merge.issues
    wrapper = MetadataWrapper(target.with_changes(body=merge.body))
    lines = symbol_lines(wrapper.module.body, wrapper.resolve(PositionProvider), "")
    additions = sorted(
        (Addition(name, lines[name]) for name in merge.added), key=lambda a: a.line
    )
    return FileChange(spec.path, created, wrapper.module.code, additions), []


def package_inits(source_root: Path, changes: list[FileChange]) -> list[Path]:
    """Relative paths of `__init__.py` files missing from directories the changes create."""
    written = {change.path for change in changes}
    missing: list[Path] = []
    for change in changes:
        for directory in change.path.parents:
            if directory == Path(".") or (source_root / directory).exists():
                continue
            init = directory / "__init__.py"
            if init not in written and init not in missing:
                missing.append(init)
    return missing


def render(changes: list[FileChange], inits: list[Path]) -> str:
    lines: list[str] = []
    for change in changes:
        lines.append(f"{'create' if change.created else 'modify'} {change.path}")
        lines.extend(
            f"  {addition.line:>4}  {addition.qualname}"
            for addition in change.additions
        )
    lines.extend(f"create {init}  (empty package marker)" for init in inits)
    return "\n".join(lines)


def main(
    source_root: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            help="directory the map's paths are relative to",
        ),
    ],
    symbol_map: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="repo-tree style listing of symbols to add",
        ),
    ],
    check: Annotated[
        bool,
        typer.Option("--check", help="report what would be written without writing"),
    ] = False,
) -> None:
    """Grow a Python source tree from a symbol map, adding only symbols that do not exist yet."""
    tree, issues = parse_map(symbol_map.read_text(encoding="utf-8"))
    changes: list[FileChange] = []
    for spec in tree.files:
        change, file_issues = plan_file(source_root, spec)
        issues.extend(file_issues)
        if change is not None:
            changes.append(change)
    if issues:
        for issue in sorted(issues, key=lambda issue: issue.line):
            print(f"{symbol_map}:{issue.line}  {issue.message}")
        raise typer.Exit(1)
    inits = package_inits(source_root, changes)
    if check:
        print("check only, nothing written")
        print(render(changes, inits))
        return
    for change in changes:
        path = source_root / change.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(change.code, encoding="utf-8")
    for init in inits:
        (source_root / init).write_text("", encoding="utf-8")
    print(render(changes, inits))


if __name__ == "__main__":
    typer.run(main)
