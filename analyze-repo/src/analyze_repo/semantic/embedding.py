from collections.abc import Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Protocol

import numpy as np
from numpy.typing import NDArray

from analyze_repo.settings import Settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class Embedder(Protocol):
    """Turns text into unit length vectors. Blocking so run it in a thread."""

    @property
    def model(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]: ...

    def embed_query(self, text: str) -> NDArray[np.float32]: ...


def parse_vectors(encoded: object) -> NDArray[np.float32]:
    """sentence-transformers types its result as a union of tensors and arrays."""
    match encoded:
        case np.ndarray():
            return encoded.astype(np.float32)
        case _:
            raise TypeError(
                f"expected an ndarray from the encoder, got {type(encoded).__name__}"
            )


class SentenceTransformerEmbedder:
    """Loads the model on first use because importing torch takes seconds."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def model(self) -> str:
        return self.settings.embedding_model

    @cached_property
    def transformer(self) -> "SentenceTransformer":
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.settings.embedding_model)

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return parse_vectors(
            self.transformer.encode_document(
                list(texts),
                batch_size=self.settings.embedding_batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        )

    def embed_query(self, text: str) -> NDArray[np.float32]:
        return parse_vectors(
            self.transformer.encode_query(
                text, normalize_embeddings=True, show_progress_bar=False
            )
        )


__all__ = [
    "Embedder",
    "SentenceTransformerEmbedder",
]
