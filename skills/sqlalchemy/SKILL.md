---
name: sqlalchemy
description: Guide for working with SQLAlchemy ORM and Core. Use when working with SQLAlchemy constructs including model definitions, querying, transactions, custom types, async patterns, session management, and connection pooling. Covers best practices for version 2.0+.
allowed-tools: Read(./*)
---

# SQLAlchemy

This skill provides guidance for working with SQLAlchemy ORM and Core constructs.

## About This Guide

SQLAlchemy has two primary interfaces. The **ORM** uses Python classes to represent database tables, where each class instance represents a row. The **Core** interface uses an expression language to construct SQL statements directly without class mapping. Identifying which you're using matters because their patterns differ significantly.

Check for these signals: ORM uses `declarative_base()`, `Column`, or `mapped_column`, `relationship`. Core uses `select()`, `insert()`, `text()`, `Table`, `Table.c.<column>`.

## Core Concepts

### Engine and Connection Pooling

The `Engine` is your entry point to SQLAlchemy. It manages the connection pool and provides connections to the database. Create it once at application startup:

```python
from sqlalchemy import create_engine

engine = create_engine("sqlite:///app.db")
```

For production use, the connection pool manages a pool of reusable connections automatically. SQLite requires special handling for threading and async—see [DEPLOYMENT.md](references/DEPLOYMENT.md).

### Session

The `Session` is your transaction context. All ORM operations happen within a session. For multi-threaded or async applications, create a `SessionMaker` that acts as a factory for thread-safe or task-safe sessions—see [SESSION.md](references/SESSION.md).

### Queries

Queries use the `select()` construct and always run within a session or connection context:

```python
from sqlalchemy import select

stmt = select(User).where(User.email == "user@example.com")
result = session.execute(stmt)
user = result.scalar_one_or_none()
```

See [CORE-PATTERNS.md](references/CORE-PATTERNS.md) for textual SQL, bind parameters, and ON CONFLICT patterns. See [ORM-PATTERNS.md](references/ORM-PATTERNS.md) for relationship loading and eager loading strategies.

## Decision Tree

**Starting a new project?**

Choose ORM or Core: ORM if you want Python class abstractions for tables and relationships. Core if you want direct SQL expression control or are building a data layer that doesn't need ORM overhead.

**Working with models and relationships?**

Go to [ORM-PATTERNS.md](references/ORM-PATTERNS.md). This covers model definition, mapped columns, relationships, table kwargs, and metadata setup.

**Constructing SQL or handling edge cases (raw SQL, bulk inserts, conflicts)?**

Go to [CORE-PATTERNS.md](references/CORE-PATTERNS.md). This covers textual SQL, bind parameters, table vs Table, inserts with ON CONFLICT, and type coercion.

**Need custom column types (JSON, UUID, encrypted data)?**

Go to [TYPES.md](references/TYPES.md). This explains TypeAdapters and how to build custom types like GZipped columns.

**Building for production or async?**

Go to [SESSION.md](references/SESSION.md) for SessionMaker and thread safety. Go to [DEPLOYMENT.md](references/DEPLOYMENT.md) for connection pooling, SQLite threading, and async SQLAlchemy patterns.

**Debugging query issues?**

Enable SQL echo: `engine = create_engine(url, echo=True)` to log all executed statements.
