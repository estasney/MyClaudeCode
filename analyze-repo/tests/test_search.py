from collections.abc import Mapping, Sequence

import pytest

from analyze_repo.search import (
    Candidate,
    SubjectMatch,
    find_entry_points,
    fuse_rankings,
    group_by_subject,
    score_keywords,
)


def test_score_keywords_prefers_documents_holding_more_question_words() -> None:
    """Arrange: three documents sharing two, three, and none of the question words.
    Act: score them with BM25.
    Assert: the document with every word leads and the unrelated one scores zero."""
    documents = [
        ["batch", "size"],
        ["delete", "entries"],
        ["create", "space", "batch", "size"],
    ]
    scores = score_keywords(["batch", "size", "space"], documents).tolist()
    assert scores[2] > scores[0] > scores[1] == 0, (
        f"scores should order the documents 2, 0, 1, got {scores}"
    )


def test_fuse_rankings_rewards_agreement() -> None:
    """Arrange: two rankings that both place document 0 near the top.
    Act: fuse them by reciprocal rank.
    Assert: the order follows the summed reciprocal ranks."""
    fused = fuse_rankings([[0, 1, 2], [2, 0]])
    order = [position for position, _ in fused]
    assert order == [0, 2, 1], f"fused order should be [0, 2, 1], got {order}"


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        (1, [SubjectMatch(subject_id=1, score=0.9, parameter_ids=[2])]),
        (
            2,
            [
                SubjectMatch(subject_id=1, score=0.9, parameter_ids=[2]),
                SubjectMatch(subject_id=3, score=0.8, parameter_ids=[4]),
            ],
        ),
    ],
    ids=["stops at the first subject past the limit", "keeps later parameters"],
)
def test_group_by_subject(limit: int, expected: list[SubjectMatch]) -> None:
    """Arrange: two functions and one parameter of each ranked with a parameter first.
    Act: group the ranking by subject.
    Assert: a parameter stands for its function and is listed under it."""
    candidates = [
        Candidate(symbol_id=1, subject_id=1, words=["f"]),
        Candidate(symbol_id=2, subject_id=1, words=["f", "a"]),
        Candidate(symbol_id=3, subject_id=3, words=["g"]),
        Candidate(symbol_id=4, subject_id=3, words=["g", "b"]),
    ]
    ranked = [(1, 0.9), (2, 0.8), (0, 0.7), (3, 0.6)]
    result = group_by_subject(ranked, candidates, limit)
    assert result == expected, f"limit {limit} should group as {expected}, got {result}"


@pytest.mark.parametrize(
    ("callers_by_callee", "depth", "expected"),
    [
        ({}, 5, [1]),
        ({1: [2], 2: [3]}, 5, [3]),
        ({1: [2], 2: [3]}, 1, []),
        ({1: [2], 2: [1]}, 5, []),
        ({1: [2, 3], 3: [4]}, 5, [2, 4]),
    ],
    ids=[
        "uncalled start is its own entry point",
        "chain ends at the outermost caller",
        "depth stops the walk",
        "cycle has no entry point",
        "nearest entry points first",
    ],
)
def test_find_entry_points(
    callers_by_callee: Mapping[int, Sequence[int]], depth: int, expected: list[int]
) -> None:
    """Arrange: a call graph given as the callers of each symbol.
    Act: walk callers from symbol 1.
    Assert: the symbols reached that nothing calls are returned."""
    result = find_entry_points(callers_by_callee, 1, depth, 5)
    assert result == expected, (
        f"{callers_by_callee} at depth {depth} should reach {expected}, got {result}"
    )
