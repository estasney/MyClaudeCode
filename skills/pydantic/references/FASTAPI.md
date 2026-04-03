# FastAPI Integration

FastAPI uses Pydantic models throughout: request bodies, response models, query parameters, dependencies, and OpenAPI schema generation.

## Request body models

FastAPI automatically validates the JSON request body against the Pydantic model:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class CreateUser(BaseModel):
    name: str
    email: str

@app.post("/users")
async def create_user(user: CreateUser) -> dict:
    return {"id": 1, **user.model_dump()}
```

Validation errors return a 422 response with Pydantic's error details.

## Response models

Use `response_model` to control what gets serialized in the response. FastAPI calls `model_dump(mode="json")` under the hood:

```python
class UserResponse(BaseModel):
    id: int
    name: str

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    return get_user_from_db(user_id)  # can return ORM object if from_attributes=True
```

With `from_attributes=True` on the response model, FastAPI can serialize ORM objects directly.

`response_model_exclude_unset`, `response_model_exclude_none`, etc. are available as decorator parameters.

## Separate input and output models

A common pattern: different models for creation, update, and response:

```python
class UserBase(BaseModel):
    name: str
    email: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None

class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
```

This keeps password out of responses and makes partial updates explicit.

## Settings as dependencies

Use `BaseSettings` with FastAPI's dependency injection:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_url: str
    secret_key: str

@lru_cache
def get_settings() -> Settings:
    return Settings()

@app.get("/info")
async def info(settings: Settings = Depends(get_settings)):
    return {"db": settings.db_url}
```

`@lru_cache` ensures the settings object is created once. For testing, override with `app.dependency_overrides[get_settings] = lambda: Settings(db_url="test")`.

## Hiding fields from OpenAPI

Use `SkipJsonSchema` to keep a field functional in Python but invisible in the generated OpenAPI schema:

```python
from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema

class InternalResponse(BaseModel):
    result: str
    trace_id: SkipJsonSchema[str | None] = None
```

`trace_id` will not appear in the Swagger UI or client-generated types, but is still available in Python code.

Alternatively, use `Field(exclude=True)` to exclude from serialization (response body) while keeping it in the schema, or combine both for full hiding.

## Strict vs lax in API context

By default, FastAPI/Pydantic runs in lax mode -- `"123"` becomes `123` for an `int` field. For stricter APIs:

```python
class StrictInput(BaseModel):
    model_config = ConfigDict(strict=True)
    count: int  # "123" will now fail validation
```

Or per-field: `count: Annotated[int, Strict()]`

JSON input from HTTP requests is inherently string-based at the transport layer, but Pydantic's JSON parser handles type coercion correctly even in strict mode (e.g., JSON `123` is an integer, not a string). Strict mode primarily catches mistyped Python objects.

## Query and path parameter validation

Pydantic types work directly in FastAPI path/query parameters:

```python
from pydantic import Field
from typing import Annotated

@app.get("/items")
async def list_items(
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
):
    ...
```

## Aliases for API field naming

Use `serialization_alias` for camelCase output and `validation_alias` for camelCase input, while keeping snake_case in Python:

```python
class Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    item_name: str = Field(serialization_alias="itemName")
```

Or use a `model_config` alias generator for consistent casing across all fields.
