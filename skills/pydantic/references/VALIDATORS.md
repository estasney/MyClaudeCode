# Validators

## field_validator

Validates individual fields. Replaces v1's `@validator`.

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    age: int

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be blank")
        return v.strip()
```

Key differences from v1 `@validator`:

- Always a `@classmethod`
- First positional arg is the value (`v`), not `cls, v` implicitly
- No `values` dict of prior fields; use `model_validator` for cross-field logic
- `mode="before"` receives raw input (before type coercion); `mode="after"` (default) receives the coerced value
- Multiple fields: `@field_validator("field_a", "field_b")`

The optional second parameter `info: FieldValidationInfo` provides `info.field_name`, `info.data` (dict of already-validated fields), and `info.context`.

```python
@field_validator("end_date")
@classmethod
def end_after_start(cls, v: date, info: FieldValidationInfo) -> date:
    if "start_date" in info.data and v <= info.data["start_date"]:
        raise ValueError("end_date must be after start_date")
    return v
```

Field ordering matters for `info.data`: only fields defined before the current one in class body order are available.

## model_validator

Validates the entire model. Replaces v1's `@root_validator`.

```python
from pydantic import BaseModel, model_validator

class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def check_range(self) -> "DateRange":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self
```

**mode="before"**: receives raw input dict before any field validation. Return the (possibly modified) dict. Useful for reshaping input.

```python
@model_validator(mode="before")
@classmethod
def normalize_input(cls, data: dict[str, object]) -> dict[str, object]:
    if "full_name" in data:
        parts = str(data.pop("full_name")).split(" ", 1)
        data.setdefault("first_name", parts[0])
        data.setdefault("last_name", parts[1] if len(parts) > 1 else "")
    return data
```

**mode="after"**: receives a fully constructed model instance. Return `self` (or a modified instance). This is the more common mode.

**mode="wrap"**: receives the input and a handler; call the handler to run inner validation, or skip/modify it. Advanced use case.

Gotcha: with `validate_assignment = True`, the `mode="after"` model_validator receives an instance (not a dict) even during assignment.

## Annotated Validators

Attach validators directly to types via `Annotated`. These are reusable across models and compose cleanly.

```python
from typing import Annotated
from pydantic import AfterValidator, BaseModel

def must_be_positive(v: int) -> int:
    if v <= 0:
        raise ValueError("must be positive")
    return v

PositiveInt = Annotated[int, AfterValidator(must_be_positive)]

class Order(BaseModel):
    quantity: PositiveInt
    price: PositiveInt
```

Available wrappers:

- `AfterValidator(func)` -- runs after Pydantic's type validation
- `BeforeValidator(func)` -- runs before type validation; receives raw input, return value is passed to type validation
- `WrapValidator(func)` -- receives value and a handler; full control over whether/how inner validation runs
- `PlainValidator(func)` -- replaces Pydantic's validation entirely

These compose via stacking in `Annotated`:

```python
from pydantic import AfterValidator, BeforeValidator

Trimmed = Annotated[str, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v)]
NonEmpty = Annotated[Trimmed, AfterValidator(lambda v: v if v else (_ for _ in ()).throw(ValueError("empty")))]
```

Prefer `Annotated` validators over `field_validator` when the logic is type-level (reusable) rather than model-specific.

## Reusable Validators

Plain functions used with `Annotated` are inherently reusable. For `field_validator` reuse across models, extract the function and reference it:

```python
def strip_whitespace(v: str) -> str:
    return v.strip()

class ModelA(BaseModel):
    name: str

    normalize_name = field_validator("name")(classmethod(strip_whitespace))
```

This works but is less readable than the `Annotated` approach. Prefer `Annotated` type aliases for cross-model reuse.

## validate_call

Decorator that applies Pydantic validation to function arguments:

```python
from pydantic import validate_call

@validate_call
def process(name: str, count: int = 1) -> str:
    return name * count

process("hi", "3")  # coerces "3" to 3, returns "hihihi"
```

Useful at boundary functions (CLI handlers, API helpers) but adds overhead. Do not apply to hot-path functions called in tight loops.
