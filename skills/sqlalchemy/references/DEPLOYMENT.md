# Deployment

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
- `PRAGMA synchronous=NORMAL`: Reduce sync overhead (trades durability for speed).

## Production Configuration

For production PostgreSQL:

```python
from sqlalchemy import create_engine, event

engine = create_engine(
    "postgresql+psycopg2://user:pass@localhost/dbname",
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,  # Disable SQL logging in production
)
```

For MySQL/MariaDB (note the pool_recycle):

```python
engine = create_engine(
    "mysql+pymysql://user:pass@localhost/dbname",
    pool_size=10,
    max_overflow=20,
    pool_recycle=28800,  # 8 hours (MySQL default is 8 hours)
    pool_pre_ping=True,
)
```

## Async Deployment

For async in production, use PostgreSQL with asyncpg:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/dbname",
    pool_size=10,
    max_overflow=20,
)
```

For SQLite with async (testing only, not production):

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

engine = create_async_engine(
    "sqlite+aiosqlite:///app.db",
    poolclass=StaticPool,
)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

**Why aiosqlite is slow:** SQLite is inherently synchronous. aiosqlite runs blocking calls in a thread pool, which is slower than native async drivers like asyncpg for PostgreSQL.

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
