# Session and SessionMaker

## SessionMaker

`SessionMaker` is a factory that creates `Session` instances. For single-threaded code, you can create a session directly, but `SessionMaker` is the standard pattern:

```python
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()
```

For a web framework (e.g., Flask, FastAPI), create the `SessionLocal` once and use it in request handlers:

```python
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

In other code, it is typical to access the sessionmaker from a settings object


## Thread Safety

**SQLAlchemy is not thread-safe by default.** Each thread must have its own session. The `SessionMaker` helps enforce this:

```python
from sqlalchemy.orm import sessionmaker
import threading

SessionLocal = sessionmaker(bind=engine)

def worker():
    session = SessionLocal()  # Each thread gets its own session
    user = User(name="Worker " + str(threading.current_thread().ident))
    session.add(user)
    session.commit()
    session.close()

threads = [threading.Thread(target=worker) for _ in range(10)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
```

For scoped sessions (thread-local storage), use `scoped_session`:

```python
from sqlalchemy.orm import scoped_session, sessionmaker

session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

def worker():
    # Each thread automatically gets its own session
    user = User(name="Worker")
    Session.add(user)
    Session.commit()
```

`scoped_session` automatically maps each thread to a unique session. When the thread ends, call `Session.remove()` to clean up:

```python
def worker():
    try:
        user = User(name="Worker")
        Session.add(user)
        Session.commit()
    finally:
        Session.remove()
```

## SQLite Special Handling

SQLite has a quirk: by default, it disallows concurrent access from multiple threads. To enable multi-threaded use, set `check_same_thread=False`:

```python
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///app.db",
    connect_args={"check_same_thread": False}
)
```

**Warning:** This doesn't make SQLite thread-safe. It just disables the check. You still need to use a session per thread or a scoped session to avoid corruption.

SQLite is suitable for testing and simple single-threaded apps. For production with concurrency, use PostgreSQL or MySQL.

## Async SQLAlchemy

For async code, use `create_async_engine` and `AsyncSession`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

async_engine = create_async_engine("sqlite+aiosqlite:///app.db")
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

async def get_user(user_id: int):
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
```

Key differences from sync:
- Use `create_async_engine()` instead of `create_engine()`
- Use `async_sessionmaker()` instead of `sessionmaker()`
- Use `async with session` instead of context manager
- Await all database operations: `await session.execute()`, `await session.commit()`

For async with FastAPI:

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/users/")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()
```

For SQLite with async, use the `aiosqlite` driver:

```python
# pip install aiosqlite
async_engine = create_async_engine("sqlite+aiosqlite:///app.db")
```
