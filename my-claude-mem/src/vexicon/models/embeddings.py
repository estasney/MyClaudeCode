from typing import Annotated

from pydantic import BaseModel, Field

RepoId = Annotated[str, Field(pattern=r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")]

EmbeddingRepoId = Annotated[
    RepoId,
    Field(
        description="Hugging Face repo_id from list_embedding_models of the "
        "sentence-transformer model that embeds this space's entries."
    ),
]

HubRepoId = Annotated[
    RepoId, Field(description="Hugging Face repo_id of the model to download.")
]


class EmbeddingModel(BaseModel):
    repo_id: str = Field(description="Hugging Face repo_id of the model.")
    downloads: int | None = Field(description="Downloads in the last 30 days.")
    cached: bool = Field(description="Whether create_space can use the model now.")
