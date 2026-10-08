import asyncio
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analyze_repo import orm
from analyze_repo.documents import split_words
from analyze_repo.embedding import Embedder
from analyze_repo.queries import (
    SymbolInfo,
    is_call_site,
    symbol_info,
    symbols_with_summaries,
)
from analyze_repo.settings import Settings


class SearchHit(BaseModel):
    symbol: SymbolInfo
    matched_parameters: Sequence[SymbolInfo]
    entry_points: Sequence[SymbolInfo]
    score: float


class NotEmbeddedError(LookupError):
    def __init__(self, snapshot_id: int, model: str) -> None:
        super().__init__(
            f"snapshot {snapshot_id} has search documents without a {model} vector;"
            " run embed_repository first"
        )


@dataclass(frozen=True)
class Candidate:
    """A search document reduced to what ranking reads."""

    symbol_id: int
    subject_id: int
    words: Sequence[str]


@dataclass(frozen=True)
class SubjectMatch:
    """A symbol worth answering with and the parameters of it that matched."""

    subject_id: int
    score: float
    parameter_ids: Sequence[int]


def score_keywords(
    question: Sequence[str],
    documents: Sequence[Sequence[str]],
    k1: float = 1.5,
    b: float = 0.75,
) -> NDArray[np.float64]:
    """Okapi BM25 score of every document."""
    counts = [Counter(words) for words in documents]
    lengths = np.array([len(words) for words in documents], dtype=np.float64)
    length_ratio = lengths / lengths.mean()
    scores = np.zeros(len(documents))
    for word in set(question):
        frequency = np.array([count[word] for count in counts], dtype=np.float64)
        containing = np.count_nonzero(frequency)
        rarity = math.log(1 + (len(documents) - containing + 0.5) / (containing + 0.5))
        scores += (
            rarity
            * frequency
            * (k1 + 1)
            / (frequency + k1 * (1 - b + b * length_ratio))
        )
    return scores


def fuse_rankings(
    rankings: Sequence[Sequence[int]], k: int = 60
) -> list[tuple[int, float]]:
    """Reciprocal rank fusion of document positions listed best first."""
    scores: defaultdict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, position in enumerate(ranking, start=1):
            scores[position] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def rank_candidates(
    question: str,
    question_vector: NDArray[np.float32],
    candidates: Sequence[Candidate],
    vectors: NDArray[np.float32],
) -> list[tuple[int, float]]:
    """Fuses keyword and vector rankings. Documents sharing no word with the
    question are left out of the keyword ranking."""
    keyword_scores = score_keywords(
        split_words(question), [candidate.words for candidate in candidates]
    )
    keyword_ranking = [
        int(position)
        for position in np.argsort(-keyword_scores, kind="stable")
        if keyword_scores[position] > 0
    ]
    vector_ranking = [
        int(position)
        for position in np.argsort(-(vectors @ question_vector), kind="stable")
    ]
    return fuse_rankings([keyword_ranking, vector_ranking])


def group_by_subject(
    ranked: Sequence[tuple[int, float]], candidates: Sequence[Candidate], limit: int
) -> list[SubjectMatch]:
    """A subject scores as its best document. Parameters ranked before the
    first subject past the limit are kept."""
    scores: dict[int, float] = {}
    parameter_ids: defaultdict[int, list[int]] = defaultdict(list)
    for position, score in ranked:
        candidate = candidates[position]
        if candidate.subject_id not in scores:
            if len(scores) == limit:
                break
            scores[candidate.subject_id] = score
        if candidate.symbol_id != candidate.subject_id:
            parameter_ids[candidate.subject_id].append(candidate.symbol_id)
    return [
        SubjectMatch(
            subject_id=subject_id, score=score, parameter_ids=parameter_ids[subject_id]
        )
        for subject_id, score in scores.items()
    ]


def is_callable(kind: orm.SymbolKind) -> bool:
    """Only callables have callers to walk toward entry points."""
    match kind:
        case orm.SymbolKind.class_ | orm.SymbolKind.function | orm.SymbolKind.method:
            return True
        case (
            orm.SymbolKind.variable | orm.SymbolKind.constant | orm.SymbolKind.parameter
        ):
            return False
        case _:
            assert_never(kind)


def find_entry_points(
    callers_by_callee: Mapping[int, Sequence[int]], start: int, depth: int, limit: int
) -> list[int]:
    """Callers reached from start that nothing calls in turn nearest first.
    Start counts as its own entry point when nothing calls it."""
    entry_points: list[int] = []
    seen = {start}
    level = [start]
    for _ in range(depth + 1):
        following: list[int] = []
        for symbol_id in level:
            callers = callers_by_callee.get(symbol_id, [])
            if not callers:
                entry_points.append(symbol_id)
            for caller in callers:
                if caller not in seen:
                    seen.add(caller)
                    following.append(caller)
        level = following
    return entry_points[:limit]


async def search_code(
    session: AsyncSession,
    snapshot: orm.Snapshot,
    question: str,
    embedder: Embedder,
    settings: Settings,
    limit: int,
) -> Sequence[SearchHit]:
    rows = (
        await session.execute(
            select(
                orm.SearchDocument.symbol_id,
                orm.SearchDocument.text,
                orm.Symbol.kind,
                orm.Symbol.parent_symbol_id,
                orm.Embedding.vector,
            )
            .join(orm.Symbol, orm.SearchDocument.symbol)
            .join(orm.File)
            .outerjoin(
                orm.Embedding,
                (orm.Embedding.text_hash == orm.SearchDocument.text_hash)
                & (orm.Embedding.model == embedder.model),
            )
            .where(orm.File.snapshot_id == snapshot.id)
            .order_by(orm.SearchDocument.id)
        )
    ).all()
    # The outer join yields None for a missing vector, which SQLAlchemy's typing does not express.
    if not rows or any(row.vector is None for row in rows):
        raise NotEmbeddedError(snapshot.id, embedder.model)
    candidates: list[Candidate] = []
    for symbol_id, text, kind, parent_symbol_id, _ in rows:
        match kind, parent_symbol_id:
            case orm.SymbolKind.parameter, int(owner_id):
                subject_id = owner_id
            case _:
                subject_id = symbol_id
        candidates.append(
            Candidate(
                symbol_id=symbol_id, subject_id=subject_id, words=split_words(text)
            )
        )
    vectors = np.stack([np.frombuffer(row.vector, dtype=np.float32) for row in rows])
    question_vector = await asyncio.to_thread(embedder.embed_query, question)
    matches = group_by_subject(
        rank_candidates(question, question_vector, candidates, vectors),
        candidates,
        limit,
    )

    edges = await session.execute(
        select(orm.Occurrence.enclosing_symbol_id, orm.Occurrence.symbol_id)
        .join(orm.File, orm.Occurrence.file)
        .where(orm.File.snapshot_id == snapshot.id)
        .where(is_call_site())
        .distinct()
        .order_by(orm.Occurrence.enclosing_symbol_id)
    )
    callers_by_callee: defaultdict[int, list[int]] = defaultdict(list)
    for caller_id, callee_id in edges:
        # Module level calls and recursion do not make a symbol reachable from elsewhere.
        if caller_id is not None and caller_id != callee_id:
            callers_by_callee[callee_id].append(caller_id)
    kinds = {row.symbol_id: row.kind for row in rows}
    entry_point_ids = {
        match.subject_id: find_entry_points(
            callers_by_callee,
            match.subject_id,
            settings.caller_depth,
            settings.entry_point_limit,
        )
        if is_callable(kinds[match.subject_id])
        else []
        for match in matches
    }

    wanted = {match.subject_id for match in matches}
    wanted.update(
        parameter_id for match in matches for parameter_id in match.parameter_ids
    )
    wanted.update(
        symbol_id for symbol_ids in entry_point_ids.values() for symbol_id in symbol_ids
    )
    infos = {
        symbol.id: symbol_info(symbol, summary)
        for symbol, summary in await session.execute(
            symbols_with_summaries().where(orm.Symbol.id.in_(wanted))
        )
    }
    return [
        SearchHit(
            symbol=infos[match.subject_id],
            matched_parameters=[infos[symbol_id] for symbol_id in match.parameter_ids],
            entry_points=[
                infos[symbol_id] for symbol_id in entry_point_ids[match.subject_id]
            ],
            score=match.score,
        )
        for match in matches
    ]


__all__ = [
    "Candidate",
    "NotEmbeddedError",
    "SearchHit",
    "SubjectMatch",
    "find_entry_points",
    "fuse_rankings",
    "group_by_subject",
    "rank_candidates",
    "score_keywords",
    "search_code",
]
