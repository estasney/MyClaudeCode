import asyncio
import hashlib
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from analyze_repo import orm
from analyze_repo.semantic.documents import split_words
from analyze_repo.semantic.summarize import SummaryFailedError


class WordHashEmbedder:
    """Hashes each word onto one of a few dimensions so tests load no model.
    Records every document text it embeds."""

    model = "word-hash"

    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self.embedded.extend(texts)
        return np.stack([self.embed_query(text) for text in texts])

    def embed_query(self, text: str) -> NDArray[np.float32]:
        vector = np.zeros(64, dtype=np.float32)
        for word in split_words(text):
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 64] += 1
        return vector / np.linalg.norm(vector)


class FailingOnceEmbedder(WordHashEmbedder):
    """Raises on one call to embed_documents and embeds on every other call."""

    def __init__(self, failing_call: int) -> None:
        super().__init__()
        self.failing_call = failing_call
        self.calls = 0

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self.calls += 1
        if self.calls == self.failing_call:
            raise RuntimeError(f"scripted failure on call {self.calls}")
        return super().embed_documents(texts)


class ScriptedSummarizer:
    """Describes a symbol by its name. Fails on the failing names and never
    answers for the blocking names."""

    def __init__(self, failing: frozenset[str], blocking: frozenset[str]) -> None:
        self.failing = failing
        self.blocking = blocking
        self.requested: list[str] = []
        self.blocked = asyncio.Event()

    async def summarize(self, symbol: orm.Symbol, body: str) -> orm.Summary:
        self.requested.append(symbol.qualified_name)
        if symbol.qualified_name in self.failing:
            raise SummaryFailedError(symbol.qualified_name, "scripted failure")
        if symbol.qualified_name in self.blocking:
            self.blocked.set()
            await asyncio.Event().wait()
        return orm.Summary(
            body_hash=symbol.body_hash,
            text=f"describes {symbol.qualified_name}",
            model="scripted",
        )


__all__ = [
    "FailingOnceEmbedder",
    "ScriptedSummarizer",
    "WordHashEmbedder",
]
