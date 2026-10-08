import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from analyze_repo import orm
from analyze_repo.semantic.documents import split_words


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


__all__ = [
    "Candidate",
    "SubjectMatch",
    "find_entry_points",
    "fuse_rankings",
    "group_by_subject",
    "is_callable",
    "rank_candidates",
    "score_keywords",
]
