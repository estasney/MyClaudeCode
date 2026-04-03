# Dependency Injection in FastAPI

## Contents

1. [Function Dependencies](#1-function-dependencies)
2. [Annotated Aliases](#2-annotated-aliases)
3. [Yield Dependencies (Resource Lifecycle)](#3-yield-dependencies-resource-lifecycle)
4. [Class Dependencies](#4-class-dependencies)
5. [Sub-Dependency Chains](#5-sub-dependency-chains)
6. [Lifespan + app.state for Singletons](#6-lifespan--appstate-for-singletons)
7. [Wiring Lifespan Resources into Depends](#7-wiring-lifespan-resources-into-depends)
8. [Anti-Patterns](#8-anti-patterns)

---

## 1. Function Dependencies

The simplest form. A callable whose return value is injected into the route parameter.

```python
from typing import Annotated
from fastapi import Depends, Query


def pagination(skip: int = Query(0, ge=0), limit: int = Query(20, le=100)) -> dict[str, int]:
    return {"skip": skip, "limit": limit}


Pagination = Annotated[dict[str, int], Depends(pagination)]


@router.get("/items")
def list_items(page: Pagination, db: GetDB) -> list[ItemOut]:
    ...
```

FastAPI resolves the dependency per-request. The function can accept its own parameters (query params, headers, other dependencies).

## 2. Annotated Aliases

**Always use `Annotated[T, Depends(dep)]` with reusable type aliases.** This is a project-wide rule.

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

GetDB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Settings = Annotated[AppSettings, Depends(get_settings)]
```

Benefits: the route signature reads as pure type information, the wiring is declared once, and refactoring the dependency function updates all consumers.

**Never** use bare default-value style:

```python
# Wrong -- hides the dependency in the default value
def list_items(db: Session = Depends(get_db)):
    ...
```

## 3. Yield Dependencies (Resource Lifecycle)

Use `yield` when the dependency needs setup *and* teardown per request. The code before `yield` runs before the route; the code after `yield` runs after the response is sent.

```python
from collections.abc import Generator
from sqlalchemy.orm import Session


def get_db(engine: GetEngine) -> Generator[Session, None, None]:
    session = Session(bind=engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Key behaviors (per FastAPI docs):

- Teardown code after `yield` runs even if the route raises an exception.
- If you catch an exception in the dependency and don't re-raise it, FastAPI won't see it. Always re-raise or raise a new exception.
- Yield dependencies compose: if C depends on B depends on A, teardown runs in reverse order (C, B, A).
- The response is **not** sent until all yield-dependency teardown completes. Don't put slow work after the yield -- it delays the response to the client.

## 4. Class Dependencies

When a dependency needs configuration or has multiple methods, use a callable class. FastAPI calls `__init__` as the dependency.

```python
from typing import Annotated
from fastapi import Depends, Query


class PaginationParams:
    def __init__(
        self,
        skip: int = Query(0, ge=0),
        limit: int = Query(20, le=100),
    ):
        self.skip = skip
        self.limit = limit


Pagination = Annotated[PaginationParams, Depends()]
```

Note: `Depends()` with no argument uses the type annotation itself as the callable. This only works with class dependencies.

## 5. Sub-Dependency Chains

Dependencies can depend on other dependencies. FastAPI resolves the graph automatically.

```python
def get_engine(settings: Settings) -> Engine:
    return create_engine(settings.database_url)

GetEngine = Annotated[Engine, Depends(get_engine)]


def get_db(engine: GetEngine) -> Generator[Session, None, None]:
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()

GetDB = Annotated[Session, Depends(get_db)]


@router.get("/items")
def list_items(db: GetDB) -> list[ItemOut]:
    ...
```

FastAPI caches dependency results within a single request by default. If `get_engine` is used by two sub-dependencies in the same request, it runs once. To disable caching: `Depends(get_engine, use_cache=False)`.

## 6. Lifespan + app.state for Singletons

Application-scoped resources (engines, connection pools, HTTP clients, config) are created once at startup and torn down at shutdown. Use the `lifespan` async context manager.

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import create_engine, Engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = AppSettings()
    app.state.engine = create_engine(settings.database_url)
    yield
    app.state.engine.dispose()


app = FastAPI(lifespan=lifespan)
```

The `lifespan` replaces the deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")` (deprecated since FastAPI 0.95+). Everything before `yield` is startup; everything after is shutdown.

**Lifespan state dict alternative.** You can `yield {"engine": engine}` instead of using `app.state`, and the dict merges into `request.state`. Both approaches work; `app.state` is more explicit and doesn't require remembering the merge behavior.

## 7. Wiring Lifespan Resources into Depends

The standard pattern: a thin dependency function reads from `app.state` via the `Request` object and yields a per-request resource.

```python
from typing import Annotated
from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Generator[Session, None, None]:
    engine = request.app.state.engine
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


GetDB = Annotated[Session, Depends(get_db)]
```

This bridges the two scopes: the engine lives for the app's lifetime (lifespan), the session lives for one request (yield dependency).

## 8. Anti-Patterns

**Module-level mutable singletons.** Don't create engines or pools at module scope. They bypass lifespan lifecycle, can't be cleanly torn down, and make testing harder.

```python
# Wrong
engine = create_engine(DATABASE_URL)  # created at import time

# Right -- created in lifespan, accessed via app.state
```

**Bare Depends in signatures.** Already covered above -- always use Annotated aliases.

**Async yield dependencies with sync teardown.** If you define an `async def` yield dependency, everything in it (including teardown) runs on the event loop. Blocking I/O after the yield will block the loop. Either use a sync `def` dependency (runs in threadpool) or ensure all teardown is truly async.

**Passing request-scoped dependencies to BackgroundTasks.** The yield dependency's teardown runs before the background task executes, so the resource (e.g., DB session) is already closed. Pass the factory (e.g., the engine or sessionmaker) to the background task and create a fresh session inside it.

**Overusing middleware for DI concerns.** Middleware runs for every request regardless of route. Use `Depends` for per-route or per-router injection. Middleware is appropriate for truly cross-cutting concerns like CORS, request-ID propagation, or global error formatting.
