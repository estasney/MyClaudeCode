from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = [
    "Base",
    "File",
    "Language",
    "Occurrence",
    "Repo",
    "Snapshot",
    "Summary",
    "Symbol",
    "SymbolKind",
]


class Language(StrEnum):
    python = "python"
    typescript = "typescript"


class SymbolKind(StrEnum):
    """The kinds basedpyright's symbol indexer emits, read from lspUtils.ts."""

    class_ = "class"
    function = "function"
    method = "method"
    variable = "variable"
    constant = "constant"


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, comment="Project Name")
    location: Mapped[str] = mapped_column(
        Text, nullable=False, comment="disk based or url"
    )

    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="repo", cascade="all, delete-orphan", passive_deletes=True
    )


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("repo_id", "digest"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    digest: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    repo: Mapped[Repo] = relationship(back_populates="snapshots")
    files: Mapped[list["File"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", passive_deletes=True
    )


class File(Base):
    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("snapshot_id", "path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Language] = mapped_column(
        SQLEnum(Language, values_callable=enum_values), nullable=False
    )

    snapshot: Mapped[Snapshot] = relationship(back_populates="files")
    symbols: Mapped[list["Symbol"]] = relationship(
        back_populates="file", cascade="all, delete-orphan", passive_deletes=True
    )


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_symbol_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("symbols.id", ondelete="CASCADE"),
        index=True,
        comment="enclosing definition; NULL at module level",
    )
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[SymbolKind] = mapped_column(
        SQLEnum(SymbolKind, values_callable=enum_values), nullable=False
    )
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)

    file: Mapped[File] = relationship(back_populates="symbols")
    parent: Mapped["Symbol | None"] = relationship(remote_side="Symbol.id")
    occurrences: Mapped[list["Occurrence"]] = relationship(
        back_populates="symbol",
        foreign_keys="Occurrence.symbol_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Occurrence(Base):
    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enclosing_symbol_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("symbols.id", ondelete="CASCADE"), index=True
    )
    line: Mapped[int] = mapped_column(Integer, nullable=False)
    column: Mapped[int] = mapped_column(Integer, nullable=False)
    node_kind: Mapped[str] = mapped_column(
        Text, nullable=False, comment="tree-sitter node kind at the reference range"
    )
    parent_kind: Mapped[str] = mapped_column(
        Text, nullable=False, comment="tree-sitter node kind of the parent"
    )
    parent_field: Mapped[str | None] = mapped_column(
        Text, comment="tree-sitter field name the node fills in its parent"
    )

    file: Mapped[File] = relationship()
    symbol: Mapped[Symbol] = relationship(
        back_populates="occurrences", foreign_keys=[symbol_id]
    )
    enclosing_symbol: Mapped[Symbol | None] = relationship(
        foreign_keys=[enclosing_symbol_id]
    )


class Summary(Base):
    __tablename__ = "summaries"

    body_hash: Mapped[str] = mapped_column(
        Text, primary_key=True, comment="matches Symbol.body_hash"
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(
        Text, nullable=False, comment="model id that wrote it"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
