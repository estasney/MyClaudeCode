from pydantic import BaseModel


class SnapshotInfo(BaseModel):
    snapshot_id: int
    repo: str
    digest: str
    files: int
    symbols: int
    occurrences: int


class AnalysisStatus(BaseModel):
    """What a snapshot still lacks. Each count is the work the next run would do."""

    snapshot: SnapshotInfo
    missing_summaries: int
    missing_vectors: int


class AnalysisReport(BaseModel):
    """A status is None when the working tree has no snapshot."""

    status: AnalysisStatus | None
    next_step: str


__all__ = [
    "AnalysisReport",
    "AnalysisStatus",
    "SnapshotInfo",
]
