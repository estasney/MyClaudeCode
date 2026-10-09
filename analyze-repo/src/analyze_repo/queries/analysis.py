from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from analyze_repo import orm
from analyze_repo.models import AnalysisStatus
from analyze_repo.queries.symbols import snapshot_info
from analyze_repo.semantic.documents import texts_missing_vectors
from analyze_repo.semantic.summarize import symbols_missing_summaries


async def get_analysis_status(
    session: AsyncSession, snapshot: orm.Snapshot, embedding_model: str
) -> AnalysisStatus:
    """Counts with the same queries the summarize and embed steps use to find their work."""
    body_hashes = (
        select(orm.Symbol.body_hash)
        .join(orm.File)
        .where(orm.File.snapshot_id == snapshot.id)
    )
    summary_cost = select(func.total(orm.Summary.cost_usd)).where(
        orm.Summary.body_hash.in_(body_hashes)
    )
    return AnalysisStatus(
        snapshot=await snapshot_info(session, snapshot),
        missing_summaries=len(await symbols_missing_summaries(session, snapshot)),
        missing_vectors=len(
            await texts_missing_vectors(session, snapshot, embedding_model)
        ),
        summary_cost_usd=(await session.execute(summary_cost)).scalar_one(),
    )


__all__ = ["get_analysis_status"]
