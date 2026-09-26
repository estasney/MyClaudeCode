"""create collections, documents and documents_fts

Revision ID: 0001
Revises:
Create Date: 2026-09-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collections")),
        sa.UniqueConstraint("name", name=op.f("uq_collections_name")),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("chroma_id", sa.String(length=32), nullable=False),
        sa.Column("document", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collections.id"],
            name=op.f("fk_documents_collection_id_collections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint(
            "collection_id", "chroma_id", name=op.f("uq_documents_collection_id")
        ),
    )
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_documents_collection_id"), ["collection_id"], unique=False
        )

    op.execute(
        "CREATE VIRTUAL TABLE documents_fts USING fts5("
        "document, content='documents', content_rowid='id', tokenize='unicode61')"
    )
    op.execute(
        "CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN "
        "INSERT INTO documents_fts(rowid, document) VALUES (new.id, new.document); "
        "END"
    )
    op.execute(
        "CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN "
        "INSERT INTO documents_fts(documents_fts, rowid, document) "
        "VALUES ('delete', old.id, old.document); "
        "END"
    )
    op.execute(
        "CREATE TRIGGER documents_au AFTER UPDATE OF document ON documents BEGIN "
        "INSERT INTO documents_fts(documents_fts, rowid, document) "
        "VALUES ('delete', old.id, old.document); "
        "INSERT INTO documents_fts(rowid, document) VALUES (new.id, new.document); "
        "END"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER documents_au")
    op.execute("DROP TRIGGER documents_ad")
    op.execute("DROP TRIGGER documents_ai")
    op.execute("DROP TABLE documents_fts")
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_documents_collection_id"))

    op.drop_table("documents")
    op.drop_table("collections")
