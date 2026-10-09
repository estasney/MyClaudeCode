from pydantic import BaseModel


class SnapshotInfo(BaseModel):
    snapshot_id: int
    repo: str
    digest: str
    files: int
    symbols: int
    occurrences: int


class AnalysisStatus(BaseModel):

    snapshot: SnapshotInfo
    missing_summaries: int
    missing_vectors: int
    summary_cost_usd: float


class AnalysisReport(BaseModel):
    """A status is None when the working tree has no snapshot."""

    status: AnalysisStatus | None
    next_step: str


__all__ = [
    "AnalysisReport",
    "AnalysisStatus",
    "SnapshotInfo",
]
