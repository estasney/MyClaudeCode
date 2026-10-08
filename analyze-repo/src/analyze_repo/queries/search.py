import asyncio
from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analyze_repo import orm
from analyze_repo.models import SearchHit
from analyze_repo.queries.symbols import (
    is_call_site,
    symbol_info,
    symbols_with_summaries,
)
from analyze_repo.semantic.documents import split_words
from analyze_repo.semantic.embedding import Embedder
from analyze_repo.semantic.ranking import (
    Candidate,
    find_entry_points,
    group_by_subject,
    is_callable,
    rank_candidates,
)
from analyze_repo.settings import Settings


class NotEmbeddedError(LookupError):
    def __init__(self, snapshot_id: int, model: str) -> None:
        super().__init__(
            f"snapshot {snapshot_id} has search documents without a {model} vector"
        )


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


__all__ = ["NotEmbeddedError", "search_code"]
