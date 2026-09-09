from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
    func,
    select,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    column_property,
    mapped_column,
    relationship,
)
from sqlalchemy.pool import ConnectionPoolEntry

from claude_memory.models import Polarity, Scope


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class Base(DeclarativeBase):
    pass


class SignalRow(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project: Mapped[str] = mapped_column(String(250))
    polarity: Mapped[Polarity] = mapped_column(
        SAEnum(Polarity, native_enum=False, values_callable=enum_values)
    )
    action: Mapped[str] = mapped_column(String(250))
    words: Mapped[str] = mapped_column(String(250))
    meaning: Mapped[str] = mapped_column(String(250))
    happened_at: Mapped[datetime] = mapped_column(DateTime)
    memory_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("memories.id"))

    memory: Mapped[MemoryRow | None] = relationship(back_populates="signals")

    def __str__(self) -> str:
        return f"signal {self.id}: {self.words}"


class MemoryRow(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(String(250))
    scope: Mapped[Scope] = mapped_column(
        SAEnum(Scope, native_enum=False, values_callable=enum_values)
    )
    project: Mapped[str] = mapped_column(String(250))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    signals: Mapped[list[SignalRow]] = relationship(back_populates="memory")

    signal_count: Mapped[int] = column_property(
        select(func.count(SignalRow.id))
        .where(SignalRow.memory_id == id)
        .correlate_except(SignalRow)
        .scalar_subquery()
    )
    last_signal_at: Mapped[datetime | None] = column_property(
        select(func.max(SignalRow.happened_at))
        .where(SignalRow.memory_id == id)
        .correlate_except(SignalRow)
        .scalar_subquery()
    )

    def __str__(self) -> str:
        return (
            f"memory {self.id} "
            f"[{self.scope}, {self.project}, {self.signal_count} signals] "
            f"{self.text}"
        )


def enable_wal_and_foreign_keys(
    dbapi_connection: DBAPIConnection, record: ConnectionPoolEntry
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def open_engine(db: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db}")
    event.listen(engine, "connect", enable_wal_and_foreign_keys)
    return engine


def create_schema(engine: Engine) -> None:
    """Tables, plus an external-content FTS5 index over memory text kept in
    step by triggers. Every statement is idempotent."""
    Base.metadata.create_all(engine)
    fts = (
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            text, content='memories', content_rowid='id', tokenize='porter unicode61'
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
            INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
        END
        """,
    )
    with engine.begin() as connection:
        for statement in fts:
            connection.execute(text(statement))
