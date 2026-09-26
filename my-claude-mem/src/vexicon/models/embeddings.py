from typing import Annotated

from pydantic import Field

EmbeddingRepoId = Annotated[
    str,
    Field(
        description="Hugging Face repo_id from list_embedding_models of the "
        "sentence-transformer model that embeds this space's entries."
    ),
]
