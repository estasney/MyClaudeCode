---
name: fastapi
description: Guide for building FastAPI applications with emphasis on dependency injection, lifecycle management, and testability.
allowed-tools:
  - Read(./*)
---

# FastAPI

Guidance for building FastAPI applications. This skill focuses on dependency injection, lifecycle management, and testability. The **pydantic** skill complements this one, covering request/response model design, validation, serialization, and settings.

## Version Awareness

FastAPI 0.95+ deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")` in favor of the `lifespan` async context manager. Do not use `on_event` in new code. If encountered, flag it and propose the lifespan equivalent.

## Project Preferences

**1. Annotated-style Depends always.** Use `Annotated[T, Depends(dep)]` with reusable type aliases. Never use bare default-value `Depends()` in function signatures.

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

GetDB = Annotated[AsyncSession, Depends(get_db)]

@router.get("/items")
def list_items(db: GetDB) -> list[ItemOut]:
    ...
```

**2. No global mutable state.** Database engines, connection pools, HTTP clients, and configuration objects are created in the `lifespan` handler and accessed via `app.state` or dependency injection. Module-level mutable singletons are forbidden.

**3. Sync routes are the safer default.** Sync `def` endpoints run in a threadpool and handle blocking I/O without incident. Async routes are actively harmful if anything in the call chain is synchronous -- it blocks the event loop and serializes all requests on that worker. Only use `async def` when the **entire** call chain (DB driver, HTTP client, file I/O) is truly async. "Async all the things" is a common newcomer footgun.

**4. Modular router structure.** Flat files for small projects, nested packages with sub-routers as complexity grows. URL prefix versioning (`/v1/`, `/v2/`). The `FastAPI()` instance and its lifespan live in an application factory or `main.py`. Routers live in their own modules and are included via `app.include_router()`. Routers never import `app`.

**5. Depends is the primary DI mechanism.** Use it for resource lifecycle (yield pattern), cross-cutting concerns (logging, timing, audit), and config injection. Middleware is reserved for truly heavy-weight concerns (CORS, request ID propagation) -- not the default choice.

**6. Router-level dependency grouping.** Shared dependencies (auth, tenant resolution, rate limiting) go on `APIRouter(dependencies=[...])`, not repeated on every endpoint.

**7. Return type annotations, not `response_model`.** Annotate the function return type instead of passing `response_model=` to the decorator. Same effect, no duplication.

```python
@router.get("/items/{item_id}")
def get_item(item_id: int, db: GetDB) -> ItemOut:
    ...
```

**8. Domain exceptions with HTTP status codes.** Custom exception classes carry their own HTTP status code and are registered globally via `app.add_exception_handler`. Routes raise domain errors directly. `HTTPException` is still fine for simple one-off cases. The API returns status codes (401, 403, etc.) -- the frontend handles redirects, not the backend.

```python
class NotFoundError(Exception):
    status_code = 404
    def __init__(self, entity: str, id: int):
        self.detail = f"{entity} {id} not found"

def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.add_exception_handler(NotFoundError, not_found_handler)
```

**9. Explicit status codes.** Always pass `status_code=` to route decorators for mutating operations. Use `status.HTTP_201_CREATED`, `status.HTTP_204_NO_CONTENT`, etc.

**10. Settings via Pydantic.** `BaseSettings` with `lru_cache(maxsize=1)`, injected via `Depends`. See the **pydantic** skill for model conventions.

**11. Background work.** Enterprise: Prefect. Lighter/personal projects: `BackgroundTasks` is acceptable. Known footgun: never pass a request-scoped session dependency into `BackgroundTasks` -- the session will be closed before the task runs. Pass the session factory instead.

**12. Lifespan context manager for startup/shutdown.** See [DEPENDENCY-INJECTION.md](references/DEPENDENCY-INJECTION.md) section 6 for the full pattern.

## Decision Tree

**Wiring up dependencies, DB sessions, service layers, or shared resources?**
Go to [DEPENDENCY-INJECTION.md](references/DEPENDENCY-INJECTION.md). Covers function dependencies, class dependencies, yield dependencies, sub-dependency chains, `Annotated` aliases, lifespan + `app.state` for singletons, and the anti-patterns to avoid.

**Writing tests or overriding dependencies for test isolation?**
Go to [TESTING.md](references/TESTING.md). Covers `dependency_overrides`, pytest fixtures with cleanup, async testing with `httpx.AsyncClient`, database session overrides, and scoped override patterns.

**Defining request bodies, response models, validation, or settings?**
See the **pydantic** skill. If unavailable, apply these minimal rules: use `BaseModel` with `model_config = ConfigDict(extra="forbid", frozen=True)`, separate Create/Update/Response models, `Field(description=..., examples=[...])` on every field.
