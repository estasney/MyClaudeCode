from collections.abc import Sequence

from pydantic import BaseModel

from analyze_repo.models.symbols import SymbolInfo


class SearchHit(BaseModel):
    symbol: SymbolInfo
    matched_parameters: Sequence[SymbolInfo]
    entry_points: Sequence[SymbolInfo]
    score: float


__all__ = ["SearchHit"]
