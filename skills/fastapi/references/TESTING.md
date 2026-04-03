# Testing FastAPI Applications

## Contents

1. [Test Client Setup](#1-test-client-setup)
2. [dependency_overrides](#2-dependency_overrides)
3. [Pytest Fixtures with Cleanup](#3-pytest-fixtures-with-cleanup)
4. [Database Session Overrides](#4-database-session-overrides)
5. [Async Testing with httpx.AsyncClient](#5-async-testing-with-httpxasyncclient)
6. [Scoped Override Patterns](#6-scoped-override-patterns)
7. [Testing Lifespan](#7-testing-lifespan)
8. [Common Pitfalls](#8-common-pitfalls)

---

## 1. Test Client Setup

For sync route testing, use `TestClient` (a wrapper around httpx). For async routes or when the test itself needs to be async, use `httpx.AsyncClient` directly.

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
```

Use the context manager form (`with TestClient(app)`) to ensure lifespan events fire. Without it, startup/shutdown handlers won't run.

## 2. dependency_overrides

`app.dependency_overrides` is a dict mapping original dependency callables to replacement callables. FastAPI swaps them at resolution time.

```python
from app.main import app
from app.dependencies import get_db


def override_get_db():
    yield fake_session


app.dependency_overrides[get_db] = override_get_db
```

The key must be the **exact function object** used in `Depends()`. If you use `Annotated[Session, Depends(get_db)]`, the key is `get_db`.

Always clean up overrides after tests to prevent cross-test contamination. See section 3 for fixture-based cleanup.

## 3. Pytest Fixtures with Cleanup

Wrap `dependency_overrides` in a fixture that clears them on teardown.

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_db


@pytest.fixture
def db_session():
    session = create_test_session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session) -> TestClient:
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

The `clear()` in teardown is essential. Without it, overrides leak into subsequent tests. An alternative is `app.dependency_overrides = {}` but `clear()` is safer if other code holds a reference to the dict.

## 4. Database Session Overrides

The standard pattern: create a test engine, bind a session to a transaction, yield the session, then rollback.

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.main import app
from app.dependencies import get_db
from app.models import Base


@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session) -> TestClient:
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

This gives each test a clean database state via transaction rollback -- fast and deterministic.

For Snowflake or other databases where in-memory engines aren't available, use a dedicated test schema/database and truncate tables in the fixture teardown instead.

## 5. Async Testing with httpx.AsyncClient

When the app uses async routes, or the test itself needs `await`, use `httpx.AsyncClient` with `pytest-asyncio`.

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def async_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_read_items(async_client: AsyncClient):
    response = await async_client.get("/items")
    assert response.status_code == 200
```

`ASGITransport` runs the app in-process with no network overhead. The `base_url` is arbitrary but required by httpx.

**Sync vs async client choice:** If all your routes are sync `def` (the project default), `TestClient` is simpler and sufficient. Use `AsyncClient` when you have `async def` routes or need to test WebSocket endpoints.

## 6. Scoped Override Patterns

### Per-test overrides

The fixture pattern from section 3 -- each test gets its own override via fixture dependency.

### Per-module overrides

Use `autouse=True` on a module-level fixture to apply an override to every test in the file.

```python
@pytest.fixture(autouse=True)
def override_auth():
    def fake_auth():
        return User(id=1, role="admin")

    app.dependency_overrides[get_current_user] = fake_auth
    yield
    app.dependency_overrides.pop(get_current_user, None)
```

### Parametrized overrides

Combine `dependency_overrides` with `@pytest.mark.parametrize` to test multiple dependency configurations.

```python
@pytest.fixture(params=["admin", "viewer"])
def client_with_role(request, db_session) -> TestClient:
    role = request.param

    def override_user():
        return User(id=1, role=role)

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### Stacking overrides

Multiple overrides coexist in the dict. Override as many dependencies as needed for a given test scenario.

```python
app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_current_user] = override_user
app.dependency_overrides[get_settings] = override_settings
```

## 7. Testing Lifespan

`TestClient` as a context manager triggers lifespan startup/shutdown. If your lifespan writes to `app.state`, those values are available during the test.

```python
@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_engine_initialized(client: TestClient):
    assert hasattr(client.app.state, "engine")
```

To override resources that lifespan creates, apply `dependency_overrides` *before* entering the `TestClient` context, or override the downstream dependencies that read from `app.state` rather than trying to replace `app.state` itself.

## 8. Common Pitfalls

**Forgetting to clear overrides.** Overrides persist on the `app` object across tests. Always clear in fixture teardown. Symptoms: tests pass individually but fail when run together.

**Wrong key in dependency_overrides.** The key must be the exact callable passed to `Depends()`. If you accidentally use a different function object (e.g., a re-import), the override silently does nothing.

**Using TestClient without context manager.** `TestClient(app)` without `with` skips lifespan. If your app depends on `app.state` being populated, tests will get `AttributeError`.

**Mixing sync TestClient with async test functions.** `TestClient` is synchronous. Don't use it inside an `async def` test -- use `httpx.AsyncClient` instead. The reverse is also true: don't `await` inside a sync test using `TestClient`.

**Session scope on async fixtures.** `pytest-asyncio` recreates event loops per test by default. A `scope="session"` async fixture may fail because the event loop it was created on no longer exists. Use `scope="session"` only for sync fixtures (like engine creation), and keep async fixtures at function scope.

**Testing BackgroundTasks.** Background tasks run after the response but within the same request cycle during testing. The test may complete before the task runs. If you need to verify side effects of background tasks, either await completion explicitly or restructure the task as a testable unit.
