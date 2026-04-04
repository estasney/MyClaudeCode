# Dependency Injection in FastAPI

## Contents

1. [Function Dependencies](#1-function-dependencies)
2. [Annotated Aliases](#2-annotated-aliases)
3. [Yield Dependencies (Resource Lifecycle)](#3-yield-dependencies-resource-lifecycle)
4. [Class Dependencies](#4-class-dependencies)
5. [Sub-Dependency Chains](#5-sub-dependency-chains)
6. [Singleton Dependencies with lru_cache](#6-singleton-dependencies-with-lru_cache)
7. [When to Use app.state and Lifespan](#7-when-to-use-appstate-and-lifespan)
8. [request.state — Middleware-to-Handler Communication](#8-requeststate--middleware-to-handler-communication)
9. [Anti-Patterns](#9-anti-patterns)

---

## 1. Function Dependencies

The simplest form. A callable whose return value is injected into the route parameter.

```python
from typing import Annotated
from fastapi import Depends, Query


def pagination(skip: int = Query(0, ge=0), limit: int = Query(20, le=100)) -> dict[str, int]:
    return {"skip": skip, "limit": limit}


PaginationDep = Annotated[dict[str, int], Depends(pagination)]


@router.get("/items")
def list_items(page: PaginationDep, db: GetDBDep) -> list[ItemOut]:
    ...
```

FastAPI resolves the dependency per-request. The function can accept its own parameters (query params, headers, other dependencies).

## 2. Annotated Aliases

**Always use `Annotated[T, Depends(dep)]` with reusable type aliases.** This is a project-wide rule. Aliases use a `Dep` suffix to signal intent and avoid name collisions with the underlying types (e.g., `SettingsDep` avoids shadowing the `AppSettings` class).

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

GetDBDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]
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


def get_db(engine: GetEngineDep) -> Generator[Session, None, None]:
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


PaginationDep = Annotated[PaginationParams, Depends()]
```

Note: `Depends()` with no argument uses the type annotation itself as the callable. This only works with class dependencies.

## 5. Sub-Dependency Chains

Dependencies can depend on other dependencies. FastAPI resolves the graph automatically.

```python
from functools import lru_cache


@lru_cache(maxsize=1)
def get_engine(settings: SettingsDep) -> Engine:
    return create_engine(settings.database_url)

GetEngineDep = Annotated[Engine, Depends(get_engine)]


def get_db(engine: GetEngineDep) -> Generator[Session, None, None]:
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()

GetDBDep = Annotated[Session, Depends(get_db)]


@router.get("/items")
def list_items(db: GetDBDep) -> list[ItemOut]:
    ...
```

FastAPI caches dependency results within a single request by default. The `lru_cache` on `get_engine` provides cross-request caching (singleton) — since `get_settings` is also `lru_cache`'d, the same `AppSettings` object is passed every time, always hitting the cache. This requires `AppSettings` to be hashable (`frozen=True` in its `ConfigDict`; see the **pydantic** skill). To disable per-request caching for a specific dependency: `Depends(dep, use_cache=False)`.

## 6. Singleton Dependencies with `lru_cache`

The preferred pattern for application-scoped resources. A `@lru_cache(maxsize=1)` dependency function creates the resource on first call and returns the cached instance thereafter. It's typed, framework-independent, and works cleanly with `dependency_overrides`.

```python
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()

SettingsDep = Annotated[AppSettings, Depends(get_settings)]


@lru_cache(maxsize=1)
def get_engine(settings: SettingsDep) -> Engine:
    return create_engine(settings.database_url)

GetEngineDep = Annotated[Engine, Depends(get_engine)]
```

**Why not `app.state`?** `lru_cache` gives you return type annotations that basedpyright can check (no untyped `request.app.state.enigne` typos), no coupling to `Request`, callable from CLI scripts or background jobs, and clean `dependency_overrides` in tests. `app.state` requires `Request` in every dependency signature and offers no static type checking.

**Trade-offs to know:**

- **Hashable settings required.** `lru_cache` uses arguments as cache keys, so `AppSettings` must be hashable. Use `frozen=True` in its `ConfigDict` (see the **pydantic** skill). Since `get_settings` is itself `lru_cache`'d, the same object is passed every time, always hitting `get_engine`'s cache after the first call.
- **Lazy initialization.** The first request that hits the dependency pays the creation cost. For most resources (engine, settings, HTTP client) this is negligible. If you need to fail before accepting traffic (e.g., verify DB connectivity), run that check in lifespan separately — don't use `app.state` just for that.
- **Not exactly-once under concurrency.** `lru_cache` is thread-safe against corruption but doesn't guarantee a single instantiation under concurrent first-call races. In practice the risk is negligible for typical resources, and `Engine` handles this gracefully (two engines would just mean two pools, quickly GC'd down to one).
- **No teardown hook.** `lru_cache` has no shutdown callback. For resources like `Engine`, this is fine — `Engine.dispose()` only closes idle pooled connections, and process exit handles the rest. SQLAlchemy's own docs describe `dispose()` as primarily useful for test suites and pool resets, not production shutdown.

### Wiring `lru_cache` singletons into yield dependencies

The standard bridge: `lru_cache` owns the long-lived resource, `yield` owns the per-request lifecycle.

```python
from collections.abc import Generator

from sqlalchemy.orm import Session


def get_db(engine: GetEngineDep) -> Generator[Session, None, None]:
    session = Session(bind=engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

GetDBDep = Annotated[Session, Depends(get_db)]
```

Because `get_engine` is `lru_cache`'d, FastAPI resolves it once (cached), then `get_db` creates a fresh session per request. The dependency chain is fully typed and `dependency_overrides` can swap any level independently.

## 7. When to Use `app.state` and Lifespan

Lifespan is still the right place for **startup validation** — checks that should prevent the app from accepting traffic if they fail. But storing the result on `app.state` for downstream dependencies is usually unnecessary.

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))  # fail fast if DB is unreachable
    yield


app = FastAPI(lifespan=lifespan)
```

Here the lifespan validates connectivity but doesn't store anything on `app.state`. The `get_engine` dependency (via `lru_cache`) handles the actual injection.

**Legitimate `app.state` use cases** are narrow:

- Resources where initialization is async and can't be expressed in a sync `lru_cache` function (e.g., an async HTTP client that needs `await` during setup).
- Sub-app state sharing where a mounted sub-application needs access to the parent's resources.

If you do use `app.state`, be aware: it's a `SimpleNamespace` with no type checking, and `dependency_overrides` can only swap the accessor function — the lifespan still runs and creates the real resource.

## 8. `request.state` — Middleware-to-Handler Communication

`request.state` is per-request scoped storage. It exists because middleware and route handlers have no other clean communication channel — middleware runs outside the `Depends` resolution graph.

```python
import uuid
from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response
```

A dependency can then read from `request.state` to bridge into the DI graph:

```python
def get_request_id(request: Request) -> str:
    return request.state.request_id

RequestIDDep = Annotated[str, Depends(get_request_id)]
```

**Use `request.state` for:** correlation IDs, request timing, auth context resolved in middleware, feature flags set per-request.

**Do not use `app.state` for per-request data.** `app.state` is process-global. Writing per-request data there (e.g., user identity from middleware) causes data leakage between concurrent requests.

**Lifespan state dict note.** If the lifespan yields a dict (`yield {"engine": engine}`), those keys merge into `request.state` as a shallow copy per request. This is a Starlette feature — it works but is less explicit than `lru_cache` for singleton access.

## 9. Anti-Patterns

**Module-level mutable singletons.** Don't create engines or pools at module scope. They bypass any lifecycle management and make testing harder.

```python
# Wrong
engine = create_engine(DATABASE_URL)  # created at import time

# Right -- lru_cache dependency or lifespan
```

**Bare Depends in signatures.** Already covered above -- always use Annotated aliases.

**`app.state` as the default DI mechanism.** Reaching for `request.app.state.X` in dependency functions couples every dependency to `Request`, loses type safety, and makes `dependency_overrides` awkward (the override swaps the accessor but the lifespan still creates the real resource). Prefer `lru_cache` for singletons.

**Async yield dependencies with sync teardown.** If you define an `async def` yield dependency, everything in it (including teardown) runs on the event loop. Blocking I/O after the yield will block the loop. Either use a sync `def` dependency (runs in threadpool) or ensure all teardown is truly async.

**Passing request-scoped dependencies to BackgroundTasks.** The yield dependency's teardown runs before the background task executes, so the resource (e.g., DB session) is already closed. Pass the factory (e.g., the engine or sessionmaker) to the background task and create a fresh session inside it.

**Overusing middleware for DI concerns.** Middleware runs for every request regardless of route. Use `Depends` for per-route or per-router injection. Middleware is appropriate for truly cross-cutting concerns like CORS, request-ID propagation, or global error formatting.

**Writing per-request data to `app.state`.** This is process-global state. Concurrent requests will overwrite each other's data. Use `request.state` for per-request context.