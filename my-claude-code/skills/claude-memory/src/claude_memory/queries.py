from sqlalchemy import Integer, String, column, func, literal_column, or_, select, table
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from claude_memory.models import Memory, Scope, Signal
from claude_memory.orm import MemoryRow, SignalRow


class Store:
    """Reads and writes for one project. The caller owns the transaction."""

    def __init__(self, session: Session, project: str) -> None:
        self.session = session
        self.project = project

    def signal(self, signal_id: int) -> SignalRow:
        row = self.session.get(SignalRow, signal_id)
        if row is None:
            raise LookupError(f"signal {signal_id} does not exist")
        return row

    def memory(self, memory_id: int) -> MemoryRow:
        row = self.session.get(MemoryRow, memory_id)
        if row is None:
            raise LookupError(f"memory {memory_id} does not exist")
        return row

    def add_signal(self, signal: Signal) -> SignalRow:
        row = SignalRow(project=self.project, **signal.model_dump())
        self.session.add(row)
        self.session.flush()
        return row

    def derive_memory(self, memory: Memory, signal_id: int) -> MemoryRow:
        signal = self.signal(signal_id)
        row = MemoryRow(project=signal.project, signals=[signal], **memory.model_dump())
        self.session.add(row)
        return self.flush_and_reload(row)

    def rewrite_memory(
        self, memory_id: int, signal_id: int, text: str, scope: Scope | None
    ) -> MemoryRow:
        row = self.memory(memory_id)
        revised = Memory(text=text, scope=scope or row.scope)
        row.text = revised.text
        row.scope = revised.scope
        row.signals.append(self.signal(signal_id))
        return self.flush_and_reload(row)

    def support_memory(self, memory_id: int, signal_id: int) -> MemoryRow:
        row = self.memory(memory_id)
        row.signals.append(self.signal(signal_id))
        return self.flush_and_reload(row)

    def search(self, query: str, limit: int) -> list[MemoryRow]:
        """query is FTS5 syntax; results are in bm25 order."""
        fts = table("memories_fts", column("rowid", Integer))
        index = literal_column("memories_fts", String)
        statement = (
            select(MemoryRow)
            .join(fts, fts.c.rowid == MemoryRow.id)
            .where(index.match(query), self.applies_here())
            .order_by(func.bm25(index))
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def ranked(self, limit: int) -> list[MemoryRow]:
        """Most supported first, then most recently supported."""
        statement = (
            select(MemoryRow)
            .where(self.applies_here())
            .order_by(MemoryRow.signal_count.desc(), MemoryRow.last_signal_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def all(self) -> list[MemoryRow]:
        statement = select(MemoryRow).where(self.applies_here()).order_by(MemoryRow.id)
        return list(self.session.scalars(statement))

    def applies_here(self) -> ColumnElement[bool]:
        return or_(
            MemoryRow.scope == Scope.everywhere, MemoryRow.project == self.project
        )

    def flush_and_reload(self, row: MemoryRow) -> MemoryRow:
        self.session.flush()
        self.session.refresh(row)
        return row
