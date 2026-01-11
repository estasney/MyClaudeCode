# ORM Patterns

## Defining Base and Metadata

In SQLAlchemy 2.0+, create a `declarative_base` once at module level:

```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

All model classes inherit from `Base`. The `Base.metadata` object tracks all table definitions and is used to create tables:

```python
Base.metadata.create_all(engine)
```

This creates all tables defined by models that haven't been created yet. For production, use a migration tool like Alembic instead—`create_all()` is mainly useful for testing or simple applications.

To drop all tables (careful—this deletes data):

```python
Base.metadata.drop_all(engine)
```

## Mapped Columns

Use `mapped_column()` to define columns in ORM models. This is the v2.0+ pattern:

```python
from sqlalchemy import String, Integer
from sqlalchemy.orm import mapped_column

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    age: Mapped[int | None] = mapped_column(nullable=True)
```

The type annotation (`Mapped[int]`) tells SQLAlchemy the Python type. The `mapped_column()` call configures the database column. This pattern is cleaner than the old `Column()` syntax and enables better IDE support.

For columns with defaults:

```python
from datetime import datetime

class Post(Base):
    __tablename__ = "posts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

## Table Kwargs

Pass `__table_args__` as a dict to set table-level options:

```python
class User(Base):
    __tablename__ = "users"
    __table_args__ = {
        "sqlite_autoincrement": True,  # SQLite-specific
    }
    
    id: Mapped[int] = mapped_column(primary_key=True)
```

You can also pass a tuple where the last element is the dict:

```python
from sqlalchemy import Index

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_email", "email"),
        {"sqlite_autoincrement": True},
    )
```

This is useful for compound indexes, constraints, or database-specific options.

## Relationships

Define relationships with `relationship()`. This creates a Python attribute that loads related rows:

```python
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    posts: Mapped[list["Post"]] = relationship(back_populates="user")

class Post(Base):
    __tablename__ = "posts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(back_populates="posts")
```

The `back_populates` argument ensures both sides of the relationship are kept in sync. When you set `post.user = user`, SQLAlchemy automatically appends `post` to `user.posts`.

For lazy loading strategies (how related data is loaded), see Eager Loading below.

## Eager Loading

By default, accessing a relationship triggers a new database query (lazy loading). For performance, use eager loading to load related data in one query:

```python
from sqlalchemy.orm import selectinload
from sqlalchemy import select

stmt = select(User).options(selectinload(User.posts))
users = session.execute(stmt).scalars().all()
```

Now accessing `user.posts` doesn't trigger another query—the data is already loaded.

Other eager loading strategies:

- `joinedload()`: Uses a JOIN to fetch related data. Good for one-to-one or many-to-one. Avoids extra queries but can result in duplicate rows if the join has multiple matches.
- `selectinload()`: Uses a second SELECT with IN clause. Good for one-to-many or many-to-many. Avoids duplicates.
- `contains_eager()`: Explicitly joins and maps the result. Use when you're already JOINing and want to populate the relationship from the join result.

Example with joinedload:

```python
from sqlalchemy.orm import joinedload

stmt = select(User).options(joinedload(User.posts))
users = session.execute(stmt).scalars().unique().all()
```

The `.unique()` call deduplicates rows that appear multiple times due to the join.

## Filtering and Aggregation

Use SQLAlchemy's expression language in `where()` clauses:

```python
stmt = select(User).where(User.age > 18).where(User.name.ilike("%john%"))
results = session.execute(stmt).scalars().all()
```

For aggregation, import and use aggregate functions:

```python
from sqlalchemy import func

count_stmt = select(func.count(User.id)).where(User.age > 18)
count = session.execute(count_stmt).scalar()
```

Other functions: `func.max()`, `func.min()`, `func.avg()`, `func.sum()`, `func.group_concat()`.

## Transactions and Commits

Changes in a session aren't saved to the database until you commit:

```python
user = User(name="Alice", email="alice@example.com")
session.add(user)
session.commit()
```

If something fails, use `rollback()` to undo pending changes:

```python
try:
    user = User(name="Alice")
    session.add(user)
    session.commit()
except Exception:
    session.rollback()
    raise
```

For context manager pattern (recommended):

```python
with session.begin():
    user = User(name="Alice")
    session.add(user)
```

Exiting the context manager automatically commits. If an exception occurs, it automatically rolls back.
