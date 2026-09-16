from typing import Any, ClassVar

import chromadb
import numpy as np
from chromadb.utils.embedding_functions import (
    DefaultEmbeddingFunction,
    register_embedding_function,
)
from huggingface_hub import CachedRepoInfo, scan_cache_dir
from sentence_transformers import SentenceTransformer


def is_sentence_transformer(repo: CachedRepoInfo) -> bool:
    markers = {"modules.json", "config_sentence_transformers.json"}
    filenames = {file.file_name for rev in repo.revisions for file in rev.files}
    return repo.repo_type == "model" and bool(filenames & markers)


def list_local_repo_ids() -> list[str]:
    """Return repo_ids of sentence-transformer models cached locally.

    HFEmbeddingFunction loads with local_files_only=True, so only cached repos
    are usable as embedding models.
    """
    repos = scan_cache_dir().repos
    return sorted(repo.repo_id for repo in repos if is_sentence_transformer(repo))


@register_embedding_function
class HFEmbeddingFunction(chromadb.EmbeddingFunction[chromadb.Documents]):
    _model: SentenceTransformer
    models: ClassVar[dict[tuple[str, str | None], SentenceTransformer]] = {}

    def __init__(
        self,
        repo_id: str,
        *,
        device: str | None = None,
        batch_size: int = 32,
        normalize_embeddings: bool = True,
    ) -> None:
        self.repo_id = repo_id
        self.device = device
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        key = (repo_id, device)
        if key not in self.models:
            self.models[key] = SentenceTransformer(
                repo_id, device=device, local_files_only=True
            )
        self._model = self.models[key]

    def max_tokens(self) -> int | None:
        """Token budget per document; longer inputs are silently truncated."""
        return self._model.max_seq_length

    def __call__(self, texts: chromadb.Documents) -> chromadb.Embeddings:
        embeddings = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        return [np.array(e, dtype=np.float32) for e in embeddings]

    @staticmethod
    def name() -> str:
        return "claude_memory_hf"

    def get_config(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "device": self.device,
            "batch_size": self.batch_size,
            "normalize_embeddings": self.normalize_embeddings,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "HFEmbeddingFunction":
        return HFEmbeddingFunction(
            repo_id=config["repo_id"],
            device=config["device"],
            batch_size=config["batch_size"],
            normalize_embeddings=config["normalize_embeddings"],
        )


def resolve_embedding_function(
    repo_id: str | None,
) -> tuple[chromadb.EmbeddingFunction[chromadb.Documents], int | None]:
    """Build the embedding function for repo_id (or Chroma's default) with its per-document token budget."""
    if repo_id is None:
        default = DefaultEmbeddingFunction()
        return default, default.max_tokens()
    hf = HFEmbeddingFunction(repo_id=repo_id)
    return hf, hf.max_tokens()
