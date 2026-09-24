from dataclasses import dataclass

from tree_sitter import Node, Tree
from tree_sitter_language_pack import get_parser

from analyze_repo.lsp.models import Position

__all__ = [
    "PythonSyntaxTree",
    "SyntaxContext",
    "utf16_offset_to_byte_offset",
]


@dataclass(frozen=True)
class SyntaxContext:
    """What the tree-sitter grammar says about the node at a reference."""

    node_kind: str
    parent_kind: str
    parent_field: str | None


class MissingParentError(ValueError):
    def __init__(self, node: Node) -> None:
        super().__init__(f"{node.type} at {node.start_point} has no parent")


def utf16_offset_to_byte_offset(line: bytes, character: int) -> int:
    """LSP columns count UTF-16 code units; tree-sitter columns count bytes."""
    prefix = line.decode("utf-8").encode("utf-16-le")[: 2 * character]
    return len(prefix.decode("utf-16-le").encode("utf-8"))


class PythonSyntaxTree:
    """Parses a file once so many positions can be looked up in it."""

    def __init__(self, source: bytes) -> None:
        self.lines = source.split(b"\n")
        self.tree: Tree = get_parser("python").parse(source)

    def context_at(self, position: Position) -> SyntaxContext:
        column = utf16_offset_to_byte_offset(
            self.lines[position.line], position.character
        )
        point = (position.line, column)
        node = self.tree.root_node.named_descendant_for_point_range(point, point)
        if node is None:
            raise MissingParentError(self.tree.root_node)
        expression = reference_expression(node)
        parent = expression.parent
        if parent is None:
            raise MissingParentError(expression)
        return SyntaxContext(
            node_kind=expression.type,
            parent_kind=parent.type,
            parent_field=parent.field_name_for_child(parent.children.index(expression)),
        )


def reference_expression(node: Node) -> Node:
    """In `a.b.c()` the name `c` stands for the whole attribute expression, so the
    role of the reference (called, assigned, passed) is that expression's role."""
    while (
        node.parent is not None
        and node.parent.type == "attribute"
        and node.parent.child_by_field_name("attribute") == node
    ):
        node = node.parent
    return node
