from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

from claude_memory.settings import Settings


def apply_sqlite_pragmas(engine: Engine) -> None:
    def set_pragmas(
        dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    event.listen(engine, "connect", set_pragmas)


def create_index_engine(settings: Settings) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{settings.index_db_path}")
    apply_sqlite_pragmas(engine.sync_engine)
    return engine


def migration_config(db_path: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def run_migrations(db_path: Path) -> None:
    """Blocking; call before the event loop starts."""
    command.upgrade(migration_config(db_path), "head")
