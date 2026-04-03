# JSON Schema

Pydantic generates JSON Schema (draft 2020-12 with OpenAPI extensions) from models.

## model_json_schema

```python
import json
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str

print(json.dumps(User.model_json_schema(), indent=2))
```

The result is a jsonable dict. For `TypeAdapter`, use `TypeAdapter(SomeType).json_schema()`.

Parameters:

- `by_alias=True` (default) -- uses alias names as property keys
- `ref_template` -- controls format of `$ref` strings
- `schema_generator` -- pass a `GenerateJsonSchema` subclass to customize generation
- `mode="validation"` (default) or `mode="serialization"` -- controls which schema is emitted when they differ (e.g., `computed_field` appears only in serialization mode)

Sub-models are placed in `$defs` and referenced. Sub-models with modified Field metadata (custom title, description, default) are inlined instead of referenced.

## SkipJsonSchema

Excludes a type (or part of a union) from the generated JSON schema. The field still participates in validation and serialization -- only its schema representation is suppressed.

```python
from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema

class Response(BaseModel):
    answer: str
    internal_state: SkipJsonSchema[dict | None] = None

assert "internal_state" not in Response.model_json_schema()["properties"]
```

Primary use case: hiding fields from schema consumers (OpenAPI clients, LLM tool-call schemas) while keeping them functional in Python.

Because the field is invisible to schema consumers, it must have a default value -- external callers will never provide it.

Note: `SkipJsonSchema[None]` within a union (e.g., `str | SkipJsonSchema[None]`) removes the `null` option from the schema while still allowing `None` in Python validation. There are open issues around edge cases with this pattern and default values.

## WithJsonSchema

Override the generated schema for a type without affecting validation:

```python
from typing import Annotated
from pydantic import BaseModel, WithJsonSchema

MyInt = Annotated[int, WithJsonSchema({"type": "integer", "examples": [1, 0, -1]})]

class Model(BaseModel):
    a: MyInt
```

Accepts an optional `mode` parameter to provide different schemas for validation vs serialization:

```python
WithJsonSchema({"type": "string"}, mode="serialization")
```

## json_schema_input_type

When a field has validators that transform input, the JSON schema should reflect the input type, not the output. Use the `json_schema_input_type` parameter on the validator instead of `WithJsonSchema`:

```python
from pydantic import AfterValidator, TypeAdapter

def parse_csv(v: str) -> list[str]:
    return v.split(",")

CsvList = Annotated[list[str], AfterValidator(parse_csv)]
# This will incorrectly show schema as array
# Instead, use json_schema_input_type on the validator
```

## GenerateJsonSchema subclassing

For broad schema customization, subclass `GenerateJsonSchema` and pass it via `schema_generator`:

```python
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema

class StrictSchema(GenerateJsonSchema):
    def str_schema(self, schema):
        result = super().str_schema(schema)
        result["minLength"] = 1
        return result

print(MyModel.model_json_schema(schema_generator=StrictSchema))
```

This is the intended extension point for global schema policy changes. It replaces the v1 approach of overriding `schema_extra` or recursive function calls.

## Validation vs Serialization mode

Some types generate different schemas depending on whether the consumer is sending data (validation) or receiving data (serialization):

- `computed_field` only appears in `mode="serialization"`
- Fields with custom serializers may have different output types
- `model_json_schema(mode="serialization")` reflects what `model_dump(mode="json")` produces

When generating OpenAPI schemas, request bodies use validation mode and response bodies use serialization mode.
