# ORM Integration

Pydantic and SQLAlchemy frequently work together. This section covers the practical patterns for converting between ORM objects and Pydantic models, including edge cases around non-ORM result types and bidirectional relationships.

## from_attributes for ORM instances

When working with fully loaded ORM model instances, set `from_attributes=True` in config. Pydantic reads Python attributes instead of expecting dict keys:

```python
from pydantic import BaseModel, ConfigDict, Field

class AppBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

class UserOut(AppBase):
    id: int = Field(description="User primary key", examples=[1])
    name: str = Field(description="Display name", examples=["Alice"])
    email: str = Field(description="Email address", examples=["alice@example.com"])

orm_user = session.get(User, 1)
schema = UserOut.model_validate(orm_user)
```

`model_validate` replaces v1's `from_orm()`. The `from_attributes` flag tells Pydantic to use `getattr()` on the input object rather than treating it as a dict.

## Row and RowMapping results

Not every query returns ORM instances. Multi-column selects, aggregates, labeled expressions, and raw SQL return `Row` objects. These are not ORM model instances, so `from_attributes` is not the right tool.

Use `result.mappings().all()` to get a list of `RowMapping` objects (dict-like), then pass them directly to `model_validate`:

```python
from sqlalchemy import func, select

result = session.execute(
    select(
        User.id,
        User.name,
        func.count(Order.id).label("order_count"),
    )
    .join(Order, isouter=True)
    .group_by(User.id, User.name)
)
rows = result.mappings().all()
summaries = [UserSummary.model_validate(row) for row in rows]
```

`RowMapping` implements the mapping protocol, so Pydantic treats it like a dict. No `from_attributes` needed.

For a single row:

```python
row = result.mappings().first()
if row:
    summary = UserSummary.model_validate(row)
```

## Scalar results

When selecting a single column or using `.scalars()`, the result is a plain Python value, not a Row. No Pydantic model is needed -- you already have the typed value:

```python
user_ids: list[int] = session.execute(select(User.id)).scalars().all()
```

## Bidirectional relationships and recursion

SQLAlchemy models commonly have bidirectional relationships (parent -> children, child -> parent). When `from_attributes=True` is set, Pydantic will chase every attribute it finds, including back-references. This causes infinite recursion if both sides are modeled.

There are two approaches:

### Approach 1: Exclude back-references at serialization time

When you need both directions modeled in the type system (e.g., navigating parent-to-child and child-to-parent in different code paths), define both but exclude the back-reference when dumping:

```python
class ChildOut(AppBase):
    id: int = Field(description="Child record ID", examples=[1])
    name: str = Field(description="Child name", examples=["Alice"])
    parent: "ParentOut" = Field(description="Parent record")

class ParentOut(AppBase):
    id: int = Field(description="Parent record ID", examples=[1])
    children: list[ChildOut] = Field(description="Child records", examples=[])

ParentOut.model_rebuild()
```

At serialization time, use `exclude` with the `__all__` key to strip the back-reference from every item in the list:

```python
parent_data = parent_out.model_dump(
    exclude={"children": {"__all__": {"parent"}}}
)
```

The `__all__` key applies the exclusion to every element in the list. Without it, Pydantic expects integer indices for element-wise exclusion.

For nested dicts (not lists), exclude directly by field name:

```python
model.model_dump(exclude={"child": {"parent"}})
```

### Approach 2: Shallow reference models

When one direction is only needed for identification (not full data), define a shallow model that carries just the ID or a minimal set of fields:

```python
class ParentRef(AppBase):
    id: int = Field(description="Parent ID", examples=[1])

class ChildOut(AppBase):
    id: int = Field(description="Child record ID", examples=[1])
    name: str = Field(description="Child name", examples=["Alice"])
    parent: ParentRef = Field(description="Parent reference")

class ParentOut(AppBase):
    id: int = Field(description="Parent record ID", examples=[1])
    children: list[ChildOut] = Field(description="Child records", examples=[])
```

No recursion possible because `ParentRef` does not include `children`. This is cleaner when you know the consuming code only needs the parent's ID from the child's perspective.

## Common base class

Always define a shared base for ORM-facing models to avoid repeating config:

```python
from pydantic import BaseModel, ConfigDict

class AppBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        extra="forbid",
    )
```

All ORM schemas inherit from `AppBase`. Config changes propagate everywhere.

## Lazy-loaded relationships

By default, accessing an unloaded relationship on an ORM object triggers a lazy load (SQL query). If the session is closed or the object is detached, this raises `DetachedInstanceError`.

Options:

- Eager load with `joinedload()`, `selectinload()`, or `subqueryload()` in the query
- Use `raiseload()` to make unloaded access fail loudly during development
- Define separate Pydantic models for "with relationships" and "without relationships" cases, matching the query's loading strategy

Do not rely on Pydantic's `from_attributes` traversal to implicitly trigger lazy loads -- it works but creates N+1 query problems silently.

## Reserved attribute names

SQLAlchemy's `Base` class reserves `metadata`. If your table has a `metadata` column, alias it in the ORM model (e.g., `metadata_`) and use `validation_alias` or `alias` in the Pydantic model to map it back.
