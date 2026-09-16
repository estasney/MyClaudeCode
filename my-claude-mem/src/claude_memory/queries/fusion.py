from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from chromadb.api.types import Include, Metadata, QueryResult

from claude_memory.queries.selects import KeywordRow


@dataclass(frozen=True)
class KeywordHit:
    chroma_id: str
    document: str
    metadata: Metadata | None
    score: float


def group_by_phrase(
    rows: Sequence[KeywordRow], phrase_count: int
) -> list[list[KeywordHit]]:
    grouped: list[list[KeywordHit]] = [[] for _ in range(phrase_count)]
    for phrase_index, chroma_id, document, metadata, score in rows:
        grouped[phrase_index].append(
            KeywordHit(
                chroma_id=chroma_id, document=document, metadata=metadata, score=score
            )
        )
    return grouped


def fuse(
    vector_ids: Sequence[str],
    keyword_ids: Sequence[str],
    vector_weight: float,
    keyword_weight: float,
    rank_offset: int,
) -> list[str]:
    """Weighted reciprocal rank fusion keyed by id; ties keep first appearance."""
    scores: defaultdict[str, float] = defaultdict(float)
    for rank, chroma_id in enumerate(vector_ids, start=1):
        scores[chroma_id] += vector_weight / (rank_offset + rank)
    for rank, chroma_id in enumerate(keyword_ids, start=1):
        scores[chroma_id] += keyword_weight / (rank_offset + rank)
    return sorted(scores, key=lambda chroma_id: -scores[chroma_id])


def assemble_query_result(
    vector: QueryResult,
    keyword: Sequence[Sequence[KeywordHit]],
    fused: Sequence[Sequence[str]],
    include: Include,
) -> QueryResult:
    """Fills each included field from Chroma for vector hits and from the keyword hit otherwise; keyword-only distances are None."""
    positions = [
        {chroma_id: i for i, chroma_id in enumerate(phrase_ids)}
        for phrase_ids in vector["ids"]
    ]
    hits = [{hit.chroma_id: hit for hit in phrase_hits} for phrase_hits in keyword]

    def documents() -> list[list[str]]:
        vector_documents = vector["documents"] or []
        return [
            [
                vector_documents[p][positions[p][chroma_id]]
                if chroma_id in positions[p]
                else hits[p][chroma_id].document
                for chroma_id in phrase_ids
            ]
            for p, phrase_ids in enumerate(fused)
        ]

    def metadatas() -> list[list[Metadata | None]]:
        vector_metadatas = vector["metadatas"] or []
        return [
            [
                vector_metadatas[p][positions[p][chroma_id]]
                if chroma_id in positions[p]
                else hits[p][chroma_id].metadata
                for chroma_id in phrase_ids
            ]
            for p, phrase_ids in enumerate(fused)
        ]

    def distances() -> list[list[float | None]]:
        vector_distances = vector["distances"] or []
        return [
            [
                vector_distances[p][positions[p][chroma_id]]
                if chroma_id in positions[p]
                else None
                for chroma_id in phrase_ids
            ]
            for p, phrase_ids in enumerate(fused)
        ]

    return QueryResult(
        ids=[list(phrase_ids) for phrase_ids in fused],
        documents=documents() if "documents" in include else None,
        metadatas=cast("list[list[Metadata]]", metadatas())
        if "metadatas" in include
        else None,
        distances=cast("list[list[float]]", distances())
        if "distances" in include
        else None,
        embeddings=None,
        uris=None,
        data=None,
        included=include,
    )
