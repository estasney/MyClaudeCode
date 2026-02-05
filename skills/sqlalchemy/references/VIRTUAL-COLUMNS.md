# Virtual Columns: Computed Attributes That Aren't Persisted

## Problem Statement

You have a model with a foreign key (`some_type_id`) that references a lookup table. You want instances to carry the resolved human-readable value (`some_type` as a string) without it being a real column. The resolved value should be populated during reads, safe to omit, and distinguishable from true columns at runtime — for example, when serializing instances or recreating rows in a different schema where the FK identity tables may not exist.

## `column_property` — Always-On Virtual Column

Use when every query should automatically resolve the value. No opt-in required at query sites.

```python
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, column_property, mapped_column


class Base(DeclarativeBase):
    pass


class SomeTypes(Base):
    __tablename__ = "sometypes"

    typed_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class MyTable(Base):
    __tablename__ = "mytable"

    id: Mapped[int] = mapped_column(primary_key=True)
    some_type_id: Mapped[int] = mapped_column(ForeignKey("sometypes.typed_id"))

    # .correlate_except(SomeTypes) tells SA to correlate against all enclosing
    # tables *except* SomeTypes — keeping it in the subquery's FROM clause.
    # See: https://docs.sqlalchemy.org/en/20/orm/mapped_sql_expr.html
    some_type = column_property(
        select(SomeTypes.name)
        .where(SomeTypes.typed_id == some_type_id)
        .correlate_except(SomeTypes)
        .scalar_subquery()
    )
```

Every `select(MyTable)` automatically includes the correlated subquery — no `.options()`, no ceremony:

```python
stmt = select(MyTable).where(MyTable.id == 1)

with engine.begin() as conn:
    for row in conn.execute(stmt).all():
        instance = row[0]
        print(instance.id, instance.some_type)
```

The attribute is read-only. Assigning to it overwrites the in-memory value but has no effect on persistence.

## `query_expression` — Opt-In Virtual Column

Use when only some query sites need the resolved value and you want a safe, cheap default (`None`) everywhere else.

### Model definition

```python
from sqlalchemy import ForeignKey, String, literal
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, query_expression


class MyTable(Base):
    __tablename__ = "mytable"

    id: Mapped[int] = mapped_column(primary_key=True)
    some_type_id: Mapped[int] = mapped_column(ForeignKey("sometypes.typed_id"))

    some_type: Mapped[str | None] = query_expression(default_expr=literal(None))
```

`default_expr=literal(None)` injects `NULL` into the SELECT when no expression is supplied. The attribute is `None` — no lazy load, no error.

### Supplying the expression — ORM subquery

```python
from sqlalchemy import select
from sqlalchemy.orm import with_expression

type_expr = (
    select(SomeTypes.name)
    .where(SomeTypes.typed_id == MyTable.some_type_id)
    .correlate(MyTable)
    .scalar_subquery()
)

stmt = select(MyTable).options(with_expression(MyTable.some_type, type_expr))

with engine.begin() as conn:
    for row in conn.execute(stmt).all():
        instance = row[0]
        print(instance.id, instance.some_type)
```

### Supplying the expression — `text()` subquery

Use when the lookup table has no ORM model or the SQL is dynamic:

```python
from sqlalchemy import String, column, text
from sqlalchemy.orm import with_expression

type_expr = (
    text("(SELECT st.name FROM sometypes st WHERE st.typed_id = mytable.some_type_id)")
    .columns(column("name", String))
    .scalar_subquery()
)

stmt = select(MyTable).options(with_expression(MyTable.some_type, type_expr))

with engine.begin() as conn:
    for row in conn.execute(stmt).all():
        print(row[0].some_type)
```

Three things to get right with `text()`:

- Reference the outer table by its **actual table name** (`mytable`) — SA won't alias it inside raw text.
- `.columns(column("name", String))` provides the return type. Without it you get untyped driver values.
- `.scalar_subquery()` is required — `with_expression` expects a scalar column expression, not a `TextClause`.

## `hybrid_property` — Filterable Virtual Column

Use when you need the virtual attribute to work in WHERE clauses at the class level (`MyTable.some_type == "foo"`) and want the resolution logic defined once on the model.

```python
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship


class MyTable(Base):
    __tablename__ = "mytable"

    id: Mapped[int] = mapped_column(primary_key=True)
    some_type_id: Mapped[int] = mapped_column(ForeignKey("sometypes.typed_id"))

    some_type_rel: Mapped["SomeTypes"] = relationship(lazy="raise")

    @hybrid_property
    def some_type(self) -> str:
        return self.some_type_rel.name

    @some_type.expression
    @classmethod
    def some_type(cls):
        return (
            select(SomeTypes.name)
            .where(SomeTypes.typed_id == cls.some_type_id)
            .correlate(cls)
            .scalar_subquery()
        )
```

Instance access reads from the relationship (must be eager-loaded to avoid N+1). Class-level access uses the `@expression` for SQL generation. Setting `lazy="raise"` forces explicit loading — use `selectinload(MyTable.some_type_rel)` or `joinedload(MyTable.some_type_rel)` at query time.

## Distinguishing Real Columns from Virtual Attributes

Both `column_property` and `query_expression` live in `mapper.column_attrs`. Distinguish them from real columns via `MappedSQLExpression`. `hybrid_property` lives separately in `all_orm_descriptors`.

```python
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.hybrid import hybrid_property as hybrid_descriptor
from sqlalchemy.orm.properties import MappedSQLExpression

mapper = sa_inspect(MyTable)

true_columns = {a.key for a in mapper.column_attrs if not isinstance(a, MappedSQLExpression)}
virtual_columns = {a.key for a in mapper.column_attrs if isinstance(a, MappedSQLExpression)}

hybrid_attrs = {
    key for key, desc in mapper.all_orm_descriptors.items()
    if isinstance(desc, hybrid_descriptor)
}
```

## Decision Guide

| Concern | `column_property` | `query_expression` | `hybrid_property` |
|---|---|---|---|
| Always resolved | Yes — every query | No — opt-in via `with_expression` | No — needs eager-loaded relationship |
| No-load behavior | N/A — always loads | `None` — safe default | Raises if relationship not loaded |
| Filterable in WHERE | Yes | Not directly | Yes via `@expression` |
| Different resolution per query | No | Yes — caller supplies expression | No |
| Requires relationship | No | No | Typically yes |
| Setter support | No | No | Yes via `@attr.setter` |