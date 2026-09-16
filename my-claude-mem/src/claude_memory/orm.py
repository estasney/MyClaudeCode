from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

type JsonValue = str | int | float | bool | list[str | int | float | bool] | None
type Json = dict[str, JsonValue]


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512), unique=True)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", passive_deletes=True
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("collection_id", "chroma_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chroma_id: Mapped[str] = mapped_column(String(32), nullable=False)
    document: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Json | None] = mapped_column("metadata", JSON, nullable=True)

    collection: Mapped[Collection] = relationship(back_populates="documents")
