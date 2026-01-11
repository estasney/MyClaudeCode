# Core Patterns

## Textual SQL with text()

For raw SQL, use `text()` from `sqlalchemy`. This safely handles parameterization:

```python
from sqlalchemy import text

stmt = text("SELECT * FROM users WHERE age > :min_age")
result = session.execute(stmt, {"min_age": 18})
```

Never use f-strings for SQL. This is a security issue (SQL injection) and SQLAlchemy can't parameterize properly:

```python
# WRONG - Security vulnerability
min_age = 18
stmt = text(f"SELECT * FROM users WHERE age > {min_age}")

# CORRECT
stmt = text("SELECT * FROM users WHERE age > :min_age").bindparams(min_age=min_age)
result = session.execute(stmt)
```

Even for what feels like "simple" values, always use parameters. SQLAlchemy's expression language handles parameterization automatically, but `text()` requires manual parameter specification.

## Bind Parameters and Expanding

Bind parameters are placeholders for values. The `:name` syntax is for scalar values:

```python
stmt = text("SELECT * FROM users WHERE id = :user_id").bindparams(user_id=42)
result = session.execute(stmt)
```

For lists or sets, use the `expanding` parameter. This expands a single parameter into multiple placeholders:

```python
from sqlalchemy import bindparam

stmt = text("SELECT * FROM users WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True, value=[1, 2, 3, 4, 5])
)
result = session.execute(stmt)
```

This generates `WHERE id IN (?, ?, ?, ?, ?)` with the values bound properly.

Or with SQLAlchemy's expression language:

```python
from sqlalchemy import select

stmt = select(User).where(User.id.in_([1, 2, 3, 4, 5]))
result = session.execute(stmt)
```

## Table vs table vs ORM Table

`Table` is a Core construct that represents a database table without ORM mapping
but with shared metadata.

```python
from sqlalchemy import Table, MetaData, Column, Integer, String

metadata = MetaData()
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255)),
)

metadata.create_all(engine)
```

Use `Table` directly when:
- You're building a pure SQL data layer without ORM
- You're working with an existing database and don't want to define ORM classes
- You need dynamic table construction

For ORM, the model class (e.g., `class User(Base)`) implicitly creates and manages a `Table` object. Access it via `User.__table__` if you need the underlying Core table.

`table` (lowercase) is a lightweight construct for ad-hoc queries without full table definitions. It's less common and mainly used for quick scripts or testing. It does not require metadata.


Querying a Core Table:

```python
stmt = select(users_table).where(users_table.c.id == 1)
result = session.execute(stmt).fetchall()
```

The `.c` attribute accesses columns: `users_table.c.id`, `users_table.c.name`.

## Inserts with ON CONFLICT

Insert a row:

```python
from sqlalchemy import insert

stmt = insert(users_table).values(id=1, name="Alice")
session.execute(stmt)
session.commit()
```

For multiple rows:

```python
stmt = insert(users_table).values([
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
])
session.execute(stmt)
session.commit()
```

With `ON CONFLICT` (SQLite syntax; adjust for your database):

```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = sqlite_insert(users_table).values(id=1, name="Alice")
stmt = stmt.on_conflict_do_update(
    index_elements=["id"],
    set_={"name": "Alice Updated"}
)
session.execute(stmt)
session.commit()
```

For ignoring conflicts (don't update, just skip):

```python
stmt = sqlite_insert(users_table).values(id=1, name="Alice")
stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
session.execute(stmt)
```

## Type Coercion with TypeAdapter

Use `TypeAdapter` to coerce columns to specific types. This is useful when you're selecting from a Core table and want SQLAlchemy to convert the result to a specific Python type:

```python
from sqlalchemy import TypeAdapter, JSON

# Coerce a text column to JSON
json_adapter = TypeAdapter(JSON)
stmt = select(json_adapter.type_engine(engine).bind_processor(engine)).from_(users_table)
```

More practically, use it when selecting raw data and needing type conversion:

```python
from sqlalchemy import TypeAdapter, String

adapter = TypeAdapter(String)
result = session.execute(select(some_column)).scalar()
converted = adapter.process_result(result, engine)
```

For custom types, see TYPES.md.
