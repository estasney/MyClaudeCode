from pathlib import Path
from typing import Protocol

from analyze_repo.lsp.models import DocumentSymbol, Location, Position

__all__ = [
    "LanguageServer",
]


class LanguageServer(Protocol):
    """Paths in and out are absolute and resolved."""

    def get_document_symbols(self, absolute_path: Path) -> list[DocumentSymbol]: ...

    def find_references(
        self, absolute_path: Path, position: Position
    ) -> list[Location]: ...
