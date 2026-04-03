# Models

## BaseModel

All Pydantic models inherit from `BaseModel`. Fields are declared as annotated class attributes. Pydantic analyzes annotations at class creation time to build a core schema used for validation and serialization.

```python
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str = "anonymous"
    email: str | None = None
```

Keyword arguments are required at construction. Positional args are not supported by default.

## Field

`Field()` adds metadata, defaults, aliases, and constraints to a field.

```python
from pydantic import BaseModel, Field

class Item(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0, description="Unit price in USD")
    sku: str = Field(alias="product_sku")
```

Key parameters: `default`, `default_factory`, `alias`, `validation_alias`, `serialization_alias`, `title`, `description`, `gt/ge/lt/le`, `min_length/max_length`, `pattern`, `exclude`, `deprecated`.

Use `alias` for a single alias that applies everywhere. Use `validation_alias` and `serialization_alias` when input and output naming differ (common in APIs with snake_case internals and camelCase JSON).

`AliasChoices` and `AliasPath` support multiple input key names and nested key extraction:

```python
from pydantic import AliasChoices, AliasPath, BaseModel, Field

class Request(BaseModel):
    user_id: int = Field(validation_alias=AliasChoices("user_id", AliasPath("user", "id")))
```

## ConfigDict

Model-level configuration uses `model_config` with a `ConfigDict`. The v1 inner `class Config` is deprecated.

```python
from pydantic import BaseModel, ConfigDict

class Strict(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    value: int
```

Commonly used settings:

- `strict` -- disables type coercion; `"123"` will not become `123`
- `frozen` -- makes instances immutable (replaces v1 `allow_mutation = False`)
- `from_attributes` -- enables construction from ORM objects via attribute access (replaces v1 `orm_mode`)
- `populate_by_name` -- allows using field names alongside aliases at construction
- `str_strip_whitespace`, `str_min_length` -- apply string constraints model-wide
- `extra = "forbid"` / `"allow"` / `"ignore"` -- controls behavior for unrecognized input fields
- `validate_assignment` -- re-validates on attribute assignment
- `validate_default` -- validates default values (always true for `BaseSettings`)
- `revalidate_instances` -- controls whether nested model instances are re-validated

`ConfigDict` is inherited by subclasses. When multiple parents define config, later bases override earlier ones.

## RootModel

For models wrapping a single value (a list, a tagged union, a primitive):

```python
from pydantic import RootModel

class Tags(RootModel[list[str]]):
    pass

tags = Tags.model_validate(["a", "b"])
print(tags.root)  # ['a', 'b']
```

`RootModel` dumps the root value directly, not wrapped in a dict. Use `TypeAdapter` instead when you do not need a named class.

## Forward References and model_rebuild

When models reference types not yet defined, Pydantic defers schema building. Call `model_rebuild()` after all types are available:

```python
from pydantic import BaseModel

class Tree(BaseModel):
    value: int
    children: list["Tree"] = []

Tree.model_rebuild()
```

In v2, `model_rebuild()` replaces v1's `update_forward_refs()`. It builds the full core schema for the model and all nested types, so all referenced types must be resolvable at rebuild time.

## Inheritance

Standard Python inheritance works. Subclasses inherit fields, validators, and config from parents.

```python
class Base(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int

class User(Base):
    name: str
```

**Subclass serialization gotcha (v2)**: When a subclass instance is assigned to a field typed as the parent, `model_dump()` only includes fields defined on the annotated type, not the subclass. This is a deliberate security change from v1. Use `serialize_as_any=True` or the `SerializeAsAny` annotation to opt back in. See [SERIALIZATION.md](SERIALIZATION.md).

## ORM Integration

Set `from_attributes = True` in config to construct models from arbitrary objects by reading attributes:

```python
class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

orm_user = get_user_from_db()  # SQLAlchemy model instance
user = UserSchema.model_validate(orm_user)
```

`model_validate` replaces v1's `from_orm()`.

## Validation Modes

Pydantic validates in three modes: Python, JSON, and strings.

- **Python mode** (`model_validate(data)`): accepts dicts and Python objects
- **JSON mode** (`model_validate_json(data)`): parses JSON bytes/str directly, faster than `json.loads` + `model_validate` because it skips the intermediate dict
- **Strings mode** (`model_validate_strings(data)`): accepts dict with string values, validates in JSON mode semantics (coercion from strings)

Prefer `model_validate_json` for incoming JSON payloads -- it avoids an extra parsing step.

## ClassVar and Private Attributes

`typing.ClassVar` fields are treated as class variables and excluded from the model schema.

Attributes with leading underscores become private attributes -- not validated, not serialized, not set via `__init__`. Initialize them via `model_post_init` or `default`/`default_factory` on `PrivateAttr`:

```python
from pydantic import BaseModel, PrivateAttr

class Service(BaseModel):
    name: str
    _client: object = PrivateAttr(default=None)

    def model_post_init(self, __context: object) -> None:
        self._client = create_client(self.name)
```

As of v2.1.0, using `Field()` with a private attribute raises `NameError`.
