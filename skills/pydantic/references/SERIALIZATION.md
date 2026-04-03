# Serialization

Pydantic uses "serialize" and "dump" interchangeably. Both refer to converting a model to a dict or JSON string.

## model_dump and model_dump_json

```python
user = User(id=1, name="Alice")
user.model_dump()                    # -> dict
user.model_dump_json()               # -> str (JSON)
user.model_dump(mode="json")         # -> dict with JSON-compatible types
```

`model_dump()` in Python mode returns dicts that may contain non-JSON-serializable objects (datetime, Decimal, etc.). Pass `mode="json"` to get a dict with only JSON-safe types without going through a JSON string.

Common parameters:

- `include` / `exclude` -- set of field names or nested dict for fine-grained control
- `exclude_unset` -- omit fields not explicitly set at construction
- `exclude_defaults` -- omit fields matching their default value
- `exclude_none` -- omit fields with `None` value
- `by_alias` -- use alias names as keys instead of field names
- `serialize_as_any` -- include subclass fields (see below)

## Subclass Serialization (v2 behavior change)

In v1, serializing a subclass always included all subclass fields. In v2, when a field is typed as a parent class, only fields defined on that parent type are included. This prevents accidental leakage of sensitive subclass fields.

```python
class User(BaseModel):
    name: str

class AdminUser(User):
    secret_token: str

class Wrapper(BaseModel):
    user: User

w = Wrapper(user=AdminUser(name="Alice", secret_token="abc"))
w.model_dump()
# {'user': {'name': 'Alice'}}  -- secret_token excluded
w.model_dump(serialize_as_any=True)
# {'user': {'name': 'Alice', 'secret_token': 'abc'}}
```

To opt in at the field level permanently, use `SerializeAsAny`:

```python
from pydantic import SerializeAsAny

class Wrapper(BaseModel):
    user: SerializeAsAny[User]
```

## computed_field

Include derived values in serialization output without storing them as fields:

```python
from pydantic import BaseModel, computed_field

class Rect(BaseModel):
    width: float
    height: float

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height
```

Computed fields appear in `model_dump()` and `model_json_schema()`. They are read-only and derived from other fields. `@cached_property` also works.

## field_serializer

Customize how a specific field is serialized:

```python
from pydantic import BaseModel, field_serializer
from datetime import datetime

class Event(BaseModel):
    ts: datetime

    @field_serializer("ts")
    def serialize_ts(self, value: datetime, _info: object) -> str:
        return value.isoformat()
```

Modes:

- `mode="plain"` -- your function is the only serializer; you handle all output
- `mode="wrap"` -- receives the value and a `handler` to call the default serializer; you can modify the result

## model_serializer

Customize the entire model's serialization:

```python
from pydantic import BaseModel, model_serializer

class Flat(BaseModel):
    x: int
    y: int

    @model_serializer
    def serialize_model(self) -> dict[str, int]:
        return {"coords": f"{self.x},{self.y}"}
```

Use sparingly -- it replaces the default dump logic entirely.

## PlainSerializer (Annotated)

Attach custom serialization to a type via `Annotated`:

```python
from typing import Annotated
from pydantic import PlainSerializer

StrDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda v: str(v), return_type=str),
]
```

This composes with validators in the same `Annotated` stack.

## Field(exclude=True)

Exclude a field from serialization entirely:

```python
class Internal(BaseModel):
    public_name: str
    _debug_info: str = Field(exclude=True, default="")
```

Note: `exclude=True` affects `model_dump()` output. It does **not** affect `model_json_schema()`. To exclude from JSON schema, see [JSON-SCHEMA.md](JSON-SCHEMA.md) for `SkipJsonSchema`.

## RootModel serialization

`RootModel` dumps the root value directly, not wrapped in a dict:

```python
class Names(RootModel[list[str]]):
    pass

Names(root=["a", "b"]).model_dump()  # ['a', 'b']
```
