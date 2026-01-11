# Deployment

## Example

For async code use this pattern to expose the engine via a pydantic model or settings model
```python
from pathlib import Path
import asyncio
from collections.abc import Awaitable, Callable
from sqlalchemy import AsyncEngine, create_async_engine, event
from pydantic import BaseModel, ConfigDict, Field

# Import the Base ORM

class TaggingSettings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    context_size: int = 60000
    data_file: Path = Field(
        default=Path(
            "~/Documents/LLMDataset/openai/conversation_export.jsonl"
        ).expanduser()
    )
    db_uri: str = Field(
        default="sqlite+aiosqlite:///...."
    )


    _engine: AsyncEngine | None = None
    _init_lock: asyncio.Lock | None = None
    _init_task: asyncio.Task[AsyncEngine] | None = None

    def _install_sqlite_pragmas(self, engine: AsyncEngine) -> None:
        is_sqlite = engine.sync_engine.dialect.name == "sqlite"

        @event.listens_for(engine.sync_engine, "connect")
        def _on_connect(dbapi_connection, connection_record) -> None:  # noqa: ANN001
            if not is_sqlite:
                return
            dbapi_connection.run_async(lambda c: c.execute("PRAGMA foreign_keys = ON;"))
            dbapi_connection.run_async(lambda c: c.execute("PRAGMA journal_mode = WAL;"))

    async def _init_engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(self.db_uri, future=True)
            self._install_sqlite_pragmas(self._engine)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return self._engine

    @property
    def db_engine(self) -> Callable[[], Awaitable[AsyncEngine]]:
        async def factory() -> AsyncEngine:
            if self._engine is not None and self._init_task is None:
                return self._engine
            if self._init_lock is None:
                self._init_lock = asyncio.Lock()
            async with self._init_lock:
                if self._init_task is None:
                    self._init_task = asyncio.create_task(self._init_engine())
                task = self._init_task
            return await task

        return factory
```

Callers will use `await settings.db_engine()` to get the initialized engine.

## Connection Pooling

The `Engine` manages a pool of reusable database connections. This is automatic, but you can configure pool size:

```python
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://user:pass@localhost/dbname",
    pool_size=10,           # Number of connections to keep in the pool
    max_overflow=20,        # Additional connections allowed when pool is exhausted
    pool_recycle=3600,      # Recycle connections older than 1 hour
)
```

**pool_size:** Number of persistent connections. Default is 5. Increase for high concurrency.

**max_overflow:** When all pool connections are in use, create up to this many additional connections. Default is 10. Total possible connections = `pool_size + max_overflow`.

**pool_recycle:** Some databases (MySQL, MariaDB) drop idle connections. Set this to recycle connections periodically (in seconds). For connections that disconnect after a few hours, set to 3600 (1 hour).

**pool_pre_ping:** Enable connection testing before use to detect stale connections:

```python
engine = create_engine(url, pool_pre_ping=True)
```

This adds a small `SELECT 1` query before reusing a connection from the pool. Useful if connections might be dropped by the database.

For testing or single-threaded apps, use `StaticPool` (no pooling):

```python
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:",
    poolclass=StaticPool
)
```

## SQLite Pitfalls

SQLite is not suitable for concurrent access. However, for testing or simple single-threaded apps:

```python
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///app.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # Avoid pooling for SQLite
)
```

**Why these settings?**

- `check_same_thread=False`: Allows multiple threads to use the same connection. Without this, SQLite raises errors on cross-thread access.
- `StaticPool`: SQLite doesn't benefit from connection pooling. Using the default `QueuePool` can cause lock contention.

**Pragmas for SQLite:**

SQLite has configuration options called PRAGMAs. Set them via event listeners:

```python
from sqlalchemy import event, create_engine

engine = create_engine("sqlite:///app.db")

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
```

Common pragmas:
- `PRAGMA foreign_keys=ON`: Enable foreign key constraints (disabled by default in SQLite).
- `PRAGMA journal_mode=WAL`: Use write-ahead logging for better concurrent read performance.

## Monitoring and Debugging

Enable SQL logging to see executed queries:

```python
engine = create_engine(url, echo=True)
```

This logs all SQL statements. In production, use a structured logger:

```python
import logging

logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
```

Check pool stats:

```python
pool = engine.pool
print(f"Pool size: {pool.size()}")
print(f"Checked out: {pool.checkedout()}")
```

This is useful for debugging connection leaks or pool exhaustion.

You can see the compiled version of a query for debugging:

```python
from sqlalchemy import select, text
q = text("SELECT * FROM users WHERE id = :id").bindparams(id=1)
print(stmt.compile(compile_kwargs={"literal_binds": True}))
```
