# TypeAdapter

`TypeAdapter` provides validation, serialization, and JSON schema generation for arbitrary types without defining a `BaseModel`.

## When to use

Use `TypeAdapter` when you need Pydantic's machinery on a type that is not a BaseModel:

- Validating a `list[SomeModel]` from an API response
- Generating a JSON schema for a `TypedDict` or `dataclass`
- Validating a primitive or union type ad-hoc
- Replacing v1's `parse_obj_as()` and `schema_of()` (both deprecated in v2)

Do **not** use `TypeAdapter` as a type annotation on model fields. Use `RootModel` if you need a named model wrapping a single type.

## Basic usage

```python
from pydantic import TypeAdapter

adapter = TypeAdapter(list[int])

result = adapter.validate_python(["1", "2", "3"])
# [1, 2, 3]

adapter.validate_json(b'[1, 2, 3]')
# [1, 2, 3]

adapter.json_schema()
# {'items': {'type': 'integer'}, 'type': 'array'}
```

## Performance: create once, reuse

Constructing a `TypeAdapter` analyzes the type and builds a core schema. This has non-trivial overhead. Create the adapter once at module level and reuse it:

```python
# module level
_int_list_adapter = TypeAdapter(list[int])

def parse_ids(raw: bytes) -> list[int]:
    return _int_list_adapter.validate_json(raw)
```

Do not create `TypeAdapter` instances inside loops or hot-path functions.

## dump_json returns bytes

Unlike `BaseModel.model_dump_json()` which returns `str` (for v1 backward compat), `TypeAdapter.dump_json()` returns `bytes`:

```python
adapter = TypeAdapter(int)
result = adapter.dump_json(42)
# b'42'  (bytes, not str)
```

Coerce to `str` with `.decode()` if needed.

## dump_python

```python
adapter.dump_python(value)                          # Python-native dict/list
adapter.dump_python(value, mode="json")             # JSON-compatible types
adapter.dump_python(value, exclude_none=True)       # same flags as model_dump
```

## TypeAdapter with TypedDict

```python
from typing import TypedDict
from pydantic import TypeAdapter

class UserData(TypedDict):
    name: str
    age: int

adapter = TypeAdapter(list[UserData])
users = adapter.validate_python([{"name": "Alice", "age": "30"}])
# [{'name': 'Alice', 'age': 30}]
```

## TypeAdapter with Annotated types

Validators and serializers composed via `Annotated` work with `TypeAdapter`:

```python
from typing import Annotated
from pydantic import AfterValidator, PlainSerializer, TypeAdapter, WithJsonSchema

TruncatedFloat = Annotated[
    float,
    AfterValidator(lambda x: round(x, 1)),
    PlainSerializer(lambda x: f"{x:.1e}", return_type=str),
    WithJsonSchema({"type": "string"}, mode="serialization"),
]

ta = TypeAdapter(TruncatedFloat)
ta.validate_python(1.02345)       # 1.0
ta.dump_json(1.0)                 # b'"1.0e+00"'
ta.json_schema(mode="validation")      # {'type': 'number'}
ta.json_schema(mode="serialization")   # {'type': 'string'}
```

## Deferred building

In v2.10+, `TypeAdapter` supports deferred schema building via `defer_build=True` in config. The schema is built on first use (validation or serialization) rather than at construction. Must also set `experimental_defer_build_mode=('model', 'type_adapter')`.

## Forward references and rebuild

If a `TypeAdapter` is constructed with a type containing unresolvable forward references, call `adapter.rebuild()` after the referenced types are defined.
