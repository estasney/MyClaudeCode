from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel

from analyze_repo import orm


class SymbolInfo(BaseModel):
    symbol_id: int
    qualified_name: str
    kind: orm.SymbolKind
    path: str
    start_line: int
    end_line: int
    summary: str | None
    decorators: Sequence[str]


class ReferenceInfo(BaseModel):
    path: str
    line: int
    column: int
    node_kind: str
    parent_kind: str
    parent_field: str | None
    enclosing_symbol: str | None


class SymbolScope(StrEnum):
    """Which nesting levels a symbol search covers."""

    module_and_class = "module_and_class"
    all = "all"


__all__ = ["ReferenceInfo", "SymbolInfo", "SymbolScope"]
