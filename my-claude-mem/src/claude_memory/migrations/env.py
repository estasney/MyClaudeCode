from alembic import context
from sqlalchemy import create_engine, text

from claude_memory.orm import Base


class ForeignKeyViolationError(RuntimeError):
    def __init__(self, violations: list[tuple[object, ...]]) -> None:
        super().__init__(f"foreign_key_check failed after migration: {violations}")


class MissingDatabaseUrlError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "sqlalchemy.url is not set; run migrations through run_migrations"
        )


def run_migrations_online() -> None:
    url = context.config.get_alembic_option("sqlalchemy.url")
    if not isinstance(url, str):
        raise MissingDatabaseUrlError
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
            violations = connection.execute(text("PRAGMA foreign_key_check")).all()
            if violations:
                raise ForeignKeyViolationError([tuple(row) for row in violations])
    engine.dispose()


run_migrations_online()
