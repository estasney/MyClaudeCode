# Custom Types

## TypeAdapter

`TypeAdapter` lets you define how values are converted to/from the database. Use it to build custom column types:

```python
from sqlalchemy import TypeDecorator, LargeBinary
import gzip

class GzipType(TypeDecorator):
    impl = LargeBinary
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            return gzip.compress(value.encode())
        return None
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return gzip.decompress(value).decode()
        return None
```

Use it in a model:

```python
class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(GzipType)
```

Now when you assign `doc.content = "large text"`, it's automatically compressed on save and decompressed on load.

`process_bind_param` is called when inserting/updating. `process_result_value` is called when reading from the database. Always return `None` if the input is `None` (for nullable columns).

## JSON Type

SQLAlchemy has a built-in `JSON` type for database-native JSON support:

```python
from sqlalchemy import JSON

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    metadata: Mapped[dict] = mapped_column(JSON)
```

Assign Python dicts directly:

```python
user = User(metadata={"theme": "dark", "notifications": True})
session.add(user)
session.commit()
```

SQLAlchemy handles serialization. To query inside JSON columns (depends on database support):

```python
from sqlalchemy import select

stmt = select(User).where(User.metadata["theme"] == "dark")
```

## UUID Type

For UUID columns, use `UUID`:

```python
from sqlalchemy import UUID
import uuid

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

`as_uuid=True` stores the UUID as a native UUID type (if the database supports it) and returns Python `uuid.UUID` objects. For databases without native UUID support, set `as_uuid=False` to use string representation.

## Custom TypeAdapter

For more complex types, use `TypeDecorator`:

```python
from sqlalchemy import TypeDecorator, String
from datetime import datetime
import json

class SerializedDateTime(TypeDecorator):
    impl = String
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps({
                "iso": value.isoformat(),
                "timestamp": value.timestamp()
            })
        return None
    
    def process_result_value(self, value, dialect):
        if value is not None:
            data = json.loads(value)
            return datetime.fromisoformat(data["iso"])
        return None
```

The `cache_ok = True` flag tells SQLAlchemy this type's behavior is stable and can be cached. Omit it (or set to `False`) if the type's behavior depends on constructor arguments.

If the type takes arguments, implement `cache_key` to make caching work:

```python
class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True
    
    def __init__(self, encryption_key: str):
        super().__init__()
        self.encryption_key = encryption_key
    
    @property
    def cache_key(self):
        return (self.__class__.__name__, self.encryption_key)
    
    def process_bind_param(self, value, dialect):
        # Use self.encryption_key to encrypt
        pass
    
    def process_result_value(self, value, dialect):
        # Use self.encryption_key to decrypt
        pass
```

Another example integrating with pydantic:

```python

class DumpKwargs(TypedDict, total=False):
    """Kwargs for TypeAdapter.dump_python and dump_json methods."""

    mode: Literal["json", "python"]
    include: set[int | str] | dict[int | str, Any] | None
    exclude: set[int | str] | dict[int | str, Any] | None
    context: dict[str, Any] | None
    by_alias: bool
    exclude_unset: bool
    exclude_defaults: bool
    exclude_none: bool
    round_trip: bool
    warnings: bool | Literal["none", "warn", "error"]
    serialize_as_any: bool


class JSONSQLAdapter[T](TypeDecorator):
    """SQLAlchemy type decorator using TypeAdapter and serde json"""

    impl = JSON
    cache_ok = True
    adapter: TypeAdapter[T]
    dump_kwargs: DumpKwargs

    def __init__(self, py_type: Any = None, **dump_kwargs: Unpack[DumpKwargs]) -> None:
        super().__init__()
        self.py_type = py_type
        self.adapter = TypeAdapter(py_type)
        self.dump_kwargs = dump_kwargs or DumpKwargs(mode="json")

    def process_bind_param(self, value: T | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return self.adapter.dump_python(value, **self.dump_kwargs)

    def process_result_value(self, value: str | None, dialect: Any) -> T | None:
        if value is None:
            return None
        return self.adapter.validate_python(value)

    def process_literal_param(self, value: T | None, dialect: "Dialect") -> str:
        if value is None:
            return "NULL"
        return self.impl.literal_processor(dialect)(self.adapter.dump_json(value))

```

## Enum Type

For enum columns:

```python
from sqlalchemy import Enum
from enum import Enum as PyEnum

class Status(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[Status] = mapped_column(Enum(Status))
```

SQLAlchemy stores the enum value in the database and returns Python enum instances.

## ARRAY Type (PostgreSQL)

For PostgreSQL arrays:

```python
from sqlalchemy import ARRAY, Integer

class Data(Base):
    __tablename__ = "data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    numbers: Mapped[list[int]] = mapped_column(ARRAY(Integer))
```

Assign Python lists:

```python
data = Data(numbers=[1, 2, 3, 4, 5])
session.add(data)
session.commit()
```

Query array elements (PostgreSQL-specific):

```python
stmt = select(Data).where(Data.numbers.contains([3]))
```
