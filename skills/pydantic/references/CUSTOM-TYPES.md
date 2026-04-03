# Custom Types

Pydantic v2 provides two approaches for custom type behavior: `Annotated` metadata (lightweight, composable) and core schema hooks (full control, heavier).

## Annotated metadata (preferred for most cases)

Stack validators, serializers, and schema overrides on any type:

```python
from typing import Annotated
from pydantic import AfterValidator, PlainSerializer, WithJsonSchema

def must_be_positive(v: float) -> float:
    if v <= 0:
        raise ValueError("must be positive")
    return v

PositivePrice = Annotated[
    float,
    AfterValidator(must_be_positive),
    PlainSerializer(lambda v: round(v, 2), return_type=float),
    WithJsonSchema({"type": "number", "exclusiveMinimum": 0}),
]
```

This is a type alias. Use it anywhere a regular type annotation goes -- model fields, function args, `TypeAdapter`, nested in generics.

Available `Annotated` metadata:

- **Validators**: `BeforeValidator`, `AfterValidator`, `WrapValidator`, `PlainValidator`
- **Serializers**: `PlainSerializer`, `WrapSerializer`
- **Schema**: `WithJsonSchema` (override JSON schema), `SkipJsonSchema` (exclude from schema)
- **Constraints**: everything from `annotated-types` (`Gt`, `Ge`, `Lt`, `Le`, `Len`, `Predicate`, etc.)

Stacking order matters: validators/serializers run in the order they appear in the `Annotated` arguments.

## Type variables in Annotated

Generic custom types work with `TypeVar`:

```python
from typing import Annotated, TypeVar
from annotated_types import Len

T = TypeVar("T")
ShortList = Annotated[list[T], Len(max_length=4)]

# Usage: ShortList[int] validates as list[int] with max 4 items
```

## __get_pydantic_core_schema__ (full control)

For custom classes that need to fully define how Pydantic handles them. Implement this as a classmethod:

```python
from typing import Any
from pydantic_core import CoreSchema, core_schema
from pydantic import GetCoreSchemaHandler

class Username(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            handler(str),
        )
```

The `handler` argument lets you delegate to Pydantic's default schema generation for the base type, then wrap it with your logic. This is the idiomatic pattern -- call `handler(base_type)` and layer on top.

This replaces v1's `__get_validators__`.

## __get_pydantic_json_schema__

Customize the JSON schema representation of a custom type:

```python
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue

class Username(str):
    @classmethod
    def __get_pydantic_json_schema__(
        cls, _schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "pattern": "^[a-z_]+$", "maxLength": 32}
```

This replaces v1's `__modify_schema__`.

## Annotated on existing classes

When you cannot modify a class (third-party types), use `Annotated` to attach schema hooks externally:

```python
from typing import Annotated, Any
from pydantic import GetCoreSchemaHandler, GetPydanticSchema
from pydantic_core import CoreSchema, core_schema

def _third_party_schema(
    source_type: Any, handler: GetCoreSchemaHandler
) -> CoreSchema:
    return core_schema.no_info_plain_validator_function(ThirdPartyClass)

AnnotatedThirdParty = Annotated[ThirdPartyClass, GetPydanticSchema(_third_party_schema)]
```

## Built-in constrained types

Pydantic ships constrained types for common cases (prefer `Annotated` with `annotated-types` constraints for new code):

- `PositiveInt`, `NegativeInt`, `NonNegativeInt`, `NonPositiveInt`
- `PositiveFloat`, `NegativeFloat`
- `conint()`, `confloat()`, `constr()`, `conlist()`, `conset()` (functional constructors)
- `StrictInt`, `StrictStr`, `StrictFloat`, `StrictBool` (no coercion)
- `AnyUrl`, `HttpUrl`, `AnyHttpUrl`, `EmailStr` (requires `email-validator`)
- `SecretStr`, `SecretBytes` (masked in repr, excluded from JSON by default)
- `Json[T]` -- validates a JSON string and parses it into type T
- `ImportString` -- imports a dotted path and returns the object

## Pattern: custom Annotated type with full stack

```python
from typing import Annotated
from decimal import Decimal
from pydantic import AfterValidator, PlainSerializer, WithJsonSchema

def validate_currency(v: Decimal) -> Decimal:
    if v.as_tuple().exponent < -2:
        raise ValueError("max 2 decimal places")
    return v

Currency = Annotated[
    Decimal,
    AfterValidator(validate_currency),
    PlainSerializer(lambda v: str(v), return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^\d+\.\d{2}$"}),
]
```

This gives you: validation (2 decimal places), serialization (to string), and a correct JSON schema -- all as a reusable type alias.
